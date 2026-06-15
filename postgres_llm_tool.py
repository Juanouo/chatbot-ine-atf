"""
title: Postgres Database Tool
author: Juan Concha (adapted from Joshua Rudy)
version: 0.3.1
license: MIT
description: A simple tool for interacting with a PostgreSQL database. Ask the model questions and it will take the request
and pass it as an API call to OpenRouter to generate a SQL query before executing the query using psycopg2.
Added safe guards with query validations. Caution should be exercised anyways. Use and adjust as you need.

This version hardcodes the database schema in the prompt. Could be moved to the system prompt, but haven't
tested performance in that case.

Adapted for docker environment with:
- toydb database
- readonly_user for safe queries
- OpenRouter for SQL generation with configurable models via Valves
- Updated table whitelist for your schema
"""

import json
import logging
import time

from typing import Callable, Any
import re
import httpx
import asyncio
import psycopg2
import os




logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

from pydantic import BaseModel, Field
from typing import Literal


def validate_sql(sql_query: str, allowed_tables=None, max_limit=100) -> str:
    """
    Validate and sanitize an SQL query before execution.

    - Only allows SELECT queries
    - Blocks access to system tables/functions
    - Ensures only whitelisted tables are queried
    - Forces a LIMIT if not present

    :param sql_query: SQL string from the LLM
    :param allowed_tables: list of allowed table names (default: None = allow all)
    :param max_limit: max number of rows to allow in results
    :return: safe SQL query (possibly modified with LIMIT)
    :raises ValueError: if query is unsafe
    """

    sql = sql_query.strip().rstrip(";")  # remove trailing semicolon
    sql = re.sub(
        r"<think>\n.*?</think>(\n+)?", "", sql, flags=re.DOTALL
    )  # remove <think>...</think> blocks
    sql = re.sub(
        r"^```(?:sql)?\s*\n?(.*?)\n?```$", r"\1", sql, flags=re.DOTALL
    ).strip()  # remove ```sql ... ``` or ``` ... ``` wrappers
    logger.debug("Validating SQL query: %s", sql)
    # Must start with SELECT
    if not sql.upper().startswith("SELECT"):
        raise ValueError("Only SELECT queries are allowed")

    # Block dangerous keywords/functions
    forbidden = [
        ";",
        "--",
        "pg_",
        "information_schema",
        "COPY",
        "ALTER",
        "DROP",
        "INSERT",
        "UPDATE",
        "DELETE",
        "SET",
    ]
    for word in forbidden:
        if re.search(rf"\b{word}\b", sql, flags=re.IGNORECASE):
            raise ValueError(f"Forbidden keyword detected: {word}")

    # Enforce table whitelist if provided
    if allowed_tables:
        found_tables = re.findall(r"FROM\s+([a-zA-Z0-9_\.]+)", sql, flags=re.IGNORECASE)
        for tbl in found_tables:
            if tbl not in allowed_tables:
                raise ValueError(f"Querying table '{tbl}' is not allowed")

    # Enforce LIMIT — always replace whatever the LLM wrote
    sql = re.sub(r'\bLIMIT\s+\d+\b', '', sql, flags=re.IGNORECASE).rstrip()
    sql += f" LIMIT {max_limit}"

    return sql


class EventEmitter:
    def __init__(self, event_emitter: Callable[[dict], Any] | None = None):
        self.event_emitter = event_emitter

    async def emit(
        self,
        description="Procesando...",
        status="in_progress",
        content="",
        message=None,
        done=False,
    ):
        if self.event_emitter:
            await self.event_emitter(
                {
                    "type": "status",
                    "data": {
                        "status": status,
                        "description": description,
                        "content": content,
                        "message": message,
                        "done": done,
                    },
                }
            )


# Allowed tables in your database schema
ALLOWED_TABLES = ["total_unificado"]


# ==============================================================================
# OpenRouter Provider for SQL Generation
# ==============================================================================

class OpenRouterProvider:
    """OpenRouter provider implementation for SQL generation"""

    def __init__(self, api_key: str, model: str):
        """
        Initialize OpenRouter provider.

        Args:
            api_key: OpenRouter API key
            model: Model identifier (e.g., 'openai/gpt-oss-120b')

        Raises:
            ValueError: If api_key is empty or None
        """
        if not api_key:
            raise ValueError("OpenRouter API key is required")

        self.base_url = "https://openrouter.ai/api/v1"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        self.model = model

    async def generate_sql(self, prompt: str, emitter: EventEmitter) -> str:
        """
        Generate SQL using OpenRouter /chat/completions endpoint.

        Args:
            prompt: Natural language prompt to convert to SQL
            emitter: Event emitter for status updates

        Returns:
            Generated SQL query string

        Raises:
            Exception: If API call fails
        """
        prompt = prompt + '\nRespond ONLY with the SQL SELECT command, no additional text or formatting is permitted. This includes ```sql``` blocks. Never use them.'
        
        is_gemini = self.model.startswith("google/gemini")
        model_id = self.model 
        logger.debug("Using model %s for SQL generation", model_id)
        payload = {
            "model": model_id,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "stream": True,
            **({"reasoning": {"effort": "low"}} if is_gemini else {}),
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    'POST',
                    f"{self.base_url}/chat/completions",
                    headers=self.headers,
                    json=payload,
                ) as response:
                    response.raise_for_status()

                    sql_query = ""
                    thinking_chars = 0
                    async for line in response.aiter_lines():
                        # Skip empty lines
                        if not line.strip():
                            continue

                        # Remove 'data: ' prefix for SSE format
                        if line.startswith('data: '):
                            line = line[6:]

                        # Check for done signal
                        if line.strip() == '[DONE]':
                            break

                        try:
                            data = json.loads(line)

                            # Extract content from delta or message
                            if 'choices' in data and len(data['choices']) > 0:
                                choice = data['choices'][0]

                                # Count thinking/reasoning tokens (not captured in content)
                                if 'delta' in choice and 'reasoning_content' in choice['delta']:
                                    rc = choice['delta']['reasoning_content']
                                    if rc:
                                        thinking_chars += len(rc)

                                # Try delta first (streaming)
                                if 'delta' in choice and 'content' in choice['delta']:
                                    content = choice['delta']['content']
                                # Fall back to message (non-streaming)
                                elif 'message' in choice and 'content' in choice['message']:
                                    content = choice['message']['content']
                                else:
                                    continue

                                sql_query += content

                                await emitter.emit(
                                    content=f"Respuesta parcial: {content}",
                                    description='',
                                    status="sql_generation_in_progress",
                                    done=False,
                                )
                        except json.JSONDecodeError:
                            continue

                    if thinking_chars > 0:
                        logger.debug("Thinking tokens (chars): %d", thinking_chars)
                    return sql_query
        except Exception as e:
            raise Exception(f"OpenRouter generation failed: {e}")


class Tools:

    class Valves(BaseModel):

        # To give the user the choice between multiple strings, you can use Literal from typing:
        openrouter_model: Literal["qwen/qwen3-32b", "deepseek/deepseek-v3.2",
                                  "openai/gpt-oss-120b", "google/gemma-3-27b-it",
                                  "google/gemini-3.1-flash-lite-preview"] = Field(
           default="openai/gpt-oss-120b",
           description="Modelo a utilizar para uso interno de herramientas",
       )
        
        pass



    def __init__(self):
        self.valves = self.Valves()

        # Get and validate API key at initialization
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")

        # Create OpenRouter provider instance (reused across calls)
        self.llm_provider = OpenRouterProvider(
            api_key=api_key,
            model=self.valves.openrouter_model
        )

    def get_db_config(self):
        """
        Get database configuration with fallback for different environments.
        Tries container name first (for running inside Docker), then localhost.
        Reads POSTGRES_HOST from environment to support db-prod and db-dev.
        """
        # Get host from environment variable (db-prod or db-dev), fallback to toy-postgres
        container_host = os.getenv("POSTGRES_HOST", "toy-postgres")

        # Password injected via env_file (.env.prod / .env.dev) — never hardcoded
        readonly_password = os.getenv("READONLY_PASSWORD")
        if not readonly_password:
            raise ValueError(
                "READONLY_PASSWORD environment variable is required "
                "(define it in .env.prod / .env.dev)"
            )

        config =             {
                "dbname": os.getenv("POSTGRES_DB", "toydb"),
                "user": "readonly_user",
                "password": readonly_password,
                "host": container_host,  # db-prod or db-dev from environment
                "port": "5432",  # Internal container port
            }
        
        try:
            # Test connection
            conn = psycopg2.connect(
                dbname=config["dbname"],
                user=config["user"],
                password=config["password"],
                host=config["host"],
                port=config["port"],
            )
            conn.close()
            return config
        
        
        except Exception:
                pass

        fallback_configs = {

            'prod': {
                "dbname": os.getenv("POSTGRES_DB", "toydb"),
                "user": "readonly_user",
                "password": readonly_password,
                "host": "localhost",  # External host
                "port": "5438",  # Mapped port for prod
            },
            'dev': {
                "dbname": os.getenv("POSTGRES_DB", "toydb"),
                "user": "readonly_user",
                "password": readonly_password,
                "host": "localhost",  # External host
                "port": "5439",  # Mapped port for dev
            },
        }

        config = fallback_configs.get(os.getenv("ENV", "dev"), fallback_configs['dev'])



        # If all fail, return the localhost config as default
        return config

    async def get_indicator_metadata(
        self,
        indicator_name: str | None = None,
        __event_emitter__: Callable[[dict], Any] | None = None,
    ) -> str:
        """
        Get comprehensive metadata about available indicators in the database.

        Returns both structured JSON and natural language summary to help the LLM
        understand what data is available before generating SQL queries.

        For each indicator, provides:
        - Available years (min, max)
        - Available groupings (national, by sex, by region)
        - Frequency types (monthly, annual)
        - Sample query patterns

        :param __event_emitter__: Event emitter for updates (optional).
        :return: JSON string with comprehensive indicator metadata.
        """
        emitter = EventEmitter(__event_emitter__)

        try:
            await emitter.emit(
                description="Fetching indicator metadata from database...",
                status="fetching_metadata",
                done=False,
            )
            
            db_config = self.get_db_config()
            indicators_metadata = []

            # Indicator descriptions
            indicator_descriptions = {
                "tasa_desocupacion": "Tasa de desocupación",
                "tasa_ocupacion": "Tasa de ocupación",
                "tasa_participacion": "Tasa de participación laboral",
                "personas_fuerza_trabajo": "Personas en la fuerza de trabajo",
                "personas_edad_trabajar": "Población en edad de trabajar",
                "personas_ocupadas": "Población ocupada",
                "personas_desocupadas": "Población desocupada",
                "percepcion_aumento_delincuencia_pais": "Percepción de aumento de la delincuencia en el país",
                "victimizacion_hogares_delitos_mayor_connotacion_social": "Victimización de hogares por delitos de mayor connotación social",
                "victimizacion_hogares_delitos_violentos": "Victimización de hogares por delitos violentos",
                "victimizacion_personas_delitos_violentos": "Victimización de personas por delitos violentos",
                "ipc_variacion_12_meses": "Variación del Índice de Precios del Consumidor (12 meses)",
                "ipc_variacion_mensual": "Variación del Índice de Precios del Consumidor (mensual)"
            }

            with psycopg2.connect(
                dbname=db_config["dbname"],
                user=db_config["user"],
                password=db_config["password"],
                host=db_config["host"],
                port=db_config["port"],
            ) as conn:
                with conn.cursor() as cur:
                    # Get overall table info
                    table_name = ALLOWED_TABLES[0]


                    # Get list of all indicators (or filter if specified)
                    if indicator_name:
                        # Validate that the indicator exists
                        cur.execute(f"SELECT DISTINCT indicador FROM {table_name} WHERE indicador = %s", (indicator_name,))
                        result = cur.fetchone()
                        if not result:
                            # Fetch available indicators for error message
                            cur.execute(f"SELECT DISTINCT indicador FROM {table_name} ORDER BY indicador")
                            available = [row[0] for row in cur.fetchall()]

                            await emitter.emit(
                                description=f"Indicator '{indicator_name}' not found in database.",
                                status="indicator_not_found",
                                done=True,
                            )
                            return json.dumps({
                                "error": f"Indicator '{indicator_name}' not found",
                                "available_indicators": available
                            }, indent=2)
                        all_indicators = [indicator_name]
                    else:
                        cur.execute(f"SELECT DISTINCT indicador FROM {table_name} ORDER BY indicador")
                        all_indicators = [row[0] for row in cur.fetchall()]

                    # For each indicator, get detailed metadata
                    for indicador in all_indicators:
                        # Get basic stats
                        cur.execute(f"""
                            SELECT

                                MIN(año) as min_year,
                                MAX(año) as max_year
                            FROM {table_name}
                            WHERE indicador = %s
                        """, (indicador,))
                        min_year, max_year = cur.fetchone()

                        # Get available frequencies
                        cur.execute(f"""
                            SELECT DISTINCT frecuencia
                            FROM {table_name}
                            WHERE indicador = %s AND frecuencia IS NOT NULL
                            ORDER BY frecuencia
                        """, (indicador,))
                        frequencies = [row[0] for row in cur.fetchall()]

                        # Get grouping information
                        cur.execute(f"""
                            SELECT
                                grupo
                            FROM {table_name}
                            WHERE indicador = %s
                            GROUP BY grupo
                            ORDER BY grupo NULLS FIRST
                        """, (indicador,))
                        grouping_rows = cur.fetchall()
                        grouping_rows = [i[0] for i in grouping_rows]

                        groupings = []
                        for grupo  in grouping_rows:
                            if grupo == 'nacional':
                                groupings.append({
                                    "type": "nacional",
                                    "description": "National aggregated data (grupo='nacional')"
                                })
                            else:

                                groupings.append({
                                    "type": grupo,

                                })

                        # Build query examples
                        query_examples = []
                        if any(g["type"] == "nacional" for g in groupings):
                            if "mensual" in frequencies:
                                query_examples.append(
                                    f"For national monthly data: WHERE indicador='{indicador}' AND grupo='nacional' AND frecuencia='mensual'"
                                )
                            if "anual" in frequencies:
                                query_examples.append(
                                    f"For national annual data: WHERE indicador='{indicador}' AND grupo='nacional' AND frecuencia='anual'"
                                )

                        for grp in groupings:
                            if grp["type"] == "sexo":
                                query_examples.append(
                                    f"For men's data: WHERE indicador='{indicador}' AND grupo='sexo' AND valor_grupo='hombre'"
                                )
                                break
                            elif grp["type"] == "region":
                                query_examples.append(
                                    f"For regional data (e.g., Metropolitana): WHERE indicador='{indicador}' AND grupo='region' AND valor_grupo='Metropolitana'"
                                )
                                break

                        # Build indicator metadata
                        indicators_metadata.append({
                            "name": indicador,
                            "description": indicator_descriptions.get(indicador, ""),
                            "time_coverage": {
                                "min_year": int(min_year) if min_year else None,
                                "max_year": int(max_year) if max_year else None,
                                "frequencies": frequencies
                            },
                            "groupings": groupings,
                            "query_examples": query_examples
                        })

                    # Get global grouping dimensions
                    cur.execute(f"""
                        SELECT DISTINCT valor_grupo
                        FROM {table_name}
                        WHERE grupo = 'sexo' AND valor_grupo IS NOT NULL
                        ORDER BY valor_grupo
                    """)
                    sexo_values = [row[0] for row in cur.fetchall()]

                    cur.execute(f"""
                        SELECT DISTINCT valor_grupo
                        FROM {table_name}
                        WHERE grupo = 'region' AND valor_grupo IS NOT NULL
                        ORDER BY valor_grupo
                    """)
                    

                    grouping_dimensions = {}
                    if 'sexo' in [g['type'] for g in groupings]:
                        grouping_dimensions["sexo"] = sexo_values
                    if 'region' in [g['type'] for g in groupings]:
                        region_values = [row[0] for row in cur.fetchall()]
                        grouping_dimensions["region"] = region_values

            # Build natural language summary
            summary_lines = ["Available Indicators:\n"]

            nombre_indicadores_empleo = ["tasa_desocupacion", "tasa_ocupacion",
                                                         "tasa_participacion", "personas_fuerza_trabajo",
                                                         "poblacion_edad_trabajar", "personas_desocupadas",
                                                         "personas_ocupadas",
                                                         "personas_edad_trabajar"]
            
            nombre_indicadores_seguridad = ["percepcion_aumento_delincuencia_pais",
                "victimizacion_hogares_delitos_mayor_connotacion_social",
                "victimizacion_hogares_delitos_violentos",
                "victimizacion_personas_delitos_violentos"]
            
            nombre_indicadores_ipc = ["ipc_variacion_12_meses", "ipc_variacion_mensual"]

            # Group by category
            employment_indicators = [ind for ind in indicators_metadata
                                      if ind["name"] in nombre_indicadores_empleo]
            crime_indicators = [ind for ind in indicators_metadata
                                if ind["name"] in nombre_indicadores_seguridad]
            ipc_indicators = [ind for ind in indicators_metadata
                              if ind["name"] in nombre_indicadores_ipc]

            if employment_indicators:
                summary_lines.append("Employment Indicators (ENE):")
                for ind in employment_indicators:
                    freqs = ", ".join(ind["time_coverage"]["frequencies"])
                    grouping_types = [g["type"] for g in ind["groupings"]]
                    summary_lines.append(
                        f"  - {ind['name']}: {ind['description']}. "
                        f"Data from {ind['time_coverage']['min_year']}-{ind['time_coverage']['max_year']}. "
                        f"Available {freqs}. Groupings: {', '.join(grouping_types)}"
                    )
                summary_lines.append("")

            if crime_indicators:
                summary_lines.append("Crime/Security Indicators (ENUSC):")
                for ind in crime_indicators:
                    freqs = ", ".join(ind["time_coverage"]["frequencies"])
                    grouping_types = [g["type"] for g in ind["groupings"]]
                    summary_lines.append(
                        f"  - {ind['name']}: {ind['description']}. "
                        f"Data from {ind['time_coverage']['min_year']}-{ind['time_coverage']['max_year']}. "
                        f"Available {freqs}. Groupings: {', '.join(grouping_types)}"
                    )

            if ipc_indicators:
                summary_lines.append("Consumer Price Index Indicators (IPC):")
                for ind in ipc_indicators:
                    freqs = ", ".join(ind["time_coverage"]["frequencies"])
                    grouping_types = [g["type"] for g in ind["groupings"]]
                    summary_lines.append(
                        f"  - {ind['name']}: {ind['description']}. "
                        f"Data from {ind['time_coverage']['min_year']}-{ind['time_coverage']['max_year']}. "
                        f"Available {freqs}. Groupings: {', '.join(grouping_types)}"
                    )
                summary_lines.append("")

            if indicator_name:
                summary_lines.append("Key SQL Patterns:")
                summary_lines.append("  - For national/total data: grupo='nacional' AND valor_grupo = 'nacional'")
                summary_lines.append("  - For sex-disaggregated data: grupo='sexo' AND valor_grupo IN ('hombre', 'mujer')")
                summary_lines.append("  - For regional data: grupo='region' AND valor_grupo IN (region names like 'Metropolitana', 'Valparaíso', etc.)")
                summary_lines.append("  - For monthly data: frecuencia='mensual'")
                summary_lines.append("  - For annual data: frecuencia='anual'")

            summary = "\n".join(summary_lines)

            # Build final result
            result = {
                #"table_name": table_name,
                "summary": summary,
                "indicators": indicators_metadata,
                "grouping_dimensions": grouping_dimensions
            }

            if not indicator_name:
                result = result["summary"]

            formatted_result = json.dumps(result, indent=2, default=str)

            await emitter.emit(
                description="Successfully retrieved indicator metadata.",
                content=formatted_result,
                status="metadata_fetched",
                done=True,
            )

            return formatted_result

        except Exception as e:
            await emitter.emit(
                description=f"Error fetching indicator metadata: {str(e)}",
                status="fetch_error",
                done=True,
            )
            return f"Error fetching indicator metadata: {e}"

    async def _instruct_llm_to_generate_sql(
        self,
        natural_language_query: str,
        __event_emitter__: Callable[[dict], Any] | None = None,
    ) -> str:
        """
        Internal helper: generate an SQL query from a natural language query.

        :param natural_language_query: The user's query in plain language.
        :param __event_emitter__: Event emitter for updates (optional).
        :return: The generated SQL query as a string.
        """
        emitter = EventEmitter(__event_emitter__)

        # Enhanced prompt with your database schema information
        prompt = f"""
        You are an assistant that converts natural language into SQL commands.
        Convert the following natural language query into an SQL command.

        Database Schema:

        Table: total_unificado
        Columns: (indicador, valor_indicador, grupo, valor_grupo, año, mes, frecuencia)

        Schema Description:
        This table contains unified Chilean indicators from multiple sources (employment survey ENE and crime/security survey ENUSC).
        It uses a flexible grouping structure to support both aggregated and disaggregated data.

        Column Descriptions:
        - indicador: Type of metric (e.g., tasa_desocupacion, personas_fuerza_trabajo, percepcion_aumento_delincuencia_pais)
        - valor_indicador: Numerical value of the indicator
        - grupo: Grouping category ('nacional' for national data, 'sexo' for sex-disaggregated, 'region' for regional)
        - valor_grupo: Value within the group (NULL for national, 'hombre'/'mujer' for sex, region names like 'Metropolitana', 'Valparaíso', etc. for regions)
        - año: Year (integer)
        - mes: Month number ('1'-'12' for monthly data, NULL for annual data)
        - frecuencia: Data frequency ('mensual' or 'anual')

        Sample Data:
        indicador: personas_fuerza_trabajo, valor_indicador: 4808.37, grupo: sexo, valor_grupo: hombre, año: 2010, mes: None, frecuencia: anual
        indicador: personas_fuerza_trabajo, valor_indicador: 3191.70, grupo: sexo, valor_grupo: mujer, año: 2010, mes: None, frecuencia: anual
        indicador: personas_fuerza_trabajo, valor_indicador: 7883.69, grupo: nacional, valor_grupo: NULL, año: 2010, mes: 1, frecuencia: mensual
        indicador: tasa_participacion, valor_indicador: 59.66, grupo: nacional, valor_grupo: NULL, año: 2022, mes: 4, frecuencia: mensual

        Available Indicators:
        Employment Indicators (ENE):
        - tasa_desocupacion (unemployment rate)
        - tasa_ocupacion (employment rate)
        - tasa_participacion (labor force participation rate)
        - personas_fuerza_trabajo (people in workforce)
        - poblacion_edad_trabajar (working age population)

        Crime/Security Indicators (ENUSC):
        - percepcion_aumento_delincuencia_pais (perception of crime increase)
        - victimizacion_hogares_delitos_mayor_connotacion_social (household victimization - major crimes)
        - victimizacion_hogares_delitos_violentos (household victimization - violent crimes)
        - victimizacion_personas_delitos_violentos (personal victimization - violent crimes)

        Inflation Indicators (IPC):
        - ipc_variacion_12_meses (CPI variation over 12 months)
        - ipc_variacion_mensual (monthly CPI variation)

        CRITICAL SQL Patterns (you MUST use these exact patterns):
        - For national/total data: WHERE grupo = 'nacional' AND valor_grupo IS NULL
        - For sex-disaggregated data: WHERE grupo = 'sexo' AND valor_grupo IN ('hombre', 'mujer')
        - For regional data: WHERE grupo = 'region' AND valor_grupo IN (region names like 'Metropolitana', 'Valparaíso', 'Biobío', etc.)
        - For inflation data data: WHERE indicador IN ('ipc_variacion_12_meses', 'ipc_variacion_mensual')


        Query Guidelines:
        - NEVER use = NULL or != NULL. ALWAYS use IS NULL or IS NOT NULL for NULL comparisons
        - You might only use aggregating functions like SUM or COUNT to aggregate data for a year if you have only monthly data available.
        - When comparing groups, use appropriate WHERE conditions on grupo and valor_grupo
        - Always include year and month (if applicable) with the query results to avoid ambiguity
        - If the user asks an open question like "what was this month's inflation?" try to answer thoroughly.
          In this case, you should answer both monthly inflation and yearly inflation, so the chances of the user being satisfied are highest. 
        - If a user request requires getting more than one indicator, always try to get them in one query
        - This is PostgreSQL, so use appropriate syntax and functions for that database. Example: never cast as UNSIGNED.
        - You don't need to specify the `frecuencia` column when filtering, because an indicator never has both monthly and annual
          data at the same time. Adding it only increases error vectors. 

        Available tables: {", ".join(ALLOWED_TABLES)}
        User Query: {natural_language_query}

        IMPORTANT:
        Reply ONLY with the SQL SELECT command, no additional text is permitted.
        """

        # Use OpenRouter to generate SQL
        try:
            await emitter.emit(
                description="Inicializando proveedor LLM...",
                status="initializing",
                done=False,
            )

            # Sync model from valves (in case user changed it via UI)
            self.llm_provider.model = self.valves.openrouter_model

            await emitter.emit(
                description="Generando SQL usando OpenRouter...",
                status="sql_generation_in_progress",
                done=False,
            )

            # Generate SQL using the provider
            sql_query = await self.llm_provider.generate_sql(prompt, emitter)

            if not sql_query or not sql_query.strip():
                raise ValueError("No SQL query was returned by the LLM.")

            await emitter.emit(
                description="Comando SQL generado exitosamente.",
                status="sql_generated",
                done=True,
            )

            return sql_query

        except ValueError as e:
            # Configuration errors or empty responses
            await emitter.emit(
                description=f"Error de configuración: {e}",
                status="config_error",
                done=True,
            )
            return f"Error de configuración: {e}"
        except httpx.HTTPStatusError as e:
            # HTTP errors (401, 403, 429, etc.)
            await emitter.emit(
                description=f"Error de API: {e.response.status_code} - {e.response.text[:200]}",
                status="api_error",
                done=True,
            )
            return f"Error de API: {e.response.status_code}"
        except Exception as e:
            await emitter.emit(
                description=f"Error al instruir al LLM para generar SQL: {e}",
                status="query_error",
                done=True,
            )
            return f"Error al instruir al LLM para generar SQL: {e}"
    async def execute_query(
        self,
        natural_language_query: str,
        __event_emitter__: Callable[[dict], Any] | None = None,
    ) -> str:
        """
        Executes a dynamically generated SQL query based on a natural language input.

        :param natural_language_query: The user's query in plain language.
        :param __event_emitter__: Event emitter for updates.
        :return: A string representation of the query results or an error message.
        """
        emitter = EventEmitter(__event_emitter__)
        t0 = time.perf_counter()
        logger.info("Using model %s for query execution", self.valves.openrouter_model)
        try:
            # Step 1: Generate the SQL command
            sql_query = await self._instruct_llm_to_generate_sql(
                natural_language_query, __event_emitter__
            )
            t1 = time.perf_counter()
            logger.info("PROFILE LLM SQL generation=%.3fs", t1 - t0)
            logger.debug("Generated SQL: %s", sql_query)

            if not sql_query:
                raise ValueError("Generated SQL query is empty.")

            await emitter.emit(
                description=f"Comando SQL generado: {sql_query}",
                status="sql_generated",
                done=False,
            )

            # Step 2: Execute the SQL command using DB config
            db_config = self.get_db_config()
            t2 = time.perf_counter()
            with psycopg2.connect(
                dbname=db_config["dbname"],
                user=db_config["user"],
                password=db_config["password"],
                host=db_config["host"],
                port=db_config["port"],
            ) as conn:
                with conn.cursor() as cur:
                    # Use your database's allowed tables
                    safe_query = validate_sql(
                        sql_query, allowed_tables=ALLOWED_TABLES, max_limit=500
                    )
                    cur.execute(safe_query)
                    rows = cur.fetchall()
                    t3 = time.perf_counter()
                    logger.info("PROFILE DB connect+query=%.3fs", t3 - t2)

                    # Get column names for formatting original_results
                    if cur.description is not None:
                        column_names = [desc[0] for desc in cur.description]
                        original_results = [dict(zip(column_names, row)) for row in rows]
                    else:
                        # This should never happen after a successful execute, but satisfies type checker
                        original_results = [list(row) for row in rows]

                    if original_results == []:
                        original_results = [{"message": "Query didn't return any original_results. Try get_indicator_metadata to see available\
                                     indicators and groupings for each indicator"}]
                    original_results.append({'used_query': safe_query})

                    if len(original_results) > 10:

                        import csv
                        import io
                        # Extract query
                        used_query = next(item['used_query'] for item in original_results if 'used_query' in item)

                        # Filter actual rows
                        rows = [item for item in original_results if 'used_query' not in item]

                        # Convert to CSV string
                        output = io.StringIO()
                        writer = csv.DictWriter(output, fieldnames=rows[0].keys())
                        writer.writeheader()
                        writer.writerows(rows)

                        csv_string = output.getvalue()

                        results = {
                            'data': csv_string,
                            'used_query': used_query
                        }
                    else:
                        results = original_results


                    formatted_results = json.dumps(results, indent=2, default=str, ensure_ascii=False)
                    logger.debug("Query results: %s", formatted_results)

                    if len(original_results) > 20:
                        import pandas as pd
                        df = pd.read_csv(io.StringIO(csv_string))
                        df = df.drop(columns=['fecha', 'grupo'], errors='ignore')

                        if 'valor_indicador' in df.columns:
                            df['valor_indicador'] = df['valor_indicador'].astype(float).round(2)

                        if 'año' in df.columns:
                            año_str = df['año'].astype(str)
                            if 'mes' in df.columns and df['mes'].notna().any():
                                mes_int = df['mes'].fillna(0).astype(int)
                                df['fecha'] = año_str.where(
                                    mes_int == 0,
                                    año_str + '-' + mes_int.astype(str).str.zfill(2)
                                )
                            else:
                                df['fecha'] = año_str
                            df = df.drop(columns=['año', 'mes'], errors='ignore')

                        multiple_indicators = (
                            'indicador' in df.columns and df['indicador'].nunique() > 1
                        )
                        has_group = (
                            'valor_grupo' in df.columns and df['valor_grupo'].notna().any()
                        )

                        if 'fecha' in df.columns:
                            if multiple_indicators and has_group:
                                df['_col'] = df['indicador'] + ' / ' + df['valor_grupo'].fillna('total')
                                df = df.pivot(index='fecha', columns='_col', values='valor_indicador')
                            elif multiple_indicators:
                                df = df.pivot(index='fecha', columns='indicador', values='valor_indicador')
                            elif has_group:
                                df = df.drop(columns=['indicador'], errors='ignore')
                                df = df.pivot(index='fecha', columns='valor_grupo', values='valor_indicador')
                            else:
                                df = df.drop(columns=['indicador', 'valor_grupo'], errors='ignore')
                                df = df.set_index('fecha')
                            df.columns.name = None
                            df = df.sort_index()

                        md = df.to_markdown()
                        logger.debug("Markdown table:\n%s", md)

                        t4 = time.perf_counter()
                        logger.info("PROFILE formatting (pandas/markdown)=%.3fs", t4 - t3)
                        logger.info("PROFILE total=%.3fs", t4 - t0)
                        return f"query: {safe_query}\n\n__SHOW_TABLE__\n{md}"

                    # Step 3: Emit success message with results
                    await emitter.emit(
                        description="Comando SQL ejecutado exitosamente.",
                        content=formatted_results,
                        status="query_success",
                        done=True,
                    )

                    t4 = time.perf_counter()
                    logger.info("PROFILE formatting (JSON)=%.3fs", t4 - t3)
                    logger.info("PROFILE total=%.3fs", t4 - t0)
                    return formatted_results

        except Exception as e:
            await emitter.emit(
                description=f"Error durante la ejecución de la consulta: {str(e)}",
                status="query_error",
                done=True,
            )
            return f"Error ejecutando la consulta: {e}"

# Example usage function for testing
async def test_tool():

    from dotenv import load_dotenv
    load_dotenv('.env.dev', override=True)  # Load development environment variables
    print(f"Current environment: {os.getenv('ENV', 'not set')}")

    """Test the database tool with sample queries"""
    tool = Tools()

    # Test queries
    test_queries = [
        "variación del IPC en 12 meses y variación mensual del IPC durante 2023",
        "What categories do we have?",
        "Show me products with their categories",
        "How many orders are there?",
    ]

    for query in test_queries:
        print(f"\n--- Testing: {query} ---")
        #res1 = await tool.get_indicator_metadata(indicator_name=None)
        result = await tool.execute_query(query)
        print(result)


if __name__ == "__main__":
    # Run the test
    asyncio.run(test_tool())

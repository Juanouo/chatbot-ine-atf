# Flujo de `postgres_llm_tool.py`

## Visión general

El script expone herramientas (Tools) para Open WebUI que permiten consultar una base de datos PostgreSQL usando lenguaje natural. El flujo principal es:

```
Pregunta del usuario
       │
       ▼
instruct_llm_to_generate_sql()   ←── OpenRouterProvider (LLM externo)
       │
       ▼
    validate_sql()
       │
       ▼
  execute_query()   ────────────── PostgreSQL (total_unificado)
       │
       ▼
  Resultado JSON
```

---

## Componentes

### 1. `validate_sql(sql, allowed_tables, max_limit)`

Función de seguridad que se ejecuta **antes** de cualquier consulta a la base de datos.

**Qué hace:**
- Elimina bloques `<think>...</think>` (modelos razonadores como DeepSeek)
- Elimina el `;` final
- Verifica que la query comience con `SELECT` — rechaza todo lo demás
- Bloquea palabras clave peligrosas: `;`, `--`, `pg_`, `information_schema`, `ALTER`, `DROP`, `INSERT`, `UPDATE`, `DELETE`, `SET`
- Valida que las tablas referenciadas estén en la whitelist (`ALLOWED_TABLES = ["total_unificado"]`)
- Agrega `LIMIT 100` automáticamente si no hay `LIMIT`

**Retorna:** SQL seguro (posiblemente modificado) o lanza `ValueError`.

---

### 2. `EventEmitter`

Wrapper sobre el callback `__event_emitter__` de Open WebUI. Emite eventos de estado al frontend durante la ejecución (spinner, mensajes de progreso).

```python
await emitter.emit(description="...", status="...", done=False)
```

---

### 3. `OpenRouterProvider`

Cliente HTTP para la API de OpenRouter. Genera SQL a partir de un prompt en lenguaje natural.

**Inicialización:**
- Requiere `OPENROUTER_API_KEY` (variable de entorno)
- Recibe el modelo a usar (configurable vía Valves en la UI)

**`generate_sql(prompt, emitter)`:**
1. Agrega al prompt: `"Respond ONLY with the SQL SELECT command, no additional text or formatting is permitted."`
2. Hace POST a `https://openrouter.ai/api/v1/chat/completions` con streaming habilitado (`"stream": True`)
3. Lee la respuesta línea por línea (formato SSE: `data: {...}`)
4. Acumula el contenido del `delta.content` de cada chunk
5. Emite eventos de progreso parcial al frontend
6. Retorna el SQL completo como string

---

### 4. `Tools` (clase principal de Open WebUI)

#### `Valves`
Parámetros configurables desde la UI de Open WebUI:
- `openrouter_model`: modelo LLM a usar para generar SQL (`openai/gpt-oss-120b` por defecto)

#### `__init__`
- Lee `OPENROUTER_API_KEY` del entorno
- Instancia `OpenRouterProvider` (reutilizado en todas las llamadas)

#### `get_db_config()`
Obtiene la configuración de conexión a PostgreSQL con **failover automático**:

```
1. Intenta container-to-container:  POSTGRES_HOST:5432  (dentro de Docker)
2. Intenta localhost:5438            (host → prod)
3. Intenta localhost:5439            (host → dev)
4. Si todo falla → retorna config de localhost:5438
```

El host del contenedor se lee desde `POSTGRES_HOST` (env var), que en `docker-compose.yml` apunta a `toy-postgres-prod` o `toy-postgres-dev`.

---

## Herramientas expuestas (métodos públicos)

### `get_indicator_metadata(indicator_name=None)`

Consulta la BD para describir qué datos hay disponibles.

**Flujo:**
1. Conecta a PostgreSQL
2. Si se pasa `indicator_name`: verifica que exista, o retorna error con lista de disponibles
3. Para cada indicador obtiene:
   - Años mínimo y máximo
   - Frecuencias disponibles (`mensual`, `anual`)
   - Agrupaciones disponibles (`nacional`, `sexo`, `region`)
4. Construye ejemplos de queries SQL para cada caso
5. Construye un resumen en lenguaje natural (separando indicadores ENE vs ENUSC)
6. Retorna JSON con `summary` + `indicators` + `grouping_dimensions`

**Cuándo usarlo:** Antes de `execute_query()` cuando no se sabe qué indicadores o agrupaciones existen.

---

### `instruct_llm_to_generate_sql(natural_language_query)`

Convierte lenguaje natural en SQL usando el LLM de OpenRouter.

**Flujo:**
1. Construye un prompt detallado que incluye:
   - Esquema de la tabla `total_unificado` (columnas y descripciones)
   - Datos de ejemplo
   - Lista de indicadores disponibles
   - Patrones SQL críticos (cómo usar `grupo`, `valor_grupo`, `frecuencia`, etc.)
   - Instrucción de responder **solo** con SQL
2. Sincroniza el modelo desde `valves.openrouter_model` (por si el usuario lo cambió en la UI)
3. Llama a `OpenRouterProvider.generate_sql()`
4. Retorna el SQL crudo generado por el LLM

---

### `execute_query(natural_language_query)` ← **Herramienta principal**

Flujo end-to-end completo:

```
natural_language_query
        │
        ▼
instruct_llm_to_generate_sql()
        │  SQL crudo (puede contener <think>, ```, etc.)
        ▼
validate_sql()
        │  SQL limpio y seguro
        ▼
psycopg2.connect() → cursor.execute(safe_query)
        │  rows + column names
        ▼
[{"col1": val, "col2": val, ...}, ..., {"used_query": "SELECT ..."}]
        │
        ▼
json.dumps() → string JSON retornado al LLM de Open WebUI
```

**Manejo de resultados vacíos:**
Si la query no retorna filas, incluye un mensaje sugiriendo usar `get_indicator_metadata`.

**Siempre agrega** `{"used_query": <SQL ejecutado>}` al final del resultado, para que el LLM pueda informar al usuario qué query se usó.

---

## Tabla de columnas: `total_unificado`

| Columna | Descripción |
|---|---|
| `indicador` | Nombre del indicador (ej: `tasa_desocupacion`) |
| `valor_indicador` | Valor numérico |
| `grupo` | Tipo de agrupación: `nacional`, `sexo`, `region` |
| `valor_grupo` | Valor del grupo: `NULL` (nacional), `hombre`/`mujer`, nombre de región |
| `año` | Año (entero) |
| `mes` | Mes 1–12 (NULL para datos anuales) |
| `frecuencia` | `mensual` o `anual` |

---

## Patrones SQL fundamentales

```sql
-- Nacional / total
WHERE grupo = 'nacional' AND valor_grupo IS NULL

-- Por sexo
WHERE grupo = 'sexo' AND valor_grupo IN ('hombre', 'mujer')

-- Por región
WHERE grupo = 'region' AND valor_grupo = 'Metropolitana'

-- Datos mensuales
WHERE frecuencia = 'mensual' AND mes IS NOT NULL

-- Datos anuales
WHERE frecuencia = 'anual' AND mes IS NULL
```

---

## Flujo de desarrollo

```bash
# Modificar postgres_llm_tool.py
python update_tools_export.py   # Exporta a exports/postgres-tool-export.json
make dev-restart                 # Recarga en dev (5-10s, bind-mounted)
make prod-rebuild                # Despliega en prod (30+s, copiado en imagen)
```

# Guía de mantención del chatbot

> **Para quién es esta guía:** La persona a cargo de mantener y extender este proyecto. Se asume que sabes Python a nivel intermedio, entiendes qué es un LLM y qué es un prompt, y que ya tienes el proyecto corriendo (si no, parte por `GUIA_LOCAL.md`). No se asume experiencia en Docker ni en ingeniería de software: lo que necesitas saber de eso está explicado aquí.

Después de leer esta guía deberías poder:

- Modificar la herramienta que consulta la base de datos (`postgres_llm_tool.py`)
- Cambiar el system prompt del chatbot
- Agregar o quitar modelos disponibles en el selector del chat
- Cargar datos nuevos a la base de datos
- Agregar un indicador nuevo de punta a punta (datos + herramienta + prompt)
- Diagnosticar los problemas más comunes

Documentos complementarios:

- `GUIA_LOCAL.md` — instalación desde cero para usuarios finales. **Ojo:** describe una versión antigua del proyecto (`docker-compose.yml`, `--profile prod`, red `webui-net`). Los comandos vigentes son los de esta guía y del `Makefile`.
- `CLAUDE.md` — resumen técnico del proyecto (en inglés).
- `docs/postgres_llm_tool_FLOW.md` — flujo interno detallado de la herramienta.

---

## Índice

1. [Mapa del sistema](#1-mapa-del-sistema)
2. [Las dos reglas de oro](#2-las-dos-reglas-de-oro)
3. [Los scripts principales y cómo interactúan](#3-los-scripts-principales-y-cómo-interactúan)
4. [Recetas](#4-recetas)
5. [Verificación y debugging](#5-verificación-y-debugging)
6. [Referencia rápida de comandos](#6-referencia-rápida-de-comandos)

---

## 1. Mapa del sistema

### Qué pasa cuando un usuario hace una pregunta

```
Usuario: "¿tasa de desocupación en la RM en 2023?"
   │
   ▼
Open WebUI (contenedor open-webui-{dev,prod})
   │
   ├─ 1. El MODELO DE CHAT (via OpenRouter) lee la pregunta y decide
   │     llamar a la herramienta postgres_database_tool
   │
   ├─ 2. La herramienta (postgres_llm_tool.py) le pide a un SEGUNDO LLM
   │     (también via OpenRouter, configurable por separado) que convierta
   │     la pregunta en una consulta SQL
   │
   ├─ 3. validate_sql() revisa que el SQL sea seguro (solo SELECT,
   │     solo tabla permitida, LIMIT forzado)
   │
   ▼
PostgreSQL (contenedor toy-postgres-{dev,prod})
   │  ejecuta la consulta como readonly_user sobre data.total_unificado
   ▼
Los resultados vuelven al modelo de chat, que redacta la respuesta
(o, si son más de 20 filas, un filtro muestra la tabla directamente)
```

Fíjate que hay **dos LLM distintos** en juego: el modelo de chat (el que eliges en el selector de la interfaz) y el modelo que genera SQL dentro de la herramienta. Se configuran en lugares distintos (ver receta 4.3).

### Los dos entornos

Todo existe duplicado: un entorno de **desarrollo** para probar cambios y uno de **producción** para los usuarios. Son stacks de Docker completamente aislados (redes, volúmenes y credenciales separadas); nada de lo que hagas en dev toca prod.

| | Desarrollo | Producción |
|---|---|---|
| URL | http://localhost:3031 | http://localhost:3030 (solo loopback) |
| Contenedores | `open-webui-dev`, `toy-postgres-dev`, `ollama-dev` | `open-webui-prod`, `toy-postgres-prod` (sin Ollama) |
| Puerto PostgreSQL | 127.0.0.1:5439 | 127.0.0.1:5438 |
| Archivo compose | `compose.dev.yml` | `compose.prod.yml` |
| Credenciales | `.env.dev` | `.env.prod` |
| Comandos | `make dev-*` | `make prod-*` |
| Volúmenes | `open-webui_open-webui-dev`, `open-webui_pgdata-dev` | `open-webui_open-webui-prod`, `open-webui_pgdata-prod` |

**Flujo de trabajo estándar:** cambias algo → lo pruebas en dev → cuando funciona, lo despliegas a prod. Nunca pruebes directo en prod.

### Las dos bases de datos

Esto confunde al principio: hay dos bases de datos con roles muy distintos.

1. **PostgreSQL (`toydb`)** — los **datos de indicadores**. Tabla `data.total_unificado` con columnas `indicador`, `valor_indicador`, `grupo`, `valor_grupo`, `año`, `mes`, `frecuencia`. También guarda el log de conversaciones (`logs.chat_turn_log`). Tiene dos usuarios: `toyuser` (dueño, carga datos) y `readonly_user` (solo lectura, es el que usa la herramienta).

2. **SQLite (`webui.db`)** — la base **interna de Open WebUI**: usuarios de la interfaz, historial de chats, y las copias importadas de herramientas, modelos, filtros y configuración. Vive dentro del volumen Docker (`open-webui-{dev,prod}`), no la editas a mano: los scripts de importación escriben en ella al arrancar el contenedor.

---

## 2. Las dos reglas de oro

**Regla 1 — dev es rápido, prod es lento.** En dev, los archivos de configuración están *bind-mounted*: el contenedor lee directamente tus archivos locales, así que basta `make dev-restart` (5–10 s) para aplicar cambios. En prod, los archivos se **copian dentro de la imagen Docker** al construirla, así que los cambios requieren `make prod-rebuild` (30+ s). Si cambiaste algo y prod no lo refleja, casi seguro te faltó el rebuild.

**Regla 2 — los archivos del repositorio mandan.** Cada vez que un contenedor arranca, el proceso de arranque sobreescribe en `webui.db` la herramienta, los modelos, los filtros y la configuración con lo que dicen los archivos de `exports/` y `system_prompt.md` (la config la importa Open WebUI mismo desde un `config.json` que el arranque le deja preparado; el resto lo escribe `import_tools.py`). Consecuencia importante: **los cambios hechos a mano en la interfaz de administración de Open WebUI no sobreviven a un reinicio** (y los modelos creados a mano en la UI se *eliminan*, porque la importación borra los modelos que no están en el JSON). Para que un cambio sea permanente, hazlo en los archivos del repositorio.

---

## 3. Los scripts principales y cómo interactúan

### Vista resumida

| Archivo | Qué hace | Dónde corre | Interactúa con |
|---|---|---|---|
| `postgres_llm_tool.py` | La herramienta: lenguaje natural → SQL → resultados | Dentro de Open WebUI (importado a `webui.db`) | OpenRouter, PostgreSQL; empaquetado por `update_tools_export.py` |
| `update_tools_export.py` | Copia el código de la herramienta y los filtros a los JSON de `exports/` | Tu máquina (lo ejecuta `make dev-restart`) | Lee `postgres_llm_tool.py` y `filters/*.py`; escribe `exports/postgres-tool-export.json` y `exports/filter-export.json` |
| `import_tools.py` | Al arrancar el contenedor, importa herramienta, modelos y filtros desde `exports/` hacia `webui.db` | Contenedor open-webui (lo llama `start_with_tools.sh`) | Lee `exports/*.json` y `system_prompt.md`; escribe `webui.db` |
| `start_with_tools.sh` | Script de arranque del contenedor: prepara la config para que Open WebUI la importe, levanta el backend, espera Ollama (solo dev) y ejecuta la importación | Contenedor open-webui | Lee `exports/config-export.json`; llama a `import_tools.py` |
| `load_parquet_to_db_auto.py` | Carga los `.parquet` de `data/current/` a PostgreSQL (reemplaza la tabla completa) | Contenedor postgres (via `docker exec` o al inicializar el volumen) | Lee `/data/current/*.parquet`; escribe `data.total_unificado` |
| `unify_tables.py` | Prepara los datos: une los parquet intermedios (ENE, ENUSC, IPC) en `data/current/total_unificado.parquet` | Tu máquina | Lee `data/intermediate/*.parquet`; escribe `data/current/total_unificado.parquet` |
| `system_prompt.md` | El system prompt de **todos** los modelos de chat | — (archivo de texto) | Lo lee `import_tools.py` al arrancar |
| `filters/*.py` | Tres filtros de Open WebUI (tablas, límite de contexto, logging) | Dentro de Open WebUI | Empaquetados por `update_tools_export.py` |
| `exports/*.json` | El "paquete" de configuración que consume el contenedor | — (archivos de datos) | Escritos por `update_tools_export.py`; leídos por `import_tools.py` (y `start_with_tools.sh` para la config) |

### La cadena de custodia del código de la herramienta

El error más común de mantención es editar `postgres_llm_tool.py` y esperar que el chatbot cambie. No funciona así: Open WebUI **no lee ese archivo**; ejecuta la copia que quedó importada en `webui.db`. El código viaja por esta cadena:

```
postgres_llm_tool.py            ← editas ESTO
      │
      │  python update_tools_export.py      (make dev-restart lo ejecuta solo)
      ▼
exports/postgres-tool-export.json
      │
      │  al arrancar el contenedor:
      │  start_with_tools.sh → import_tools.py
      ▼
webui.db (base interna de Open WebUI)
      │
      ▼
esto es lo que ejecuta el chatbot
```

Lo mismo aplica a los filtros (`filters/*.py` → `exports/filter-export.json` → `webui.db`).

### Detalle por script

#### `postgres_llm_tool.py` — la herramienta

El corazón del proyecto. Define la clase `Tools` que Open WebUI expone al modelo de chat, con estas funciones:

- **`get_indicator_metadata()`** — consulta la base y devuelve qué indicadores existen, en qué años, con qué desgloses. El modelo de chat la usa cuando no está seguro de qué datos hay.
- **`execute_query(natural_language_query)`** — el flujo completo: llama a `_instruct_llm_to_generate_sql()` para obtener el SQL, lo pasa por `validate_sql()` y lo ejecuta contra PostgreSQL como `readonly_user`.
- **`_instruct_llm_to_generate_sql()`** — arma un prompt con el esquema de la tabla, los indicadores disponibles y las reglas de SQL (todo **hardcodeado en el string del prompt**, dentro de esta función), y se lo manda al LLM de OpenRouter para que genere el SELECT.
- **`validate_sql(sql)`** — la barrera de seguridad: solo acepta SELECT, bloquea palabras peligrosas (`;`, `--`, `pg_`, `information_schema`, `DROP`, `INSERT`, `UPDATE`, `DELETE`, `SET`, etc.), verifica que solo se consulte `total_unificado` (whitelist `ALLOWED_TABLES`) y **reemplaza siempre el LIMIT** por el máximo permitido (500 filas). También limpia bloques `<think>` y fences ```` ```sql ```` que algunos modelos agregan.

Otras piezas dentro del mismo archivo:

- **`Valves`** — la configuración editable desde la interfaz. Hoy solo tiene `openrouter_model`: el modelo que genera SQL (independiente del modelo de chat). Es un `Literal` con la lista de opciones y un default.
- **`OpenRouterProvider`** — el cliente HTTP que llama a OpenRouter (usa `OPENAI_API_KEY` del entorno).
- **`get_db_config()`** — resuelve cómo conectarse a PostgreSQL: primero el host del entorno (`POSTGRES_HOST` = `db-dev` o `db-prod`, contenedor a contenedor) y si falla, `localhost:5439`/`5438` (útil cuando corres el script fuera de Docker).
- **Formato de resultados:** hasta 10 filas se devuelven como JSON al modelo; más de 10 se comprimen a CSV; más de 20 se convierten en una tabla Markdown marcada con el centinela `__SHOW_TABLE__`, que el filtro `table_display_filter` muestra tal cual al usuario (sin que el LLM pueda "reinterpretar" los números).
- **`test_tool()`** — si ejecutas `python postgres_llm_tool.py` en tu máquina (con `.env.dev` presente y la base de dev arriba), corre consultas de prueba sin pasar por la interfaz. Es la forma más rápida de iterar.

#### `update_tools_export.py` — el empaquetador

Script corto y sin misterio: lee `postgres_llm_tool.py` y lo mete en el campo `content` de `exports/postgres-tool-export.json`; hace lo mismo con cada archivo de `filters/` hacia `exports/filter-export.json`, actualizando timestamps. **`make dev-restart` lo ejecuta automáticamente**; solo necesitas correrlo a mano si vas a hacer `make prod-rebuild` sin haber pasado por un `dev-restart` antes (mala idea de todos modos: prueba en dev primero).

#### `import_tools.py` — el importador

Corre **dentro del contenedor** open-webui, una vez en cada arranque. Hace tres importaciones hacia `webui.db`:

1. **Herramienta** (`postgres-tool-export.json`) — inserta o actualiza `postgres_database_tool`.
2. **Modelos** (`models-export.json`) — inserta/actualiza cada modelo y **elimina los que no están en el JSON**. Aquí también se inyecta el system prompt: la función `load_system_prompt()` usa el contenido de `/app/system_prompt.md` para *todos* los modelos (el prompt inline que pueda traer el JSON queda solo como respaldo si el archivo faltara).
3. **Filtros** (`filter-export.json`) — los tres filtros como "functions" globales.

La **configuración global** (`config-export.json`) ya no se importa aquí: la maneja `start_with_tools.sh` (ver abajo). El importador conserva la función `substitute_env_vars()`, que el arranque usa para reemplazar placeholders `${VARIABLE}` — así `${OPENAI_API_KEY}` toma el valor de `.env.dev`/`.env.prod` sin que la clave quede en el repositorio.

#### `start_with_tools.sh` — el arranque

Entrypoint del contenedor open-webui. En orden:

1. **Prepara la configuración**: toma `exports/config-export.json`, sustituye los `${VARIABLE}` con variables de entorno y deja el resultado en `/app/backend/data/config.json`. Esto aprovecha un mecanismo **nativo de Open WebUI**: al arrancar, si existe `config.json` en su carpeta de datos, lo importa a `webui.db` *antes* de construir su configuración en memoria, y lo renombra a `old_config.json` (que el script borra después, para no dejar la API key en un archivo plano).
2. Levanta el backend de Open WebUI y espera 10 segundos.
3. En dev, espera además a que Ollama responda.
4. Ejecuta `import_tools.py` (herramienta, modelos, filtros).

Cuando en los logs ves `✅ Open WebUI startup complete!`, todo el proceso terminó.

#### `load_parquet_to_db_auto.py` — el cargador de datos

Corre **dentro del contenedor postgres**. Busca todos los `.parquet` en `/data/current/` (que es la carpeta local `./data/current/` montada en modo solo-lectura), y carga cada uno como tabla en el esquema `data` de PostgreSQL usando el mapeo `TABLE_NAME_MAPPING` (hoy: `total_unificado.parquet` → `data.total_unificado`). La carga es **destructiva**: `if_exists='replace'` bota la tabla y la recrea con el contenido del parquet. Al final da `GRANT SELECT` a `readonly_user`. Se ejecuta automáticamente la primera vez que se crea el volumen de la base, y a mano (via `docker exec`) cada vez que actualizas datos.

#### `unify_tables.py` — la preparación de datos

Corre en tu máquina, con el venv del proyecto. Une los parquet intermedios (`data/intermediate/ene_unificado.parquet`, `enusc_unificado.parquet`, `ipc_general.parquet`) en la tabla única: renombra indicadores, multiplica por 1.000 las cifras de personas, redondea, convierte códigos de región a nombres (`13` → `Metropolitana`) y escribe `data/current/total_unificado.parquet`. Si tus datos nuevos ya vienen con el formato final, no lo necesitas; si vienen de los intermedios, este es el paso 1.

#### `filters/` — los tres filtros

Los filtros son plugins de Open WebUI que interceptan los mensajes antes o después del LLM:

- **`table_display_filter.py`** — detecta el centinela `__SHOW_TABLE__` en la salida de la herramienta y muestra la tabla Markdown directamente, suprimiendo el texto del LLM (evita que "alucine" valores al resumir tablas grandes).
- **`context_limit_filter.py`** — recorta el historial que se envía al LLM a las últimas N vueltas (valve `max_turns`, default 5), para controlar costo y contexto.
- **`turn_logger_filter.py`** — registra cada turno (pregunta, respuesta, herramientas usadas, modelo, usuario, costo) en la tabla `logs.chat_turn_log` de PostgreSQL. Por ahora activo solo en dev (`ENV=dev`).

#### `exports/` — el paquete de configuración

| Archivo | Contenido | Cómo se genera |
|---|---|---|
| `postgres-tool-export.json` | El código de la herramienta + metadatos | `update_tools_export.py` (no editar a mano) |
| `filter-export.json` | El código de los tres filtros | `update_tools_export.py` (no editar a mano) |
| `models-export-dev.json` / `-prod.json` | Los modelos del selector de chat: id de OpenRouter, herramienta asociada (`toolIds`), capacidades | A mano (receta 4.3) |
| `config-export-dev.json` / `-prod.json` | Config global: signup, conexión a OpenRouter y su lista de modelos (`model_ids`) | A mano |

Diferencias dev/prod: dev tiene signup habilitado, prod no. Cada entorno usa su par de archivos (en dev via bind mount, en prod copiados a la imagen por `Dockerfile.openwebui`).

#### Infraestructura (solo lo que necesitas saber)

- **`Makefile`** — todos los comandos de operación (`make help` lista todo). Por dentro solo llama a `docker compose` con el archivo del entorno correspondiente.
- **`compose.dev.yml` / `compose.prod.yml`** — declaran los contenedores de cada entorno, sus puertos, volúmenes y qué archivos locales se montan. Si te preguntas "¿este archivo llega al contenedor por mount o por copia?", la respuesta está aquí (dev) o en `Dockerfile.openwebui` (prod).
- **`Dockerfile.openwebui`** — construye la imagen de Open WebUI sobre la imagen oficial, copiando los scripts, `exports/` y `system_prompt.md`. Tiene dos variantes (`dev`/`prod`) que solo difieren en qué config/modelos copian.
- **`Dockerfile.postgres`** — PostgreSQL 16 + Python (pandas, sqlalchemy) para poder correr el cargador dentro del contenedor. Copia `init.sql/` al directorio de inicialización.
- **`init.sql/`** — scripts que corren **solo la primera vez** que se crea el volumen de la base: crean los esquemas `data` y `logs`, el usuario `readonly_user` (con password de `READONLY_PASSWORD`), la tabla de logs, y disparan la primera carga de parquet. Si el volumen ya existe, cambiar estos archivos no tiene efecto (por eso existe `make {env}-rotate-passwords`).
- **`.env.dev` / `.env.prod`** — credenciales y variables de entorno (gitignored). Contienen `OPENAI_API_KEY` (la clave de OpenRouter, usada tanto por la conexión de chat como por la herramienta), `POSTGRES_PASSWORD`, `READONLY_PASSWORD`, `ENV`, entre otras.

---

## 4. Recetas

### 4.1 Modificar la herramienta

```bash
# 1. Edita postgres_llm_tool.py

# 2. (Opcional pero recomendado) prueba rápida sin interfaz:
source .venv/bin/activate
python postgres_llm_tool.py        # corre test_tool() contra la base de dev

# 3. Aplica en dev (esto ya ejecuta update_tools_export.py por ti):
make dev-restart

# 4. Prueba en http://localhost:3031 con preguntas reales

# 5. Cuando estés conforme, despliega a prod:
make prod-rebuild
```

**Verificar:** en `make dev-logs` debe aparecer `Updated tool: Postgres Database Tool`. Si el chatbot se comporta como antes, revisa la [cadena de custodia](#la-cadena-de-custodia-del-código-de-la-herramienta).

Cosas a tener en cuenta al editar:

- El prompt que genera el SQL está **dentro** de `_instruct_llm_to_generate_sql()`. Si cambias la estructura de datos, cambia ese prompt.
- `validate_sql()` es la barrera de seguridad; no la relajes sin pensarlo dos veces. Recuerda que bloquea `SET`, `--` y `;` en cualquier parte del SQL.
- La herramienta usa `readonly_user`: aunque el LLM genere algo destructivo y pasara la validación, la base lo rechazaría. Mantén ese doble seguro.

### 4.2 Cambiar el system prompt

El system prompt de **todos** los modelos vive en un solo archivo: `system_prompt.md`. Ahí se definen el rol del chatbot, cuándo usar cada función de la herramienta, los patrones de filtrado y la lista de indicadores que el modelo "sabe" que existen.

```bash
# 1. Edita system_prompt.md

# 2. Aplica:
make dev-restart      # dev
make prod-rebuild     # prod (cuando ya lo probaste)
```

**Verificar:** en los logs de arranque, cada modelo debe mostrar `Loaded system prompt for <modelo> from default:system_prompt.md`. Abre un chat **nuevo** para probar (los chats existentes pueden arrastrar contexto).

Notas:

- Los JSON de modelos (`models-export-*.json`) traen prompts inline en `params.system`, pero son solo un **respaldo** por si `system_prompt.md` faltara. No los edites para cambiar el prompt; siempre se impone el archivo.
- Editar el prompt desde la interfaz de administración funciona… hasta el próximo reinicio (regla de oro 2).

### 4.3 Cambiar los modelos disponibles

Hay **tres** configuraciones de modelo distintas; identifica cuál quieres cambiar:

**A. Los modelos del selector de chat.** Requiere tocar dos archivos por entorno:

1. `exports/config-export-{dev,prod}.json` → `openai.api_configs."0".model_ids`: la lista de IDs de OpenRouter que la conexión expone. Agrega o quita el ID aquí (debe existir en [openrouter.ai/models](https://openrouter.ai/models)).
2. `exports/models-export-{dev,prod}.json` → la entrada del modelo. Lo más simple es **copiar una entrada completa existente** (una que tenga `params` y `meta`) y cambiar todos los campos de id/nombre (incluido el `openai.id` anidado). Los campos que importan:
   - `meta.toolIds: ["postgres_database_tool"]` — sin esto, el modelo no tiene acceso a la herramienta.
   - `params.function_calling: "native"` — necesario para que llame herramientas correctamente.
   - No te preocupes del `params.system` inline: `system_prompt.md` lo pisa (receta 4.2).
3. `make dev-restart` / `make prod-rebuild`.

> **Advertencia:** la importación **elimina** de Open WebUI cualquier modelo que no esté en `models-export-*.json`. Un modelo creado a mano en la interfaz desaparece en el próximo reinicio. El JSON es la única fuente duradera.

**B. El modelo que genera SQL dentro de la herramienta.** Es la valve `openrouter_model` en `postgres_llm_tool.py`:

- Cambio temporal (para probar): interfaz de Open WebUI → Workspace → Tools → ícono de ajustes de la herramienta → elige el modelo. Se pierde en el próximo reinicio.
- Cambio permanente: edita en `postgres_llm_tool.py` la lista `Literal[...]` de la clase `Valves` (para agregar la opción) y/o el `default`, y sigue la receta 4.1.

**C. Los modelos locales de Ollama (solo dev).** Existen solo para experimentar en dev; prod opera exclusivamente con OpenRouter. Se administran con `docker exec -it ollama-dev ollama pull <modelo>`.

### 4.4 Actualizar los datos (mismos indicadores, períodos nuevos)

```bash
# 1. Genera/reemplaza el parquet final
#    a) si partes de los parquet intermedios (data/intermediate/):
source .venv/bin/activate
python unify_tables.py
#    b) o simplemente reemplaza data/current/total_unificado.parquet
#       (mismas columnas: indicador, valor_indicador, grupo, valor_grupo, año, mes, frecuencia)

# 2. Carga a la base de dev (reemplaza la tabla COMPLETA):
docker exec -it toy-postgres-dev python3 /scripts/load_parquet_to_db_auto.py

# 3. Verifica:
make dev-db-shell
#   SELECT indicador, MIN(año), MAX(año), COUNT(*) FROM data.total_unificado GROUP BY indicador;

# 4. Prueba en el chat de dev (no hace falta reiniciar nada: la herramienta lee la base en vivo)

# 5. Repite la carga en prod:
docker exec -it toy-postgres-prod python3 /scripts/load_parquet_to_db_auto.py
```

Convenciones de los datos que hay que respetar (las espera el prompt de la herramienta):

- Nacional: `grupo = 'nacional'` y `valor_grupo` NULL
- Por sexo: `grupo = 'sexo'`, `valor_grupo` ∈ `hombre`/`mujer`
- Por región: `grupo = 'region'`, `valor_grupo` con el **nombre** de la región (`'Metropolitana'`, no `'13'`)
- Mensual: `frecuencia = 'mensual'` y `mes` 1–12; anual: `frecuencia = 'anual'` y `mes` NULL

### 4.5 Agregar un indicador nuevo

Un indicador nuevo toca datos + herramienta + prompt. Checklist completo:

```bash
# 1. DATOS: agrega las filas del indicador al parquet (formato de la receta 4.4)
#    y cárgalo a dev:
docker exec -it toy-postgres-dev python3 /scripts/load_parquet_to_db_auto.py
```

2. **HERRAMIENTA** — en `postgres_llm_tool.py` hay tres lugares que nombran indicadores:
   - El diccionario `indicator_descriptions` (dentro de `get_indicator_metadata`): agrega `"nombre_indicador": "Descripción legible"`.
   - Las listas de categorías `nombre_indicadores_empleo` / `nombre_indicadores_seguridad` / `nombre_indicadores_ipc` (misma función): agrega el indicador a la que corresponda. Si es una categoría nueva, crea la lista y replica el bloque de resumen correspondiente.
   - El prompt de `_instruct_llm_to_generate_sql()`: agrégalo a la sección "Available Indicators" (y si requiere un patrón SQL especial, a "CRITICAL SQL Patterns").

3. **PROMPT** — en `system_prompt.md`, agrega el indicador a la sección "IMPORTANT: available indicators" (es la lista con la que el modelo de chat decide si puede responder una pregunta).

```bash
# 4. Aplica y prueba en dev:
make dev-restart
#    En http://localhost:3031 pregunta por el indicador nuevo; verifica que
#    get_indicator_metadata lo liste y que execute_query traiga datos.

# 5. Despliega a prod:
docker exec -it toy-postgres-prod python3 /scripts/load_parquet_to_db_auto.py
make prod-rebuild
```

### 4.6 Modificar los filtros

```bash
# 1. Edita el filtro en filters/ (p. ej. filters/context_limit_filter.py)
# 2. make dev-restart      (empaqueta e importa, igual que la herramienta)
# 3. Prueba en dev, luego: make prod-rebuild
```

Para un filtro **nuevo**: crea `filters/mi_filtro.py` (estructura de clase `Filter` con `inlet`/`stream`/`outlet`, mira los existentes), agrégalo al diccionario `filter_files` de `update_tools_export.py`, y agrega una entrada con el mismo `id` en `exports/filter-export.json` (copia una existente como plantilla y deja `content` vacío: el empaquetador lo rellena).

### 4.7 Credenciales, API keys y contraseñas

Todo vive en `.env.dev` / `.env.prod` (gitignored, permisos 600). Las variables clave:

- `OPENAI_API_KEY` — la clave de OpenRouter (`sk-or-v1-...`). La usan tanto la conexión de chat de Open WebUI (via el placeholder `${OPENAI_API_KEY}` de `config-export-*.json`) como la herramienta.
- `POSTGRES_PASSWORD` — password de `toyuser` (dueño de la base).
- `READONLY_PASSWORD` — password de `readonly_user` (el que usa la herramienta).

**Cualquier cambio en `.env.*` requiere bajar y subir el entorno** (un `restart` no recarga el archivo):

```bash
make dev-down && make dev-up      # o prod-down && prod-up
```

**Rotar contraseñas de la base** tiene un paso extra: PostgreSQL solo lee las passwords del `.env` al crear el volumen por primera vez, así que en un volumen existente hay que aplicarlas por dentro:

```bash
# 1. Edita POSTGRES_PASSWORD / READONLY_PASSWORD en .env.dev (o .env.prod)
make dev-down && make dev-up
make dev-rotate-passwords          # ejecuta ALTER USER dentro del contenedor
```

Para rotar la clave de OpenRouter basta editarla en el `.env` y hacer `down && up`.

---

## 5. Verificación y debugging

### Herramientas de diagnóstico

```bash
make status          # ¿están corriendo los contenedores?
make dev-logs        # logs en vivo de dev (Ctrl+C para salir; no apaga nada)
make prod-logs       # ídem prod
make dev-db-shell    # psql dentro de la base de dev
make dev-shell       # bash dentro del contenedor open-webui-dev
```

En los logs de arranque, la secuencia sana es: `Config staged: ...` → `Starting Open WebUI backend` → (dev) `Ollama service is ready` → `Updated tool: ...` → `Loaded system prompt for ... from default:system_prompt.md` → `Updated model: ...` → `✅ Open WebUI startup complete!`.

Consultas útiles en `make dev-db-shell`:

```sql
-- ¿Qué datos hay cargados?
SELECT indicador, MIN(año), MAX(año), COUNT(*) FROM data.total_unificado GROUP BY indicador ORDER BY indicador;

-- ¿Qué ha estado preguntando la gente y qué SQL se generó? (log de turnos, dev)
SELECT ts, user_name, model, LEFT(user_message, 60) AS pregunta, tool_uses
FROM logs.chat_turn_log ORDER BY ts DESC LIMIT 20;
```

### Problemas comunes

| Síntoma | Causa probable | Solución |
|---|---|---|
| Edité `postgres_llm_tool.py` y el chatbot sigue igual | El código no llegó a `webui.db` | `make dev-restart` (regenera el export e importa). En prod: `make prod-rebuild` |
| El cambio funciona en dev pero no en prod | Prod usa archivos copiados a la imagen | `make prod-rebuild` (regla de oro 1) |
| Cambié algo en la interfaz de admin y desapareció | La importación al arrancar pisa la UI | Haz el cambio en los archivos del repo (regla de oro 2) |
| Un modelo que creé en la UI ya no está | La importación borra modelos fuera del JSON | Agrégalo a `models-export-*.json` (receta 4.3) |
| Cambié `.env` y no tiene efecto | `restart` no recarga env_file | `make {env}-down && make {env}-up` |
| La herramienta responde `Forbidden keyword detected` u `Only SELECT queries are allowed` | `validate_sql` rechazó el SQL generado | Suele bastar reformular la pregunta; si es recurrente, ajusta el prompt de `_instruct_llm_to_generate_sql()` |
| `Error de API: 401` / `402` en la herramienta | Clave de OpenRouter inválida o sin créditos | Revisa la clave en `.env.*` y los créditos en openrouter.ai |
| La herramienta no conecta a la base | Password o contenedor caído | `make status`; revisa `READONLY_PASSWORD`; ¿rotaste passwords sin `rotate-passwords`? |
| El indicador nuevo "no existe" según el chatbot | Falta en `system_prompt.md` o en las listas de la herramienta | Completa el checklist de la receta 4.5 |
| Pregunté por datos y responde que no hay | Los datos no están cargados en ese entorno | Receta 4.4, paso de verificación con `db-shell` |

### Probar la herramienta sin la interfaz

La iteración más rápida cuando trabajas en `postgres_llm_tool.py`:

```bash
make dev-up                        # asegura la base de dev arriba
source .venv/bin/activate
python postgres_llm_tool.py        # ejecuta test_tool() con .env.dev
```

Edita las consultas de prueba en `test_tool()` (al final del archivo) según lo que estés probando.

---

## 6. Referencia rápida de comandos

| Acción | Dev | Prod |
|---|---|---|
| Iniciar | `make dev-up` | `make prod-up` |
| Detener | `make dev-down` | `make prod-down` |
| Aplicar cambios de archivos | `make dev-restart` | `make prod-rebuild` |
| Reconstruir imagen | `make dev-rebuild` | `make prod-rebuild` |
| Ver logs | `make dev-logs` | `make prod-logs` |
| Shell en Open WebUI | `make dev-shell` | `make prod-shell` |
| Shell de PostgreSQL | `make dev-db-shell` | `make prod-db-shell` |
| Cargar parquet a la base | `docker exec -it toy-postgres-dev python3 /scripts/load_parquet_to_db_auto.py` | ídem con `toy-postgres-prod` |
| Rotar passwords de la base | `make dev-rotate-passwords` | `make prod-rotate-passwords` |
| Estado de contenedores | `make status` | `make status` |
| Borrar TODO (datos incluidos) | `make clean-dev` ⚠️ | `make clean-prod` ⚠️ |

Y el flujo que resume el 90 % de la mantención:

```bash
# editar archivos → probar en dev → desplegar a prod
make dev-restart      # http://localhost:3031
make prod-rebuild     # http://localhost:3030
```

---

*Guía de mantención — Proyecto chatbot indicadores ENE/ENUSC/IPC*

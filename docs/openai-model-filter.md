# OpenAI Model Filter on Startup

> **⚠️ SUPERSEDED (julio 2026):** El mecanismo descrito aquí (escritura a la DB + llamada a `/openai/config/update` con JWT) fue reemplazado por el import nativo de Open WebUI: `start_with_tools.sh` ahora deja el config (con `${VARS}` sustituidas) en `/app/backend/data/config.json` **antes** de arrancar el backend, y Open WebUI lo importa él mismo al inicio (lo renombra a `old_config.json`, que el script luego borra). `update_openai_config_via_api()` e `import_config_from_json()` fueron eliminadas de `import_tools.py`. La edición de `model_ids` en `exports/config-export-*.json` sigue funcionando igual. Este documento se conserva como referencia histórica del problema de caché en memoria.

This document explains how to limit the models shown in Open WebUI to a specific list when using OpenRouter (or other OpenAI-compatible providers).

## Problem

When connecting Open WebUI to OpenRouter, all available models from the provider are displayed by default. While this can be changed manually in the UI (Admin Settings > Connections), the setting doesn't persist reliably on container restart because:

1. Open WebUI loads `CONFIG_DATA` into memory once at startup
2. The `import_tools.py` script updates the database AFTER startup
3. The in-memory cache is never refreshed from the database

## Solution

We implemented an API-based config update that runs during startup. After importing the config to the database, the script calls Open WebUI's internal `/openai/config/update` endpoint, which triggers `PersistentConfig.save()` and updates the in-memory cache.

### How It Works

```
┌─────────────────────────────────────────────────────────────────┐
│                     Container Startup                            │
├─────────────────────────────────────────────────────────────────┤
│ 1. start_with_tools.sh launches Open WebUI in background        │
│ 2. Open WebUI initializes, loads CONFIG_DATA into memory        │
│ 3. After 10s delay, import_tools.py runs:                       │
│    a. Imports tools from postgres-tool-export.json              │
│    b. Imports models from models-export-dev.json                │
│    c. Imports config to database (raw SQL)                      │
│    d. Calls API to update in-memory cache (NEW)                 │
│ 4. Model filter is now active                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Key Components

#### 1. Config File: `exports/config-export-dev.json`

```json
{
  "version": 0,
  "ui": {
    "enable_signup": true
  },
  "openai": {
    "enable": true,
    "api_base_urls": ["https://openrouter.ai/api/v1"],
    "api_keys": ["${OPENAI_API_KEY}"],
    "api_configs": {
      "0": {
        "enable": true,
        "model_ids": [
          "qwen/qwen3-32b",
          "openai/gpt-oss-120b",
          "deepseek/deepseek-v3.2"
        ],
        "connection_type": "external",
        "auth_type": "bearer"
      }
    }
  }
}
```

The `model_ids` array under `api_configs.0` specifies which models to show. The `"0"` key corresponds to the first URL in `api_base_urls`.

#### 2. API Update Function: `import_tools.py`

The `update_openai_config_via_api()` function:

1. Finds an admin user in the database
2. Reads `WEBUI_SECRET_KEY` from `/app/backend/.webui_secret_key`
3. Generates a JWT token for authentication
4. Calls `POST /openai/config/update` with the config data
5. Open WebUI's internal handler updates the in-memory cache

```python
def update_openai_config_via_api(config_data, db_path, base_url="http://localhost:8080", secret_key_dir="/app/backend"):
    # ... generates JWT token ...

    payload = {
        "ENABLE_OPENAI_API": enable_openai,
        "OPENAI_API_BASE_URLS": api_base_urls,
        "OPENAI_API_KEYS": api_keys,
        "OPENAI_API_CONFIGS": api_configs
    }

    response = requests.post(
        f"{base_url}/openai/config/update",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
```

## Usage

### Adding/Removing Models

1. Edit `exports/config-export-dev.json`
2. Update the `model_ids` array with your desired models
3. Restart the container:
   ```bash
   make dev-restart
   ```

### Syncing with models-export-dev.json

The models in `config-export-dev.json` should match those defined in `models-export-dev.json`. The config file controls what's shown from the provider, while the models file defines custom model configurations (system prompts, capabilities, etc.).

### Verification

Check the logs for successful update:
```
✅ Generated JWT token for admin user
Saving 'OPENAI_API_CONFIGS' to the database
POST /openai/config/update HTTP/1.1" 200
✅ OpenAI config updated via API successfully
```

Or verify in the database:
```bash
docker exec open-webui-dev python3 -c "
import sqlite3, json
conn = sqlite3.connect('/app/backend/data/webui.db')
cursor = conn.cursor()
cursor.execute('SELECT data FROM config WHERE id = 1')
config = json.loads(cursor.fetchone()[0])
print(config['openai']['api_configs']['0']['model_ids'])
"
```

## Limitations

### Fresh Volume Startup

On a completely fresh volume (no existing database), the API update will be skipped because there's no admin user yet:

```
⚠️  No admin user found, skipping API update
```

**Workaround:** After creating your first admin account, restart the container:
```bash
make dev-restart
```

### Multiple Connections

If you have multiple OpenAI-compatible connections (multiple URLs in `api_base_urls`), you need to add corresponding entries in `api_configs`:

```json
{
  "openai": {
    "api_base_urls": [
      "https://openrouter.ai/api/v1",
      "https://api.openai.com/v1"
    ],
    "api_keys": ["${OPENROUTER_API_KEY}", "${OPENAI_API_KEY}"],
    "api_configs": {
      "0": {
        "model_ids": ["qwen/qwen3-32b", "deepseek/deepseek-v3.2"]
      },
      "1": {
        "model_ids": ["gpt-4o", "gpt-4o-mini"]
      }
    }
  }
}
```

## Technical Background

### Open WebUI's Config System

Open WebUI uses `PersistentConfig` objects that:
- Load initial values from environment variables
- Override with values from the database `config` table
- Cache values in memory (`CONFIG_DATA` global)
- Only refresh when `.save()` is called

The `/openai/config/update` endpoint sets config values via:
```python
request.app.state.config.OPENAI_API_CONFIGS = form_data.OPENAI_API_CONFIGS
```

This triggers `PersistentConfig.__setattr__` which calls `.save()`, updating both the database and in-memory cache.

### Why Raw SQL Wasn't Enough

The original `import_config_from_json()` wrote directly to the database:
```python
cursor.execute("UPDATE config SET data = ? WHERE id = 1", (config_json,))
```

But `CONFIG_DATA` was already loaded into memory before this ran, and there's no mechanism to reload it from the database during runtime.

### JWT Authentication

We use JWT instead of API keys because:
- API keys require `ENABLE_API_KEYS=True` environment variable
- JWT tokens work with just the `WEBUI_SECRET_KEY` file
- No cleanup needed (tokens expire automatically)

## Files Modified

- `import_tools.py` - Added `update_openai_config_via_api()` function
- `exports/config-export-dev.json` - Model filter configuration

## Related Files

- `start_with_tools.sh` - Startup script that calls import_tools.py
- `exports/models-export-dev.json` - Model definitions
- `docker-compose.yml` - Bind mounts for config files

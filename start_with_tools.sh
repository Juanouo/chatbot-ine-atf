#!/bin/bash
set -e

echo "🚀 Starting Open WebUI with automatic tool import..."
echo "Running in $ENV"

# Stage the config BEFORE starting the backend: Open WebUI's config.py imports
# DATA_DIR/config.json into the DB at startup (before building its in-memory
# config) and renames it to old_config.json. This replaces the old post-startup
# DB write + /openai/config/update API call.
if [ -f /app/exports/config-export.json ]; then
  echo "📋 Staging config.json for Open WebUI's native import..."
  python3 - <<'EOF' || echo "⚠️  Config staging failed; continuing with existing DB config"
import json
import sys

sys.path.insert(0, "/app")
from import_tools import substitute_env_vars

SRC = "/app/exports/config-export.json"
DST = "/app/backend/data/config.json"

with open(SRC) as f:
    config = json.load(f)

with open(DST, "w") as f:
    json.dump(substitute_env_vars(config), f, indent=2)

print(f"Config staged: {SRC} -> {DST}")
EOF
fi

# Start Open WebUI in the background
echo "📦 Starting Open WebUI backend..."
/app/backend/start.sh &

# Get the PID of the background process
BACKEND_PID=$!

# Wait for Open WebUI to start and database to be available
echo "⏳ Waiting for Open WebUI to initialize..."
sleep 10

# Wait for Ollama to be ready (dev only — prod runs OpenRouter-only, no Ollama)
if [ "$ENV" = "dev" ]; then
  OLLAMA_URL="${OLLAMA_BASE_URL:-http://ollama:11434}"
  echo "⏳ Waiting for Ollama service at ${OLLAMA_URL}..."
  until curl -sf "${OLLAMA_URL}/api/tags" > /dev/null 2>&1; do
    echo "Ollama not ready yet, waiting..."
    sleep 2
  done
  echo "✅ Ollama service is ready!"
else
  echo "⏭️  Skipping Ollama wait (ENV=$ENV, OpenRouter-only)"
fi

# # Create custom model from Modelfile if it doesn't exist
# MODEL_NAME="nemotron-3-nano-q3"
# if ollama list | grep -q "^${MODEL_NAME}"; then
#   echo "✅ Model '${MODEL_NAME}' already exists, skipping creation"
# else
#   echo "🤖 Creating model '${MODEL_NAME}' from Modelfile..."
#   cd /app/backend/hf_models/${MODEL_NAME}
#   ollama create ${MODEL_NAME} 
#   echo "✅ Model '${MODEL_NAME}' created successfully!"
# fi

# MODEL_NAME="nemotron-3-nano-q4"
# if ollama list | grep -q "^${MODEL_NAME}"; then
#   echo "✅ Model '${MODEL_NAME}' already exists, skipping creation"
# else
#   echo "🤖 Creating model '${MODEL_NAME}' from Modelfile..."
#   cd /app/backend/hf_models/${MODEL_NAME}
#   ollama create ${MODEL_NAME} 
#   echo "✅ Model '${MODEL_NAME}' created successfully!"
# fi


# Import tools, models, and filter functions if the export files exist
# (config is no longer imported here — it was staged as config.json above)
echo "🔧 Importing tools, models, and filters from export files..."
python3 /app/import_tools.py /app/exports/postgres-tool-export.json /app/exports/models-export.json /app/backend/data/webui.db /app/exports/filter-export.json

# The native import renamed config.json to old_config.json; remove it so the
# substituted API key doesn't linger in a plaintext file inside the volume.
rm -f /app/backend/data/old_config.json

echo "✅ Open WebUI startup complete!"

# Wait for the backend process to finish
wait $BACKEND_PID

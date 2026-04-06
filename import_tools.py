#!/usr/bin/env python3
"""
Open WebUI Tool and Model Importer
Imports tools and models from JSON export files into the Open WebUI database during container startup.
"""

import json
import logging
import sqlite3
import sys
import os
import re
import time

logger = logging.getLogger(__name__)


def load_system_prompt(params, prompts_base_path="/app/", model_id=None, no_override_ids=None):
    """
    Load system prompt. By default, system_prompt.md overrides any inline prompt from the JSON.
    Models listed in no_override_ids keep their own system prompt (inline or file).

    Priority for models NOT in no_override_ids:
    1. system_prompt.md (default override)
    2. Inline prompt from JSON (fallback if system_prompt.md is missing)

    Priority for models IN no_override_ids:
    1. Inline prompt from JSON
    2. system_prompt_file specified in params
    3. system_prompt.md

    :param params: The model params dict
    :param prompts_base_path: Base path for prompt files (default: /app/)
    :param model_id: Model ID, used to check against no_override_ids
    :param no_override_ids: List of model IDs whose inline prompts should not be overridden
    :return: Tuple of (prompt_content, source_description)
    """
    if no_override_ids is None:
        no_override_ids = []

    if model_id in no_override_ids:
        # Preserve model's own prompt: inline → file → system_prompt.md
        if params.get('system') and params['system'].strip():
            return params['system'], "inline"
        if params.get('system_prompt_file'):
            file_path = os.path.join(prompts_base_path, params['system_prompt_file'])
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    return content, f"file:{params['system_prompt_file']}"
                except Exception as e:
                    logger.warning("Error reading prompt file %s: %s", file_path, e)
            else:
                logger.warning("Prompt file not found: %s", file_path)

    # Default: system_prompt.md overrides everything
    default_path = os.path.join(prompts_base_path, "system_prompt.md")
    if os.path.exists(default_path):
        try:
            with open(default_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return content, "default:system_prompt.md"
        except Exception as e:
            logger.warning("Error reading default prompt file %s: %s", default_path, e)

    # Fallback: inline prompt from JSON (only reached if system_prompt.md is missing)
    if params.get('system') and params['system'].strip():
        return params['system'], "inline"

    return None, "none"


def wait_for_db(db_path, max_retries=30):
    """Wait for the database file to appear. Returns True if found, False if timed out."""
    for i in range(max_retries):
        if os.path.exists(db_path):
            return True
        logger.info("Waiting for database... (%d/%d)", i + 1, max_retries)
        time.sleep(1)
    logger.error("Database not found after waiting: %s", db_path)
    return False


def apply_schema_migrations(db_path):
    """
    Ensure the database schema has all expected columns, adding any that are missing.
    This handles cases where the Open WebUI DB was created with an older schema version.
    """
    migrations = [
        ("tool",  "access_control", "TEXT"),
        ("model", "access_control", "TEXT"),
    ]

    if not wait_for_db(db_path):
        return False

    try:
        with sqlite3.connect(db_path, timeout=30.0) as conn:
            for table, column, col_type in migrations:
                cursor = conn.execute(f"PRAGMA table_info({table})")
                existing_columns = {row[1] for row in cursor.fetchall()}
                if column not in existing_columns:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
                    logger.info("Migration: added column %s.%s", table, column)
        return True
    except Exception as e:
        logger.error("Schema migration failed: %s", e)
        return False


def import_tools_from_json(json_file_path, db_path):
    """
    Import tools from JSON export file into Open WebUI database.

    :param json_file_path: Path to the tools export JSON file
    :param db_path: Path to the Open WebUI database file
    """
    logger.info("Starting tool import from %s", json_file_path)

    # Check if JSON file exists
    if not os.path.exists(json_file_path):
        logger.error("JSON file not found: %s", json_file_path)
        return False

    # Load tools from JSON file
    try:
        with open(json_file_path, 'r') as f:
            tools_data = json.load(f)
        logger.info("Loaded %d tools from JSON file", len(tools_data))
    except Exception as e:
        logger.error("Error reading JSON file: %s", e)
        return False

    # Wait for database to be available
    if not wait_for_db(db_path):
        return False

    # Connect to database and import tools
    try:
        with sqlite3.connect(db_path, timeout=30.0) as conn:
            cursor = conn.cursor()

            # Check if tool table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tool';")
            if not cursor.fetchone():
                logger.error("Tool table does not exist in database")
                return False

            imported_count = 0
            updated_count = 0

            for tool in tools_data:
                tool_id = tool.get('id')
                if not tool_id:
                    logger.warning("Skipping tool without ID")
                    continue

                # Check if tool already exists
                cursor.execute("SELECT id FROM tool WHERE id = ?", (tool_id,))
                exists = cursor.fetchone()

                if exists:
                    # Update existing tool
                    cursor.execute("""
                        UPDATE tool
                        SET name = ?, content = ?, specs = ?, meta = ?,
                            access_control = ?, updated_at = ?
                        WHERE id = ?
                    """, (
                        tool.get('name'),
                        tool.get('content'),
                        json.dumps(tool.get('specs', [])),
                        json.dumps(tool.get('meta', {})),
                        tool.get('access_control'),
                        tool.get('updated_at'),
                        tool_id
                    ))
                    updated_count += 1
                    logger.info("Updated tool: %s", tool.get('name', tool_id))
                else:
                    # Insert new tool
                    cursor.execute("""
                        INSERT INTO tool (id, user_id, name, content, specs, meta,
                                        access_control, updated_at, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        tool_id,
                        tool.get('user_id'),
                        tool.get('name'),
                        tool.get('content'),
                        json.dumps(tool.get('specs', [])),
                        json.dumps(tool.get('meta', {})),
                        tool.get('access_control'),
                        tool.get('updated_at'),
                        tool.get('created_at')
                    ))
                    imported_count += 1
                    logger.info("Imported tool: %s", tool.get('name', tool_id))

        logger.info("Tool import completed! Imported: %d, Updated: %d", imported_count, updated_count)
        return True

    except Exception as e:
        logger.error("Error importing tools: %s", e)
        return False

def import_functions_from_json(json_file_path, db_path):
    """
    Import filter/pipe functions from JSON export file into Open WebUI database.

    :param json_file_path: Path to the functions export JSON file
    :param db_path: Path to the Open WebUI database file
    """
    logger.info("Starting function import from %s", json_file_path)

    if not os.path.exists(json_file_path):
        logger.error("JSON file not found: %s", json_file_path)
        return False

    try:
        with open(json_file_path, 'r') as f:
            functions_data = json.load(f)
        logger.info("Loaded %d functions from JSON file", len(functions_data))
    except Exception as e:
        logger.error("Error reading JSON file: %s", e)
        return False

    if not wait_for_db(db_path):
        return False

    try:
        with sqlite3.connect(db_path, timeout=30.0) as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='function';")
            if not cursor.fetchone():
                logger.error("Function table does not exist in database")
                return False

            imported_count = 0
            updated_count = 0

            for func in functions_data:
                func_id = func.get('id')
                if not func_id:
                    logger.warning("Skipping function without ID")
                    continue

                cursor.execute("SELECT id FROM function WHERE id = ?", (func_id,))
                existing = cursor.fetchone()

                if existing:
                    cursor.execute("""
                        UPDATE function
                        SET name = ?, type = ?, content = ?, meta = ?, valves = ?,
                            is_active = ?, is_global = ?, updated_at = ?
                        WHERE id = ?
                    """, (
                        func.get('name'),
                        func.get('type'),
                        func.get('content'),
                        json.dumps(func.get('meta', {})),
                        json.dumps(func.get('valves')) if func.get('valves') else None,
                        1 if func.get('is_active', True) else 0,
                        1 if func.get('is_global', True) else 0,
                        func.get('updated_at'),
                        func_id
                    ))
                    updated_count += 1
                    logger.info("Updated function: %s", func.get('name', func_id))
                else:
                    cursor.execute("""
                        INSERT INTO function (id, user_id, name, type, content, meta, valves,
                                             is_active, is_global, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        func_id,
                        func.get('user_id'),
                        func.get('name'),
                        func.get('type'),
                        func.get('content'),
                        json.dumps(func.get('meta', {})),
                        json.dumps(func.get('valves')) if func.get('valves') else None,
                        1 if func.get('is_active', True) else 0,
                        1 if func.get('is_global', True) else 0,
                        func.get('created_at'),
                        func.get('updated_at')
                    ))
                    imported_count += 1
                    logger.info("Imported function: %s", func.get('name', func_id))

            conn.commit()

        logger.info("Function import completed! Imported: %d, Updated: %d", imported_count, updated_count)
        return True

    except Exception as e:
        logger.error("Error importing functions: %s", e)
        return False


def import_models_from_json(json_file_path, db_path, prompts_base_path="/app/", no_override_ids=None):
    """
    Import models from JSON export file into Open WebUI database.

    :param json_file_path: Path to the models export JSON file
    :param db_path: Path to the Open WebUI database file
    :param prompts_base_path: Base path for system prompt files (default: /app/)
    :param no_override_ids: List of model IDs whose inline system prompts should not be overridden
    """
    if no_override_ids is None:
        no_override_ids = []
    logger.info("Starting model import from %s", json_file_path)

    # Check if JSON file exists
    if not os.path.exists(json_file_path):
        logger.error("JSON file not found: %s", json_file_path)
        return False

    # Load models from JSON file
    try:
        with open(json_file_path, 'r') as f:
            models_data = json.load(f)
        logger.info("Loaded %d models from JSON file", len(models_data))
    except Exception as e:
        logger.error("Error reading JSON file: %s", e)
        return False

    # Wait for database to be available
    if not wait_for_db(db_path):
        return False

    # Connect to database and import models
    try:
        with sqlite3.connect(db_path, timeout=30.0) as conn:
            cursor = conn.cursor()

            # Check if model table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='model';")
            if not cursor.fetchone():
                logger.error("Model table does not exist in database")
                return False

            # Get fallback admin user_id for models missing one
            cursor.execute("SELECT id FROM user WHERE role = 'admin' LIMIT 1")
            admin_row = cursor.fetchone()
            fallback_user_id = admin_row[0] if admin_row else None

            imported_count = 0
            updated_count = 0
            deleted_count = 0

            # Get all model IDs from JSON file
            json_model_ids = {model.get('id') for model in models_data if model.get('id')}

            # Delete models not in JSON file
            cursor.execute("SELECT id FROM model")
            existing_models = cursor.fetchall()
            for (model_id,) in existing_models:
                if model_id not in json_model_ids:
                    cursor.execute("DELETE FROM model WHERE id = ?", (model_id,))
                    deleted_count += 1
                    logger.info("Deleted model: %s", model_id)

            for model in models_data:
                model_id = model.get('id')
                if not model_id:
                    logger.warning("Skipping model without ID")
                    continue

                # Load system prompt for this model
                params = model.get('params', {})
                prompt_content, prompt_source = load_system_prompt(params, prompts_base_path, model_id=model_id, no_override_ids=no_override_ids)
                if prompt_content:
                    params['system'] = prompt_content
                    model['params'] = params
                    logger.info("Loaded system prompt for %s from %s", model_id, prompt_source)
                elif prompt_source == "none":
                    logger.warning("No system prompt found for %s", model_id)

                # Check if model already exists
                cursor.execute("SELECT id FROM model WHERE id = ?", (model_id,))
                exists = cursor.fetchone()
                now = int(time.time())

                if exists:
                    # Update existing model
                    cursor.execute("""
                        UPDATE model
                        SET name = ?, meta = ?, params = ?,
                            access_control = ?, updated_at = ?, is_active = ?
                        WHERE id = ?
                    """, (
                        model.get('name'),
                        json.dumps(model.get('meta', {})),
                        json.dumps(model.get('params', {})),
                        json.dumps(model.get('access_control')) if model.get('access_control') is not None else None,
                        model.get('updated_at') or now,
                        model.get('is_active', True),
                        model_id
                    ))
                    updated_count += 1
                    logger.info("Updated model: %s", model.get('name', model_id))
                else:
                    # Insert new model
                    cursor.execute("""
                        INSERT INTO model (id, user_id, base_model_id, name, meta, params,
                                         access_control, updated_at, created_at, is_active)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        model_id,
                        model.get('user_id') or fallback_user_id,
                        model.get('base_model_id'),
                        model.get('name'),
                        json.dumps(model.get('meta', {})),
                        json.dumps(model.get('params', {})),
                        json.dumps(model.get('access_control')) if model.get('access_control') is not None else None,
                        model.get('updated_at') or now,
                        model.get('created_at') or now,
                        model.get('is_active', True)
                    ))
                    imported_count += 1
                    logger.info("Imported model: %s", model.get('name', model_id))

        logger.info(
            "Model import completed! Imported: %d, Updated: %d, Deleted: %d",
            imported_count, updated_count, deleted_count,
        )
        return True

    except Exception as e:
        logger.error("Error importing models: %s", e)
        return False

def substitute_env_vars(obj):
    """
    Recursively substitute environment variable placeholders in a JSON object.
    Placeholders are in the format ${VAR_NAME}.
    """
    if isinstance(obj, str):
        # Find all ${VAR_NAME} patterns and substitute
        pattern = r'\$\{([^}]+)\}'
        def replace_var(match):
            var_name = match.group(1)
            value = os.environ.get(var_name, '')
            if not value:
                logger.warning("Environment variable %s not set", var_name)
            return value
        return re.sub(pattern, replace_var, obj)
    elif isinstance(obj, dict):
        return {k: substitute_env_vars(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [substitute_env_vars(item) for item in obj]
    else:
        return obj

def update_openai_config_via_api(config_data, db_path, base_url="http://localhost:8080", secret_key_dir="/app/backend"):
    """
    Update OpenAI config via the Open WebUI API.
    This ensures the in-memory config cache is refreshed.

    :param config_data: The full config dict (with openai section)
    :param db_path: Path to the Open WebUI database file
    :param base_url: Open WebUI base URL
    :param secret_key_dir: Directory containing .webui_secret_key file
    """
    import uuid
    import requests

    openai_config = config_data.get('openai', {})
    if not openai_config:
        logger.warning("No OpenAI config found, skipping API update")
        return True

    logger.info("Updating OpenAI config via API...")

    try:
        with sqlite3.connect(db_path, timeout=30.0) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM user WHERE role = 'admin' LIMIT 1")
            admin_row = cursor.fetchone()

        if not admin_row:
            logger.warning("No admin user found, skipping API update")
            return True

        admin_id = admin_row[0]

        # Read WEBUI_SECRET_KEY from file
        secret_key_path = os.path.join(secret_key_dir, ".webui_secret_key")
        if not os.path.exists(secret_key_path):
            logger.warning("Secret key file not found: %s", secret_key_path)
            return False

        with open(secret_key_path, 'r') as f:
            webui_secret_key = f.read().strip()

        # Generate a JWT token for the admin user
        import jwt
        from datetime import datetime, timedelta, timezone

        payload = {
            "id": admin_id,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
            "jti": str(uuid.uuid4())
        }
        token = jwt.encode(payload, webui_secret_key, algorithm="HS256")
        logger.info("Generated JWT token for admin user")

        # Prepare the API request
        api_configs = openai_config.get('api_configs', {})
        api_base_urls = openai_config.get('api_base_urls', [])
        api_keys = openai_config.get('api_keys', [])
        enable_openai = openai_config.get('enable', True)

        payload = {
            "ENABLE_OPENAI_API": enable_openai,
            "OPENAI_API_BASE_URLS": api_base_urls,
            "OPENAI_API_KEYS": api_keys,
            "OPENAI_API_CONFIGS": api_configs
        }

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        # Wait for the API to be ready
        max_retries = 30
        for i in range(max_retries):
            try:
                response = requests.get(f"{base_url}/health", timeout=5)
                if response.status_code == 200:
                    break
            except requests.exceptions.RequestException:
                pass
            logger.info("Waiting for API to be ready... (%d/%d)", i + 1, max_retries)
            time.sleep(2)

        # Make the API call
        response = requests.post(
            f"{base_url}/openai/config/update",
            json=payload,
            headers=headers,
            timeout=30
        )

        if response.status_code == 200:
            logger.info("OpenAI config updated via API successfully")
            return True
        else:
            logger.warning("API call returned status %d: %s", response.status_code, response.text)
            return False

    except Exception as e:
        logger.exception("Error updating OpenAI config via API: %s", e)
        return False


def import_config_from_json(json_file_path, db_path):
    """
    Import config from JSON export file into Open WebUI database.
    Supports environment variable substitution for sensitive values like API keys.

    :param json_file_path: Path to the config export JSON file
    :param db_path: Path to the Open WebUI database file
    :return: Tuple of (success, config_data) where config_data is the loaded config
    """
    logger.info("Starting config import from %s", json_file_path)

    # Check if JSON file exists
    if not os.path.exists(json_file_path):
        logger.error("JSON file not found: %s", json_file_path)
        return False, None

    # Load config from JSON file
    try:
        with open(json_file_path, 'r') as f:
            config_data = json.load(f)
        logger.info("Loaded config from JSON file")
    except Exception as e:
        logger.error("Error reading JSON file: %s", e)
        return False, None

    # Substitute environment variables
    config_data = substitute_env_vars(config_data)

    # Wait for database to be available
    if not wait_for_db(db_path):
        return False, None

    # Connect to database and import config
    try:
        with sqlite3.connect(db_path, timeout=30.0) as conn:
            cursor = conn.cursor()

            # Check if config table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='config';")
            if not cursor.fetchone():
                logger.error("Config table does not exist in database")
                return False, None

            # Check if config row exists (id=1)
            cursor.execute("SELECT id FROM config WHERE id = 1")
            exists = cursor.fetchone()

            config_json = json.dumps(config_data)

            if exists:
                # Update existing config
                cursor.execute("""
                    UPDATE config
                    SET data = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = 1
                """, (config_json,))
                logger.info("Updated existing config")
            else:
                # Insert new config
                cursor.execute("""
                    INSERT INTO config (id, data, version, created_at, updated_at)
                    VALUES (1, ?, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """, (config_json,))
                logger.info("Imported new config")

        logger.info("Config import completed!")
        return True, config_data

    except Exception as e:
        logger.error("Error importing config: %s", e)
        return False, None

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    # Default paths
    tools_json = "/app/exports/postgres-tool-export.json"
    models_json = "/app/exports/models-export.json"
    config_json = "/app/exports/config-export.json"
    functions_json = "/app/exports/filter-export.json"
    db_file = "/app/backend/data/webui.db"

    # Override with command line arguments if provided
    if len(sys.argv) > 1:
        tools_json = sys.argv[1]
    if len(sys.argv) > 2:
        models_json = sys.argv[2]
    if len(sys.argv) > 3:
        config_json = sys.argv[3]
    if len(sys.argv) > 4:
        db_file = sys.argv[4]
    if len(sys.argv) > 5:
        functions_json = sys.argv[5]

    # Apply any missing schema migrations before importing
    apply_schema_migrations(db_file)

    # Import tools, models, config, and functions with delays to prevent database locks
    tools_success = import_tools_from_json(tools_json, db_file)
    time.sleep(1)  # Wait for database to release locks

    models_success = import_models_from_json(models_json, db_file)
    time.sleep(1)  # Wait for database to release locks

    config_success, config_data = import_config_from_json(config_json, db_file)
    time.sleep(1)  # Wait for database to release locks

    functions_success = import_functions_from_json(functions_json, db_file)
    time.sleep(1)  # Wait for database to release locks

    # Update OpenAI config via API to refresh in-memory cache
    if config_success and config_data:
        update_openai_config_via_api(config_data, db_file)

    # Exit with success only if all imports succeeded
    success = tools_success and models_success and config_success and functions_success
    sys.exit(0 if success else 1)

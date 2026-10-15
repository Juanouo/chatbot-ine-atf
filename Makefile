.PHONY: help prod-up prod-up-fg prod-down prod-clean-pgdata prod-restart prod-logs prod-rebuild prod-shell prod-db-shell prod-rotate-passwords dev-up dev-up-fg dev-down dev-restart dev-logs dev-rebuild dev-shell dev-db-shell dev-rotate-passwords both-up both-up-fg both-down both-logs status dev-clean-pgdata clean-dev clean-prod

# Compose separado por entorno (compose.prod.yml / compose.dev.yml),
# cada uno con su propia red (prod-net / dev-net) y su env_file (.env.prod / .env.dev)
PROD_COMPOSE := docker compose -f compose.prod.yml
DEV_COMPOSE := docker compose -f compose.dev.yml

# Default target
help:
	@echo "Open WebUI Development & Production Environment"
	@echo ""
	@echo "Production Environment (loopback: 3030 WebUI, 5438 PostgreSQL — sin Ollama):"
	@echo "  make prod-up          - Start production containers (detached)"
	@echo "  make prod-up-fg       - Start production containers (foreground with logs)"
	@echo "  make prod-down        - Stop production containers"
	@echo "  make prod-restart     - Restart production containers"
	@echo "  make prod-rebuild     - Rebuild and restart production"
	@echo "  make prod-logs        - View production logs (follow)"
	@echo "  make prod-shell       - Shell into production open-webui container"
	@echo "  make prod-db-shell    - PostgreSQL shell for production database"
	@echo "  make prod-rotate-passwords - Apply .env.prod passwords to existing DB volume"
	@echo ""
	@echo "Development / Demo Environment (3031 WebUI, loopback 5439 PostgreSQL — OpenRouter only, uses .env):"
	@echo "  make dev-up           - Start development containers (detached)"
	@echo "  make dev-up-fg       - Start development containers (foreground with logs)"
	@echo "  make dev-down         - Stop development containers"
	@echo "  make dev-restart      - Restart development containers"
	@echo "  make dev-rebuild      - Rebuild and restart development"
	@echo "  make dev-logs         - View development logs (follow)"
	@echo "  make dev-shell        - Shell into development open-webui container"
	@echo "  make dev-db-shell     - PostgreSQL shell for development database"
	@echo "  make dev-rotate-passwords - Apply .env passwords to existing DB volume"
	@echo ""
	@echo "Both Environments:"
	@echo "  make both-up          - Start both dev and prod (detached)"
	@echo "  make both-down        - Stop both dev and prod"
	@echo "  make both-logs        - View prod logs + dev logs (sequential)"
	@echo "  make status           - Show status of all containers"
	@echo ""
	@echo "Cleanup (CAUTION - DELETES DATA):"
	@echo "  make clean-dev        - Remove dev volumes (deletes dev data)"
	@echo "  make clean-prod       - Remove prod volumes (deletes prod data)"
	@echo "  make dev-clean-pgdata     - Remove PostgreSQL data directories"
	@echo "  make prod-clean-pgdata     - Remove PostgreSQL data directories"


# Production commands
prod-up:
	@echo "Starting production environment..."
	$(PROD_COMPOSE) up -d

prod-up-fg:
	@echo "Starting production environment (foreground with logs)..."
	$(PROD_COMPOSE) up

prod-down:
	@echo "Stopping production environment..."
	$(PROD_COMPOSE) down

prod-restart:
	@echo "Restarting production environment..."
	$(PROD_COMPOSE) down && $(PROD_COMPOSE) up -d

prod-rebuild:
	@echo "Rebuilding and restarting production environment..."
	python update_tools_export.py && $(PROD_COMPOSE) up -d --build

prod-logs:
	@echo "Showing production logs (Ctrl+C to exit)..."
	$(PROD_COMPOSE) logs -f

prod-shell:
	@echo "Opening shell in production open-webui container..."
	docker exec -it open-webui-prod /bin/bash

prod-db-shell:
	@echo "Opening PostgreSQL shell for production database..."
	docker exec -it toy-postgres-prod psql -U toyuser -d toydb

# Rota passwords en un volumen pgdata ya inicializado (initdb no re-ejecuta).
# Requiere el contenedor corriendo con el .env actualizado (down && up primero).
prod-rotate-passwords:
	@echo "Applying .env.prod passwords to existing production database..."
	docker exec toy-postgres-prod bash -c "psql -U \$$POSTGRES_USER -d \$$POSTGRES_DB -c \"ALTER USER \$$POSTGRES_USER WITH PASSWORD '\$$POSTGRES_PASSWORD';\" -c \"ALTER USER readonly_user WITH PASSWORD '\$$READONLY_PASSWORD';\""
	@echo "Passwords rotated."

prod-clean-pgdata:
	@echo "WARNING: This will delete PostgreSQL data directories for production!"
	@bash -c 'read -p "Are you sure? [y/N] " -n 1 -r REPLY; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		docker volume rm open-webui_pgdata-prod; \
		echo "Production PostgreSQL data directories deleted"; \
	else \
		echo "Cancelled"; \
	fi'

# Development commands
dev-up:
	@echo "Starting development environment..."
	$(DEV_COMPOSE) up -d

dev-up-fg:
	@echo "Starting development environment (foreground with logs)..."
	$(DEV_COMPOSE) up

dev-down:
	@echo "Stopping development environment..."
	$(DEV_COMPOSE) down

dev-restart:
	@echo "Restarting development environment..."
	$(DEV_COMPOSE) down &&  python update_tools_export.py  && $(DEV_COMPOSE) up -d

dev-rebuild:
	@echo "Rebuilding and restarting development environment..."
	python update_tools_export.py && $(DEV_COMPOSE) up -d --build

dev-logs:
	@echo "Showing development logs (Ctrl+C to exit)..."
	$(DEV_COMPOSE) logs -f | grep --line-buffered --color=always -E 'ERROR|$$'

dev-shell:
	@echo "Opening shell in development open-webui container..."
	docker exec -it open-webui-dev /bin/bash

dev-db-shell:
	@echo "Opening PostgreSQL shell for development database..."
	docker exec -it toy-postgres-dev psql -U toyuser -d toydb

# Rota passwords en un volumen pgdata ya inicializado (initdb no re-ejecuta).
# Requiere el contenedor corriendo con el .env actualizado (down && up primero).
dev-rotate-passwords:
	@echo "Applying .env.dev passwords to existing development database..."
	docker exec toy-postgres-dev bash -c "psql -U \$$POSTGRES_USER -d \$$POSTGRES_DB -c \"ALTER USER \$$POSTGRES_USER WITH PASSWORD '\$$POSTGRES_PASSWORD';\" -c \"ALTER USER readonly_user WITH PASSWORD '\$$READONLY_PASSWORD';\""
	@echo "Passwords rotated."

# Both environments
both-up:
	@echo "Starting both development and production environments..."
	$(DEV_COMPOSE) up -d
	$(PROD_COMPOSE) up -d

both-down:
	@echo "Stopping both environments..."
	$(DEV_COMPOSE) down
	$(PROD_COMPOSE) down

both-logs:
	@echo "Showing logs from both environments (Ctrl+C to exit)..."
	$(PROD_COMPOSE) logs --tail 100
	$(DEV_COMPOSE) logs -f

# Status
status:
	@echo "Container Status:"
	@docker ps -a --filter "name=open-webui" --filter "name=toy-postgres" --filter "name=ollama" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Cleanup (dangerous)
clean-dev:
	@echo "WARNING: This will delete all development data!"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		$(DEV_COMPOSE) down -v; \
		echo "Development volumes deleted"; \
	else \
		echo "Cancelled"; \
	fi

clean-prod:
	@echo "WARNING: This will delete all production data!"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		$(PROD_COMPOSE) down -v; \
		echo "Production volumes deleted"; \
	else \
		echo "Cancelled"; \
	fi

dev-clean-pgdata:
	@echo "WARNING: This will delete PostgreSQL data directories for development!"
	@bash -c 'read -p "Are you sure? [y/N] " -n 1 -r REPLY; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		docker volume rm open-webui_pgdata-dev; \
		echo "Development PostgreSQL data directories deleted"; \
	else \
		echo "Cancelled"; \
	fi'

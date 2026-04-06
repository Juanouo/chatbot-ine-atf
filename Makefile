.PHONY: help prod-up prod-up-fg prod-down prod-clean-pgdata prod-restart prod-logs prod-rebuild prod-shell prod-db-shell prod-ollama-shell dev-up dev-up-fg dev-down dev-restart dev-logs dev-rebuild dev-shell dev-db-shell both-up both-up-fg both-down both-logs network-create status dev-clean-pgdata clean-dev clean-prod

# Default target
help:
	@echo "Open WebUI Development & Production Environment"
	@echo ""
	@echo "Network Setup:"
	@echo "  make network-create    - Create the webui-net network (run once)"
	@echo ""
	@echo "Production Environment (ports 3030, 11434, 5438):"
	@echo "  make prod-up          - Start production containers (detached)"
	@echo "  make prod-up-fg       - Start production containers (foreground with logs)"
	@echo "  make prod-down        - Stop production containers"
	@echo "  make prod-restart     - Restart production containers"
	@echo "  make prod-rebuild     - Rebuild and restart production"
	@echo "  make prod-logs        - View production logs (follow)"
	@echo "  make prod-shell       - Shell into production open-webui container"
	@echo "  make prod-db-shell    - PostgreSQL shell for production database"
	@echo "  make prod-ollama-shell - Shell into production ollama container"
	@echo ""
	@echo "Development Environment (ports 3031, 11435, 5439):"
	@echo "  make dev-up           - Start development containers (detached)"
	@echo "  make dev-up-fg        - Start development containers (foreground with logs)"
	@echo "  make dev-down         - Stop development containers"
	@echo "  make dev-restart      - Restart development containers"
	@echo "  make dev-rebuild      - Rebuild and restart development"
	@echo "  make dev-logs         - View development logs (follow)"
	@echo "  make dev-shell        - Shell into development open-webui container"
	@echo "  make dev-db-shell     - PostgreSQL shell for development database"
	@echo ""
	@echo "Both Environments:"
	@echo "  make both-up          - Start both dev and prod (detached)"
	@echo "  make both-up-fg       - Start both dev and prod (foreground with logs)"
	@echo "  make both-down        - Stop both dev and prod"
	@echo "  make both-logs        - View logs from both environments"
	@echo "  make status           - Show status of all containers"
	@echo ""
	@echo "Cleanup (CAUTION - DELETES DATA):"
	@echo "  make clean-dev        - Remove dev volumes (deletes dev data)"
	@echo "  make clean-prod       - Remove prod volumes (deletes prod data)"
	@echo "  make dev-clean-pgdata     - Remove PostgreSQL data directories"
	@echo "  make prod-clean-pgdata     - Remove PostgreSQL data directories"
	

# Network setup
network-create:
	@echo "Creating webui-net network..."
	docker network create webui-net || echo "Network already exists"

# Production commands
prod-up:
	@echo "Starting production environment..."
	docker compose --profile prod up -d

prod-up-fg:
	@echo "Starting production environment (foreground with logs)..."
	docker compose --profile prod up

prod-down:
	@echo "Stopping production environment..."
	docker compose --profile prod down

prod-restart:
	@echo "Restarting production environment..."
	docker compose --profile prod down && docker compose --profile prod up -d
prod-rebuild:
	@echo "Rebuilding and restarting production environment..."
	docker compose --profile prod up -d --build

prod-logs:
	@echo "Showing production logs (Ctrl+C to exit)..."
	docker compose --profile prod logs -f

prod-shell:
	@echo "Opening shell in production open-webui container..."
	docker exec -it open-webui-prod /bin/bash

prod-db-shell:
	@echo "Opening PostgreSQL shell for production database..."
	docker exec -it toy-postgres-prod psql -U toyuser -d toydb

prod-ollama-shell:
	@echo "Opening shell in production ollama container..."
	docker exec -it ollama-prod /bin/bash
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
	docker compose --profile dev up -d

dev-up-fg:
	@echo "Starting development environment (foreground with logs)..."
	docker compose --profile dev up

dev-down:
	@echo "Stopping development environment..."
	docker compose --profile dev down

dev-restart:
	@echo "Restarting development environment..."
	docker compose --profile dev down &&  python update_tools_export.py  && docker compose --profile dev up -d

dev-rebuild:
	@echo "Rebuilding and restarting development environment..."
	docker compose --profile dev up -d --build

dev-logs:
	@echo "Showing development logs (Ctrl+C to exit)..."
	docker compose --profile dev logs -f | grep --line-buffered --color=always -E 'ERROR|$$'

dev-shell:
	@echo "Opening shell in development open-webui container..."
	docker exec -it open-webui-dev /bin/bash

dev-db-shell:
	@echo "Opening PostgreSQL shell for development database..."
	docker exec -it toy-postgres-dev psql -U toyuser -d toydb

# Both environments
both-up:
	@echo "Starting both development and production environments..."
	docker compose --profile dev --profile prod up -d

both-up-fg:
	@echo "Starting both development and production environments (foreground with logs)..."
	docker compose --profile dev --profile prod up

both-down:
	@echo "Stopping both environments..."
	docker compose --profile dev --profile prod down

both-logs:
	@echo "Showing logs from both environments (Ctrl+C to exit)..."
	docker compose --profile dev --profile prod logs -f

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
		docker compose --profile dev down -v; \
		echo "Development volumes deleted"; \
	else \
		echo "Cancelled"; \
	fi

clean-prod:
	@echo "WARNING: This will delete all production data!"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		docker compose --profile prod down -v; \
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
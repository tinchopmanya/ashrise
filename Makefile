.PHONY: up down logs seed verify psql

COMPOSE = docker compose
DB_SERVICE = db
DB_NAME = ashrise
DB_USER = postgres
PSQL = $(COMPOSE) exec -T $(DB_SERVICE) psql -U $(DB_USER) -v ON_ERROR_STOP=1

up:
	$(COMPOSE) up -d --wait $(DB_SERVICE)

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f $(DB_SERVICE)

seed: up
	$(PSQL) -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$(DB_NAME)' AND pid <> pg_backend_pid();"
	$(PSQL) -d postgres -c "DROP DATABASE IF EXISTS $(DB_NAME);"
	$(PSQL) -d postgres -c "CREATE DATABASE $(DB_NAME);"
	$(PSQL) -d $(DB_NAME) -f /workspace/sql/001_init.sql

verify: up
	$(PSQL) -d $(DB_NAME) -f /workspace/sql/verify_sanity.sql

psql: up
	$(COMPOSE) exec $(DB_SERVICE) psql -U $(DB_USER) -d $(DB_NAME)

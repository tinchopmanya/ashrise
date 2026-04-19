.PHONY: up down logs logs-api seed verify psql test

DOCKER_COMPOSE := env MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL="*" docker compose
DC_EXEC := $(DOCKER_COMPOSE) exec --interactive=false -T
DC_EXEC_TTY := $(DOCKER_COMPOSE) exec
DB_SERVICE = db
API_SERVICE = api
DB_NAME = ashrise
DB_USER = postgres
PSQL = $(DC_EXEC) $(DB_SERVICE) psql -U $(DB_USER) -v ON_ERROR_STOP=1

up:
	$(DOCKER_COMPOSE) up -d --build --wait $(DB_SERVICE) $(API_SERVICE)

down:
	$(DOCKER_COMPOSE) down

logs:
	$(DOCKER_COMPOSE) logs -f $(DB_SERVICE)

logs-api:
	$(DOCKER_COMPOSE) logs -f $(API_SERVICE)

seed: up
	$(PSQL) -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$(DB_NAME)' AND pid <> pg_backend_pid();"
	$(PSQL) -d postgres -c "DROP DATABASE IF EXISTS $(DB_NAME);"
	$(PSQL) -d postgres -c "CREATE DATABASE $(DB_NAME);"
	$(PSQL) -d $(DB_NAME) -f /workspace/sql/001_init.sql

verify: up
	$(PSQL) -d $(DB_NAME) -f /workspace/sql/verify_sanity.sql

psql: up
	$(DC_EXEC_TTY) $(DB_SERVICE) psql -U $(DB_USER) -d $(DB_NAME)

test: up
	$(DC_EXEC) $(API_SERVICE) pytest -p no:cacheprovider tests

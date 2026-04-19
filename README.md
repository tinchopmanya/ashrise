# Ashrise

Sprint 2 deja el repo-local completo para Ashrise Core: Postgres 15, schema, API minima FastAPI con auth Bearer y tests happy path sobre Docker. Langfuse queda solo como placeholder de config y los prompts siguen repo-locales en `prompts/`.

## Requisitos

- Docker Desktop con `docker compose`
- GNU Make

## Windows

En Windows puede pasar que `make` este instalado via MSYS2 pero no aparezca en PowerShell o Codex, porque `C:\msys64\usr\bin` no siempre queda en el `PATH` de esas sesiones. Ademas, algunas instalaciones de PowerShell bloquean `.ps1` por `ExecutionPolicy`.

El `Makefile` ya envuelve `docker compose` con `MSYS_NO_PATHCONV=1` y `MSYS2_ARG_CONV_EXCL="*"`, asi que no hace falta exportar esas variables a mano para `make seed` o `make verify`.

Opciones:

- usar MSYS2 directamente si preferis esa terminal
- si PowerShell bloquea scripts, correr `Set-ExecutionPolicy -Scope Process Bypass` en esa sesion; no requiere admin y no cambia la policy global
- correr `.\scripts\windows\ensure-make.ps1 -SessionOnly` para agregar `C:\msys64\usr\bin` solo al `PATH` de la sesion actual
- correr `powershell -ExecutionPolicy Bypass -File .\scripts\windows\ensure-make.ps1 -PersistUserPath` para agregar `C:\msys64\usr\bin` al `PATH` de usuario sin duplicarlo

Despues de cambiar el `PATH` persistente, puede hacer falta reiniciar PowerShell o Codex para que nuevas sesiones vean el cambio.

## Flujo repo-local

- `make up`: levanta `db` y `api`
- `make seed`: recrea la base `ashrise` y aplica `sql/001_init.sql`
- `make verify`: valida conteos y `project_state_code`
- `make test`: corre `pytest` dentro del contenedor `api`
- `make psql`: abre `psql` contra la base `ashrise`
- `make down`: baja los servicios
- `make logs`: sigue logs de `db`
- `make logs-api`: sigue logs de `api`

## Variables de entorno

`.env.example` documenta las variables compartidas de Ashrise y Langfuse:

- `ASHRISE_BASE_URL`
- `ASHRISE_TOKEN`
- `LANGFUSE_BASE_URL`
- `LANGFUSE_PUBLIC_KEY`
- `LANGFUSE_SECRET_KEY`

Para el flujo local de Sprint 2, Docker Compose usa `ASHRISE_TOKEN=dev-token` si no hay override en el entorno.

## API local

Con el stack levantado, la API queda en `http://localhost:8080`.

Ejemplo:

```powershell
curl -H "Authorization: Bearer dev-token" http://localhost:8080/health
curl -H "Authorization: Bearer dev-token" http://localhost:8080/projects
curl -H "Authorization: Bearer dev-token" http://localhost:8080/candidates
```

## Flujo recomendado

```powershell
make up
make seed
make verify
make test
make psql
```

## Alcance actual

- Postgres 15 local con volumen persistente
- `sql/001_init.sql` aplicado via `make seed`
- verificacion repo-local via `sql/verify_sanity.sql`
- API FastAPI minima con auth Bearer para operacion e investigacion
- tests happy path con `pytest`

## Lo que sigue siendo Sprint 3+

- `ashrise-hook` y wrapper runtime para sesiones
- bot de Telegram
- captura automatica de `ashrise-close`
- Langfuse operativo mas alla de placeholders de config

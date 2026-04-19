# Ashrise

Sprint 3 deja el repo-local completo para Ashrise Core: Postgres 15, schema, API minima FastAPI con auth Bearer, `ashrise-hook`, wrapper para Codex, bot de Telegram por polling y recordatorio diario pasivo cron-friendly. Langfuse queda solo como placeholder de config y los prompts siguen repo-locales en `prompts/`.

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
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

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
- `ashrise-hook` para abrir/cerrar runs contra la API
- wrapper repo-local para Codex
- bot de Telegram por polling
- recordatorio diario pasivo via `reminder-once`

## Hook de sesiones

Defini estas variables antes de usar el hook contra la API:

```powershell
$env:ASHRISE_BASE_URL = "http://localhost:8080"
$env:ASHRISE_TOKEN = "dev-token"
```

Abrir una sesion:

```powershell
python .\scripts\ashrise-hook.py session-start --project ashrise
```

Cerrar una sesion usando un transcript:

```powershell
python .\scripts\ashrise-hook.py session-stop --project ashrise --transcript .\.ashrise\transcripts\ashrise-YYYYMMDD-HHMMSS.log
```

Si no queres usar archivo, `session-stop` tambien acepta `--text` o stdin.

## Wrapper de Codex

El wrapper abre el run, ejecuta un comando, guarda transcript en `.ashrise/transcripts/` y llama `session-stop` al final.

Ejemplo generico:

```powershell
python .\scripts\run_codex_task.py --project ashrise -- codex exec "Implement something"
```

Si tu flujo de Codex consume prompt por stdin, podes pasar contexto + tarea con `--prompt-file` o `--prompt-text`.

## Bot de Telegram

El bot usa polling y habla contra la API, no contra la base.

Variables necesarias:

```powershell
$env:ASHRISE_BASE_URL = "http://localhost:8080"
$env:ASHRISE_TOKEN = "dev-token"
$env:TELEGRAM_BOT_TOKEN = "..."
```

Modo polling:

```powershell
python .\scripts\telegram_bot.py polling
```

Comandos disponibles:

- `/estado <proyecto>`
- `/ultimo <proyecto>`
- `/idea <texto>`
- `/candidatas [categoria]`
- `/candidata <slug>`
- `/auditar <proyecto|candidata>` devuelve stub claro hasta Sprint 4

## Recordatorio diario pasivo

`reminder-once` es cron-friendly. Cuenta:

- items en `research_queue` con `due <= today`
- proyectos activos sin audit en los ultimos 7 dias

Ejemplo:

```powershell
$env:TELEGRAM_CHAT_ID = "123456"
python .\scripts\telegram_bot.py reminder-once
```

La idea es programarlo a las 9am con Task Scheduler, cron o un scheduler externo simple.

## Lo que sigue siendo Sprint 4+

- agente unificado auditor + investigador
- endpoint `/agent/run`
- `/auditar` real en Telegram
- Langfuse operativo mas alla de placeholders de config

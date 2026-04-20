# Ashrise

Sprint 5 deja el repo-local operativo para Ashrise Core con Postgres, API FastAPI, runtime tooling, agente unificado, `POST /agent/run`, Langfuse self-hosted local, promoción manual de candidatas y reminder diario activo. `ashrise.research` sigue usando fallback `stub` controlado hasta que entre un provider real.

## Requisitos

- Docker Desktop con `docker compose`
- GNU Make

## Windows

En Windows puede pasar que `make` esté instalado vía MSYS2 pero no aparezca en PowerShell o Codex, porque `C:\msys64\usr\bin` no siempre queda en el `PATH` de esas sesiones. Además, algunas instalaciones de PowerShell bloquean `.ps1` por `ExecutionPolicy`.

El `Makefile` ya envuelve `docker compose` con `MSYS_NO_PATHCONV=1` y `MSYS2_ARG_CONV_EXCL="*"`, así que no hace falta exportar esas variables a mano.

Opciones:

- usar MSYS2 directamente si preferís esa terminal
- si PowerShell bloquea scripts, correr `Set-ExecutionPolicy -Scope Process Bypass` en esa sesión
- correr `.\scripts\windows\ensure-make.ps1 -SessionOnly`
- correr `powershell -ExecutionPolicy Bypass -File .\scripts\windows\ensure-make.ps1 -PersistUserPath`

Después de cambiar el `PATH` persistente, puede hacer falta reiniciar PowerShell o Codex.

## Variables de entorno

`.env.example` deja un set repo-local utilizable:

- `ASHRISE_BASE_URL`
- `ASHRISE_TOKEN`
- `LANGFUSE_BASE_URL`
- `LANGFUSE_PUBLIC_KEY`
- `LANGFUSE_SECRET_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Para usar Ashrise/Langfuse fuera de la máquina local, cambiá las URLs por el hostname Headscale correspondiente.

## Flujo repo-local

- `make up`: levanta `db` y `api`
- `make seed`: recrea la base `ashrise` y aplica `sql/001_init.sql`
- `make verify`: valida conteos y `project_state_code`
- `make test`: corre `pytest` dentro del contenedor `api`
- `make psql`: abre `psql` contra la base `ashrise`
- `make down`: baja todos los servicios
- `make logs`: sigue logs de `db`
- `make logs-api`: sigue logs de `api`

Flujo base recomendado:

```powershell
make up
make seed
make verify
make test
```

## Langfuse local

Langfuse corre como stack opcional en el mismo compose. No hace falta para usar Ashrise Core, pero sí para Sprint 5 completo con prompts sincronizados y trazabilidad.

Levantar Langfuse local:

```powershell
make langfuse-up
make langfuse-sync-prompts
```

Servicios locales:

- Ashrise API: `http://localhost:8080`
- Langfuse UI/API: `http://localhost:3000`

Credenciales de desarrollo del stack local:

- usuario: `admin@ashrise.local`
- password: `ashrise-local-dev`
- public key: `pk-lf-local`
- secret key: `sk-lf-local`

Si usás scripts fuera de Docker, exportá:

```powershell
$env:ASHRISE_BASE_URL = "http://localhost:8080"
$env:ASHRISE_TOKEN = "dev-token"
$env:LANGFUSE_BASE_URL = "http://localhost:3000"
$env:LANGFUSE_PUBLIC_KEY = "pk-lf-local"
$env:LANGFUSE_SECRET_KEY = "sk-lf-local"
```

## API local

Con el stack levantado, la API queda en `http://localhost:8080`.

Health:

```powershell
curl -H "Authorization: Bearer dev-token" http://localhost:8080/health
```

Proyecto y candidata:

```powershell
curl -H "Authorization: Bearer dev-token" http://localhost:8080/projects
curl -H "Authorization: Bearer dev-token" http://localhost:8080/candidates
```

Agente con trazabilidad:

```powershell
curl -H "Authorization: Bearer dev-token" `
  -H "Content-Type: application/json" `
  -X POST `
  -d '{"target_type":"project","target_id":"procurement-licitaciones"}' `
  http://localhost:8080/agent/run
```

La respuesta del run incluye:

- `prompt_ref`
- `langfuse_trace_id`
- metadata con `prompt_source`, `langfuse_status` y target asociado

Si Langfuse no está disponible, el flujo no se rompe: el agente sigue corriendo y deja `langfuse_status='disabled'` o `trace-error`.

## Promoción de candidatas

El agente marca señal de promoción cuando una candidata acumula 3 reportes consecutivos con:

- `verdict='advance'`
- `confidence > 0.7`

Esa señal queda en `vertical_candidates.metadata.promotion`.

La aprobación sigue siendo manual y explícita. Para promover:

```powershell
curl -H "Authorization: Bearer dev-token" `
  -H "Content-Type: application/json" `
  -X POST `
  -d '{"project_id":"mi-nuevo-proyecto","name":"Mi Nuevo Proyecto","host_machine":"i7-main"}' `
  http://localhost:8080/candidates/mi-candidata/promote
```

La promoción hace esto:

- crea `projects`
- setea `projects.promoted_from_candidate_id`
- marca la candidata como `promoted`
- setea `promoted_to_project_id`
- crea `project_state` inicial para el proyecto nuevo

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
- `/auditar <proyecto|candidata>`

## Reminder diario activo

`reminder-once` ahora ejecuta el flujo activo de Sprint 5:

1. lee `research_queue` con `scheduled_for <= today`
2. corre `POST /agent/run` para cada item
3. actualiza la queue
4. manda resumen por Telegram con veredictos y señales de promoción

Reglas actuales:

- `kill` o `park` → `research_queue.status='done'`
- `iterate` o `split` → reencola a 7 días
- `advance` → reencola a 7 días, salvo que quede `ready` para promoción; en ese caso sale de la queue
- proyectos con `recurrence` semanal/mensual se reprograman según esa recurrencia

Ejemplo:

```powershell
$env:TELEGRAM_CHAT_ID = "123456"
python .\scripts\telegram_bot.py reminder-once
```

Si querés el resumen pasivo viejo:

```powershell
python .\scripts\telegram_bot.py reminder-passive-once
```

También podés correr el ciclo activo sin Telegram, solo contra la API:

```powershell
docker compose exec --interactive=false -T `
  -e ASHRISE_BASE_URL=http://localhost:8080 `
  -e ASHRISE_TOKEN=dev-token `
  api python -c "from ashrise_runtime.api_client import AshriseApiClient; from ashrise_runtime.telegram_bot import build_active_daily_summary, run_active_daily_cycle; api = AshriseApiClient(); result = run_active_daily_cycle(api); print(build_active_daily_summary(result)); api.close()"
```

## Hook y wrapper

Hook de sesiones:

```powershell
python .\scripts\ashrise-hook.py session-start --project ashrise
python .\scripts\ashrise-hook.py session-stop --project ashrise --transcript .\.ashrise\transcripts\ashrise-YYYYMMDD-HHMMSS.log
```

Wrapper de Codex:

```powershell
python .\scripts\run_codex_task.py --project ashrise -- codex exec "Implement something"
```

## Qué es real hoy y qué sigue en fallback

Real en Sprint 5:

- Langfuse self-hosted local en Compose
- sync de prompts críticos a Langfuse
- `prompt_ref` y `langfuse_trace_id` en runs/reports relevantes
- promoción manual de candidatas listas
- reminder diario activo con actualización de `research_queue`

Fallback temporal:

- `ashrise.research` sigue con provider `stub`
- el agente sigue siendo heurístico; la observabilidad de Langfuse traza prompt, input, output y metadata, pero no hay provider LLM externo enchufado todavía

## Qué queda fuera de Sprint 5

- provider real de research web
- Promptfoo / evals automáticas
- Langfuse como fuente única de prompts fuera del repo
- aprobación interactiva desde Telegram
- automatización tipo Temporal o scheduler residente complejo

# Ashrise

Sprint 5 deja el repo-local operativo para Ashrise Core con Postgres, API FastAPI, runtime tooling, agente unificado, `POST /agent/run`, Langfuse local, promocion manual de candidatas y reminder diario activo. El provider real recomendado para `ashrise.research` ahora es Tavily, con fallback `stub` cuando faltan credenciales o el provider no responde.

## Requisitos

- Docker Desktop con `docker compose`
- GNU Make

## Windows

En Windows puede pasar que `make` este instalado via MSYS2 pero no aparezca en PowerShell o Codex porque `C:\msys64\usr\bin` no siempre queda en el `PATH` de esas sesiones. Algunas instalaciones de PowerShell tambien bloquean `.ps1` por `ExecutionPolicy`.

El `Makefile` ya envuelve `docker compose` con `MSYS_NO_PATHCONV=1` y `MSYS2_ARG_CONV_EXCL="*"`, asi que no hace falta exportar esas variables a mano.

Opciones:

- usar MSYS2 directamente si preferis esa terminal
- si PowerShell bloquea scripts, correr `Set-ExecutionPolicy -Scope Process Bypass` en esa sesion
- correr `.\scripts\windows\ensure-make.ps1 -SessionOnly`
- correr `powershell -ExecutionPolicy Bypass -File .\scripts\windows\ensure-make.ps1 -PersistUserPath`

Despues de cambiar el `PATH` persistente, puede hacer falta reiniciar PowerShell o Codex.

## Variables de entorno

`.env.example` deja un set repo-local utilizable:

- `ASHRISE_BASE_URL`
- `ASHRISE_TOKEN`
- `LANGFUSE_BASE_URL`
- `LANGFUSE_PUBLIC_KEY`
- `LANGFUSE_SECRET_KEY`
- `ASHRISE_RESEARCH_PROVIDER`
- `ASHRISE_RESEARCH_API_KEY`
- `ASHRISE_RESEARCH_BASE_URL`
- `ASHRISE_RESEARCH_PROJECT_ID`
- `ASHRISE_RESEARCH_REGION`
- `ASHRISE_RESEARCH_COUNTRY`
- `ASHRISE_RESEARCH_SEARCH_LANG`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Para usar Ashrise o Langfuse fuera de la maquina local, cambia las URLs por el hostname Headscale correspondiente.

## Flujo repo-local

- `make up`: levanta `db` y `api`
- `make seed`: recrea la base `ashrise` y aplica `sql/001_init.sql`
- `make verify`: valida conteos y `project_state_code`
- `make test`: corre `pytest` dentro del contenedor `api`
- `make psql`: abre `psql` contra la base `ashrise`
- `make down`: baja todos los servicios
- `make logs`: sigue logs de `db`
- `make logs-api`: sigue logs de `api`
- `make langfuse-up`: levanta el stack local de Langfuse
- `make langfuse-sync-prompts`: sincroniza prompts criticos a Langfuse

Flujo base recomendado:

```powershell
make up
make seed
make verify
make test
```

## Langfuse local

Langfuse corre como stack opcional en el mismo compose. No hace falta para usar Ashrise Core, pero si para trazabilidad y prompts sincronizados.

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

Si usas scripts fuera de Docker, exporta:

```powershell
$env:ASHRISE_BASE_URL = "http://localhost:8080"
$env:ASHRISE_TOKEN = "dev-token"
$env:LANGFUSE_BASE_URL = "http://localhost:3000"
$env:LANGFUSE_PUBLIC_KEY = "pk-lf-local"
$env:LANGFUSE_SECRET_KEY = "sk-lf-local"
$env:ASHRISE_RESEARCH_PROVIDER = "tavily"
$env:ASHRISE_RESEARCH_API_KEY = ""
$env:ASHRISE_RESEARCH_BASE_URL = "https://api.tavily.com"
$env:ASHRISE_RESEARCH_PROJECT_ID = ""
```

## Research provider real

El provider real recomendado es **Tavily Search API**. `ashrise.research` lo usa con `httpx` contra el endpoint HTTP oficial y mantiene exactamente las mismas funciones:

- `web_search(...)`
- `find_competitors(...)`
- `check_ai_encroachment(...)`
- `assess_stack(...)`

Configuracion minima para usar Tavily:

```powershell
$env:ASHRISE_RESEARCH_PROVIDER = "tavily"
$env:ASHRISE_RESEARCH_API_KEY = "tvly-tu-api-key"
$env:ASHRISE_RESEARCH_BASE_URL = "https://api.tavily.com"
$env:ASHRISE_RESEARCH_PROJECT_ID = ""
$env:ASHRISE_RESEARCH_REGION = "LATAM"
$env:ASHRISE_RESEARCH_COUNTRY = "UY"
$env:ASHRISE_RESEARCH_SEARCH_LANG = "es"
```

Notas operativas:

- Tavily usa `Authorization: Bearer <API_KEY>`
- `ASHRISE_RESEARCH_PROJECT_ID` es opcional y viaja como `X-Project-ID`
- si falta `ASHRISE_RESEARCH_API_KEY`, Tavily falla o `ASHRISE_RESEARCH_PROVIDER=stub`, el flujo vuelve a `stub` sin romper `/agent/run`
- metadata y traces preservan `research_provider`, `research_fallback` y `research_fallback_reason`
- errores y metadata pasan por sanitizacion basica para no exponer tokens o API keys

Brave queda soportado como compatibilidad legacy para setups previos, pero Tavily es el provider principal documentado.

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
- metadata con `prompt_source`, `langfuse_status`, `research_provider` y target asociado

Si Langfuse no esta disponible, el flujo no se rompe: el agente sigue corriendo y deja `langfuse_status='disabled'` o `trace-error`. Cuando el provider real esta activo, cada busqueda relevante deja observabilidad minima asociada a `run_id`, `target_type`, `target_id` y `prompt_ref`.

## Dashboard F6B

El repo ahora incluye la base interactiva de tasks, el primer corte del grafo visual de Project Detail, la ola de acciones seguras y el cierre read-only de Langfuse + Notifications/System sobre el dashboard ya estable:

- Overview
- Projects
- Project Detail
- Runs
- Handoffs
- Ideas
- Research
- Prompts & Traces
- Notifications
- System

Los datos del dashboard salen solo de los endpoints agregados del backend:

- `GET /dashboard/overview`
- `GET /dashboard/projects`
- `GET /dashboard/projects/{id}`
- `GET /dashboard/projects/{id}/graph`
- `GET /dashboard/runs/recent`
- `GET /dashboard/runs/{id}`
- `GET /dashboard/handoffs/open`
- `GET /dashboard/ideas/overview`
- `GET /dashboard/ideas/{id}/workspace`
- `GET /dashboard/tasks/board`
- `GET /dashboard/research/overview`
- `GET /dashboard/langfuse/summary`
- `GET /dashboard/langfuse/prompts`
- `GET /dashboard/langfuse/traces`
- `GET /dashboard/notifications`
- `GET /dashboard/notifications/{id}`
- `GET /dashboard/telegram/summary`
- `GET /dashboard/system/health`
- `GET /dashboard/system/jobs`
- `GET /dashboard/system/integrations`
- `POST /dashboard/actions/run-agent`
- `POST /dashboard/actions/resolve-handoff`
- `POST /dashboard/actions/requeue`
- `PATCH /projects/{id}`
- `PUT /state/{project_id}`
- `GET /tasks`
- `GET /tasks/{id}`
- `POST /tasks`
- `PATCH /tasks/{id}`
- `DELETE /tasks/{id}`
- `PATCH /ideas/{id}/triage`
- `PATCH /candidates/{id}`
- `POST /decisions`
- `POST /decisions/{id}/supersede`

F6B cierra la base read-only útil de Fase 6:

- `Prompts & Traces` usa primero datos reales ya persistidos en `runs`
- `Notifications` lee `notification_events` reales y muestra vacío honesto si todavía no hay eventos suficientes
- `System` combina `health`, jobs recientes e integraciones usando señales reales disponibles
- no duplica prompt bodies ni inventa actividad cuando todavía no existe persistida

Por ahora el frontend vive como app Vite separada. Esto evita colisionar rutas UI (`/dashboard/...`) con los endpoints backend del mismo prefijo en la instancia FastAPI actual.

Backend:

```powershell
make up
docker compose exec --interactive=false -T api alembic upgrade head
```

Frontend:

```powershell
cd dashboard-ui
Copy-Item .env.example .env -ErrorAction SilentlyContinue
npm.cmd install
npm.cmd run dev
```

La API permite CORS para la SPA local en:

- `http://localhost:5173`
- `http://127.0.0.1:5173`
- `http://localhost:4173`
- `http://127.0.0.1:4173`

Si necesitás otro origen local, podés extenderlo con `ASHRISE_DASHBOARD_CORS_ORIGINS` como lista separada por comas.

Variables esperadas por el frontend:

- `VITE_API_BASE_URL`, default recomendado `http://localhost:8080`
- `VITE_API_TOKEN`, default de desarrollo `dev-token`

Build del frontend:

```powershell
cd dashboard-ui
npm.cmd run build
```

Fase 1 sigue cerrada con esta superficie read-only:

- Overview
- Projects + Project Detail
- Runs
- Handoffs
- Ideas inbox read-only
- Research
- System health
- Decisions dentro de Project Detail

Fase 2A abrio:

- tabla `tasks` via Alembic
- CRUD real de tasks (`/tasks`)
- aggregates reales de ideas + task counts
- workspace de idea con create/edit/delete/status para tasks
- board de tasks con move actions explicitas en vez de drag and drop

Fase 3A abre:

- tab `Graph` dentro de `Project Detail`
- `GET /dashboard/projects/{id}/graph`
- nodo central de proyecto con satelites reales de runs, handoffs, decisions, audit, related research, ideas y tasks
- panel lateral read-only con metadata util
- layout radial determinista temporal sobre SVG nativo, con drag de nodos, pan y zoom

Fase 4A abre:

- `Run agent` desde `Project Detail` con confirmacion explicita
- `Resolve` desde `Handoffs` con nota opcional y refetch real
- `Triage` de ideas desde `/dashboard/ideas`
- `Create decision` desde `Project Detail`
- wrapper dashboard para `POST /agent/run` y resolucion segura de handoffs

Se mantiene deliberadamente fuera de este turno:

Fase 4B completa la superficie segura de `Research`:

- `Run agent` sobre candidates desde `/dashboard/research`
- `Requeue` de `research_queue` desde un wrapper dashboard seguro
- `Promote candidate` desde `/dashboard/research` usando el flujo real existente `POST /candidates/{id}/promote`
- refetch real, confirmacion explicita para `run-agent` y `promote`, y formularios sobrios para `requeue`

Fase 5A abre una primera ola de edicion full minima y segura:

- `Edit state` en `Project Detail` usando el contrato canonico `PUT /state/{project_id}`
- edicion minima de metadata de proyecto usando `PATCH /projects/{id}` para `status`, `priority`, `importance`, `host_machine` y `progress_pct`
- edicion minima de metadata de candidate desde `Research` usando `PATCH /candidates/{id}`
- `Create decision` se mantiene y ahora se suma `supersede` explicito via `POST /decisions/{id}/supersede`
- `kill_verdict` queda fuera de la UI de F5A porque en el modelo real es JSON y todavia no tiene una semantica chica y estable para exponerlo como formulario seguro

Pendiente para cerrar mejor Fase 3:

- evaluar si hace falta pasar de radial a force-directed sin d3
- mini-graphs fuera de `Project Detail`

Sigue fuera de alcance para F6B/Fase 7:

- same-origin refactor
- write actions adicionales fuera de las seguras ya agregadas
- pagina global de Decisions

Fase 2B cierra mejor el modulo Ideas & Tasks antes de graph:

- arbol + detalle de ideas con seleccion activa mas clara y task counts mas visibles
- subvista `Tasks` con split-arrows mas legibles entre idea raiz y tareas
- board scoped a la idea seleccionada en `/dashboard/ideas`, en vez de mezclar tareas de otras ideas
- orden persistente por `position` dentro del scope real de cada task (`idea_id` / `project_id` / `candidate_id` + `status`)
- move actions explicitas (`Up`, `Down`, `Move left`, `Move right`) mantenidas por robustez; drag and drop sigue diferido
- decision consolidada de modelo: `ideas.title` y `ideas.description` siguen derivados desde `raw_text`

No agregue migracion nueva para `ideas.title` o `ideas.description` en F2B. La decision queda explicita: por ahora se mantiene la derivacion desde `raw_text` porque el flujo actual ya es usable y meter duplicacion persistida antes de graph agregaba riesgo innecesario.

Explícitamente queda para Fase 7+:

- actions write nuevas fuera de las ya validadas
- notifications multi-canal más allá de Telegram
- integraciones más profundas de sistema si aparecen nuevas señales persistidas

Alcance y omisiones intencionales en este corte:

- no hay same-origin serving; backend y `dashboard-ui` siguen separados
- `Decisions` sigue dentro de Project Detail; no hay página global standalone todavía
- no hay same-origin ni nuevas acciones write en Notifications/System
- el módulo `Ideas` sigue derivando `title` desde `raw_text` porque el schema persistido no tiene `title` ni `description` propios

## Promocion de candidatas

El agente marca senal de promocion cuando una candidata acumula 3 reportes consecutivos con:

- `verdict='advance'`
- `confidence > 0.7`

Esa senal queda en `vertical_candidates.metadata.promotion`.

La aprobacion sigue siendo manual y explicita. Para promover:

```powershell
curl -H "Authorization: Bearer dev-token" `
  -H "Content-Type: application/json" `
  -X POST `
  -d '{"project_id":"mi-nuevo-proyecto","name":"Mi Nuevo Proyecto","host_machine":"i7-main"}' `
  http://localhost:8080/candidates/mi-candidata/promote
```

La promocion hace esto:

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

`reminder-once` ejecuta el flujo activo:

1. lee `research_queue` con `scheduled_for <= today`
2. corre `POST /agent/run` para cada item
3. actualiza la queue
4. manda resumen por Telegram con veredictos y senales de promocion

Reglas actuales:

- `kill` o `park` -> `research_queue.status='done'`
- `iterate` o `split` -> reencola a 7 dias
- `advance` -> reencola a 7 dias, salvo que quede `ready` para promocion; en ese caso sale de la queue
- proyectos con `recurrence` semanal o mensual se reprograman segun esa recurrencia

Ejemplo:

```powershell
$env:TELEGRAM_CHAT_ID = "123456"
python .\scripts\telegram_bot.py reminder-once
```

Si quieres el resumen pasivo viejo:

```powershell
python .\scripts\telegram_bot.py reminder-passive-once
```

Tambien puedes correr el ciclo activo sin Telegram, solo contra la API:

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

## Que es real hoy y que sigue en fallback

Real hoy:

- Langfuse local en Compose
- sync de prompts criticos a Langfuse
- `prompt_ref` y `langfuse_trace_id` en runs y reportes relevantes
- provider real opcional via Tavily Search detras de `ashrise.research`
- promocion manual de candidatas listas
- reminder diario activo con actualizacion de `research_queue`

Fallback temporal:

- `ashrise.research` vuelve a `stub` si faltan credenciales o el provider externo falla
- el agente sigue siendo heuristico; Langfuse ya traza prompt, input, output, metadata y uso del provider de search, pero no hay provider LLM externo enchufado todavia

## Que queda fuera de Sprint 5

- Promptfoo o evals automaticas
- Langfuse como fuente unica de prompts fuera del repo
- aprobacion interactiva desde Telegram
- automatizacion tipo Temporal o scheduler residente complejo

# Ashrise — Roadmap

**Versión:** 2.1
**Fecha:** Abril 2026
**Estado:** activo — listo para implementación
**Owner:** Martin (solo founder)

---

## Qué es Ashrise

Ashrise es la **capa de estado compartido** entre los proyectos de Martin y los agentes IA (Claude Code, Codex, etc.) que trabajan en ellos.

Un microservicio local (FastAPI + Postgres) que corre en la i7 y cubre dos dominios:

- **Operación**: qué se está construyendo, cómo va, quién lo tocó, qué decidió, qué ideas están en intake.
- **Investigación**: qué verticales candidatas podrían valer la pena construir, cuáles se matan.

**Lo que Ashrise NO es:**

| NO es | Para eso usamos |
|---|---|
| Un PM / tracker | GitHub Projects |
| Observabilidad de prompts | Langfuse |
| Evals / red teaming | Promptfoo |
| Un bot conversacional | Telegram es superficie de entrada, no el core |

---

## Principios de diseño

1. **Una sola máquina operativa para Ashrise**: i7 como host de Ashrise. Otros repos (ProcurementUY en notebook-procurement, OSLA en notebook-osla-docker) consumen la API via Headscale.
2. **URLs configurables**: `ASHRISE_BASE_URL` y `LANGFUSE_BASE_URL` como env vars. Nunca `localhost:8080` hardcodeado.
3. **Agent-agnostic**: contrato `ashrise-close` definido en `AGENTS.md`, funciona con cualquier agente IA.
4. **Capa delgada**: Ashrise no reinventa herramientas existentes. Se conecta a ellas.
5. **Prompts fuera del schema**: en git (estables) o Langfuse (volátiles). Ashrise solo guarda `prompt_ref`.
6. **Un solo agente IA para arrancar**: auditor+investigador unificado con prompt condicional por tipo de target. Dividir en dos más adelante si costo+calidad lo justifican.

---

## Sprints

### Sprint 1 — Host operativo y schema (2-3 días)

**Objetivo:** infraestructura base corriendo.

**Entregables:**

- [ ] **Headscale** self-hosted en i7. Clientes en celular, notebook-procurement, notebook-osla-docker, notebook backup.
- [ ] Hostnames tailnet definidos (ej: `ashrise.ts.net`, `notebook-procurement.ts.net`).
- [ ] Postgres 15+ local en i7.
- [ ] Schema `sql/001_init.sql` aplicado. 14 proyectos seedeados con `host_machine` correcto.
- [ ] Worktree de `ashrise` creado en i7.
- [ ] Worktree de `procurement-core` operativo en notebook-procurement.
- [ ] tmux/zellij con sesiones nombradas.
- [ ] `codex login --device-auth` validado desde SSH remoto.
- [ ] `AGENTS.md` + `CLAUDE.md` stub en cada repo activo.
- [ ] `.env.example` documentando `ASHRISE_BASE_URL`, `ASHRISE_TOKEN`, `LANGFUSE_*`.

**Criterio de éxito:** desde el celular por Headscale, abrir tmux en i7 y ejecutar `psql ashrise -c "SELECT id, name, host_machine, status FROM projects;"` devuelve los 14 proyectos con host correctamente poblado.

---

### Sprint 2 — Ashrise Core API (4-5 días)

**Objetivo:** API mínima funcional para dominio de operación **y dominio de investigación**.

**Incremento vs versión anterior del roadmap:** los endpoints de candidatas entran en Sprint 2, no en Sprint 4. Sprint 3 y 4 los necesitan.

**Entregables:**

- [ ] FastAPI app con estructura estándar (`main.py`, `routers/`, `models/`, `db.py`, `config.py` para env vars).
- [ ] Autenticación simple por Bearer token (`ASHRISE_TOKEN` del server, validado en todos los endpoints).

**Endpoints — dominio de operación:**

- [ ] `GET /health`
- [ ] `GET /projects` (lista, filtrable por status/kind/host_machine)
- [ ] `GET /projects/{id}` (detalle con parent/children)
- [ ] `GET /state/{project_id}`
- [ ] `PUT /state/{project_id}`
- [ ] `POST /runs`
- [ ] `PATCH /runs/{id}` (cerrar un running)
- [ ] `GET /runs/{project_id}?limit=N`
- [ ] `POST /handoffs`
- [ ] `GET /handoffs/{project_id}?status=open`
- [ ] `PATCH /handoffs/{id}` (resolver)
- [ ] `POST /decisions`
- [ ] `GET /decisions/{project_id}`
- [ ] `GET /audit/{project_id}` (último; vacío hasta Sprint 4)
- [ ] `POST /ideas`
- [ ] `GET /ideas?status=new`
- [ ] `PATCH /ideas/{id}` (triage: asignar proyecto, promover, descartar)

**Endpoints — dominio de investigación:**

- [ ] `GET /candidates` (lista, filtrable por status/category/parent_group)
- [ ] `GET /candidates/{id}`
- [ ] `POST /candidates`
- [ ] `PATCH /candidates/{id}`
- [ ] `GET /candidates/{id}/research` (último reporte)
- [ ] `GET /research-queue?due=today` (para el recordatorio diario)

**Tests + deploy:**

- [ ] Tests pytest: happy path de cada endpoint con auth.
- [ ] Docker Compose que levanta Postgres + API juntos.
- [ ] README con `make up`, `make test`, `make seed`.

**Criterio de éxito:**
- `curl -H "Authorization: Bearer $T" $ASHRISE_BASE_URL/projects` desde el celular devuelve los 14.
- `curl -H "Authorization: Bearer $T" $ASHRISE_BASE_URL/candidates` devuelve lista vacía (todavía no hay candidatas).
- `POST /ideas` acepta idea sin project_id, queda en status=new.

---

### Sprint 3 — Runtime + captura + bot Telegram (4-5 días)

**Objetivo:** cerrar el loop de trabajo diario.

**Entregables:**

- [ ] **Script `ashrise-hook`** (Python, CLI, instalable via pip):
  - `ashrise-hook session-start --project <id>` — crea run, inyecta state+audit+handoffs a stdout (Claude Code lee vía hook).
  - `ashrise-hook session-stop --project <id> [--transcript <path>]` — lee el último turno del transcript, extrae bloque `ashrise-close`, valida YAML, hace POSTs/PATCH a Ashrise.
  - Lee `$ASHRISE_BASE_URL` y `$ASHRISE_TOKEN` del entorno.

- [ ] **Wrapper `run_codex_task.sh`** — equivalente para Codex sin hooks nativos.

- [ ] **Bot de Telegram** (Python, polling, sin webhook público):
  - `/estado [proyecto]` — muestra state actual.
  - `/ultimo [proyecto]` — último run.
  - `/idea <texto>` — crea registro en `ideas` con source=telegram.
  - `/candidatas [categoría]` — lista candidatas agrupadas por status.
  - `/candidata <slug>` — detalle de una candidata con último research_report si existe.
  - `/auditar <proyecto|candidata>` — dispara agente on-demand (stub hasta Sprint 4).
  - **Recordatorio diario pasivo** (cron 9am): cuenta pendientes en `research_queue` con `due <= today` + proyectos sin audit > 7 días. Solo notifica, no ejecuta todavía.

**Criterio de éxito:** desde el celular, `/idea probar nano banana para thumbnails` queda en Ashrise. Abrir Claude Code en `procurement-core`, trabajar, al cerrar el hook captura el bloque y se ve el run nuevo con `/ultimo procurement-core`.

---

### Sprint 4 — Agente unificado (auditor + investigador) (5-7 días)

**Objetivo:** el agente inteligente que diferencia a Ashrise.

**Decisión:** un solo agente Python con prompt condicional por `target_type`. Ahorra costos. Si más adelante costo+calidad justifican separar, se bifurca sin migración de schema (ya está preparado).

**Entregables:**

- [ ] **Librería `ashrise.research`** (Python):
  - `web_search(query, recency_days=30)` — wrapper sobre web search API.
  - `find_competitors(topic, region='LATAM')` — busca competidores en dominios relevantes.
  - `check_ai_encroachment(topic)` — evalúa si Claude/GPT absorbieron el valor.
  - `assess_stack(tech_list)` — detecta obsolescencia, alternativas OSS.

- [ ] **Agente unificado** (Python):
  - Entrada: `target_type` (`project` | `candidate`) + `target_id`.
  - Si `project`: lee `project_state + roadmap`, genera `audit_report` con verdict `keep/adjust/pivot-lite/stop`.
  - Si `candidate`: lee `vertical_candidates + kill_criteria_templates`, genera `candidate_research_report` con verdict `advance/iterate/split/kill/park`.
  - Prompts en **Langfuse** (Sprint 5 lo migra, en Sprint 4 pueden estar en git temporalmente).
  - El valor de `runs.agent` refleja el rol en esa ejecución: `auditor` si target_type=project, `investigator` si target_type=candidate.

- [ ] **Cron semanal** que corre agente contra proyectos activos y candidatas con `research_queue.status='pending'`.

- [ ] **Endpoint `POST /agent/run`** para disparar on-demand desde `/auditar` del bot.

**Orden de prioridad de targets en la primera semana:**

1. `procurement-licitaciones` — proyecto activo, apuesta principal.
2. `neytiri` — auditoría explícita pedida (decidir stop vs pivot).
3. `osla-small-qw` — primeras 5 candidatas seedeadas (no las 20 a la vez).
4. `procurement-core` — revisar alineación con Licitaciones.
5. `osla-medium-long` — 2-3 candidatas.

**Criterio de éxito:** el agente corre contra `procurement-licitaciones` y emite reporte con findings reales de competidores (Veritrade, SmartDATA) y veredicto justificado. Contra `neytiri` emite veredicto claro.

---

### Sprint 5 — Langfuse + flujo de promoción + recordatorio activo (3-4 días)

**Objetivo:** observabilidad y ciclo completo candidata → proyecto.

**Entregables:**

- [ ] **Langfuse self-hosted** (Docker Compose en i7, accesible via `$LANGFUSE_BASE_URL`).

- [ ] **Migración de prompts críticos a Langfuse:**
  - `kill-vertical-small-qw@v1` a `kill-vertical-core-sub@v1` (6 templates).
  - `auditor-project@v1`
  - `investigator-candidate@v1`

- [ ] **Tracking LLM completo:** cada llamada del agente queda trazada con `project_id` o `candidate_id` como metadata, y `run_id` como session.

- [ ] **Flujo de promoción de candidatas:**
  - Cuando una candidata alcanza 3 reportes consecutivos con `verdict='advance'` y `confidence > 0.7`, el bot manda mensaje a Telegram: "candidata X lista para promover a proyecto, ¿apruebas?".
  - Approval manual crea registro en `projects` con `promoted_from_candidate_id`.
  - La candidata pasa a `status='promoted'`.

- [ ] **Recordatorio diario activo:**
  - Cron 9am: lee `research_queue` con `scheduled_for <= today`, dispara agente sobre ellos, manda resumen a Telegram con veredictos del día.
  - `verdict='kill'` o `park` → salen de queue. `iterate` → re-encola en 7 días. `advance` → incrementa contador de promoción.

**Criterio de éxito:** a las 9am recibís en Telegram "Hoy revisé 4 candidatas. 2 killed, 1 iterate, 1 advance. Ver detalles: [link]".

---

## Tracks paralelos

### Track O — OSLA Ashrise Integration

**Arranque:** apenas Sprint 2 esté terminado (fin de semana 2).

**Objetivo:** mini-núcleo cliente reutilizable para que las apps OSLA en notebook-osla-docker consuman Ashrise API.

**Entregables:**

- [ ] SDK Python delgado `ashrise_client` (publicable en PyPI o vendored):
  ```python
  from ashrise_client import Ashrise
  a = Ashrise()  # lee ASHRISE_BASE_URL y ASHRISE_TOKEN del entorno
  a.state("osla-learning")
  a.run_create(project="osla-learning", agent="codex", mode="implement")
  ```
- [ ] Auth: mismo `ASHRISE_TOKEN` via env var.
- [ ] README con ejemplos de uso en repo OSLA.

### Track N — Auditoría Neytiri

**Arranque:** apenas Sprint 4 esté funcionando.

**Objetivo:** decidir qué hacer con Neytiri.

**Pasos:**

1. Correr agente unificado contra `neytiri` (target_type=project).
2. Evaluar reporte:
   - `verdict='stop'`: crear `decision` archivando el proyecto (`projects.status='archived'`).
   - `verdict='pivot-lite'`: crear `vertical_candidates` con sub-gaps identificados (categorías probables: `profound-ai` o `medium-long`).
3. **Decisión separada y humana:** ¿ExReply se beneficia de avatar+lip-sync tech aprendida en Neytiri? El agente provee inputs (tech vigente en 2026), la decisión de producto es tuya.

---

## Lo que NO entra en esta iteración

- **ExReply integración con Ashrise.** Decisión explícita: ExReply queda autónomo. Puede retomarse después.
- **WhatsApp como canal.** Solo Telegram. WhatsApp eventual como track experimental outbound-only, no prioritario.
- **Temporal.** Cron es suficiente al inicio. Migrar solo cuando Neytiri Roadmap 1.7 también lo requiera.
- **Promptfoo.** Post-Sprint 5, cuando haya prompts estables que merezcan regresión.
- **Plane / herramientas PM alternativas.** GitHub Projects suficiente para 1 founder.
- **Dividir el agente en auditor + investigador separados.** Schema lo permite (los valores de `runs.agent` existen), código se bifurca solo cuando costo+calidad lo justifiquen.

---

## Métricas de salud del sistema

A monitorear semanalmente (manual al inicio, automatizado después):

- Runs por proyecto por semana.
- % de sesiones con `ashrise-close` válido (target: >90%).
- Candidatas por categoría en cada status.
- Candidatas killed por mes (target: >50% del proposed — el sistema debe matar agresivamente).
- Candidatas promovidas a proyecto por mes (target: 0-2, si es más el filtro está flojo).
- Proyectos sin audit > 14 días (target: 0).
- Costo LLM semanal total (tracked via Langfuse).

---

## Orden recomendado de ejecución

**Semana 1:**
- Día 1-3: Sprint 1 completo.
- Día 4-7: Sprint 2 completo (endpoints operación + investigación).

**Semana 2:**
- Día 8-12: Sprint 3 completo.
- Track O arranca en paralelo (puede quedar incompleto, no crítico).

**Semana 3:**
- Día 13-19: Sprint 4 completo. Track N arranca hacia el final.

**Semana 4:**
- Día 20-23: Sprint 5 completo.

**Total estimado:** ~4 semanas para sistema completo operativo. Sprints 1-3 (loop básico corriendo) en 12 días.

---

## Archivos relacionados

- Schema SQL: `./sql/001_init.sql`
- Contrato de agentes: `./AGENTS.md`
- Claude Code pointer: `./CLAUDE.md`

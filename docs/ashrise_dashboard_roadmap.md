# Ashrise Dashboard — Roadmap integral v2

Fecha: 2026-04-21
Estado objetivo: diseño final, interactivo, operativo
Alcance: tablero visual sobre Ashrise, con módulo de descomposición de ideas → tareas inspirado en Ideathread

---

## 1. Objetivo

Construir una superficie visual sobre Ashrise para:

- ver el estado vivo de todos los proyectos, runs, handoffs, decisiones, audits
- gestionar el pipeline de ideas → tareas → promociones a proyecto o candidata
- disparar acciones operativas seguras desde UI
- entender la evolución temporal del sistema (métricas, trends)
- navegar prompts y traces sin duplicar Langfuse
- revisar notificaciones Telegram una vez persistidas
- usar Ashrise como herramienta operativa diaria, no solo como API

---

## 2. Cambios respecto al roadmap anterior

1. **Nueva tabla `tasks`**: subunidad de trabajo ligada a una `idea`, `project` o `candidate`. Complementa a handoffs (que son cambios de actor) sin pisarlos. Esto habilita los módulos interactivos tipo Ideathread.
2. **Vista de grafo en Project Detail**: fuerza-dirigida, nodo central = proyecto; satélites = runs, handoffs, decisions, candidates relacionadas, ideas promovidas. Reemplaza la lista estática por exploración visual.
3. **Módulo "Idea Workspace"**: nueva pantalla que combina árbol de ideas + vista split-arrows de tareas + board kanban. Inspirado directamente en Ideathread.
4. **No reemplaza GitHub Projects**: las `tasks` de Ashrise viven antes de convertirse en issues. Una vez que una tarea se promueve a issue/PR, GitHub toma el relevo. La UI debe marcar el handoff `github:issue_url`.

---

## 3. Principios de diseño

1. El dashboard no reemplaza GitHub Projects ni Langfuse. Se integra.
2. V1 debe ser útil en lectura antes de ser completo en escritura.
3. Todo cambio editable queda trazado como `decision` o `handoff`.
4. Los datos salen por endpoints pensados para UI, no por queries crudas desde el frontend.
5. Lo animado tiene propósito: feedback de estado, transiciones de carga, relaciones. No decoración vacía.
6. Mobile no es objetivo V1. El target es laptop/desktop.

---

## 4. Arquitectura propuesta

### Frontend
- React + Vite + TypeScript (SPA)
- React Router para navegación interna
- TanStack Query para cache y refetch
- TanStack Table para tablas grandes
- Recharts para gráficos temporales (evolución)
- SVG nativo para grafo force-directed y componentes animados (sin d3)
- Tokens de diseño: mismo set que Tenderlab + Ideathread (ver sección 12)

### Backend
- Reutilizar API actual de Ashrise
- Agregar tabla `tasks` + endpoints asociados
- Agregar endpoints agregados `/dashboard/*` para evitar N+1 desde la UI
- Proxy/deep-link a Langfuse para observabilidad

---

## 5. Navegación principal

1. **Overview** — KPIs, evolución semanal, runs recientes, handoffs abiertos, health
2. **Projects** — tabla + detalle con grafo relacional
3. **Ideas & Tasks** — árbol de ideas, tareas tipo flecha, board kanban
4. **Research** — candidates, queue, reports, readiness para promote
5. **Runs** — timeline con trace de Langfuse
6. **Handoffs** — inbox operativo por actor
7. **Decisions** — timeline de ADRs
8. **Notifications** — Telegram outbound/inbound (requiere `notification_events`)
9. **Prompts & Traces** — catálogo Langfuse + deep-links
10. **System** — health de servicios, jobs, integraciones

---

## 6. Nuevo modelo: `tasks`

### Tabla sugerida

```
tasks
  id                    text primary key
  idea_id               text nullable (fk ideas.id)
  project_id            text nullable (fk projects.id)
  candidate_id          text nullable (fk candidates.id)
  title                 text
  description           text nullable
  status                text check (status in ('backlog','ready','progress','blocked','done'))
  priority              int default 0
  position              int default 0
  tags                  text[] default '{}'
  promoted_to           text nullable  (ej: 'github:issue/42' o 'run:<id>')
  created_at            timestamptz
  updated_at            timestamptz
  closed_at             timestamptz nullable
```

### Semántica

- Una `task` siempre cuelga de algo (idea, proyecto o candidata). Al menos una FK debe estar seteada.
- `status` lineal Backlog → Ready → Progress → Done. `Blocked` es estado auxiliar.
- `position` es para ordenar dentro de una columna kanban o dentro de las tareas de una idea.
- `promoted_to` registra dónde terminó la tarea cuando ya salió del ciclo Ashrise (issue, PR, run, decision).
- Si una tarea se rompe en subtareas, se crean tareas nuevas con la misma `idea_id`. No hay jerarquía de tareas; eso es para GitHub Projects.

### Endpoints nuevos para tasks

```
GET  /tasks?idea_id=&project_id=&candidate_id=&status=
GET  /tasks/{id}
POST /tasks
PATCH /tasks/{id}
DELETE /tasks/{id}
POST /tasks/{id}/promote  -> crea decision + marca promoted_to
GET  /ideas/{idea_id}/tasks
```

### Endpoint de dashboard

```
GET /dashboard/ideas/{idea_id}/workspace
  -> idea + tasks[] + related_tasks_in_other_ideas + suggested_next
```

---

## 7. Roadmap por fases

### Fase 0 — Diseño y contrato UI (CERRADA)
Entregables: este documento + mapa de endpoints + HTML navegable.

### Fase 1 — Dashboard V1 read-only (4-5 días)
Objetivo: ver Ashrise sin editar nada crítico.

- Overview con KPIs y evolución semanal
- Projects tabla + detalle
- Runs timeline
- Ideas inbox (read-only)
- Handoffs inbox
- Decisions timeline
- Research tabla
- System health

### Fase 2 — Ideas & Tasks (3-4 días)
Objetivo: la interacción que diferencia al dashboard.

- Migración SQL: tabla `tasks`, índices, FKs
- Endpoints CRUD de tasks
- Pantalla Ideas con árbol expandible
- Vista tasks tipo split-arrows (una idea + N flechas numeradas)
- Board kanban de todas las tasks con drag&drop
- Creación inline de tareas

### Fase 3 — Grafo y visualización (2-3 días)
Objetivo: Project Detail visual.

- Endpoint `/dashboard/projects/{id}/graph` que devuelve nodos y aristas
- Vista grafo force-directed en Project Detail
- Cross-links entre candidatas y proyectos promovidos
- Mini-grafo en Ideas (ideas padre/hijo/cross-link)

### Fase 4 — Acciones seguras (2-3 días)
Objetivo: operar el sistema desde UI.

- Disparar `/agent/run` para project o candidate
- Resolver handoff
- Triage de idea
- Promote de candidata
- Reencolar item de research queue
- Crear decision
- Crear/mover task

### Fase 5 — Edición full (3-4 días)
- Project state editable (current_focus, next_step, blockers, questions)
- Project metadata editable
- Supersede de decisions
- Edición de candidatas

### Fase 6 — Integraciones (3-4 días)
- Langfuse: prompt catalog + traces recientes + filtros
- Notifications: tabla `notification_events` + UI de historial Telegram
- System: health jobs + integraciones

### Fase 7 — Polish final (2-3 días)
- Activity feed consolidado
- Filtros persistidos
- Vistas guardadas
- Animaciones de carga progresiva
- Shortcuts de teclado

**Total estimado: 19-26 días de desarrollo front + backend delta.**

---

## 8. Animaciones y estado visual (principios)

El dashboard debe sentirse vivo sin ser ruidoso. Patrones que deben respetarse:

- **Carga**: entrada con `fadeIn` escalonado (50ms por ítem, máximo 10).
- **Transiciones de valor**: números, barras de progreso y rings animan con cubic-bezier `.2,.7,.3,1` en 800-1200ms.
- **Pulse**: solo para estados "vivo/running" (runs en ejecución, agentes activos, cron próximo).
- **Glow**: solo para selección y hover, no permanente.
- **Grafo**: spring physics constantes, con damping que estabiliza en ~2s.
- **Kanban**: transición de columna con traslación + fade corto (<200ms). Sin bounce.
- **Task arrow entrando**: `slideInRight` con delay incremental por index.

Todo lo anterior ya está probado en Ideathread y Tenderlab. Reutilizar.

---

## 9. Criterio de éxito final

El dashboard se considera cerrado cuando Martín pueda:

- abrir el tablero por la mañana y saber en <10s qué necesita atención hoy
- capturar una idea, romperla en 3-5 tareas, y arrastrarlas a ready en <2 min
- ver un proyecto como grafo y entender sus relaciones sin abrir 5 tabs
- disparar agent/run y ver el estado vivir
- revisar handoffs y resolverlos sin shell
- seguir una conversación de Telegram (una vez persistida) hasta su outcome

---

## 10. Lo que NO entra

- Login multi-usuario (es solo-founder)
- Mobile responsive completo (solo laptop/desktop)
- Duplicar observabilidad de Langfuse dentro de Ashrise
- Reemplazar GitHub Projects para tracking de código
- Editor WYSIWYG de prompts (ese trabajo pertenece a Langfuse)

---

## 11. Archivos relacionados

- `ashrise_dashboard_endpoints_ui_map.txt` — mapa campo-por-campo
- `ashrise_dashboard.html` — mockup navegable interactivo
- `ROADMAP.md` — roadmap del backend Ashrise
- `AGENTS.md` — contrato de agentes

---

## 12. Tokens de diseño (canónicos)

```
bg:       #0b1220
bg2:      #0f1828
bg3:      #152236
bg4:      #1c2c44
bgSide:   #060b16
border:   #1e2d47
border2:  #2a3e5f
ink:      #e8ecf3
ink2:     #b4c0d4
ink3:     #6b7a93
ink4:     #42526e
accent:   #7dd3fc (cyan)
accent2:  #a5b4fc (violet)
green:    #4ade80
yellow:   #fbbf24
red:      #f87171
pink:     #f472b6
claude:   #d97757
codex:    #10a37f
arrStart: #38bdf8  (gradiente flechas)
arrMid:   #6b8bff
arrEnd:   #a78bfa
```

Fuentes:

```
display: Space Grotesk (600 para headings, letter-spacing -0.3 a -0.5)
body:    Inter
mono:    IBM Plex Mono (pills, labels, IDs, metadata)
```

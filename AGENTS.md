# AGENTS.md

> Contrato de trabajo para cualquier agente IA (Claude Code, Codex, Aider, Cursor, etc.)
> operando en este repositorio bajo orquestación de **Ashrise Core**.
>
> Agent-agnostic. Cada agente lee este archivo al iniciar sesión y respeta
> las reglas de cierre (bloque `ashrise-close`).

---

## Proyecto

- **Ashrise ID:** `[PROYECTO-ID]`  <!-- ej: procurement-core, neytiri, osla-small-qw -->
- **Nombre:** `[Nombre humano]`
- **Kind:** `[core | project | vertical | group]`
- **Parent (si aplica):** `[parent_id]`
- **Stack principal:** `[.NET / FastAPI / Next.js / …]`
- **Worktree activo:** `[path absoluto]`
- **Host machine:** `[i7-main | notebook-procurement | notebook-osla-docker]`

---

## Entorno y endpoints

Ashrise Core corre en la i7 principal. Repos en otras máquinas acceden por Headscale/Tailscale.

El agente **nunca asume un hostname fijo para Ashrise o Langfuse** — siempre usa variables de entorno:

| Variable | Default | Descripción |
|---|---|---|
| `ASHRISE_BASE_URL` | `http://ashrise.ts.net:8080` | Hostname Headscale de la i7 + puerto Ashrise |
| `ASHRISE_TOKEN` | (obligatorio) | Bearer token de autenticación |
| `LANGFUSE_BASE_URL` | `http://langfuse.ts.net:3000` | Hostname Headscale + puerto Langfuse |
| `LANGFUSE_PUBLIC_KEY` | (obligatorio si se usa) | |
| `LANGFUSE_SECRET_KEY` | (obligatorio si se usa) | |

Si el repo corre **en la misma máquina que Ashrise** (i7), el hostname Headscale resuelve a la propia máquina, igual funciona. Esto evita lógica condicional por host.

Todos los ejemplos `curl` de este archivo asumen `$ASHRISE_BASE_URL` seteado.

---

## Contexto operativo

Este repo es parte de una flota multi-proyecto orquestada por Ashrise Core. Ashrise guarda el **estado vivo** compartido entre todos los agentes IA.

Rol y límites de Ashrise:

- **Sí guarda:** estado actual de proyectos, runs de agentes, handoffs, decisiones, reportes de auditoría/investigación, ideas en intake.
- **No guarda:** código (vive en el repo), prompts runtime (viven en Langfuse), tickets (viven en GitHub Projects), traces de LLM (viven en Langfuse).

Múltiples agentes pueden trabajar en paralelo en el mismo proyecto (worktrees separados). El estado compartido en Ashrise es cómo se coordinan sin pisarse.

---

## Contratos de trabajo

### 1. Al inicio de cada sesión

Antes de tocar código, el agente debe:

1. **Leer el estado actual** del proyecto:
   ```bash
   curl -sH "Authorization: Bearer $ASHRISE_TOKEN" "$ASHRISE_BASE_URL/state/[PROYECTO-ID]"
   ```
2. **Leer el último reporte** si existe:
   - Proyectos activos: `GET $ASHRISE_BASE_URL/audit/[PROYECTO-ID]`
   - Candidatas: `GET $ASHRISE_BASE_URL/candidates/[CANDIDATE-ID]/research`
3. **Revisar handoffs abiertos:**
   ```bash
   curl -sH "Authorization: Bearer $ASHRISE_TOKEN" "$ASHRISE_BASE_URL/handoffs/[PROYECTO-ID]?status=open"
   ```
4. **Declarar en la primera respuesta:**
   - `focus`: qué vas a hacer en esta sesión (una frase).
   - `mode`: `implement` | `plan` | `refactor` | `debug` | `audit` | `investigate`.
   - `acknowledged`: lista de handoffs abiertos que tomás en cuenta.

Si existe hook/wrapper automatizado (ver "Integración por agente"), los tres curls se inyectan en el contexto automáticamente.

### 2. Durante la sesión

- **Un solo foco por sesión.** Algo fuera de foco → handoff con `reason='scope-change'`, no desviarse.
- **Decisiones arquitecturales** → `POST /decisions`. No enterrarlas en commits.
- **Bloqueos reales** → `blockers` en `project_state` vía bloque de cierre.
- **Prompts runtime** → Langfuse, no commits al repo. Prompts estables repo-locales (build, test, lint) sí van en git.
- **Decisiones que impactan roadmap** → además del `decision`, emitir handoff a `human:martin` con `reason='needs-human-review'` antes de commit.

### 3. Al cerrar la sesión

**Obligatorio.** El agente imprime como última parte de su respuesta final el bloque `ashrise-close` (formato abajo). Hook/wrapper externo lo parsea y lo envía a Ashrise.

Si el bloque falta o es inválido, el run queda con `summary=null` y requiere completarlo manual después.

---

## Formato de cierre

Último bloque de la última respuesta de la sesión:

````markdown
```ashrise-close
run:
  status: completed        # completed | failed | cancelled
  summary: |
    Resumen humano de 2-5 oraciones. Qué se hizo, qué quedó,
    por qué se tomó la decisión clave (si la hubo).
  files_touched:
    - src/foo.py
    - docs/bar.md
  diff_stats:
    added: 120
    removed: 34
    files: 5
  next_step_proposed: |
    Una frase: qué haría el próximo ejecutor.

state_update:
  current_focus: "string libre"
  current_milestone: "Sprint 6"           # o null si no aplica
  next_step: "string"
  blockers_add: []                        # nuevos blockers descubiertos
  blockers_clear: []                      # ids de blockers resueltos
  open_questions_add: []
  open_questions_clear: []

handoffs:                                 # opcional
  - to_actor: "codex"                     # "codex" | "claude-code" | "human:martin" | "auditor"
    reason: "pass-to-implementer"         # ver enum de handoffs.reason en schema
    message: "qué se deja y por qué"
    context_refs: ["files:src/foo.py:120-180"]

decisions:                                # opcional
  - title: "..."
    context: "..."
    decision: "..."
    consequences: "..."
    alternatives:
      - title: "opción B"
        why_rejected: "..."
```
````

**Reglas del bloque:**

- Siempre presente, incluso si no cambió archivos (`files_touched: []`).
- `run` y `state_update` son requeridos.
- `handoffs` y `decisions` son opcionales.
- YAML válido. No usar notación tipo `"A" | "B"` (no es YAML). Usar comentarios para indicar opciones.
- **Solo la sesión padre (top-level) emite este bloque.** Los subagentes (si se usan) producen salidas internas, no tocan `project_state` directamente.

---

## Integración por agente

El contrato del bloque `ashrise-close` es agnóstico. Lo que cambia entre agentes es **cómo se parsea ese bloque al final**.

### Claude Code

Hooks en `.claude/settings.json`:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "*",
        "hooks": [
          { "type": "command", "command": "ashrise-hook session-start --project [PROYECTO-ID]" }
        ]
      }
    ],
    "Stop": [
      {
        "matcher": "*",
        "hooks": [
          { "type": "command", "command": "ashrise-hook session-stop --project [PROYECTO-ID]" }
        ]
      }
    ]
  }
}
```

- `SessionStart` abre run con `status=running`, inyecta state + audit + handoffs en contexto.
- `Stop` parsea bloque `ashrise-close` del último turno y hace PUT/POST a Ashrise.

El script `ashrise-hook` lee `$ASHRISE_BASE_URL` y `$ASHRISE_TOKEN` del entorno.

### Codex

Codex no tiene hooks nativos equivalentes. Dos opciones:

1. **Wrapper CLI** (`run_codex_task.sh`): envuelve la ejecución, abre run al inicio, lee output al final, parsea bloque, llama a Ashrise. Ver `scripts/run_codex_task.sh`.
2. **Instrucción explícita + cierre manual**: el agente emite el bloque en el chat final, vos corrés `ashrise-hook session-stop` manual.

Recomendado: wrapper. Una vez configurado, es invisible.

### Otros agentes (Aider, Cursor, genérico)

Mismo patrón: wrapper que respeta contrato de inicio/cierre. El bloque `ashrise-close` es el único contrato que importa.

---

## Subagentes (opcional, solo Claude Code)

Por proyecto, definir subagentes en `.claude/agents/` con roles acotados:

- **`planner.md`** — produce plan ejecutable sin tocar código.
- **`implementer.md`** — ejecuta el plan.
- **`reviewer.md`** — revisa diffs antes de commit.

**Regla importante:** los subagentes **NO emiten** `ashrise-close` y **NO tocan** `project_state` directamente. Solo producen salidas internas que la sesión padre consume. El cierre canónico lo hace la sesión padre una sola vez.

Para otros agentes sin subagents nativos, el mismo rol se emula con prompts separados dentro de la misma sesión.

---

## Convenciones de ejecución

### Worktrees

Cada feature importante en worktree separado:

```bash
cd [repo-root]
git worktree add ../[repo-name].wt/[feature-slug] -b feature/[feature-slug]
```

El agente opera en el worktree declarado arriba. No crea worktrees por cuenta propia.

Varios agentes pueden operar en worktrees distintos del mismo repo simultáneamente. Ashrise los diferencia por `runs.worktree_path`.

### Prompts

- **Estables del repo** (build, test, lint, setup) → `.claude/prompts/` o `prompts/` en git.
- **Volátiles y cross-proyecto** (auditor, investigador, kill-templates) → **Langfuse**. Referencia por `prompt_ref: langfuse:nombre@version`.
- **Inline de sesión** (lo que vos escribís en el chat) → no se persisten.

### Decisiones

Todo cambio arquitectural, de dependencia o de alcance que afecte al roadmap → `POST /decisions`. Si el cambio es grande, también handoff a `human:martin` con `reason='needs-human-review'` antes de commit.

---

## Qué NO hace el agente en este repo

- No crea issues en GitHub directamente. Ideas → bot de Telegram (o `POST /ideas`), triage humano las promueve.
- No modifica `roadmap.md` sin una `decision` que lo respalde.
- No ejecuta migraciones de BD en prod. Solo en `dev` local, loggeando el comando en `decisions`.
- No toca `.env` ni secrets. Falta variable → handoff con `reason='blocked'`.
- No promueve candidatas a proyectos automáticamente. Requiere approval humano explícito.

---

## Enlaces

- **Ashrise API docs:** `$ASHRISE_BASE_URL/docs` (FastAPI auto-docs)
- **Langfuse:** `$LANGFUSE_BASE_URL`
- **GitHub Project:** `[URL]`
- **Roadmap canónico del proyecto:** `[path-al-roadmap.md]`
- **Ashrise repo (meta):** `[URL al repo donde viven schema, hooks, docs]`

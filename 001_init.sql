-- ==============================================================================
-- Ashrise Core — Schema
-- Version: 0.2.1
-- Target: PostgreSQL 15+
-- Changelog vs 0.2.0:
--   - Restaurada tabla `ideas` (minimal, como buffer de captura desde Telegram/WhatsApp)
--   - FIX seed: host_machine ahora va en la columna, no en metadata
-- ==============================================================================
--
-- Principios de diseño:
--
-- 1. Ashrise NO es PM. El tracker vive en GitHub Projects.
--
-- 2. Dos dominios separados pero relacionados:
--    - "Operación": projects + project_state + runs + handoffs + decisions + audit_reports + ideas
--      → qué se está construyendo y cómo va.
--    - "Investigación": vertical_candidates + candidate_research_reports + research_queue
--      → qué podría valer la pena construir en el futuro.
--    Las candidatas validadas "nacen" como projects. Trazabilidad preservada.
--
-- 3. Prompts NO viven acá. Solo `prompt_ref`. Los criterios de matar sí tienen
--    una tabla (kill_criteria_templates) porque son estructurados y críticos.
--
-- 4. Append-only donde importa: runs, handoffs, decisions, audit_reports,
--    candidate_research_reports. project_state, vertical_candidates e ideas
--    sí se actualizan en sitio.
--
-- 5. `ideas` es buffer mínimo de captura. No es PM. Una vez triada,
--    se promueve a GitHub Issue (o a candidate, o a handoff/decision según aplique)
--    y queda con status='promoted' como histórico.
--
-- ==============================================================================

BEGIN;

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ==============================================================================
-- DOMINIO 1: OPERACIÓN (proyectos activos)
-- ==============================================================================

CREATE TABLE projects (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    kind            TEXT NOT NULL DEFAULT 'project'
                    CHECK (kind IN ('core','project','vertical','group')),
    parent_id       TEXT REFERENCES projects(id) ON DELETE RESTRICT,
    repo_url        TEXT,
    repo_path       TEXT,
    worktree_path   TEXT,
    gh_project_id   TEXT,
    host_machine    TEXT,
                    -- "i7-main", "notebook-procurement", "notebook-osla-docker"
    status          TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active','paused','archived','killed')),
    priority        SMALLINT CHECK (priority BETWEEN 1 AND 6),
    importance      SMALLINT CHECK (importance BETWEEN 1 AND 5),
    size_scope      SMALLINT CHECK (size_scope BETWEEN 1 AND 4),
    progress_pct    SMALLINT CHECK (progress_pct BETWEEN 0 AND 100),
    promoted_from_candidate_id UUID,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX projects_parent_idx ON projects(parent_id) WHERE parent_id IS NOT NULL;
CREATE INDEX projects_status_idx ON projects(status, priority);
CREATE INDEX projects_host_idx ON projects(host_machine) WHERE host_machine IS NOT NULL;

CREATE TABLE project_state (
    project_id          TEXT PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
    current_focus       TEXT,
    current_milestone   TEXT,
    roadmap_version     TEXT,
    roadmap_ref         TEXT,
    project_state_code  SMALLINT CHECK (project_state_code BETWEEN 1 AND 6),
    next_step           TEXT,
    blockers            JSONB NOT NULL DEFAULT '[]'::jsonb,
    open_questions      JSONB NOT NULL DEFAULT '[]'::jsonb,
    last_run_id         UUID,
    last_audit_id       UUID,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    extra               JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE runs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id      TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    agent           TEXT NOT NULL
                    CHECK (agent IN (
                        'codex','claude-code','claude-chat',
                        'manual','auditor','investigator','other'
                    )),
    agent_version   TEXT,
    mode            TEXT,
    prompt_ref      TEXT,
    worktree_path   TEXT,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at        TIMESTAMPTZ,
    status          TEXT NOT NULL DEFAULT 'running'
                    CHECK (status IN ('running','completed','failed','cancelled')),
    summary         TEXT,
    files_touched   JSONB NOT NULL DEFAULT '[]'::jsonb,
    diff_stats      JSONB NOT NULL DEFAULT '{}'::jsonb,
    next_step_proposed TEXT,
    cost_usd        NUMERIC(10,4),
    langfuse_trace_id TEXT,
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX runs_project_started_idx ON runs(project_id, started_at DESC);
CREATE INDEX runs_status_idx ON runs(status) WHERE status = 'running';

CREATE TABLE handoffs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id      TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    from_run_id     UUID REFERENCES runs(id) ON DELETE SET NULL,
    from_actor      TEXT NOT NULL,
    to_actor        TEXT NOT NULL,
    reason          TEXT NOT NULL
                    CHECK (reason IN (
                        'needs-human-review','blocked','context-exhausted',
                        'scope-change','needs-clarification',
                        'pass-to-implementer','pass-to-reviewer','other'
                    )),
    message         TEXT NOT NULL,
    context_refs    JSONB NOT NULL DEFAULT '[]'::jsonb,
    status          TEXT NOT NULL DEFAULT 'open'
                    CHECK (status IN ('open','picked-up','resolved','abandoned')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at     TIMESTAMPTZ,
    resolved_by_run_id UUID REFERENCES runs(id) ON DELETE SET NULL
);

CREATE INDEX handoffs_project_open_idx ON handoffs(project_id, created_at DESC)
    WHERE status = 'open';

CREATE TABLE decisions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id      TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title           TEXT NOT NULL,
    context         TEXT NOT NULL,
    decision        TEXT NOT NULL,
    consequences    TEXT,
    alternatives    JSONB NOT NULL DEFAULT '[]'::jsonb,
    status          TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('proposed','active','superseded','rejected')),
    supersedes      UUID REFERENCES decisions(id) ON DELETE SET NULL,
    created_by      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX decisions_project_idx ON decisions(project_id, created_at DESC);

CREATE TABLE audit_reports (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id      TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    verdict         TEXT NOT NULL
                    CHECK (verdict IN ('keep','adjust','pivot-lite','stop')),
    confidence      NUMERIC(3,2) CHECK (confidence BETWEEN 0 AND 1),
    summary         TEXT NOT NULL,
    findings        JSONB NOT NULL DEFAULT '[]'::jsonb,
    proposed_changes JSONB NOT NULL DEFAULT '[]'::jsonb,
    evidence_refs   JSONB NOT NULL DEFAULT '[]'::jsonb,
    roadmap_ref     TEXT,
    state_snapshot  JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX audit_project_created_idx ON audit_reports(project_id, created_at DESC);

-- ------------------------------------------------------------------------------
-- ideas
-- ------------------------------------------------------------------------------
-- Buffer mínimo de captura desde superficies externas (Telegram, WhatsApp, CLI).
-- NO es PM — los tickets viven en GitHub Projects. Esta tabla es solo un buffer
-- para que la captura sea instantánea (no depende de GH API up) y para que
-- ideas sin proyecto asignado tengan dónde vivir hasta el triage.
--
-- Ciclo de vida típico:
--   new → triaged → promoted | discarded
--
-- Cuando se promueve, queda el link en `promoted_to` (ej: github:owner/repo#123
-- si fue a issue, o ashrise:candidate:<uuid> si fue a vertical_candidates, etc.)
-- ------------------------------------------------------------------------------

CREATE TABLE ideas (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id      TEXT REFERENCES projects(id) ON DELETE SET NULL,
                    -- NULL si todavía no se sabe a qué proyecto pertenece
    raw_text        TEXT NOT NULL,
    source          TEXT NOT NULL
                    CHECK (source IN ('telegram','whatsapp','cli','web','other')),
    source_ref      TEXT,                              -- chat_id:message_id
    tags            TEXT[] NOT NULL DEFAULT '{}',
    status          TEXT NOT NULL DEFAULT 'new'
                    CHECK (status IN ('new','triaged','promoted','discarded')),
    promoted_to     TEXT,
                    -- "github:owner/repo#123"
                    -- "ashrise:candidate:<uuid>"
                    -- "ashrise:decision:<uuid>"
                    -- "ashrise:handoff:<uuid>"
    triage_notes    TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    triaged_at      TIMESTAMPTZ
);

CREATE INDEX ideas_status_idx ON ideas(status, created_at DESC);
CREATE INDEX ideas_project_idx ON ideas(project_id) WHERE project_id IS NOT NULL;

-- ==============================================================================
-- DOMINIO 2: INVESTIGACIÓN (verticales candidatas pre-proyecto)
-- ==============================================================================

CREATE TABLE vertical_candidates (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    slug            TEXT UNIQUE NOT NULL,
    name            TEXT NOT NULL,
    category        TEXT NOT NULL
                    CHECK (category IN (
                        'small-quickwin','medium-long','unicorn',
                        'learning','profound-ai','core-sub-vertical'
                    )),
    parent_group    TEXT REFERENCES projects(id) ON DELETE SET NULL,
    hypothesis      TEXT NOT NULL,
    problem_desc    TEXT,
    kill_criteria   JSONB NOT NULL DEFAULT '[]'::jsonb,
    status          TEXT NOT NULL DEFAULT 'proposed'
                    CHECK (status IN (
                        'proposed','investigating','promising',
                        'promoted','killed','paused'
                    )),
    priority        SMALLINT CHECK (priority BETWEEN 1 AND 6),
    importance      SMALLINT CHECK (importance BETWEEN 1 AND 5),
    estimated_size  SMALLINT CHECK (estimated_size BETWEEN 1 AND 4),
    kill_verdict    JSONB,
    promoted_to_project_id TEXT REFERENCES projects(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_research_id UUID,
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX candidates_status_idx ON vertical_candidates(status, category);
CREATE INDEX candidates_parent_idx ON vertical_candidates(parent_group)
    WHERE parent_group IS NOT NULL;
CREATE INDEX candidates_active_priority_idx
    ON vertical_candidates(priority, importance)
    WHERE status IN ('proposed','investigating','promising');

CREATE TABLE candidate_research_reports (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    candidate_id    UUID NOT NULL REFERENCES vertical_candidates(id) ON DELETE CASCADE,
    verdict         TEXT NOT NULL
                    CHECK (verdict IN ('advance','iterate','split','kill','park')),
    confidence      NUMERIC(3,2) CHECK (confidence BETWEEN 0 AND 1),
    summary         TEXT NOT NULL,
    competitors_found JSONB NOT NULL DEFAULT '[]'::jsonb,
    market_signals  JSONB NOT NULL DEFAULT '[]'::jsonb,
    stack_findings  JSONB NOT NULL DEFAULT '[]'::jsonb,
    kill_criteria_hits JSONB NOT NULL DEFAULT '[]'::jsonb,
    ai_encroachment TEXT,
    sub_gap_proposals JSONB NOT NULL DEFAULT '[]'::jsonb,
    proposed_next_steps JSONB NOT NULL DEFAULT '[]'::jsonb,
    evidence_refs   JSONB NOT NULL DEFAULT '[]'::jsonb,
    kill_template_id UUID,
    prompt_ref      TEXT,
    candidate_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX research_candidate_created_idx
    ON candidate_research_reports(candidate_id, created_at DESC);

CREATE TABLE kill_criteria_templates (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    category        TEXT NOT NULL
                    CHECK (category IN (
                        'small-quickwin','medium-long','unicorn',
                        'learning','profound-ai','core-sub-vertical'
                    )),
    version         INTEGER NOT NULL,
    prompt_ref      TEXT NOT NULL,
    criteria        JSONB NOT NULL,
    notes           TEXT,
    is_active       BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(category, version)
);

CREATE INDEX kill_templates_active_idx ON kill_criteria_templates(category)
    WHERE is_active = true;

CREATE TABLE research_queue (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    candidate_id    UUID REFERENCES vertical_candidates(id) ON DELETE CASCADE,
    project_id      TEXT REFERENCES projects(id) ON DELETE CASCADE,
    queue_type      TEXT NOT NULL
                    CHECK (queue_type IN (
                        'initial-research','recurring-watch','market-recheck',
                        'project-audit','follow-up'
                    )),
    priority        SMALLINT NOT NULL DEFAULT 3 CHECK (priority BETWEEN 1 AND 5),
    scheduled_for   DATE NOT NULL DEFAULT CURRENT_DATE,
    recurrence      TEXT CHECK (recurrence IN ('once','daily','weekly','monthly')),
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','in-progress','done','skipped')),
    last_run_at     TIMESTAMPTZ,
    last_report_id  UUID,
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (
        (candidate_id IS NOT NULL AND project_id IS NULL)
        OR (candidate_id IS NULL AND project_id IS NOT NULL)
    )
);

CREATE INDEX research_queue_due_idx ON research_queue(scheduled_for, priority)
    WHERE status = 'pending';

-- ==============================================================================
-- FKs diferidas
-- ==============================================================================

ALTER TABLE project_state
    ADD CONSTRAINT project_state_last_run_fk
    FOREIGN KEY (last_run_id) REFERENCES runs(id) ON DELETE SET NULL;

ALTER TABLE project_state
    ADD CONSTRAINT project_state_last_audit_fk
    FOREIGN KEY (last_audit_id) REFERENCES audit_reports(id) ON DELETE SET NULL;

ALTER TABLE projects
    ADD CONSTRAINT projects_promoted_from_candidate_fk
    FOREIGN KEY (promoted_from_candidate_id)
    REFERENCES vertical_candidates(id) ON DELETE SET NULL;

ALTER TABLE vertical_candidates
    ADD CONSTRAINT candidates_last_research_fk
    FOREIGN KEY (last_research_id)
    REFERENCES candidate_research_reports(id) ON DELETE SET NULL;

ALTER TABLE candidate_research_reports
    ADD CONSTRAINT research_kill_template_fk
    FOREIGN KEY (kill_template_id)
    REFERENCES kill_criteria_templates(id) ON DELETE SET NULL;

-- ==============================================================================
-- Triggers
-- ==============================================================================

CREATE OR REPLACE FUNCTION touch_updated_at() RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER projects_touch BEFORE UPDATE ON projects
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

CREATE TRIGGER project_state_touch BEFORE UPDATE ON project_state
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

CREATE TRIGGER candidates_touch BEFORE UPDATE ON vertical_candidates
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- ==============================================================================
-- Seed: proyectos reales
-- FIX v0.2.1: host_machine va en la columna, no en metadata
-- ==============================================================================

INSERT INTO projects (id, name, kind, parent_id, host_machine, status, priority, importance, size_scope, progress_pct, metadata) VALUES
    ('ashrise',         'Ashrise',                  'project', NULL,             'i7-main',               'active', 1, 1, 1, 5,
     '{"is_meta_project": true}'::jsonb),

    ('procurement-core','ProcurementUY Core',       'core',    NULL,             'notebook-procurement',  'active', 1, 1, 1, 70,
     '{}'::jsonb),
    ('procurement-licitaciones', 'Licitaciones',    'vertical','procurement-core','notebook-procurement', 'active', 1, 1, 2, 80, '{}'::jsonb),
    ('procurement-aduana',       'Importaciones Aduana','vertical','procurement-core','notebook-procurement','paused', 1, 1, 2, 5,
     '{"waiting_reason": "esperar maduración del núcleo"}'::jsonb),

    ('neytiri',         'Neytiri',                  'project', NULL,             NULL,                    'paused', 2, 2, 1, NULL,
     '{"pause_reason": "pendiente auditoría y análisis de pivot", "host_machine_tbd": true}'::jsonb),

    ('exreply',         'ExReply',                  'project', NULL,             NULL,                    'paused', 4, 3, 3, 70,
     '{"not_integrated_with_ashrise": true, "web_progress": 70, "mobile_progress": 0}'::jsonb),

    ('osla',            'OSLA (grupo de verticales)','group',  NULL,             'notebook-osla-docker',  'active', 1, 1, 1, 0,
     '{}'::jsonb),
    ('osla-ashrise-integration', 'OSLA Ashrise Integration','vertical','osla','notebook-osla-docker',    'active', 1, 1, 3, 0, '{}'::jsonb),
    ('osla-learning',   'OSLA Learning Verticals',  'vertical','osla',           'notebook-osla-docker',  'active', 2, 1, 2, 0, '{}'::jsonb),
    ('osla-small-qw',   'OSLA Small Quick Wins',    'vertical','osla',           'notebook-osla-docker',  'active', 1, 1, 2, 0,
     '{"target_count": 20, "goal": "fuente de ingreso rápida"}'::jsonb),
    ('osla-medium-long','OSLA Medium & Long',       'vertical','osla',           'notebook-osla-docker',  'active', 1, 1, 2, 0,
     '{"target_count": 10}'::jsonb),
    ('osla-unicorns',   'OSLA Possible Unicorns',   'vertical','osla',           'notebook-osla-docker',  'active', 2, 1, 1, 0,
     '{"target_count": 3}'::jsonb),
    ('osla-profound-ai','OSLA Profound AI Learning','vertical','osla',           'notebook-osla-docker',  'active', 2, 1, 2, 0, '{}'::jsonb),
    ('osla-continue-search', 'OSLA Continue Search','vertical','osla',           'notebook-osla-docker',  'active', 1, 1, 2, 0,
     '{"description": "investigación diaria continua, divide-y-venceras"}'::jsonb);

INSERT INTO project_state (project_id, project_state_code, current_focus) VALUES
    ('ashrise',                 1, 'Sprint 1: host operativo + schema core'),
    ('procurement-core',        1, 'Nucleo en construcción; soporta vertical Licitaciones'),
    ('procurement-licitaciones',1, 'MVP demostrable, pulido de diferenciación'),
    ('procurement-aduana',      3, 'Esperando madurez del nucleo antes de arrancar'),
    ('neytiri',                 3, 'Pendiente auditoría de viabilidad y exploración de pivots'),
    ('exreply',                 4, 'Pausada; MVP web 70%, evaluar mobile después'),
    ('osla',                    5, 'Grupo en investigación'),
    ('osla-ashrise-integration',5, 'Definir mini-nucleo cliente para consumir Ashrise API'),
    ('osla-learning',           5, 'Investigando qué aprender con retorno didáctico'),
    ('osla-small-qw',           5, 'Investigar 20 candidatas con retorno rápido'),
    ('osla-medium-long',        5, 'Investigar 10 candidatas con perspectiva a mediano/largo'),
    ('osla-unicorns',           5, 'Investigar 3 big bets con el prompt de matar muy pulido'),
    ('osla-profound-ai',        5, 'Aprendizaje profundo de tech IA actual'),
    ('osla-continue-search',    5, 'Proceso recurrente, no proyecto terminable');

INSERT INTO kill_criteria_templates (category, version, prompt_ref, criteria, notes, is_active) VALUES
    ('small-quickwin', 1, 'langfuse:kill-vertical-small-qw@v1',
     '[
        {"id":"no-workana-demand","type":"hard","description":"No se encuentran >10 postings recientes en Workana/Fiverr/Upwork en los últimos 90 días"},
        {"id":"saturated-market","type":"hard","description":"Top 3 freelancers de la plataforma cubren el servicio a precios imposibles de competir"},
        {"id":"requires-long-trust","type":"hard","description":"El tipo de cliente no paga sin track record largo"},
        {"id":"weak-delivery-time","type":"soft","description":"Estimación de delivery > 15 días para un primer cliente"}
      ]'::jsonb,
     'Enfoque: velocidad al primer USD. No MVP, no validación larga. Sí ingreso seguro.',
     true),

    ('medium-long', 1, 'langfuse:kill-vertical-medium-long@v1',
     '[
        {"id":"ai-commoditized","type":"hard","description":"ChatGPT/Claude ya resuelven el problema en modo conversacional directo"},
        {"id":"no-defensible-moat","type":"hard","description":"No hay semántica/datos/regulación propia que proteja"},
        {"id":"saturated-incumbents","type":"hard","description":"Existen >3 competidores consolidados cubriendo >80% del scope"},
        {"id":"no-latam-specifics","type":"soft","description":"No aprovecha contexto LATAM/Uruguay (DGI, BPS, MTSS, TOCAF, Ley Karin, aduana)"}
      ]'::jsonb,
     'Enfoque: gap defensible en mediano/largo plazo.',
     true),

    ('unicorn', 1, 'langfuse:kill-vertical-unicorn@v1',
     '[
        {"id":"llm-absorption","type":"hard","description":"Claude/GPT ya absorben o están absorbiendo >50% del valor propuesto"},
        {"id":"not-pattern-based","type":"hard","description":"Es gap aislado, no patrón emergente replicable"},
        {"id":"sub-1B-ceiling","type":"hard","description":"Techo de mercado claramente por debajo de USD 1B"},
        {"id":"single-founder-unfeasible","type":"hard","description":"No puede validarse o avanzar meaningfully con 1 persona en 6 meses"}
      ]'::jsonb,
     'Criterio muy duro. Buscar patrones en startups IA 2026, no gaps aislados.',
     true),

    ('learning', 1, 'langfuse:kill-vertical-learning@v1',
     '[
        {"id":"no-skill-transfer","type":"soft","description":"Lo aprendido no aplica a otros proyectos del portfolio"},
        {"id":"obsolete-tech","type":"hard","description":"La tecnología está siendo reemplazada o deprecada en 2026"},
        {"id":"trivial-already-known","type":"soft","description":"Martin ya domina el 70%+ del skill objetivo"}
      ]'::jsonb,
     'Aprendizaje útil cross-proyecto. No monetización directa.',
     true),

    ('profound-ai', 1, 'langfuse:kill-vertical-profound-ai@v1',
     '[
        {"id":"already-in-stack","type":"hard","description":"La herramienta ya está evaluada y adoptada en otro proyecto"},
        {"id":"declining-trajectory","type":"hard","description":"Métricas de comunidad/releases muestran declive en 2026"},
        {"id":"no-applicable-project","type":"soft","description":"No se ve aplicación en ningún proyecto/candidata actual"}
      ]'::jsonb,
     'Profundización en IA avanzada. Usable cross-proyecto.',
     true),

    ('core-sub-vertical', 1, 'langfuse:kill-vertical-core-sub@v1',
     '[
        {"id":"core-not-ready","type":"hard","description":"El núcleo no tiene las capabilities necesarias ni las tendrá en 3 meses"},
        {"id":"no-reuse","type":"hard","description":"La sub-vertical no reutiliza componentes del núcleo (rompe la tesis)"},
        {"id":"competitor-saturated","type":"soft","description":"La vertical está saturada en LATAM con incumbents fuertes"}
      ]'::jsonb,
     'Sub-verticales de un núcleo (ProcurementUY → Aduana, Agro, etc).',
     true);

COMMIT;

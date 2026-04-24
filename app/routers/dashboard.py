from __future__ import annotations

from datetime import date, datetime, timedelta
import os
from urllib.parse import urlparse, urlunparse
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
import httpx
import psycopg

from app.auth import require_bearer_token
from app.db import fetch_all, fetch_one, get_db, update_row
from app.schemas import AgentRunRequest, DashboardRequeueRequest, DashboardResolveHandoff
from ashrise.unified_agent import run_unified_agent
from ashrise.langfuse_support import resolve_langfuse_base_url


router = APIRouter(prefix="/dashboard", tags=["dashboard"], dependencies=[Depends(require_bearer_token)])

MONTEVIDEO_TZ = ZoneInfo("America/Montevideo")
ZERO_HEALTH_NOTE = "probe not implemented"
TASK_STATUSES = ("backlog", "ready", "progress", "blocked", "done")
GRAPH_NODE_COLORS = {
    "project": "accent",
    "run": "accent-2",
    "handoff": "amber",
    "decision": "pink",
    "candidate": "green",
    "idea": "accent",
    "task": "accent-2",
    "audit": "red",
}
LANGFUSE_METADATA_KEYS = ("prompt_source", "prompt_fallback", "langfuse_status", "langfuse_error")


def montevideo_today() -> date:
    return datetime.now(MONTEVIDEO_TZ).date()


def last_seven_days() -> list[date]:
    today = montevideo_today()
    return [today - timedelta(days=offset) for offset in range(6, -1, -1)]


def group_counts_by_day(
    conn: psycopg.Connection,
    table: str,
    timestamp_column: str,
    *,
    start_date: date,
    end_date: date,
    extra_clause: str = "",
) -> dict[date, int]:
    query = f"""
        SELECT (({timestamp_column} AT TIME ZONE 'America/Montevideo')::date) AS bucket_date, COUNT(*) AS total
        FROM {table}
        WHERE {timestamp_column} IS NOT NULL
          AND (({timestamp_column} AT TIME ZONE 'America/Montevideo')::date) BETWEEN %s AND %s
          {extra_clause}
        GROUP BY bucket_date
    """
    rows = fetch_all(conn, query, (start_date, end_date))
    return {row["bucket_date"]: row["total"] for row in rows}


def jsonb_array_length_or_none(value: object) -> int | None:
    if isinstance(value, list):
        return len(value)
    return None


def empty_project_state(project_id: str) -> dict[str, object]:
    return {
        "project_id": project_id,
        "current_focus": None,
        "current_milestone": None,
        "roadmap_ref": None,
        "project_state_code": None,
        "next_step": None,
        "blockers": [],
        "open_questions": [],
        "updated_at": None,
    }


def candidate_ready_clause(alias: str = "c") -> str:
    return (
        f"({alias}.status = 'ready_to_promote' "
        f"OR COALESCE(({alias}.metadata->'promotion'->>'ready')::boolean, false)) "
        f"AND {alias}.status <> 'promoted'"
    )


def probe_langfuse() -> dict[str, str | None]:
    base_url = resolve_langfuse_base_url()
    if not base_url:
        return {"status": "unknown", "note": "not configured"}

    try:
        response = httpx.get(f"{base_url.rstrip('/')}/api/public/health", timeout=1.5)
    except Exception:
        return {"status": "down", "note": "unreachable"}

    if response.is_success:
        return {"status": "ok", "note": None}
    if 500 <= response.status_code:
        return {"status": "down", "note": f"http {response.status_code}"}
    return {"status": "degraded", "note": f"http {response.status_code}"}


def get_health_summary(conn: psycopg.Connection) -> dict[str, dict[str, str | None]]:
    db_health = {"status": "ok", "note": None}
    try:
        fetch_one(conn, "SELECT 1 AS ok")
    except Exception:
        db_health = {"status": "down", "note": "query failed"}

    return {
        "api": {"status": "ok", "note": None},
        "db": db_health,
        "langfuse": probe_langfuse(),
        "telegram_bot": {"status": "unknown", "note": ZERO_HEALTH_NOTE},
        "cron_scheduler": {"status": "unknown", "note": ZERO_HEALTH_NOTE},
    }


def serialize_run(
    row: dict[str, object],
    *,
    include_files: bool = False,
    include_metadata: bool = False,
) -> dict[str, object]:
    payload: dict[str, object] = {
        **row,
        "id": str(row["id"]),
        "diff_stats": row.get("diff_stats") or None,
    }
    files_touched = row.get("files_touched")
    files_list = files_touched if isinstance(files_touched, list) else []
    payload["files_touched_count"] = len(files_list)
    payload["files_touched"] = files_list if include_files else None

    if row.get("cost_usd") is not None:
        payload["cost_usd"] = float(row["cost_usd"])
    if not include_metadata:
        payload.pop("metadata", None)

    return payload


def serialize_handoff(row: dict[str, object]) -> dict[str, object]:
    return {
        **row,
        "id": str(row["id"]),
        "from_run_id": str(row["from_run_id"]) if row.get("from_run_id") is not None else None,
        "resolved_by_run_id": (
            str(row["resolved_by_run_id"]) if row.get("resolved_by_run_id") is not None else None
        ),
        "context_refs": row.get("context_refs") or [],
    }


def serialize_research_queue_item(row: dict[str, object]) -> dict[str, object]:
    return {
        **row,
        "id": str(row["id"]),
        "candidate_id": str(row["candidate_id"]) if row.get("candidate_id") is not None else None,
    }


def bool_from_metadata(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(value, (int, float)):
        return bool(value)
    return False


def langfuse_metadata(metadata: object) -> dict[str, object]:
    payload = metadata if isinstance(metadata, dict) else {}
    return {
        "prompt_source": payload.get("prompt_source"),
        "prompt_fallback": bool_from_metadata(payload.get("prompt_fallback")),
        "langfuse_status": payload.get("langfuse_status"),
        "langfuse_error": payload.get("langfuse_error"),
    }


def browser_langfuse_base_url() -> str | None:
    configured = (os.getenv("LANGFUSE_PUBLIC_BASE_URL") or os.getenv("LANGFUSE_BASE_URL") or "").strip()
    if not configured:
        return None

    parsed = urlparse(configured)
    hostname = (parsed.hostname or "").lower()
    if hostname != "langfuse-web":
        return configured

    scheme = parsed.scheme or "http"
    port = parsed.port or 3000
    netloc = f"localhost:{port}" if port else "localhost"
    return urlunparse((scheme, netloc, parsed.path or "", "", "", ""))


def langfuse_relevant_clause(alias: str = "r") -> str:
    metadata = f"COALESCE({alias}.metadata, '{{}}'::jsonb)"
    return (
        f"({alias}.prompt_ref IS NOT NULL "
        f"OR {alias}.langfuse_trace_id IS NOT NULL "
        f"OR {metadata} ? 'prompt_source' "
        f"OR {metadata} ? 'prompt_fallback' "
        f"OR {metadata} ? 'langfuse_status' "
        f"OR {metadata} ? 'langfuse_error')"
    )


def prompt_name_from_ref(prompt_ref_value: object) -> str | None:
    prompt_ref = prompt_ref_value if isinstance(prompt_ref_value, str) else None
    if not prompt_ref:
        return None
    return prompt_ref.removeprefix("langfuse:")


def serialize_langfuse_trace(row: dict[str, object]) -> dict[str, object]:
    metadata = langfuse_metadata(row.get("metadata"))
    return {
        "run_id": str(row["id"]),
        "project_id": row["project_id"],
        "project_name": row.get("project_name"),
        "agent": row["agent"],
        "mode": row.get("mode"),
        "status": row["status"],
        "summary": row.get("summary"),
        "started_at": row["started_at"],
        "ended_at": row.get("ended_at"),
        "prompt_ref": row.get("prompt_ref"),
        "prompt_name": prompt_name_from_ref(row.get("prompt_ref")),
        "langfuse_trace_id": row.get("langfuse_trace_id"),
        "prompt_source": metadata["prompt_source"],
        "prompt_fallback": metadata["prompt_fallback"],
        "langfuse_status": metadata["langfuse_status"],
        "langfuse_error": metadata["langfuse_error"],
    }


def serialize_notification_event(row: dict[str, object]) -> dict[str, object]:
    return {
        "id": str(row["id"]),
        "channel": row["channel"],
        "direction": row["direction"],
        "project_id": row.get("project_id"),
        "project_name": row.get("project_name"),
        "candidate_id": str(row["candidate_id"]) if row.get("candidate_id") is not None else None,
        "candidate_name": row.get("candidate_name"),
        "run_id": str(row["run_id"]) if row.get("run_id") is not None else None,
        "idea_id": str(row["idea_id"]) if row.get("idea_id") is not None else None,
        "idea_title": derive_idea_title_from_raw_text(row.get("idea_raw_text"), max_length=56)
        if row.get("idea_raw_text")
        else None,
        "task_id": str(row["task_id"]) if row.get("task_id") is not None else None,
        "task_title": row.get("task_title"),
        "message_type": row.get("message_type"),
        "external_ref": row.get("external_ref"),
        "delivery_status": row.get("delivery_status"),
        "summary": row.get("summary"),
        "payload_summary": row.get("payload_summary") or {},
        "error_summary": row.get("error_summary"),
        "created_at": row.get("created_at"),
        "delivered_at": row.get("delivered_at"),
    }


def notification_where_sql(clauses: list[str]) -> str:
    return f"WHERE {' AND '.join(clauses)}" if clauses else ""


def latest_notification_event(
    conn: psycopg.Connection,
    *,
    channel: str | None = None,
    direction: str | None = None,
    message_type: str | None = None,
) -> dict[str, object] | None:
    clauses: list[str] = []
    params: list[object] = []
    if channel:
        clauses.append("channel = %s")
        params.append(channel)
    if direction:
        clauses.append("direction = %s")
        params.append(direction)
    if message_type:
        clauses.append("message_type = %s")
        params.append(message_type)
    where_sql = notification_where_sql(clauses)
    return fetch_one(
        conn,
        f"""
        SELECT *
        FROM notification_events
        {where_sql}
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """,
        params,
    )


def latest_langfuse_activity(conn: psycopg.Connection) -> dict[str, object] | None:
    rows = recent_langfuse_runs(conn, limit=1)
    return rows[0] if rows else None


def recent_langfuse_runs(
    conn: psycopg.Connection,
    *,
    filters: list[str] | None = None,
    params: list[object] | None = None,
    limit: int | None = None,
) -> list[dict[str, object]]:
    clauses = [langfuse_relevant_clause("r")]
    clauses.extend(filters or [])
    query_params = list(params or [])
    limit_sql = ""
    if limit is not None:
        limit_sql = "LIMIT %s"
        query_params.append(limit)

    return fetch_all(
        conn,
        f"""
        SELECT
            r.id,
            r.project_id,
            p.name AS project_name,
            r.agent,
            r.mode,
            r.status,
            r.summary,
            r.started_at,
            r.ended_at,
            r.prompt_ref,
            r.langfuse_trace_id,
            r.metadata
        FROM runs r
        LEFT JOIN projects p ON p.id = r.project_id
        WHERE {' AND '.join(clauses)}
        ORDER BY r.started_at DESC, r.id DESC
        {limit_sql}
        """,
        query_params,
    )


def langfuse_error_present(item: dict[str, object]) -> bool:
    if item.get("langfuse_error"):
        return True
    status = item.get("langfuse_status")
    return isinstance(status, str) and status in {"trace-error", "error", "failed"}


def summarize_text(value: str | None, max_length: int = 96) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.split())
    if len(normalized) <= max_length:
        return normalized
    return f"{normalized[: max_length - 3].rstrip()}..."


def derive_idea_title_from_raw_text(value: str | None, max_length: int = 72) -> str:
    return summarize_text(value, max_length=max_length) or ""


def empty_task_counts() -> dict[str, int]:
    return {
        "total": 0,
        "backlog": 0,
        "ready": 0,
        "progress": 0,
        "blocked": 0,
        "done": 0,
    }


def task_counts_from_row(row: dict[str, object]) -> dict[str, int]:
    return {
        "total": row.get("tasks_total") or 0,
        "backlog": row.get("tasks_backlog") or 0,
        "ready": row.get("tasks_ready") or 0,
        "progress": row.get("tasks_progress") or 0,
        "blocked": row.get("tasks_blocked") or 0,
        "done": row.get("tasks_done") or 0,
    }


def serialize_task(row: dict[str, object]) -> dict[str, object]:
    return {
        **row,
        "id": str(row["id"]),
        "idea_id": str(row["idea_id"]) if row.get("idea_id") is not None else None,
        "candidate_id": str(row["candidate_id"]) if row.get("candidate_id") is not None else None,
        "tags": row.get("tags") or [],
    }


def serialize_board_task(row: dict[str, object]) -> dict[str, object]:
    task = serialize_task(row)
    task["idea_summary"] = summarize_text(row.get("idea_raw_text"), max_length=72)
    task["idea_title"] = derive_idea_title_from_raw_text(row.get("idea_raw_text"), max_length=56)
    task.pop("idea_raw_text", None)
    return task


def serialize_idea(row: dict[str, object]) -> dict[str, object]:
    return {
        **row,
        "id": str(row["id"]),
        "tags": row.get("tags") or [],
        "title": derive_idea_title_from_raw_text(row.get("raw_text"), max_length=72),
        "task_counts": task_counts_from_row(row) if "tasks_total" in row else empty_task_counts(),
        "cross_links": row.get("cross_links") or [],
    }


def graph_node(
    *,
    node_id: str,
    node_type: str,
    label: str,
    meta: dict[str, object],
    color_hint: str | None = None,
) -> dict[str, object]:
    return {
        "id": node_id,
        "type": node_type,
        "label": label,
        "color_hint": color_hint or GRAPH_NODE_COLORS.get(node_type),
        "meta": meta,
    }


def graph_edge(from_id: str, to_id: str, kind: str) -> dict[str, str]:
    return {
        "from": from_id,
        "to": to_id,
        "kind": kind,
    }


def graph_node_id(node_type: str, raw_id: object) -> str:
    return f"{node_type}:{raw_id}"


def utc_now() -> datetime:
    return datetime.now(ZoneInfo("UTC"))


@router.get("/overview")
def get_dashboard_overview(conn: psycopg.Connection = Depends(get_db)):
    today = montevideo_today()
    days = last_seven_days()
    start_date = days[0]
    end_date = days[-1]

    kpis_row = fetch_one(
        conn,
        f"""
        SELECT
            (SELECT COUNT(*) FROM projects WHERE status = 'active') AS active_projects,
            (
                SELECT COUNT(*)
                FROM runs
                WHERE ((started_at AT TIME ZONE 'America/Montevideo')::date) = %s
            ) AS runs_today,
            (SELECT COUNT(*) FROM handoffs WHERE status = 'open') AS open_handoffs,
            (SELECT COUNT(*) FROM ideas WHERE status = 'new') AS ideas_new,
            (
                SELECT COUNT(*)
                FROM research_queue
                WHERE status = 'pending' AND scheduled_for <= %s
            ) AS queue_due_today,
            (
                SELECT COUNT(*)
                FROM vertical_candidates c
                WHERE {candidate_ready_clause("c")}
            ) AS candidates_ready_to_promote
        """,
        (today, today),
    )

    runs_by_day = group_counts_by_day(conn, "runs", "started_at", start_date=start_date, end_date=end_date)
    handoffs_opened_by_day = group_counts_by_day(
        conn,
        "handoffs",
        "created_at",
        start_date=start_date,
        end_date=end_date,
    )
    handoffs_resolved_by_day = group_counts_by_day(
        conn,
        "handoffs",
        "resolved_at",
        start_date=start_date,
        end_date=end_date,
    )
    audits_by_day = group_counts_by_day(
        conn,
        "audit_reports",
        "created_at",
        start_date=start_date,
        end_date=end_date,
    )
    ideas_by_day = group_counts_by_day(
        conn,
        "ideas",
        "created_at",
        start_date=start_date,
        end_date=end_date,
    )

    latest_runs = fetch_all(
        conn,
        """
        SELECT id, project_id, agent, mode, status, summary, started_at, ended_at, prompt_ref, langfuse_trace_id
        FROM runs
        ORDER BY started_at DESC
        LIMIT 5
        """,
    )
    open_handoffs = fetch_all(
        conn,
        """
        SELECT id, project_id, from_actor, to_actor, reason, message, status, created_at, resolved_at
        FROM handoffs
        WHERE status = 'open'
        ORDER BY created_at DESC
        LIMIT 3
        """,
    )
    latest_audits = fetch_all(
        conn,
        """
        SELECT id, project_id, verdict, confidence, summary, created_at
        FROM audit_reports
        ORDER BY created_at DESC
        LIMIT 3
        """,
    )

    return {
        "kpis": {
            "active_projects": kpis_row["active_projects"],
            "runs_today": kpis_row["runs_today"],
            "open_handoffs": kpis_row["open_handoffs"],
            "ideas_new": kpis_row["ideas_new"],
            "queue_due_today": kpis_row["queue_due_today"],
            "candidates_ready_to_promote": kpis_row["candidates_ready_to_promote"],
        },
        "weekly_evolution": [
            {
                "date": day.isoformat(),
                "runs": runs_by_day.get(day, 0),
                "handoffs_opened": handoffs_opened_by_day.get(day, 0),
                "handoffs_resolved": handoffs_resolved_by_day.get(day, 0),
                "audits": audits_by_day.get(day, 0),
                "ideas": ideas_by_day.get(day, 0),
            }
            for day in days
        ],
        "latest_runs": [
            {
                **row,
                "id": str(row["id"]),
            }
            for row in latest_runs
        ],
        "open_handoffs": [
            {
                **row,
                "id": str(row["id"]),
            }
            for row in open_handoffs
        ],
        "latest_audits": [
            {
                **row,
                "id": str(row["id"]),
                "confidence": float(row["confidence"]) if row["confidence"] is not None else None,
            }
            for row in latest_audits
        ],
        "health_summary": get_health_summary(conn),
    }


@router.get("/projects")
def list_dashboard_projects(
    status: str | None = None,
    kind: str | None = None,
    host_machine: str | None = None,
    q: str | None = None,
    conn: psycopg.Connection = Depends(get_db),
):
    clauses: list[str] = []
    params: list[object] = []

    if status:
        clauses.append("p.status = %s")
        params.append(status)
    if kind:
        clauses.append("p.kind = %s")
        params.append(kind)
    if host_machine:
        clauses.append("p.host_machine = %s")
        params.append(host_machine)
    if q:
        clauses.append("p.name ILIKE %s")
        params.append(f"%{q}%")

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    query = f"""
        SELECT
            p.id,
            p.name,
            p.kind,
            p.parent_id,
            p.host_machine,
            p.status,
            p.priority,
            p.importance,
            p.size_scope,
            p.progress_pct,
            ps.current_focus,
            ps.current_milestone,
            ps.next_step,
            MAX(r.started_at) AS last_run_at,
            MAX(a.created_at) AS last_audit_at,
            COUNT(DISTINCT h.id) FILTER (WHERE h.status = 'open') AS open_handoffs_count
        FROM projects p
        LEFT JOIN project_state ps ON ps.project_id = p.id
        LEFT JOIN runs r ON r.project_id = p.id
        LEFT JOIN audit_reports a ON a.project_id = p.id
        LEFT JOIN handoffs h ON h.project_id = p.id
        {where_sql}
        GROUP BY
            p.id, p.name, p.kind, p.parent_id, p.host_machine, p.status,
            p.priority, p.importance, p.size_scope, p.progress_pct,
            ps.current_focus, ps.current_milestone, ps.next_step
        ORDER BY p.priority NULLS LAST, p.importance NULLS LAST, p.created_at, p.id
    """
    return fetch_all(conn, query, params)


@router.get("/projects/{project_id}")
def get_dashboard_project_detail(project_id: str, conn: psycopg.Connection = Depends(get_db)):
    project = fetch_one(
        conn,
        """
        SELECT id, name, kind, parent_id, host_machine, status, priority, importance, size_scope, progress_pct
        FROM projects
        WHERE id = %s
        """,
        (project_id,),
    )
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    state = fetch_one(
        conn,
        """
        SELECT
            project_id,
            current_focus,
            current_milestone,
            roadmap_ref,
            project_state_code,
            next_step,
            blockers,
            open_questions,
            updated_at
        FROM project_state
        WHERE project_id = %s
        """,
        (project_id,),
    ) or empty_project_state(project_id)

    latest_audit = fetch_one(
        conn,
        """
        SELECT id, verdict, confidence, summary, findings, created_at
        FROM audit_reports
        WHERE project_id = %s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (project_id,),
    )
    recent_runs = fetch_all(
        conn,
        """
        SELECT id, agent, mode, status, summary, started_at, ended_at, prompt_ref, langfuse_trace_id, files_touched, diff_stats
        FROM runs
        WHERE project_id = %s
        ORDER BY started_at DESC
        LIMIT 5
        """,
        (project_id,),
    )
    open_handoffs = fetch_all(
        conn,
        """
        SELECT id, from_actor, to_actor, reason, message, status, created_at
        FROM handoffs
        WHERE project_id = %s AND status = 'open'
        ORDER BY created_at DESC
        """,
        (project_id,),
    )
    decisions = fetch_all(
        conn,
        """
        SELECT id, title, context, decision, consequences, status, supersedes, created_by, created_at
        FROM decisions
        WHERE project_id = %s
        ORDER BY created_at DESC
        LIMIT 5
        """,
        (project_id,),
    )
    related_research = fetch_all(
        conn,
        """
        SELECT id, slug, name, status, promoted_to_project_id
        FROM vertical_candidates
        WHERE promoted_to_project_id = %s
        ORDER BY updated_at DESC, slug
        LIMIT 10
        """,
        (project_id,),
    )
    related_ideas = fetch_all(
        conn,
        """
        SELECT id, raw_text, source, status, created_at
        FROM ideas
        WHERE project_id = %s
        ORDER BY created_at DESC
        LIMIT 10
        """,
        (project_id,),
    )

    return {
        "project": project,
        "state": {
            "current_focus": state["current_focus"],
            "current_milestone": state["current_milestone"],
            "roadmap_ref": state["roadmap_ref"],
            "project_state_code": state["project_state_code"],
            "next_step": state["next_step"],
            "blockers": state["blockers"] or [],
            "open_questions": state["open_questions"] or [],
            "updated_at": state["updated_at"],
        },
        "latest_audit": (
            {
                **latest_audit,
                "id": str(latest_audit["id"]),
                "confidence": float(latest_audit["confidence"]) if latest_audit["confidence"] is not None else None,
            }
            if latest_audit
            else None
        ),
        "recent_runs": [
            {
                **row,
                "id": str(row["id"]),
                "files_touched": jsonb_array_length_or_none(row["files_touched"]),
                "diff_stats": row["diff_stats"] or None,
            }
            for row in recent_runs
        ],
        "open_handoffs": [
            {
                **row,
                "id": str(row["id"]),
            }
            for row in open_handoffs
        ],
        "decisions": [
            {
                **row,
                "id": str(row["id"]),
                "supersedes": str(row["supersedes"]) if row.get("supersedes") is not None else None,
            }
            for row in decisions
        ],
        "related_research": [
            {
                **row,
                "id": str(row["id"]),
            }
            for row in related_research
        ],
        "related_ideas": [
            {
                **row,
                "id": str(row["id"]),
            }
            for row in related_ideas
        ],
    }


@router.get("/projects/{project_id}/graph")
def get_dashboard_project_graph(project_id: str, conn: psycopg.Connection = Depends(get_db)):
    project = fetch_one(
        conn,
        """
        SELECT id, name, status, host_machine, progress_pct
        FROM projects
        WHERE id = %s
        """,
        (project_id,),
    )
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    recent_runs = fetch_all(
        conn,
        """
        SELECT id, agent, mode, status, summary, started_at, ended_at, prompt_ref, langfuse_trace_id
        FROM runs
        WHERE project_id = %s
        ORDER BY started_at DESC
        LIMIT 5
        """,
        (project_id,),
    )
    handoffs = fetch_all(
        conn,
        """
        SELECT
            id,
            from_run_id,
            from_actor,
            to_actor,
            reason,
            message,
            status,
            created_at,
            resolved_at,
            resolved_by_run_id
        FROM handoffs
        WHERE project_id = %s
        ORDER BY COALESCE(resolved_at, created_at) DESC, created_at DESC
        LIMIT 8
        """,
        (project_id,),
    )
    decisions = fetch_all(
        conn,
        """
        SELECT id, title, context, decision, consequences, status, created_at
        FROM decisions
        WHERE project_id = %s
        ORDER BY created_at DESC
        LIMIT 5
        """,
        (project_id,),
    )
    latest_audit = fetch_one(
        conn,
        """
        SELECT id, verdict, confidence, summary, created_at
        FROM audit_reports
        WHERE project_id = %s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (project_id,),
    )
    related_research = fetch_all(
        conn,
        """
        SELECT id, slug, name, status, promoted_to_project_id
        FROM vertical_candidates
        WHERE promoted_to_project_id = %s
        ORDER BY updated_at DESC, slug
        LIMIT 10
        """,
        (project_id,),
    )
    related_ideas = fetch_all(
        conn,
        """
        SELECT id, raw_text, source, status, created_at
        FROM ideas
        WHERE project_id = %s
        ORDER BY created_at DESC
        LIMIT 10
        """,
        (project_id,),
    )
    related_tasks = fetch_all(
        conn,
        """
        WITH related_candidates AS (
            SELECT id
            FROM vertical_candidates
            WHERE promoted_to_project_id = %s
        ),
        related_ideas AS (
            SELECT id
            FROM ideas
            WHERE project_id = %s
        )
        SELECT DISTINCT
            t.id,
            t.idea_id,
            t.project_id,
            t.candidate_id,
            t.title,
            t.status,
            t.priority,
            t.position,
            t.created_at,
            t.updated_at
        FROM tasks t
        LEFT JOIN related_ideas ri ON ri.id = t.idea_id
        LEFT JOIN related_candidates rc ON rc.id = t.candidate_id
        WHERE t.project_id = %s OR ri.id IS NOT NULL OR rc.id IS NOT NULL
        ORDER BY t.updated_at DESC, t.created_at DESC, t.id
        LIMIT 12
        """,
        (project_id, project_id, project_id),
    )

    nodes: list[dict[str, object]] = []
    edges: list[dict[str, str]] = []
    seen_nodes: set[str] = set()
    seen_edges: set[tuple[str, str, str]] = set()

    def add_node(node: dict[str, object]) -> None:
        if node["id"] in seen_nodes:
            return
        seen_nodes.add(node["id"])
        nodes.append(node)

    def add_edge(from_id: str, to_id: str, kind: str) -> None:
        edge_key = (from_id, to_id, kind)
        if edge_key in seen_edges:
            return
        if from_id not in seen_nodes or to_id not in seen_nodes:
            return
        seen_edges.add(edge_key)
        edges.append(graph_edge(from_id, to_id, kind))

    project_node_id = graph_node_id("project", project["id"])
    add_node(
        graph_node(
            node_id=project_node_id,
            node_type="project",
            label=project["name"],
            meta={
                "status": project["status"],
                "host_machine": project["host_machine"],
                "progress_pct": project["progress_pct"],
            },
        )
    )

    run_node_ids = {
        row["id"]: graph_node_id("run", row["id"])
        for row in recent_runs
    }
    for row in recent_runs:
        node_id = run_node_ids[row["id"]]
        add_node(
            graph_node(
                node_id=node_id,
                node_type="run",
                label=f"{row['agent']} · {row['mode']}" if row.get("mode") else row["agent"],
                meta={
                    "status": row["status"],
                    "started_at": row["started_at"],
                    "ended_at": row["ended_at"],
                    "summary": row["summary"],
                    "prompt_ref": row["prompt_ref"],
                    "langfuse_trace_id": row["langfuse_trace_id"],
                },
            )
        )
        add_edge(node_id, project_node_id, "touches")

    handoff_node_ids = {
        row["id"]: graph_node_id("handoff", row["id"])
        for row in handoffs
    }
    for row in handoffs:
        node_id = handoff_node_ids[row["id"]]
        add_node(
            graph_node(
                node_id=node_id,
                node_type="handoff",
                label=f"{row['from_actor']} -> {row['to_actor']}",
                meta={
                    "reason": row["reason"],
                    "status": row["status"],
                    "created_at": row["created_at"],
                    "resolved_at": row["resolved_at"],
                    "message": row["message"],
                },
            )
        )
        add_edge(node_id, project_node_id, "relates_to")
        if row.get("from_run_id") in run_node_ids:
            add_edge(run_node_ids[row["from_run_id"]], node_id, "produced")
        if row.get("resolved_by_run_id") in run_node_ids:
            add_edge(node_id, run_node_ids[row["resolved_by_run_id"]], "resolved_by")

    for row in decisions:
        node_id = graph_node_id("decision", row["id"])
        add_node(
            graph_node(
                node_id=node_id,
                node_type="decision",
                label=summarize_text(row["title"], max_length=56) or "Decision",
                meta={
                    "status": row["status"],
                    "created_at": row["created_at"],
                    "context": row["context"],
                    "decision": row["decision"],
                    "consequences": row["consequences"],
                },
            )
        )
        add_edge(node_id, project_node_id, "relates_to")

    if latest_audit is not None:
        audit_node_id = graph_node_id("audit", latest_audit["id"])
        add_node(
            graph_node(
                node_id=audit_node_id,
                node_type="audit",
                label=latest_audit["verdict"],
                meta={
                    "verdict": latest_audit["verdict"],
                    "confidence": float(latest_audit["confidence"]) if latest_audit["confidence"] is not None else None,
                    "created_at": latest_audit["created_at"],
                    "summary": latest_audit["summary"],
                },
            )
        )
        add_edge(audit_node_id, project_node_id, "audits")

    candidate_node_ids = {
        row["id"]: graph_node_id("candidate", row["id"])
        for row in related_research
    }
    for row in related_research:
        node_id = candidate_node_ids[row["id"]]
        add_node(
            graph_node(
                node_id=node_id,
                node_type="candidate",
                label=row["name"],
                meta={
                    "status": row["status"],
                    "promoted_to_project_id": row["promoted_to_project_id"],
                },
            )
        )
        add_edge(node_id, project_node_id, "promoted_from")

    idea_node_ids = {
        row["id"]: graph_node_id("idea", row["id"])
        for row in related_ideas
    }
    for row in related_ideas:
        node_id = idea_node_ids[row["id"]]
        add_node(
            graph_node(
                node_id=node_id,
                node_type="idea",
                label=derive_idea_title_from_raw_text(row["raw_text"], max_length=56) or "Idea",
                meta={
                    "source": row["source"],
                    "status": row["status"],
                    "created_at": row["created_at"],
                },
            )
        )
        add_edge(node_id, project_node_id, "relates_to")

    for row in related_tasks:
        node_id = graph_node_id("task", row["id"])
        add_node(
            graph_node(
                node_id=node_id,
                node_type="task",
                label=row["title"],
                meta={
                    "status": row["status"],
                    "priority": row["priority"],
                    "position": row["position"],
                },
            )
        )
        add_edge(node_id, project_node_id, "touches")
        if row.get("idea_id") in idea_node_ids:
            add_edge(node_id, idea_node_ids[row["idea_id"]], "relates_to")
        if row.get("candidate_id") in candidate_node_ids:
            add_edge(node_id, candidate_node_ids[row["candidate_id"]], "relates_to")

    return {
        "nodes": nodes,
        "edges": edges,
    }


@router.get("/research/overview")
def get_dashboard_research_overview(conn: psycopg.Connection = Depends(get_db)):
    today = montevideo_today()
    ready_clause = candidate_ready_clause("c")

    kpis = fetch_one(
        conn,
        f"""
        SELECT
            (SELECT COUNT(*) FROM vertical_candidates c WHERE {ready_clause}) AS ready_to_promote,
            (
                SELECT COUNT(*)
                FROM research_queue
                WHERE status = 'pending' AND scheduled_for <= %s
            ) AS queue_due_today,
            (SELECT COUNT(*) FROM research_queue WHERE status = 'pending') AS pending_queue_total
        """,
        (today,),
    )

    candidates = fetch_all(
        conn,
        """
        SELECT
            c.id,
            c.slug,
            c.name,
            c.category,
            c.parent_group,
            c.hypothesis,
            c.problem_desc,
            c.status,
            c.priority,
            c.importance,
            c.estimated_size,
            c.kill_verdict,
            c.promoted_to_project_id,
            rr.id AS last_research_id,
            rr.verdict AS last_research_verdict,
            rr.confidence AS last_research_confidence,
            rr.summary AS last_research_summary,
            rr.created_at AS last_research_created_at
        FROM vertical_candidates c
        LEFT JOIN LATERAL (
            SELECT id, verdict, confidence, summary, created_at
            FROM candidate_research_reports
            WHERE candidate_id = c.id
            ORDER BY created_at DESC
            LIMIT 1
        ) rr ON TRUE
        ORDER BY c.updated_at DESC, c.slug
        """,
    )
    ready_to_promote = fetch_all(
        conn,
        f"""
        SELECT
            c.id,
            c.slug,
            c.name,
            c.status,
            rr.id AS last_research_id,
            rr.verdict AS last_research_verdict,
            rr.confidence AS last_research_confidence,
            rr.summary AS last_research_summary,
            rr.created_at AS last_research_created_at
        FROM vertical_candidates c
        LEFT JOIN LATERAL (
            SELECT id, verdict, confidence, summary, created_at
            FROM candidate_research_reports
            WHERE candidate_id = c.id
            ORDER BY created_at DESC
            LIMIT 1
        ) rr ON TRUE
        WHERE {ready_clause}
        ORDER BY COALESCE(rr.created_at, c.updated_at) DESC, c.slug
        """,
    )
    queue = fetch_all(
        conn,
        """
        SELECT id, candidate_id, project_id, queue_type, priority, scheduled_for, status, last_run_at, notes
        FROM research_queue
        ORDER BY status = 'pending' DESC, scheduled_for, priority, created_at
        """,
    )
    recent_reports = fetch_all(
        conn,
        """
        SELECT id, candidate_id, verdict, confidence, summary, created_at
        FROM candidate_research_reports
        ORDER BY created_at DESC
        LIMIT 10
        """,
    )

    def build_last_research(row: dict[str, object]) -> dict[str, object] | None:
        if row["last_research_id"] is None:
            return None
        return {
            "id": str(row["last_research_id"]),
            "verdict": row["last_research_verdict"],
            "confidence": (
                float(row["last_research_confidence"]) if row["last_research_confidence"] is not None else None
            ),
            "summary": row["last_research_summary"],
            "created_at": row["last_research_created_at"],
        }

    return {
        "kpis": {
            "ready_to_promote": kpis["ready_to_promote"],
            "queue_due_today": kpis["queue_due_today"],
            "pending_queue_total": kpis["pending_queue_total"],
        },
        "ready_to_promote": [
            {
                "id": str(row["id"]),
                "slug": row["slug"],
                "name": row["name"],
                "status": row["status"],
                "last_research": build_last_research(row),
            }
            for row in ready_to_promote
        ],
        "candidates": [
            {
                "id": str(row["id"]),
                "slug": row["slug"],
                "name": row["name"],
                "category": row["category"],
                "parent_group": row["parent_group"],
                "hypothesis": row["hypothesis"],
                "problem_desc": row["problem_desc"],
                "status": row["status"],
                "priority": row["priority"],
                "importance": row["importance"],
                "estimated_size": row["estimated_size"],
                "kill_verdict": row["kill_verdict"],
                "promoted_to_project_id": row["promoted_to_project_id"],
                "last_research": build_last_research(row),
            }
            for row in candidates
        ],
        "queue": [serialize_research_queue_item(row) for row in queue],
        "recent_reports": [
            {
                **row,
                "id": str(row["id"]),
                "candidate_id": str(row["candidate_id"]),
                "confidence": float(row["confidence"]) if row["confidence"] is not None else None,
            }
            for row in recent_reports
        ],
    }


@router.get("/runs/recent")
def get_dashboard_runs_recent(
    project_id: str | None = None,
    agent: str | None = None,
    status: str | None = None,
    mode: str | None = None,
    limit: int = 20,
    conn: psycopg.Connection = Depends(get_db),
):
    clauses: list[str] = []
    params: list[object] = []

    if project_id:
        clauses.append("r.project_id = %s")
        params.append(project_id)
    if agent:
        clauses.append("r.agent = %s")
        params.append(agent)
    if status:
        clauses.append("r.status = %s")
        params.append(status)
    if mode:
        clauses.append("r.mode = %s")
        params.append(mode)

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(min(max(limit, 1), 100))
    rows = fetch_all(
        conn,
        f"""
        SELECT
            r.id,
            r.project_id,
            p.name AS project_name,
            r.agent,
            r.agent_version,
            r.mode,
            r.prompt_ref,
            r.worktree_path,
            r.started_at,
            r.ended_at,
            r.status,
            r.summary,
            r.files_touched,
            r.diff_stats,
            r.next_step_proposed,
            r.cost_usd,
            r.langfuse_trace_id,
            r.metadata
        FROM runs r
        LEFT JOIN projects p ON p.id = r.project_id
        {where_sql}
        ORDER BY r.started_at DESC
        LIMIT %s
        """,
        params,
    )
    return [serialize_run(row) for row in rows]


@router.get("/runs/{run_id}")
def get_dashboard_run_detail(run_id: UUID, conn: psycopg.Connection = Depends(get_db)):
    run = fetch_one(
        conn,
        """
        SELECT
            r.id,
            r.project_id,
            p.name AS project_name,
            r.agent,
            r.agent_version,
            r.mode,
            r.prompt_ref,
            r.worktree_path,
            r.started_at,
            r.ended_at,
            r.status,
            r.summary,
            r.files_touched,
            r.diff_stats,
            r.next_step_proposed,
            r.cost_usd,
            r.langfuse_trace_id,
            r.metadata
        FROM runs r
        LEFT JOIN projects p ON p.id = r.project_id
        WHERE r.id = %s
        """,
        (run_id,),
    )
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    return serialize_run(run, include_files=True, include_metadata=True)


@router.get("/langfuse/summary")
def get_dashboard_langfuse_summary(conn: psycopg.Connection = Depends(get_db)):
    rows = recent_langfuse_runs(conn)
    serialized = [serialize_langfuse_trace(row) for row in rows]

    prompt_sources: dict[str, int] = {}
    langfuse_statuses: dict[str, int] = {}
    unique_prompts: set[str] = set()
    traced_runs = 0
    fallback_runs = 0
    error_runs = 0
    recent_fallbacks: list[dict[str, object]] = []
    recent_errors: list[dict[str, object]] = []

    for item in serialized:
        prompt_source = item["prompt_source"] if isinstance(item["prompt_source"], str) else "unknown"
        prompt_sources[prompt_source] = prompt_sources.get(prompt_source, 0) + 1

        langfuse_status = item["langfuse_status"] if isinstance(item["langfuse_status"], str) else "unknown"
        langfuse_statuses[langfuse_status] = langfuse_statuses.get(langfuse_status, 0) + 1

        prompt_ref = item["prompt_ref"]
        if isinstance(prompt_ref, str) and prompt_ref:
            unique_prompts.add(prompt_ref)
        if item["langfuse_trace_id"]:
            traced_runs += 1
        if item["prompt_fallback"]:
            fallback_runs += 1
            if len(recent_fallbacks) < 5:
                recent_fallbacks.append(item)
        if langfuse_error_present(item):
            error_runs += 1
            if len(recent_errors) < 5:
                recent_errors.append(item)

    return {
        "langfuse_base_url": browser_langfuse_base_url(),
        "kpis": {
            "observed_runs": len(serialized),
            "unique_prompts": len(unique_prompts),
            "traced_runs": traced_runs,
            "fallback_runs": fallback_runs,
            "error_runs": error_runs,
        },
        "prompt_sources": [
            {"source": source, "count": count}
            for source, count in sorted(prompt_sources.items(), key=lambda item: (-item[1], item[0]))
        ],
        "langfuse_statuses": [
            {"status": status, "count": count}
            for status, count in sorted(langfuse_statuses.items(), key=lambda item: (-item[1], item[0]))
        ],
        "recent_fallbacks": recent_fallbacks,
        "recent_errors": recent_errors,
    }


@router.get("/langfuse/prompts")
def get_dashboard_langfuse_prompts(conn: psycopg.Connection = Depends(get_db)):
    rows = recent_langfuse_runs(conn)
    prompt_index: dict[str, dict[str, object]] = {}

    for row in rows:
        prompt_ref = row.get("prompt_ref")
        if not isinstance(prompt_ref, str) or not prompt_ref:
            continue

        item = serialize_langfuse_trace(row)
        if prompt_ref not in prompt_index:
            prompt_index[prompt_ref] = {
                "prompt_ref": prompt_ref,
                "prompt_name": prompt_name_from_ref(prompt_ref),
                "runs_count": 0,
                "last_used_at": item["started_at"],
                "last_project_id": item["project_id"],
                "last_project_name": item["project_name"],
                "last_prompt_source": item["prompt_source"],
                "last_prompt_fallback": item["prompt_fallback"],
                "last_langfuse_status": item["langfuse_status"],
                "last_langfuse_error": item["langfuse_error"],
                "last_trace_id": item["langfuse_trace_id"],
            }
        prompt_index[prompt_ref]["runs_count"] = int(prompt_index[prompt_ref]["runs_count"]) + 1

    items = sorted(prompt_index.values(), key=lambda item: str(item["last_used_at"]), reverse=True)
    return {
        "langfuse_base_url": browser_langfuse_base_url(),
        "items": items,
    }


@router.get("/langfuse/traces")
def get_dashboard_langfuse_traces(
    project_id: str | None = None,
    agent: str | None = None,
    prompt_source: str | None = None,
    langfuse_status: str | None = None,
    limit: int = 50,
    conn: psycopg.Connection = Depends(get_db),
):
    filters: list[str] = []
    params: list[object] = []

    if project_id:
        filters.append("r.project_id = %s")
        params.append(project_id)
    if agent:
        filters.append("r.agent = %s")
        params.append(agent)
    if prompt_source:
        filters.append("COALESCE(r.metadata->>'prompt_source', '') = %s")
        params.append(prompt_source)
    if langfuse_status:
        filters.append("COALESCE(r.metadata->>'langfuse_status', '') = %s")
        params.append(langfuse_status)

    rows = recent_langfuse_runs(
        conn,
        filters=filters,
        params=params,
        limit=min(max(limit, 1), 100),
    )
    return {
        "langfuse_base_url": browser_langfuse_base_url(),
        "items": [serialize_langfuse_trace(row) for row in rows],
    }


@router.get("/handoffs/open")
def get_dashboard_open_handoffs(
    to_actor: str | None = None,
    project_id: str | None = None,
    limit: int = 50,
    conn: psycopg.Connection = Depends(get_db),
):
    clauses = ["h.status = 'open'"]
    params: list[object] = []

    if to_actor:
        clauses.append("h.to_actor = %s")
        params.append(to_actor)
    if project_id:
        clauses.append("h.project_id = %s")
        params.append(project_id)

    params.append(min(max(limit, 1), 100))
    rows = fetch_all(
        conn,
        f"""
        SELECT
            h.id,
            h.project_id,
            p.name AS project_name,
            h.from_run_id,
            h.from_actor,
            h.to_actor,
            h.reason,
            h.message,
            h.context_refs,
            h.status,
            h.created_at,
            h.resolved_at,
            h.resolved_by_run_id
        FROM handoffs h
        LEFT JOIN projects p ON p.id = h.project_id
        WHERE {' AND '.join(clauses)}
        ORDER BY h.created_at DESC
        LIMIT %s
        """,
        params,
    )
    return [serialize_handoff(row) for row in rows]


@router.get("/ideas/overview")
def get_dashboard_ideas_overview(conn: psycopg.Connection = Depends(get_db)):
    kpis = fetch_one(
        conn,
        """
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE status = 'new') AS new_count,
            COUNT(*) FILTER (WHERE status = 'triaged') AS triaged_count,
            COUNT(*) FILTER (WHERE status = 'promoted') AS promoted_count,
            COUNT(*) FILTER (WHERE status = 'discarded') AS discarded_count,
            COUNT(*) FILTER (WHERE source = 'telegram') AS telegram_count,
            COUNT(*) FILTER (WHERE source = 'whatsapp') AS whatsapp_count,
            COUNT(*) FILTER (WHERE source = 'cli') AS cli_count,
            COUNT(*) FILTER (WHERE source = 'web') AS web_count,
            COUNT(*) FILTER (WHERE source = 'other') AS other_count
        FROM ideas
        """,
    )
    task_kpis = fetch_one(
        conn,
        """
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE status = 'backlog') AS backlog_count,
            COUNT(*) FILTER (WHERE status = 'ready') AS ready_count,
            COUNT(*) FILTER (WHERE status = 'progress') AS progress_count,
            COUNT(*) FILTER (WHERE status = 'blocked') AS blocked_count,
            COUNT(*) FILTER (WHERE status = 'done') AS done_count
        FROM tasks
        """,
    )
    ideas = fetch_all(
        conn,
        """
        SELECT
            i.id,
            i.project_id,
            p.name AS project_name,
            i.raw_text,
            i.source,
            i.source_ref,
            i.tags,
            i.status,
            i.promoted_to,
            i.triage_notes,
            i.created_at,
            i.triaged_at,
            COALESCE(tc.total, 0) AS tasks_total,
            COALESCE(tc.backlog_count, 0) AS tasks_backlog,
            COALESCE(tc.ready_count, 0) AS tasks_ready,
            COALESCE(tc.progress_count, 0) AS tasks_progress,
            COALESCE(tc.blocked_count, 0) AS tasks_blocked,
            COALESCE(tc.done_count, 0) AS tasks_done
        FROM ideas i
        LEFT JOIN projects p ON p.id = i.project_id
        LEFT JOIN (
            SELECT
                idea_id,
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE status = 'backlog') AS backlog_count,
                COUNT(*) FILTER (WHERE status = 'ready') AS ready_count,
                COUNT(*) FILTER (WHERE status = 'progress') AS progress_count,
                COUNT(*) FILTER (WHERE status = 'blocked') AS blocked_count,
                COUNT(*) FILTER (WHERE status = 'done') AS done_count
            FROM tasks
            WHERE idea_id IS NOT NULL
            GROUP BY idea_id
        ) tc ON tc.idea_id = i.id
        ORDER BY i.created_at DESC
        LIMIT 100
        """,
    )
    sources = {
        "telegram": kpis["telegram_count"],
        "whatsapp": kpis["whatsapp_count"],
        "cli": kpis["cli_count"],
        "web": kpis["web_count"],
        "other": kpis["other_count"],
    }
    return {
        "kpis": {
            "total": kpis["total"],
            "new": kpis["new_count"],
            "triaged": kpis["triaged_count"],
            "promoted": kpis["promoted_count"],
            "discarded": kpis["discarded_count"],
        },
        "task_kpis": {
            "total": task_kpis["total"],
            "backlog": task_kpis["backlog_count"],
            "ready": task_kpis["ready_count"],
            "progress": task_kpis["progress_count"],
            "blocked": task_kpis["blocked_count"],
            "done": task_kpis["done_count"],
        },
        "sources": sources,
        "counts_by_source": sources,
        "ideas": [serialize_idea(row) for row in ideas],
    }


@router.get("/ideas/{idea_id}/workspace")
def get_dashboard_idea_workspace(idea_id: UUID, conn: psycopg.Connection = Depends(get_db)):
    idea = fetch_one(
        conn,
        """
        SELECT
            i.id,
            i.project_id,
            p.name AS project_name,
            i.raw_text,
            i.source,
            i.source_ref,
            i.tags,
            i.status,
            i.promoted_to,
            i.triage_notes,
            i.created_at,
            i.triaged_at,
            COALESCE(tc.total, 0) AS tasks_total,
            COALESCE(tc.backlog_count, 0) AS tasks_backlog,
            COALESCE(tc.ready_count, 0) AS tasks_ready,
            COALESCE(tc.progress_count, 0) AS tasks_progress,
            COALESCE(tc.blocked_count, 0) AS tasks_blocked,
            COALESCE(tc.done_count, 0) AS tasks_done
        FROM ideas i
        LEFT JOIN projects p ON p.id = i.project_id
        LEFT JOIN (
            SELECT
                idea_id,
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE status = 'backlog') AS backlog_count,
                COUNT(*) FILTER (WHERE status = 'ready') AS ready_count,
                COUNT(*) FILTER (WHERE status = 'progress') AS progress_count,
                COUNT(*) FILTER (WHERE status = 'blocked') AS blocked_count,
                COUNT(*) FILTER (WHERE status = 'done') AS done_count
            FROM tasks
            WHERE idea_id IS NOT NULL
            GROUP BY idea_id
        ) tc ON tc.idea_id = i.id
        WHERE i.id = %s
        """,
        (idea_id,),
    )
    if idea is None:
        raise HTTPException(status_code=404, detail=f"Idea {idea_id} not found")

    tasks = fetch_all(
        conn,
        """
        SELECT
            id,
            idea_id,
            project_id,
            candidate_id,
            title,
            description,
            status,
            priority,
            position,
            tags,
            promoted_to,
            created_at,
            updated_at,
            closed_at
        FROM tasks
        WHERE idea_id = %s
        ORDER BY
            CASE status
                WHEN 'backlog' THEN 0
                WHEN 'ready' THEN 1
                WHEN 'progress' THEN 2
                WHEN 'blocked' THEN 3
                WHEN 'done' THEN 4
                ELSE 5
            END,
            position,
            created_at,
            id
        """,
        (idea_id,),
    )
    sibling_ideas = []
    if idea.get("tags"):
        sibling_ideas = fetch_all(
            conn,
            """
            SELECT
                i.id,
                i.project_id,
                p.name AS project_name,
                i.raw_text,
                i.source,
                i.source_ref,
                i.tags,
                i.status,
                i.promoted_to,
                i.triage_notes,
                i.created_at,
                i.triaged_at,
                COALESCE(tc.total, 0) AS tasks_total,
                COALESCE(tc.backlog_count, 0) AS tasks_backlog,
                COALESCE(tc.ready_count, 0) AS tasks_ready,
                COALESCE(tc.progress_count, 0) AS tasks_progress,
                COALESCE(tc.blocked_count, 0) AS tasks_blocked,
                COALESCE(tc.done_count, 0) AS tasks_done
            FROM ideas i
            LEFT JOIN projects p ON p.id = i.project_id
            LEFT JOIN (
                SELECT
                    idea_id,
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE status = 'backlog') AS backlog_count,
                    COUNT(*) FILTER (WHERE status = 'ready') AS ready_count,
                    COUNT(*) FILTER (WHERE status = 'progress') AS progress_count,
                    COUNT(*) FILTER (WHERE status = 'blocked') AS blocked_count,
                    COUNT(*) FILTER (WHERE status = 'done') AS done_count
                FROM tasks
                WHERE idea_id IS NOT NULL
                GROUP BY idea_id
            ) tc ON tc.idea_id = i.id
            WHERE i.id <> %s AND i.tags && %s
            ORDER BY i.created_at DESC
            LIMIT 10
            """,
            (idea_id, idea["tags"]),
        )

    return {
        "idea": serialize_idea(idea),
        "tasks": [serialize_task(row) for row in tasks],
        "sibling_ideas_in_same_tag": [serialize_idea(row) for row in sibling_ideas],
        "suggested_next": [],
    }


@router.get("/tasks/board")
def get_dashboard_tasks_board(
    idea_id: UUID | None = None,
    project_id: str | None = None,
    candidate_id: UUID | None = None,
    conn: psycopg.Connection = Depends(get_db),
):
    clauses: list[str] = []
    params: list[object] = []
    if idea_id is not None:
        clauses.append("t.idea_id = %s")
        params.append(idea_id)
    if project_id is not None:
        clauses.append("t.project_id = %s")
        params.append(project_id)
    if candidate_id is not None:
        clauses.append("t.candidate_id = %s")
        params.append(candidate_id)

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = fetch_all(
        conn,
        f"""
        SELECT
            t.id,
            t.idea_id,
            t.project_id,
            t.candidate_id,
            t.title,
            t.description,
            t.status,
            t.priority,
            t.position,
            t.tags,
            t.promoted_to,
            t.created_at,
            t.updated_at,
            t.closed_at,
            i.raw_text AS idea_raw_text
        FROM tasks t
        LEFT JOIN ideas i ON i.id = t.idea_id
        {where_sql}
        ORDER BY
            CASE t.status
                WHEN 'backlog' THEN 0
                WHEN 'ready' THEN 1
                WHEN 'progress' THEN 2
                WHEN 'blocked' THEN 3
                WHEN 'done' THEN 4
                ELSE 5
            END,
            t.position,
            t.created_at,
            t.id
        """,
        params,
    )
    board = {status: [] for status in TASK_STATUSES}
    for row in rows:
        board[row["status"]].append(serialize_board_task(row))
    return board


@router.get("/system/health")
def get_dashboard_system_health(conn: psycopg.Connection = Depends(get_db)):
    return get_health_summary(conn)


@router.get("/notifications")
def get_dashboard_notifications(
    channel: str | None = None,
    direction: str | None = None,
    delivery_status: str | None = None,
    project_id: str | None = None,
    limit: int = 50,
    conn: psycopg.Connection = Depends(get_db),
):
    clauses: list[str] = []
    params: list[object] = []
    if channel:
        clauses.append("ne.channel = %s")
        params.append(channel)
    if direction:
        clauses.append("ne.direction = %s")
        params.append(direction)
    if delivery_status:
        clauses.append("ne.delivery_status = %s")
        params.append(delivery_status)
    if project_id:
        clauses.append("ne.project_id = %s")
        params.append(project_id)

    where_sql = notification_where_sql(clauses)
    rows = fetch_all(
        conn,
        f"""
        SELECT
            ne.*,
            p.name AS project_name,
            c.name AS candidate_name,
            i.raw_text AS idea_raw_text,
            t.title AS task_title
        FROM notification_events ne
        LEFT JOIN projects p ON p.id = ne.project_id
        LEFT JOIN vertical_candidates c ON c.id = ne.candidate_id
        LEFT JOIN ideas i ON i.id = ne.idea_id
        LEFT JOIN tasks t ON t.id = ne.task_id
        {where_sql}
        ORDER BY ne.created_at DESC, ne.id DESC
        LIMIT %s
        """,
        [*params, max(1, min(limit, 100))],
    )
    total_row = fetch_one(
        conn,
        f"""
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE ne.channel = 'telegram') AS telegram_count,
            COUNT(*) FILTER (WHERE ne.direction = 'inbound') AS inbound_count,
            COUNT(*) FILTER (WHERE ne.direction = 'outbound') AS outbound_count,
            COUNT(*) FILTER (WHERE ne.delivery_status = 'delivered') AS delivered_count,
            COUNT(*) FILTER (WHERE ne.delivery_status = 'failed') AS failed_count
        FROM notification_events ne
        {where_sql}
        """,
        params,
    ) or {}
    return {
        "summary": {
            "total": total_row.get("total", 0),
            "telegram": total_row.get("telegram_count", 0),
            "inbound": total_row.get("inbound_count", 0),
            "outbound": total_row.get("outbound_count", 0),
            "delivered": total_row.get("delivered_count", 0),
            "failed": total_row.get("failed_count", 0),
        },
        "items": [serialize_notification_event(row) for row in rows],
    }


@router.get("/notifications/{notification_id}")
def get_dashboard_notification_detail(
    notification_id: UUID,
    conn: psycopg.Connection = Depends(get_db),
):
    row = fetch_one(
        conn,
        """
        SELECT
            ne.*,
            p.name AS project_name,
            c.name AS candidate_name,
            i.raw_text AS idea_raw_text,
            t.title AS task_title
        FROM notification_events ne
        LEFT JOIN projects p ON p.id = ne.project_id
        LEFT JOIN vertical_candidates c ON c.id = ne.candidate_id
        LEFT JOIN ideas i ON i.id = ne.idea_id
        LEFT JOIN tasks t ON t.id = ne.task_id
        WHERE ne.id = %s
        """,
        (notification_id,),
    )
    if row is None:
        raise HTTPException(status_code=404, detail=f"Notification event '{notification_id}' not found")
    return serialize_notification_event(row)


@router.get("/telegram/summary")
def get_dashboard_telegram_summary(conn: psycopg.Connection = Depends(get_db)):
    kpis = fetch_one(
        conn,
        """
        SELECT
            COUNT(*) AS total_events,
            COUNT(*) FILTER (WHERE direction = 'inbound') AS inbound_events,
            COUNT(*) FILTER (WHERE direction = 'outbound') AS outbound_events,
            COUNT(*) FILTER (WHERE delivery_status = 'delivered') AS delivered_events,
            COUNT(*) FILTER (WHERE delivery_status = 'failed') AS failed_events
        FROM notification_events
        WHERE channel = 'telegram'
        """,
    ) or {}
    message_types = fetch_all(
        conn,
        """
        SELECT COALESCE(message_type, 'unknown') AS message_type, COUNT(*) AS total
        FROM notification_events
        WHERE channel = 'telegram'
        GROUP BY COALESCE(message_type, 'unknown')
        ORDER BY total DESC, message_type
        """,
    )
    recent = fetch_all(
        conn,
        """
        SELECT
            ne.*,
            p.name AS project_name,
            c.name AS candidate_name,
            i.raw_text AS idea_raw_text,
            t.title AS task_title
        FROM notification_events ne
        LEFT JOIN projects p ON p.id = ne.project_id
        LEFT JOIN vertical_candidates c ON c.id = ne.candidate_id
        LEFT JOIN ideas i ON i.id = ne.idea_id
        LEFT JOIN tasks t ON t.id = ne.task_id
        WHERE ne.channel = 'telegram'
        ORDER BY ne.created_at DESC, ne.id DESC
        LIMIT 10
        """,
    )
    return {
        "kpis": {
            "total_events": kpis.get("total_events", 0),
            "inbound_events": kpis.get("inbound_events", 0),
            "outbound_events": kpis.get("outbound_events", 0),
            "delivered_events": kpis.get("delivered_events", 0),
            "failed_events": kpis.get("failed_events", 0),
        },
        "message_types": [
            {"message_type": row["message_type"], "count": row["total"]}
            for row in message_types
        ],
        "recent_events": [serialize_notification_event(row) for row in recent],
    }


@router.get("/system/jobs")
def get_dashboard_system_jobs(conn: psycopg.Connection = Depends(get_db)):
    active_summary = latest_notification_event(
        conn,
        channel="telegram",
        direction="outbound",
        message_type="active-daily-summary",
    )
    passive_summary = latest_notification_event(
        conn,
        channel="telegram",
        direction="outbound",
        message_type="passive-daily-summary",
    )
    weekly_signal = fetch_one(
        conn,
        """
        SELECT
            MAX(started_at) AS last_run_at,
            COUNT(*) FILTER (WHERE started_at >= (NOW() - INTERVAL '14 days')) AS recent_runs
        FROM runs
        WHERE agent IN ('auditor', 'investigator')
        """,
    ) or {}

    def job_item(
        *,
        key: str,
        label: str,
        event: dict[str, object] | None,
        note_when_missing: str,
    ) -> dict[str, object]:
        if event is None:
            return {
                "key": key,
                "label": label,
                "status": "unknown",
                "note": note_when_missing,
                "last_run_at": None,
                "last_success_at": None,
                "signal_source": "notification_events",
            }
        status = "ok" if event.get("delivery_status") == "delivered" else "degraded"
        last_run_at = event.get("created_at")
        last_success_at = (
            event.get("delivered_at") or event.get("created_at")
            if event.get("delivery_status") == "delivered"
            else None
        )
        return {
            "key": key,
            "label": label,
            "status": status,
            "note": event.get("error_summary") or event.get("summary"),
            "last_run_at": last_run_at,
            "last_success_at": last_success_at,
            "signal_source": "notification_events",
        }

    weekly_last_run = weekly_signal.get("last_run_at")
    if weekly_last_run is None:
        weekly_status = "unknown"
        weekly_note = "no auditor/investigator runs observed yet"
    elif weekly_signal.get("recent_runs", 0):
        weekly_status = "ok"
        weekly_note = "derived from auditor/investigator runs in the last 14 days"
    else:
        weekly_status = "degraded"
        weekly_note = "latest weekly-like run is older than 14 days"

    return {
        "items": [
            job_item(
                key="telegram-active-daily-summary",
                label="Telegram active daily summary",
                event=active_summary,
                note_when_missing="no active daily summary persisted yet",
            ),
            job_item(
                key="telegram-passive-daily-summary",
                label="Telegram passive daily summary",
                event=passive_summary,
                note_when_missing="no passive daily summary persisted yet",
            ),
            {
                "key": "weekly-agent-batch",
                "label": "Weekly agent batch",
                "status": weekly_status,
                "note": weekly_note,
                "last_run_at": weekly_last_run,
                "last_success_at": weekly_last_run if weekly_status == "ok" else None,
                "signal_source": "runs",
            },
        ]
    }


@router.get("/system/integrations")
def get_dashboard_system_integrations(conn: psycopg.Connection = Depends(get_db)):
    health = get_health_summary(conn)
    telegram_last = latest_notification_event(conn, channel="telegram")
    langfuse_last = latest_langfuse_activity(conn)

    telegram_note = health["telegram_bot"]["note"]
    telegram_status = health["telegram_bot"]["status"]
    telegram_last_activity = telegram_last.get("created_at") if telegram_last else None
    telegram_last_success = (
        (telegram_last.get("delivered_at") or telegram_last.get("created_at"))
        if telegram_last and telegram_last.get("delivery_status") == "delivered"
        else None
    )
    if telegram_last is not None:
        telegram_status = "ok" if telegram_last.get("delivery_status") == "delivered" else "degraded"
        telegram_note = telegram_last.get("summary") or telegram_note

    langfuse_note = health["langfuse"]["note"]
    if langfuse_last is not None:
        langfuse_note = (
            summarize_text(langfuse_last.get("summary"), max_length=96)
            or health["langfuse"]["note"]
            or "latest traced/fallback run"
        )

    return {
        "items": [
            {
                "key": "langfuse",
                "label": "Langfuse",
                "status": health["langfuse"]["status"],
                "note": langfuse_note,
                "last_activity_at": langfuse_last.get("started_at") if langfuse_last else None,
                "last_success_at": (
                    langfuse_last.get("started_at")
                    if langfuse_last and langfuse_last.get("langfuse_trace_id")
                    else None
                ),
                "signal_source": "runs",
            },
            {
                "key": "telegram",
                "label": "Telegram",
                "status": telegram_status,
                "note": telegram_note,
                "last_activity_at": telegram_last_activity,
                "last_success_at": telegram_last_success,
                "signal_source": "notification_events",
            },
            {
                "key": "cron_scheduler",
                "label": "Cron scheduler",
                "status": health["cron_scheduler"]["status"],
                "note": health["cron_scheduler"]["note"],
                "last_activity_at": None,
                "last_success_at": None,
                "signal_source": "health",
            },
        ]
    }


@router.post("/actions/run-agent")
def dashboard_run_agent(
    payload: AgentRunRequest,
    conn: psycopg.Connection = Depends(get_db),
):
    result = run_unified_agent(
        conn,
        target_type=payload.target_type,
        target_id=payload.target_id,
        prompt_ref=payload.prompt_ref,
    )
    return {
        "target_type": result.target_type,
        "target_id": result.target_id,
        "report_type": result.report_type,
        "summary": result.summary,
        "run": result.run,
        "report": result.report,
    }


@router.post("/actions/resolve-handoff")
def dashboard_resolve_handoff(
    payload: DashboardResolveHandoff,
    conn: psycopg.Connection = Depends(get_db),
):
    handoff = fetch_one(conn, "SELECT * FROM handoffs WHERE id = %s", (payload.handoff_id,))
    if handoff is None:
        raise HTTPException(status_code=404, detail=f"Handoff '{payload.handoff_id}' not found")
    if handoff["status"] == "resolved":
        raise HTTPException(status_code=409, detail=f"Handoff '{payload.handoff_id}' is already resolved")

    message = handoff.get("message")
    if payload.resolution_note:
        message = (
            f"{message}\n\nResolution note: {payload.resolution_note}"
            if message
            else f"Resolution note: {payload.resolution_note}"
        )

    resolved = update_row(
        conn,
        "handoffs",
        {"id": payload.handoff_id},
        {
            "status": "resolved",
            "resolved_at": utc_now(),
            "message": message,
        },
    )
    if resolved is None:
        raise HTTPException(status_code=404, detail=f"Handoff '{payload.handoff_id}' not found")
    return serialize_handoff(resolved)


@router.post("/actions/requeue")
def dashboard_requeue(
    payload: DashboardRequeueRequest,
    conn: psycopg.Connection = Depends(get_db),
):
    queue_item = fetch_one(conn, "SELECT * FROM research_queue WHERE id = %s", (payload.queue_id,))
    if queue_item is None:
        raise HTTPException(status_code=404, detail=f"Research queue item '{payload.queue_id}' not found")

    scheduled_for = queue_item["scheduled_for"]
    if isinstance(payload.scheduled_for, datetime):
        scheduled_for = payload.scheduled_for.date()
    elif isinstance(payload.scheduled_for, date):
        scheduled_for = payload.scheduled_for

    updated = update_row(
        conn,
        "research_queue",
        {"id": payload.queue_id},
        {
            "status": "pending",
            "scheduled_for": scheduled_for,
            "notes": payload.notes if payload.notes is not None else queue_item.get("notes"),
        },
    )
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Research queue item '{payload.queue_id}' not found")
    return serialize_research_queue_item(updated)

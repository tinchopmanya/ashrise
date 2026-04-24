from collections.abc import Generator

from fastapi import HTTPException
import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.config import get_settings


JSON_COLUMNS = {
    "projects": {"metadata"},
    "project_state": {"blockers", "open_questions", "extra"},
    "runs": {"files_touched", "diff_stats", "metadata"},
    "handoffs": {"context_refs"},
    "decisions": {"alternatives", "metadata"},
    "audit_reports": {"findings", "proposed_changes", "evidence_refs", "state_snapshot", "metadata"},
    "ideas": set(),
    "tasks": set(),
    "vertical_candidates": {"kill_criteria", "kill_verdict", "metadata"},
    "candidate_research_reports": {
        "competitors_found",
        "market_signals",
        "stack_findings",
        "kill_criteria_hits",
        "sub_gap_proposals",
        "proposed_next_steps",
        "evidence_refs",
        "candidate_snapshot",
        "metadata",
    },
    "research_queue": set(),
    "notification_events": {"payload_summary"},
}


def get_db() -> Generator[psycopg.Connection, None, None]:
    settings = get_settings()
    with psycopg.connect(settings.database_url, row_factory=dict_row) as conn:
        yield conn


def fetch_one(
    conn: psycopg.Connection,
    query: str | sql.SQL,
    params: tuple | list | None = None,
):
    return conn.execute(query, params or ()).fetchone()


def fetch_all(
    conn: psycopg.Connection,
    query: str | sql.SQL,
    params: tuple | list | None = None,
):
    return conn.execute(query, params or ()).fetchall()


def adapt_value(table: str, column: str, value):
    if value is None:
        return None

    if column in JSON_COLUMNS.get(table, set()):
        return Jsonb(value)

    return value


def select_row(conn: psycopg.Connection, table: str, key_fields: dict[str, object]):
    where_sql = sql.SQL(" AND ").join(
        sql.SQL("{} = {}").format(sql.Identifier(column), sql.Placeholder())
        for column in key_fields
    )
    query = sql.SQL("SELECT * FROM {} WHERE {}").format(sql.Identifier(table), where_sql)
    return fetch_one(conn, query, list(key_fields.values()))


def insert_row(conn: psycopg.Connection, table: str, data: dict[str, object]):
    columns = list(data.keys())
    query = sql.SQL("INSERT INTO {} ({}) VALUES ({}) RETURNING *").format(
        sql.Identifier(table),
        sql.SQL(", ").join(sql.Identifier(column) for column in columns),
        sql.SQL(", ").join(sql.Placeholder() for _ in columns),
    )
    params = [adapt_value(table, column, data[column]) for column in columns]
    return fetch_one(conn, query, params)


def update_row(
    conn: psycopg.Connection,
    table: str,
    key_fields: dict[str, object],
    data: dict[str, object],
):
    if not data:
        return select_row(conn, table, key_fields)

    set_sql = sql.SQL(", ").join(
        sql.SQL("{} = {}").format(sql.Identifier(column), sql.Placeholder())
        for column in data
    )
    where_sql = sql.SQL(" AND ").join(
        sql.SQL("{} = {}").format(sql.Identifier(column), sql.Placeholder())
        for column in key_fields
    )
    query = sql.SQL("UPDATE {} SET {} WHERE {} RETURNING *").format(
        sql.Identifier(table),
        set_sql,
        where_sql,
    )
    params = [adapt_value(table, column, data[column]) for column in data]
    params.extend(key_fields.values())
    return fetch_one(conn, query, params)


def upsert_project_state(
    conn: psycopg.Connection,
    project_id: str,
    data: dict[str, object],
):
    columns = ["project_id", *data.keys()]
    update_columns = list(data.keys()) or ["project_id"]
    update_sql = sql.SQL(", ").join(
        sql.SQL("{} = EXCLUDED.{}").format(sql.Identifier(column), sql.Identifier(column))
        for column in update_columns
    )
    query = sql.SQL(
        "INSERT INTO project_state ({}) VALUES ({}) "
        "ON CONFLICT (project_id) DO UPDATE SET {} RETURNING *"
    ).format(
        sql.SQL(", ").join(sql.Identifier(column) for column in columns),
        sql.SQL(", ").join(sql.Placeholder() for _ in columns),
        update_sql,
    )
    params = [project_id]
    params.extend(adapt_value("project_state", column, data[column]) for column in data)
    return fetch_one(conn, query, params)


def ensure_project_exists(conn: psycopg.Connection, project_id: str):
    project = fetch_one(conn, "SELECT id FROM projects WHERE id = %s", (project_id,))
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


def ensure_idea_exists(conn: psycopg.Connection, idea_id):
    idea = fetch_one(conn, "SELECT id FROM ideas WHERE id = %s", (idea_id,))
    if idea is None:
        raise HTTPException(status_code=404, detail=f"Idea '{idea_id}' not found")


def ensure_candidate_exists(conn: psycopg.Connection, candidate_id):
    candidate = fetch_one(conn, "SELECT id FROM vertical_candidates WHERE id = %s", (candidate_id,))
    if candidate is None:
        raise HTTPException(status_code=404, detail=f"Candidate '{candidate_id}' not found")


def get_candidate_by_ref(conn: psycopg.Connection, candidate_ref: str):
    candidate = fetch_one(
        conn,
        (
            "SELECT * FROM vertical_candidates "
            "WHERE id::text = %s OR slug = %s "
            "ORDER BY created_at DESC "
            "LIMIT 1"
        ),
        (candidate_ref, candidate_ref),
    )
    if candidate is None:
        raise HTTPException(status_code=404, detail=f"Candidate '{candidate_ref}' not found")

    return candidate

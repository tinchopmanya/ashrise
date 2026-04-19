from datetime import UTC, date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
import psycopg

from app.auth import require_bearer_token
from app.db import (
    ensure_project_exists,
    fetch_all,
    fetch_one,
    get_db,
    insert_row,
    upsert_project_state,
    update_row,
)
from app.schemas import (
    DecisionCreate,
    HandoffCreate,
    HandoffPatch,
    IdeaCreate,
    IdeaPatch,
    ProjectStateUpsert,
    RunCreate,
    RunPatch,
)


router = APIRouter(tags=["operations"], dependencies=[Depends(require_bearer_token)])


def utc_now() -> datetime:
    return datetime.now(UTC)


@router.get("/projects")
def list_projects(
    status: str | None = None,
    kind: str | None = None,
    host_machine: str | None = None,
    conn: psycopg.Connection = Depends(get_db),
):
    clauses: list[str] = []
    params: list[object] = []

    if status:
        clauses.append("status = %s")
        params.append(status)
    if kind:
        clauses.append("kind = %s")
        params.append(kind)
    if host_machine:
        clauses.append("host_machine = %s")
        params.append(host_machine)

    query = "SELECT * FROM projects"
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY priority NULLS LAST, created_at, id"

    return fetch_all(conn, query, params)


@router.get("/projects/{project_id}")
def get_project(project_id: str, conn: psycopg.Connection = Depends(get_db)):
    project = fetch_one(conn, "SELECT * FROM projects WHERE id = %s", (project_id,))
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    parent = None
    if project["parent_id"]:
        parent = fetch_one(conn, "SELECT * FROM projects WHERE id = %s", (project["parent_id"],))

    children = fetch_all(
        conn,
        "SELECT * FROM projects WHERE parent_id = %s ORDER BY created_at, id",
        (project_id,),
    )

    project["parent"] = parent
    project["children"] = children
    return project


@router.get("/state/{project_id}")
def get_project_state(project_id: str, conn: psycopg.Connection = Depends(get_db)):
    ensure_project_exists(conn, project_id)
    state = fetch_one(conn, "SELECT * FROM project_state WHERE project_id = %s", (project_id,))
    if state is None:
        raise HTTPException(status_code=404, detail=f"State for project '{project_id}' not found")

    return state


@router.put("/state/{project_id}")
def put_project_state(
    project_id: str,
    payload: ProjectStateUpsert,
    conn: psycopg.Connection = Depends(get_db),
):
    ensure_project_exists(conn, project_id)
    state = upsert_project_state(conn, project_id, payload.model_dump(exclude_unset=True))
    return state


@router.post("/runs", status_code=201)
def create_run(payload: RunCreate, conn: psycopg.Connection = Depends(get_db)):
    ensure_project_exists(conn, payload.project_id)
    data = payload.model_dump(exclude_unset=True)
    if data.get("status") and data["status"] != "running" and "ended_at" not in data:
        data["ended_at"] = utc_now()
    return insert_row(conn, "runs", data)


@router.patch("/runs/{run_id}")
def patch_run(
    run_id: UUID,
    payload: RunPatch,
    conn: psycopg.Connection = Depends(get_db),
):
    data = payload.model_dump(exclude_unset=True)
    if data.get("status") and data["status"] != "running" and "ended_at" not in data:
        data["ended_at"] = utc_now()

    run = update_row(conn, "runs", {"id": run_id}, data)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

    return run


@router.get("/runs/{project_id}")
def list_runs(
    project_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    conn: psycopg.Connection = Depends(get_db),
):
    ensure_project_exists(conn, project_id)
    return fetch_all(
        conn,
        "SELECT * FROM runs WHERE project_id = %s ORDER BY started_at DESC LIMIT %s",
        (project_id, limit),
    )


@router.post("/handoffs", status_code=201)
def create_handoff(payload: HandoffCreate, conn: psycopg.Connection = Depends(get_db)):
    ensure_project_exists(conn, payload.project_id)
    data = payload.model_dump(exclude_unset=True)
    if data.get("status") and data["status"] != "open" and "resolved_at" not in data:
        data["resolved_at"] = utc_now()
    return insert_row(conn, "handoffs", data)


@router.get("/handoffs/{project_id}")
def list_handoffs(
    project_id: str,
    status: str = "open",
    conn: psycopg.Connection = Depends(get_db),
):
    ensure_project_exists(conn, project_id)
    return fetch_all(
        conn,
        "SELECT * FROM handoffs WHERE project_id = %s AND status = %s ORDER BY created_at DESC",
        (project_id, status),
    )


@router.patch("/handoffs/{handoff_id}")
def patch_handoff(
    handoff_id: UUID,
    payload: HandoffPatch,
    conn: psycopg.Connection = Depends(get_db),
):
    data = payload.model_dump(exclude_unset=True)
    if data.get("status") and data["status"] != "open" and "resolved_at" not in data:
        data["resolved_at"] = utc_now()

    handoff = update_row(conn, "handoffs", {"id": handoff_id}, data)
    if handoff is None:
        raise HTTPException(status_code=404, detail=f"Handoff '{handoff_id}' not found")

    return handoff


@router.post("/decisions", status_code=201)
def create_decision(payload: DecisionCreate, conn: psycopg.Connection = Depends(get_db)):
    ensure_project_exists(conn, payload.project_id)
    return insert_row(conn, "decisions", payload.model_dump(exclude_unset=True))


@router.get("/decisions/{project_id}")
def list_decisions(project_id: str, conn: psycopg.Connection = Depends(get_db)):
    ensure_project_exists(conn, project_id)
    return fetch_all(
        conn,
        "SELECT * FROM decisions WHERE project_id = %s ORDER BY created_at DESC",
        (project_id,),
    )


@router.get("/audit/{project_id}")
def get_latest_audit(project_id: str, conn: psycopg.Connection = Depends(get_db)):
    ensure_project_exists(conn, project_id)
    return fetch_one(
        conn,
        "SELECT * FROM audit_reports WHERE project_id = %s ORDER BY created_at DESC LIMIT 1",
        (project_id,),
    )


@router.post("/ideas", status_code=201)
def create_idea(payload: IdeaCreate, conn: psycopg.Connection = Depends(get_db)):
    data = payload.model_dump(exclude_unset=True)
    if data.get("project_id"):
        ensure_project_exists(conn, data["project_id"])
    if data.get("status") and data["status"] != "new" and "triaged_at" not in data:
        data["triaged_at"] = utc_now()
    return insert_row(conn, "ideas", data)


@router.get("/ideas")
def list_ideas(
    status: str | None = "new",
    conn: psycopg.Connection = Depends(get_db),
):
    if status is None:
        return fetch_all(conn, "SELECT * FROM ideas ORDER BY created_at DESC")

    return fetch_all(
        conn,
        "SELECT * FROM ideas WHERE status = %s ORDER BY created_at DESC",
        (status,),
    )


@router.patch("/ideas/{idea_id}")
def patch_idea(
    idea_id: UUID,
    payload: IdeaPatch,
    conn: psycopg.Connection = Depends(get_db),
):
    data = payload.model_dump(exclude_unset=True)
    if data.get("project_id"):
        ensure_project_exists(conn, data["project_id"])
    if data.get("status") and data["status"] != "new" and "triaged_at" not in data:
        data["triaged_at"] = utc_now()

    idea = update_row(conn, "ideas", {"id": idea_id}, data)
    if idea is None:
        raise HTTPException(status_code=404, detail=f"Idea '{idea_id}' not found")

    return idea

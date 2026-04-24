from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
import psycopg

from app.auth import require_bearer_token
from app.db import (
    ensure_candidate_exists,
    ensure_idea_exists,
    ensure_project_exists,
    fetch_all,
    fetch_one,
    get_db,
    insert_row,
    update_row,
)
from app.schemas import TaskCreate, TaskPatch


router = APIRouter(tags=["tasks"], dependencies=[Depends(require_bearer_token)])
STATUS_ORDER_SQL = """
CASE status
    WHEN 'backlog' THEN 0
    WHEN 'ready' THEN 1
    WHEN 'progress' THEN 2
    WHEN 'blocked' THEN 3
    WHEN 'done' THEN 4
    ELSE 5
END
"""


def utc_now() -> datetime:
    return datetime.now(UTC)


def serialize_task(row: dict[str, object]) -> dict[str, object]:
    return {
        **row,
        "id": str(row["id"]),
        "idea_id": str(row["idea_id"]) if row.get("idea_id") is not None else None,
        "candidate_id": str(row["candidate_id"]) if row.get("candidate_id") is not None else None,
        "tags": row.get("tags") or [],
    }


def get_task_row(conn: psycopg.Connection, task_id: UUID):
    return fetch_one(
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
        WHERE id = %s
        """,
        (task_id,),
    )


def task_scope(row: dict[str, object]) -> tuple[UUID | None, str | None, UUID | None]:
    return (
        row.get("idea_id"),
        row.get("project_id"),
        row.get("candidate_id"),
    )


def validate_task_links(
    conn: psycopg.Connection,
    *,
    idea_id: UUID | None,
    project_id: str | None,
    candidate_id: UUID | None,
) -> None:
    if not any([idea_id, project_id, candidate_id]):
        raise HTTPException(
            status_code=422,
            detail="at least one of idea_id, project_id or candidate_id is required",
        )

    if idea_id is not None:
        ensure_idea_exists(conn, idea_id)
    if project_id is not None:
        ensure_project_exists(conn, project_id)
    if candidate_id is not None:
        ensure_candidate_exists(conn, candidate_id)


def apply_status_side_effects(data: dict[str, object], *, current: dict[str, object] | None = None) -> None:
    status = data.get("status")
    if status is None:
        return

    if status == "done":
        if current and current.get("status") == "done" and current.get("closed_at") is not None:
            data["closed_at"] = current["closed_at"]
        else:
            data["closed_at"] = utc_now()
    else:
        data["closed_at"] = None


def normalize_status_positions(
    conn: psycopg.Connection,
    *,
    status: str,
    idea_id: UUID | None,
    project_id: str | None,
    candidate_id: UUID | None,
    preferred_task_id: UUID | str | None = None,
    preferred_position: int | None = None,
) -> None:
    rows = fetch_all(
        conn,
        """
        SELECT id
        FROM tasks
        WHERE status = %s
          AND idea_id IS NOT DISTINCT FROM %s
          AND project_id IS NOT DISTINCT FROM %s
          AND candidate_id IS NOT DISTINCT FROM %s
        ORDER BY position, created_at, id
        """,
        (status, idea_id, project_id, candidate_id),
    )
    ordered_ids = [row["id"] for row in rows]
    if preferred_task_id is not None and preferred_task_id in ordered_ids:
        ordered_ids.remove(preferred_task_id)
        target_index = preferred_position if preferred_position is not None else len(ordered_ids)
        bounded_index = max(0, min(target_index, len(ordered_ids)))
        ordered_ids.insert(bounded_index, preferred_task_id)

    for index, task_id in enumerate(ordered_ids):
        conn.execute("UPDATE tasks SET position = %s WHERE id = %s", (index, task_id))


@router.get("/tasks")
def list_tasks(
    idea_id: UUID | None = None,
    project_id: str | None = None,
    candidate_id: UUID | None = None,
    status: str | None = None,
    limit: int = 100,
    conn: psycopg.Connection = Depends(get_db),
):
    clauses: list[str] = []
    params: list[object] = []

    if idea_id is not None:
        clauses.append("idea_id = %s")
        params.append(idea_id)
    if project_id is not None:
        clauses.append("project_id = %s")
        params.append(project_id)
    if candidate_id is not None:
        clauses.append("candidate_id = %s")
        params.append(candidate_id)
    if status is not None:
        clauses.append("status = %s")
        params.append(status)

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(min(max(limit, 1), 200))
    rows = fetch_all(
        conn,
        f"""
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
        {where_sql}
        ORDER BY {STATUS_ORDER_SQL}, position, created_at, id
        LIMIT %s
        """,
        params,
    )
    return [serialize_task(row) for row in rows]


@router.get("/tasks/{task_id}")
def get_task(task_id: UUID, conn: psycopg.Connection = Depends(get_db)):
    row = get_task_row(conn, task_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    return serialize_task(row)


@router.post("/tasks", status_code=201)
def create_task(payload: TaskCreate, conn: psycopg.Connection = Depends(get_db)):
    validate_task_links(
        conn,
        idea_id=payload.idea_id,
        project_id=payload.project_id,
        candidate_id=payload.candidate_id,
    )

    data = payload.model_dump(exclude_unset=True)
    status = data.get("status", "backlog")
    preferred_position = data.get("position")
    if preferred_position is None:
        tail_row = fetch_one(conn, "SELECT COUNT(*) AS total FROM tasks WHERE status = %s", (status,))
        data["position"] = tail_row["total"]
    data["updated_at"] = utc_now()
    apply_status_side_effects(data)

    row = insert_row(conn, "tasks", data)
    normalize_status_positions(
        conn,
        status=row["status"],
        idea_id=row["idea_id"],
        project_id=row["project_id"],
        candidate_id=row["candidate_id"],
        preferred_task_id=row["id"],
        preferred_position=row["position"],
    )
    row = get_task_row(conn, row["id"])
    return serialize_task(row)


@router.patch("/tasks/{task_id}")
def patch_task(task_id: UUID, payload: TaskPatch, conn: psycopg.Connection = Depends(get_db)):
    current = get_task_row(conn, task_id)
    if current is None:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")

    data = payload.model_dump(exclude_unset=True)
    merged_idea_id = data.get("idea_id", current["idea_id"])
    merged_project_id = data.get("project_id", current["project_id"])
    merged_candidate_id = data.get("candidate_id", current["candidate_id"])
    validate_task_links(
        conn,
        idea_id=merged_idea_id,
        project_id=merged_project_id,
        candidate_id=merged_candidate_id,
    )

    data["updated_at"] = utc_now()
    apply_status_side_effects(data, current=current)
    row = update_row(conn, "tasks", {"id": task_id}, data)
    current_scope = task_scope(current)
    row_scope = task_scope(row)
    if current["status"] != row["status"] or current_scope != row_scope:
        normalize_status_positions(
            conn,
            status=current["status"],
            idea_id=current_scope[0],
            project_id=current_scope[1],
            candidate_id=current_scope[2],
        )
        normalize_status_positions(
            conn,
            status=row["status"],
            idea_id=row_scope[0],
            project_id=row_scope[1],
            candidate_id=row_scope[2],
            preferred_task_id=row["id"],
            preferred_position=row["position"],
        )
    elif "position" in data:
        normalize_status_positions(
            conn,
            status=row["status"],
            idea_id=row_scope[0],
            project_id=row_scope[1],
            candidate_id=row_scope[2],
            preferred_task_id=row["id"],
            preferred_position=row["position"],
        )
    row = get_task_row(conn, task_id)
    return serialize_task(row)


@router.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: UUID, conn: psycopg.Connection = Depends(get_db)):
    current = get_task_row(conn, task_id)
    if current is None:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")

    deleted = fetch_one(conn, "DELETE FROM tasks WHERE id = %s RETURNING id", (task_id,))
    if deleted is None:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    current_scope = task_scope(current)
    normalize_status_positions(
        conn,
        status=current["status"],
        idea_id=current_scope[0],
        project_id=current_scope[1],
        candidate_id=current_scope[2],
    )
    return Response(status_code=204)

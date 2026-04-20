from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
import psycopg

from app.auth import require_bearer_token
from app.db import (
    ensure_project_exists,
    fetch_all,
    fetch_one,
    get_candidate_by_ref,
    get_db,
    insert_row,
    update_row,
    upsert_project_state,
)
from app.schemas import CandidateCreate, CandidatePatch, CandidatePromotionRequest, ResearchQueuePatch


router = APIRouter(tags=["research"], dependencies=[Depends(require_bearer_token)])


@router.get("/candidates")
def list_candidates(
    status: str | None = None,
    category: str | None = None,
    parent_group: str | None = None,
    conn: psycopg.Connection = Depends(get_db),
):
    clauses: list[str] = []
    params: list[object] = []

    if status:
        clauses.append("status = %s")
        params.append(status)
    if category:
        clauses.append("category = %s")
        params.append(category)
    if parent_group:
        clauses.append("parent_group = %s")
        params.append(parent_group)

    query = "SELECT * FROM vertical_candidates"
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY created_at DESC, slug"

    return fetch_all(conn, query, params)


@router.post("/candidates", status_code=201)
def create_candidate(payload: CandidateCreate, conn: psycopg.Connection = Depends(get_db)):
    return insert_row(conn, "vertical_candidates", payload.model_dump(exclude_unset=True))


@router.get("/candidates/{candidate_ref}")
def get_candidate(candidate_ref: str, conn: psycopg.Connection = Depends(get_db)):
    return get_candidate_by_ref(conn, candidate_ref)


@router.patch("/candidates/{candidate_ref}")
def patch_candidate(
    candidate_ref: str,
    payload: CandidatePatch,
    conn: psycopg.Connection = Depends(get_db),
):
    candidate = get_candidate_by_ref(conn, candidate_ref)
    updated = update_row(
        conn,
        "vertical_candidates",
        {"id": candidate["id"]},
        payload.model_dump(exclude_unset=True),
    )
    return updated


@router.get("/candidates/{candidate_ref}/research")
def get_candidate_research(candidate_ref: str, conn: psycopg.Connection = Depends(get_db)):
    candidate = get_candidate_by_ref(conn, candidate_ref)
    return fetch_one(
        conn,
        (
            "SELECT * FROM candidate_research_reports "
            "WHERE candidate_id = %s "
            "ORDER BY created_at DESC "
            "LIMIT 1"
        ),
        (candidate["id"],),
    )


@router.get("/research-queue")
def get_research_queue(
    due: str | None = Query(default=None),
    conn: psycopg.Connection = Depends(get_db),
):
    query = "SELECT * FROM research_queue"
    clauses: list[str] = []
    params: list[object] = []

    if due == "today":
        clauses.append("scheduled_for <= %s")
        params.append(date.today())
        clauses.append("status = 'pending'")
    elif due:
        clauses.append("scheduled_for <= %s")
        params.append(date.fromisoformat(due))

    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY scheduled_for, priority, created_at"

    return fetch_all(conn, query, params)


@router.patch("/research-queue/{queue_id}")
def patch_research_queue(
    queue_id: str,
    payload: ResearchQueuePatch,
    conn: psycopg.Connection = Depends(get_db),
):
    queue_item = update_row(
        conn,
        "research_queue",
        {"id": queue_id},
        payload.model_dump(exclude_unset=True),
    )
    if queue_item is None:
        raise HTTPException(status_code=404, detail=f"Research queue item '{queue_id}' not found")
    return queue_item


@router.post("/candidates/{candidate_ref}/promote", status_code=201)
def promote_candidate(
    candidate_ref: str,
    payload: CandidatePromotionRequest,
    conn: psycopg.Connection = Depends(get_db),
):
    candidate = get_candidate_by_ref(conn, candidate_ref)
    if candidate.get("status") == "promoted":
        raise HTTPException(status_code=409, detail=f"Candidate '{candidate_ref}' is already promoted")

    existing_project = fetch_one(conn, "SELECT id FROM projects WHERE id = %s", (payload.project_id,))
    if existing_project is not None:
        raise HTTPException(status_code=409, detail=f"Project '{payload.project_id}' already exists")

    promotion = dict(candidate.get("metadata") or {}).get("promotion") or {}
    if not promotion.get("ready"):
        raise HTTPException(
            status_code=409,
            detail=f"Candidate '{candidate_ref}' is not ready for promotion yet",
        )

    if payload.parent_id:
        ensure_project_exists(conn, payload.parent_id)
    elif candidate.get("parent_group"):
        ensure_project_exists(conn, candidate["parent_group"])

    project = insert_row(
        conn,
        "projects",
        {
            "id": payload.project_id,
            "name": payload.name or candidate["name"],
            "kind": payload.kind,
            "parent_id": payload.parent_id if payload.parent_id is not None else candidate.get("parent_group"),
            "repo_url": payload.repo_url,
            "repo_path": payload.repo_path,
            "worktree_path": payload.worktree_path,
            "host_machine": payload.host_machine,
            "status": "active",
            "priority": payload.priority if payload.priority is not None else candidate.get("priority"),
            "importance": payload.importance if payload.importance is not None else candidate.get("importance"),
            "size_scope": payload.size_scope if payload.size_scope is not None else candidate.get("estimated_size"),
            "progress_pct": payload.progress_pct if payload.progress_pct is not None else 0,
            "promoted_from_candidate_id": candidate["id"],
            "metadata": {
                **(payload.metadata or {}),
                "source_candidate_slug": candidate["slug"],
                "source_candidate_id": str(candidate["id"]),
            },
        },
    )

    candidate_metadata = dict(candidate.get("metadata") or {})
    candidate_metadata["promotion"] = {
        **promotion,
        "approved": True,
        "approved_at": datetime.now(UTC).isoformat(),
        "project_id": project["id"],
    }

    updated_candidate = update_row(
        conn,
        "vertical_candidates",
        {"id": candidate["id"]},
        {
            "status": "promoted",
            "promoted_to_project_id": project["id"],
            "metadata": candidate_metadata,
        },
    )
    assert updated_candidate is not None

    upsert_project_state(
        conn,
        project["id"],
        {
            "current_focus": f"Kickoff from candidate {candidate['slug']}",
            "current_milestone": "Sprint 5",
            "next_step": "Run first implementation or audit session for the promoted project.",
            "project_state_code": 1,
            "extra": {"promoted_from_candidate_id": str(candidate["id"])},
        },
    )

    return {
        "project": project,
        "candidate": updated_candidate,
        "message": f"Candidate '{candidate['slug']}' promoted to project '{project['id']}'",
    }

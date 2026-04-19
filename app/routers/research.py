from datetime import date

from fastapi import APIRouter, Depends, Query
import psycopg

from app.auth import require_bearer_token
from app.db import fetch_all, fetch_one, get_candidate_by_ref, get_db, insert_row, update_row
from app.schemas import CandidateCreate, CandidatePatch


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

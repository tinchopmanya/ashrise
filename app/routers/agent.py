from fastapi import APIRouter, Depends
import psycopg

from app.auth import require_bearer_token
from app.db import get_db
from app.schemas import AgentRunRequest
from ashrise.unified_agent import run_unified_agent


router = APIRouter(tags=["agent"], dependencies=[Depends(require_bearer_token)])


@router.post("/agent/run")
def run_agent(
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


"""AI Query router — LCARS computer RAG interface."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from fitness.auth import current_active_user
from fitness.security import limiter
from fitness.services.rag_service import RagResponse, rag_service

logger = logging.getLogger(__name__)

# current_active_user is the admin gate for this personal portfolio app
require_admin = current_active_user

router = APIRouter(
    prefix="/admin/computer",
    tags=["ai-query"],
    dependencies=[Depends(require_admin)],
)


class QueryRequest(BaseModel):
    """Inbound question payload."""

    question: str


@router.post("/query", response_model=RagResponse)
@limiter.limit("5/minute")
async def computer_query(request: Request, payload: QueryRequest) -> RagResponse:
    """Submit a question to the ship's computer (RAG pipeline).

    The LCARS computer embeds the question, performs hybrid search against
    the witness-data index, and returns a grounded Starfleet briefing with
    source citations.
    """
    if not payload.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    try:
        return await rag_service.query(payload.question.strip())
    except Exception as exc:
        logger.exception("Computer query failed")
        raise HTTPException(
            status_code=500,
            detail="The main computer encountered an error processing your query.",
        ) from exc

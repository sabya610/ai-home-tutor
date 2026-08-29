"""Tutor endpoints: list tutor modes and explain a concept at the child's level."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from .. import db
from ..ai_client import get_ai_client
from ..config import get_settings
from ..schemas import (
    ExplainIn,
    ExplainOut,
    TeachMeIn,
    TeachMeResult,
    TeachMeTurnIn,
    TeachMeTurnResult,
)

router = APIRouter(prefix="/api/tutor", tags=["tutor"])


def _transcript_text(turns) -> str:
    return "\n".join(f"{t.speaker}: {t.text}" for t in turns)


@router.get("/modes")
def tutor_modes() -> dict:
    """Tutor providers the UI toggle can pick from (names + labels + default)."""
    return get_ai_client().tutor_modes()


@router.post("/explain", response_model=ExplainOut)
def explain(payload: ExplainIn) -> ExplainOut:
    text = get_ai_client().explain(payload.topic, payload.grade_level, mode=payload.tutor_mode)
    resolved = get_settings().resolve_tutor_mode(payload.tutor_mode)
    return ExplainOut(topic=payload.topic, explanation=text, tutor_mode=resolved)


@router.post("/explain/stream")
def explain_stream(payload: ExplainIn) -> StreamingResponse:
    """Same as /explain but streams the answer token-by-token (lower perceived latency)."""
    resolved = get_settings().resolve_tutor_mode(payload.tutor_mode)
    tokens = get_ai_client().explain_stream(
        payload.topic, payload.grade_level, mode=payload.tutor_mode
    )
    return StreamingResponse(
        tokens,
        media_type="text/plain; charset=utf-8",
        headers={
            "X-Tutor-Mode": resolved,
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/teachme", response_model=TeachMeResult)
def teachme(payload: TeachMeIn) -> TeachMeResult:
    """Assess whether the child's spoken explanation shows real understanding."""
    if not payload.explanation.strip():
        raise HTTPException(status_code=400, detail="explanation is required")
    result = get_ai_client().assess_understanding(
        payload.question,
        payload.answer,
        payload.explanation,
        payload.grade_level,
        mode=payload.tutor_mode,
    )
    score = int(result.get("score", 0))
    attempt_id = db.add_attempt(
        student_id=payload.student_id,
        mode="teachme",
        topic="teach-me",
        expected=payload.question,
        recognized=payload.explanation,
        score=float(score),
        max_score=10,
        details=result,
    )
    return TeachMeResult(
        understands=bool(result.get("understands", False)),
        verdict=result.get("verdict", ""),
        feedback=result.get("feedback", ""),
        followup=result.get("followup", ""),
        score=score,
        max_score=10,
        tutor_mode=result.get("tutor_mode", ""),
        attempt_id=attempt_id,
    )


@router.post("/teachme/turn", response_model=TeachMeTurnResult)
def teachme_turn(payload: TeachMeTurnIn) -> TeachMeTurnResult:
    """One turn of a back-and-forth 'teach me' dialogue (stateless)."""
    child_turns = [t for t in payload.turns if t.speaker == "child"]
    if not child_turns or not child_turns[-1].text.strip():
        raise HTTPException(status_code=400, detail="a child explanation turn is required")
    result = get_ai_client().converse_teachme(
        payload.question,
        payload.answer,
        [t.model_dump() for t in payload.turns],
        payload.grade_level,
        mode=payload.tutor_mode,
    )
    score = int(result.get("score", 0))
    attempt_id = None
    if result.get("done"):
        attempt_id = db.add_attempt(
            student_id=payload.student_id,
            mode="teachme",
            topic="teach-me-chat",
            expected=payload.question,
            recognized=_transcript_text(payload.turns),
            score=float(score),
            max_score=10,
            details=result,
        )
    return TeachMeTurnResult(
        understands=bool(result.get("understands", False)),
        done=bool(result.get("done", False)),
        feedback=result.get("feedback", ""),
        followup=result.get("followup", ""),
        score=score,
        max_score=10,
        turn_count=len(child_turns),
        tutor_mode=result.get("tutor_mode", ""),
        attempt_id=attempt_id,
    )

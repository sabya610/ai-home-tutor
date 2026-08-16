"""Homework checker: read a page, find the mistake, give a hint and a score."""

from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from .. import db
from ..ai_client import get_ai_client
from ..schemas import HomeworkResult
from ..vision import image_to_text

router = APIRouter(prefix="/api/homework", tags=["homework"])


@router.post("/check", response_model=HomeworkResult)
async def check_homework(
    question: str = Form(""),
    topic: str = Form("homework"),
    grade_level: int = Form(3),
    student_id: int | None = Form(None),
    recognized_text: str | None = Form(None),
    tutor_mode: str = Form("auto"),
    image: UploadFile | None = File(None),
) -> HomeworkResult:
    ai = get_ai_client()
    if recognized_text is not None:
        recognized = recognized_text
    elif image is not None:
        recognized = image_to_text(
            await image.read(), ai, mime=image.content_type or "image/jpeg"
        )
    else:
        raise HTTPException(
            status_code=400, detail="provide an image or recognized_text"
        )

    result = ai.evaluate_homework(question, recognized, grade_level, mode=tutor_mode)
    score = int(result.get("score", 0))
    attempt_id = db.add_attempt(
        student_id=student_id,
        mode="homework",
        topic=topic,
        expected=question,
        recognized=recognized,
        score=float(score),
        max_score=10,
        details=result,
    )
    return HomeworkResult(
        is_correct=bool(result.get("is_correct", False)),
        verdict=result.get("verdict", ""),
        recognized=recognized,
        mistake=result.get("mistake", ""),
        hint=result.get("hint", ""),
        score=score,
        max_score=10,
        explanation=result.get("explanation", ""),
        next_step=result.get("next_step", ""),
        tutor_mode=result.get("tutor_mode", ""),
        attempt_id=attempt_id,
    )

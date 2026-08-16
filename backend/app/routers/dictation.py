"""Dictation tutor: serve a sentence, then grade the child's handwriting."""

from __future__ import annotations

import random

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from .. import db
from ..ai_client import get_ai_client
from ..evaluator import score_dictation
from ..schemas import DictationResult, DictationSentence
from ..vision import image_to_text

router = APIRouter(prefix="/api/dictation", tags=["dictation"])

# Small starter sentence bank keyed by difficulty level.
_SENTENCES: dict[int, list[str]] = {
    1: [
        "The sun is very hot.",
        "My dog likes to run.",
        "We play in the park.",
        "I can see a red ball.",
    ],
    2: [
        "The quick brown fox jumps over the lazy dog.",
        "She sells seashells by the seashore.",
        "Please bring your book to class tomorrow.",
        "The busy bees buzzed around the bright flowers.",
    ],
    3: [
        "Curiosity leads to wonderful discoveries every single day.",
        "The ancient castle stood quietly beneath the silver moon.",
        "Reading carefully helps you understand difficult questions.",
        "Kindness and patience make learning enjoyable for everyone.",
    ],
}


@router.get("/new", response_model=DictationSentence)
def new_sentence(level: int = 1) -> DictationSentence:
    level = max(1, min(level, 3))
    return DictationSentence(sentence=random.choice(_SENTENCES[level]), level=level)


@router.post("/check", response_model=DictationResult)
async def check_dictation(
    expected: str = Form(...),
    student_id: int | None = Form(None),
    recognized_text: str | None = Form(None),
    image: UploadFile | None = File(None),
) -> DictationResult:
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

    score = score_dictation(expected, recognized)
    attempt_id = db.add_attempt(
        student_id=student_id,
        mode="dictation",
        topic="dictation",
        expected=expected,
        recognized=recognized,
        score=score.overall_score,
        max_score=10,
        details=score.to_dict(),
    )
    return DictationResult(attempt_id=attempt_id, **score.to_dict())

"""Pydantic response/request schemas for the API."""

from __future__ import annotations

from pydantic import BaseModel


class StudentIn(BaseModel):
    name: str
    grade_level: int = 3
    tutor_mode: str = "auto"


class Student(BaseModel):
    id: int
    name: str
    grade_level: int = 3
    tutor_mode: str = "auto"


class StudentTutorMode(BaseModel):
    tutor_mode: str


class DictationSentence(BaseModel):
    sentence: str
    level: int


class Mistake(BaseModel):
    type: str
    expected: str | None = None
    got: str | None = None


class DictationResult(BaseModel):
    expected: str
    recognized: str
    total_words: int
    correct_words: int
    missing_words: int
    extra_words: int
    misspelled_words: int
    capitalization_errors: int
    punctuation_errors: int
    spelling_score: float
    overall_score: float
    accuracy: float
    mistakes: list[Mistake]
    feedback: str
    attempt_id: int | None = None


class HomeworkResult(BaseModel):
    is_correct: bool
    verdict: str
    recognized: str
    mistake: str = ""
    hint: str = ""
    score: int = 0
    max_score: int = 10
    explanation: str = ""
    next_step: str = ""
    tutor_mode: str = ""
    attempt_id: int | None = None


class ExplainIn(BaseModel):
    topic: str
    grade_level: int = 3
    tutor_mode: str = "auto"


class ExplainOut(BaseModel):
    topic: str
    explanation: str
    tutor_mode: str = ""


class TeachMeIn(BaseModel):
    answer: str
    explanation: str
    question: str = ""
    grade_level: int = 3
    tutor_mode: str = "auto"
    student_id: int | None = None


class TeachMeResult(BaseModel):
    understands: bool
    verdict: str
    feedback: str = ""
    followup: str = ""
    score: int = 0
    max_score: int = 10
    tutor_mode: str = ""
    attempt_id: int | None = None


class TeachMeTurn(BaseModel):
    speaker: str  # "tutor" | "child"
    text: str


class TeachMeTurnIn(BaseModel):
    turns: list[TeachMeTurn]
    question: str = ""
    answer: str = ""
    grade_level: int = 3
    tutor_mode: str = "auto"
    student_id: int | None = None


class TeachMeTurnResult(BaseModel):
    understands: bool
    done: bool
    feedback: str = ""
    followup: str = ""
    score: int = 0
    max_score: int = 10
    turn_count: int = 0
    tutor_mode: str = ""
    attempt_id: int | None = None

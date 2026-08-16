"""Student profile and progress endpoints."""

from fastapi import APIRouter, HTTPException

from .. import db
from ..config import get_settings
from ..schemas import Student, StudentIn, StudentTutorMode

router = APIRouter(prefix="/api/students", tags=["students"])


@router.get("", response_model=list[Student])
def list_students() -> list[dict]:
    return db.list_students()


@router.post("", response_model=Student, status_code=201)
def create_student(payload: StudentIn) -> dict:
    return db.add_student(payload.name, payload.grade_level, payload.tutor_mode)


@router.put("/{student_id}/tutor-mode", response_model=Student)
def set_tutor_mode(student_id: int, payload: StudentTutorMode) -> dict:
    if not db.get_student(student_id):
        raise HTTPException(status_code=404, detail="student not found")
    allowed = {"auto", *get_settings().tutor_mode_targets().keys()}
    mode = payload.tutor_mode if payload.tutor_mode in allowed else "auto"
    return db.set_student_tutor_mode(student_id, mode)


@router.get("/{student_id}/progress")
def student_progress(student_id: int) -> dict:
    if not db.get_student(student_id):
        raise HTTPException(status_code=404, detail="student not found")
    return db.progress(student_id)

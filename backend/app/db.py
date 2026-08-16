"""SQLite persistence for students, attempts and progress."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .config import get_settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS students (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    grade_level INTEGER NOT NULL DEFAULT 3,
    tutor_mode  TEXT NOT NULL DEFAULT 'auto',
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS attempts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id  INTEGER,
    mode        TEXT NOT NULL,
    topic       TEXT,
    expected    TEXT,
    recognized  TEXT,
    score       REAL,
    max_score   REAL DEFAULT 10,
    details     TEXT,
    created_at  TEXT NOT NULL,
    FOREIGN KEY (student_id) REFERENCES students(id)
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db_file() -> Path:
    return Path(get_settings().db_path)


@contextmanager
def _conn() -> Iterator[sqlite3.Connection]:
    path = _db_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _conn() as conn:
        conn.executescript(_SCHEMA)
        _ensure_columns(conn)


def _ensure_columns(conn: sqlite3.Connection) -> None:
    """Add columns introduced after a DB was first created."""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(students)")}
    if "tutor_mode" not in cols:
        conn.execute(
            "ALTER TABLE students ADD COLUMN tutor_mode TEXT NOT NULL DEFAULT 'auto'"
        )


def add_student(
    name: str, grade_level: int = 3, tutor_mode: str = "auto"
) -> dict[str, Any]:
    with _conn() as conn:
        cur = conn.execute(
            "INSERT INTO students (name, grade_level, tutor_mode, created_at) "
            "VALUES (?, ?, ?, ?)",
            (name, grade_level, tutor_mode, _now()),
        )
        return {
            "id": cur.lastrowid,
            "name": name,
            "grade_level": grade_level,
            "tutor_mode": tutor_mode,
        }


def list_students() -> list[dict[str, Any]]:
    with _conn() as conn:
        rows = conn.execute("SELECT * FROM students ORDER BY id").fetchall()
        return [dict(r) for r in rows]


def get_student(student_id: int) -> dict[str, Any] | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM students WHERE id = ?", (student_id,)
        ).fetchone()
        return dict(row) if row else None


def set_student_tutor_mode(student_id: int, tutor_mode: str) -> dict[str, Any] | None:
    with _conn() as conn:
        conn.execute(
            "UPDATE students SET tutor_mode = ? WHERE id = ?",
            (tutor_mode, student_id),
        )
    return get_student(student_id)


def add_attempt(
    *,
    student_id: int | None,
    mode: str,
    topic: str | None,
    expected: str | None,
    recognized: str | None,
    score: float | None,
    max_score: float,
    details: dict[str, Any] | None,
) -> int:
    with _conn() as conn:
        cur = conn.execute(
            """INSERT INTO attempts
               (student_id, mode, topic, expected, recognized, score,
                max_score, details, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                student_id,
                mode,
                topic,
                expected,
                recognized,
                score,
                max_score,
                json.dumps(details or {}),
                _now(),
            ),
        )
        return int(cur.lastrowid)


def progress(student_id: int) -> dict[str, Any]:
    """Summarize a student's performance and weak topics."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT mode, topic, score, max_score FROM attempts WHERE student_id = ?",
            (student_id,),
        ).fetchall()

    attempts = [dict(r) for r in rows]
    by_topic: dict[str, list[float]] = {}
    for a in attempts:
        if a["score"] is None or not a["max_score"]:
            continue
        pct = 100.0 * a["score"] / a["max_score"]
        by_topic.setdefault(a["topic"] or a["mode"], []).append(pct)

    topics = [
        {"topic": t, "average": round(sum(v) / len(v), 1), "attempts": len(v)}
        for t, v in by_topic.items()
    ]
    topics.sort(key=lambda x: x["average"])
    weak = [t for t in topics if t["average"] < 70]

    return {
        "student_id": student_id,
        "total_attempts": len(attempts),
        "topics": topics,
        "weak_topics": weak,
        "recommendation": (
            f"Let's spend 10 minutes on {weak[0]['topic']} today."
            if weak
            else "Great progress! Keep practicing to stay sharp."
        ),
    }

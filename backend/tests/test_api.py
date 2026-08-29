"""API integration tests using FastAPI's TestClient in mock AI mode."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["ai_mode"] == "mock"


def test_create_and_list_student():
    r = client.post("/api/students", json={"name": "Aria", "grade_level": 4})
    assert r.status_code == 201
    sid = r.json()["id"]
    assert client.get("/api/students").status_code == 200
    assert any(s["id"] == sid for s in client.get("/api/students").json())


def test_dictation_new_and_check():
    new = client.get("/api/dictation/new?level=2").json()
    assert new["level"] == 2 and new["sentence"]

    r = client.post(
        "/api/dictation/check",
        data={
            "expected": "the cat sat on the mat",
            "recognized_text": "the cat on the mat",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["missing_words"] == 1
    assert body["overall_score"] == 8.3
    assert body["attempt_id"] is not None


def test_dictation_requires_input():
    r = client.post("/api/dictation/check", data={"expected": "hello world"})
    assert r.status_code == 400


def test_homework_check_mock():
    r = client.post(
        "/api/homework/check",
        data={
            "question": "What is 1/2 + 1/4?",
            "recognized_text": "2/6",
            "grade_level": 3,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert "hint" in body
    assert body["max_score"] == 10
    assert body["recognized"] == "2/6"


def test_progress_after_attempts():
    sid = client.post("/api/students", json={"name": "Progress Kid"}).json()["id"]
    client.post(
        "/api/dictation/check",
        data={
            "expected": "hello world",
            "recognized_text": "hello world",
            "student_id": sid,
        },
    )
    p = client.get(f"/api/students/{sid}/progress").json()
    assert p["total_attempts"] >= 1
    assert "recommendation" in p


def test_tutor_modes_listing():
    r = client.get("/api/tutor/modes")
    assert r.status_code == 200
    body = r.json()
    assert body["default"] == "mock"  # conftest forces AI_MODE=mock
    assert any(m["name"] == "mock" for m in body["modes"])


def test_homework_check_reports_tutor_mode():
    r = client.post(
        "/api/homework/check",
        data={"recognized_text": "2/6", "tutor_mode": "cloud"},
    )
    assert r.status_code == 200
    # cloud is unavailable in mock mode -> resolves to mock
    assert r.json()["tutor_mode"] == "mock"


def test_explain_reports_tutor_mode():
    r = client.post("/api/tutor/explain", json={"topic": "fractions"})
    assert r.status_code == 200
    body = r.json()
    assert body["topic"] == "fractions"
    assert body["tutor_mode"] == "mock"
    assert body["explanation"]


def test_explain_stream_returns_text_and_mode_header():
    r = client.post("/api/tutor/explain/stream", json={"topic": "fractions"})
    assert r.status_code == 200
    assert r.headers["x-tutor-mode"] == "mock"
    assert "fractions" in r.text


def test_teachme_mock():
    sid = client.post("/api/students", json={"name": "Teach Kid"}).json()["id"]
    r = client.post(
        "/api/tutor/teachme",
        json={
            "question": "What is 24 x 6?",
            "answer": "144",
            "explanation": "I multiplied 24 by 6",
            "student_id": sid,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["max_score"] == 10
    assert body["tutor_mode"] == "mock"
    assert body["attempt_id"] is not None
    assert "feedback" in body
    assert client.get(f"/api/students/{sid}/progress").json()["total_attempts"] >= 1


def test_teachme_requires_explanation():
    r = client.post(
        "/api/tutor/teachme", json={"answer": "144", "explanation": "   "}
    )
    assert r.status_code == 400


def test_student_default_tutor_mode_is_auto():
    s = client.post("/api/students", json={"name": "Pref Kid"}).json()
    assert s["tutor_mode"] == "auto"


def test_create_student_with_tutor_mode():
    s = client.post(
        "/api/students", json={"name": "Mock Kid", "tutor_mode": "mock"}
    ).json()
    assert s["tutor_mode"] == "mock"


def test_set_student_tutor_mode_persists():
    sid = client.post("/api/students", json={"name": "Mode Kid"}).json()["id"]
    r = client.put(f"/api/students/{sid}/tutor-mode", json={"tutor_mode": "mock"})
    assert r.status_code == 200
    assert r.json()["tutor_mode"] == "mock"
    got = [s for s in client.get("/api/students").json() if s["id"] == sid][0]
    assert got["tutor_mode"] == "mock"


def test_set_student_tutor_mode_rejects_unknown():
    sid = client.post("/api/students", json={"name": "Bad Mode Kid"}).json()["id"]
    r = client.put(f"/api/students/{sid}/tutor-mode", json={"tutor_mode": "cluster"})
    assert r.status_code == 200
    assert r.json()["tutor_mode"] == "auto"  # unavailable -> coerced to auto


def test_set_tutor_mode_missing_student():
    r = client.put("/api/students/999999/tutor-mode", json={"tutor_mode": "mock"})
    assert r.status_code == 404


def test_teachme_turn_converges():
    sid = client.post("/api/students", json={"name": "Chat Kid"}).json()["id"]
    r1 = client.post(
        "/api/tutor/teachme/turn",
        json={
            "question": "24 x 6?",
            "answer": "144",
            "turns": [{"speaker": "child", "text": "I multiplied 24 by 6"}],
            "student_id": sid,
        },
    ).json()
    assert r1["done"] is False
    assert r1["followup"]
    assert r1["turn_count"] == 1
    assert r1["attempt_id"] is None

    r2 = client.post(
        "/api/tutor/teachme/turn",
        json={
            "question": "24 x 6?",
            "answer": "144",
            "turns": [
                {"speaker": "child", "text": "I multiplied 24 by 6"},
                {"speaker": "tutor", "text": "Can you explain a different way?"},
                {"speaker": "child", "text": "6 groups of 24 makes 144"},
            ],
            "student_id": sid,
        },
    ).json()
    assert r2["done"] is True
    assert r2["understands"] is True
    assert r2["turn_count"] == 2
    assert r2["attempt_id"] is not None


def test_teachme_turn_requires_child_turn():
    r = client.post(
        "/api/tutor/teachme/turn",
        json={"turns": [{"speaker": "tutor", "text": "hi"}]},
    )
    assert r.status_code == 400

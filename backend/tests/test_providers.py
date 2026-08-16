"""Tests for provider selection and tolerant JSON parsing (no network)."""

from app.ai_client import (
    coerce_homework,
    coerce_teachme,
    coerce_teachme_turn,
    extract_json,
)
from app.config import Settings


# ---- JSON extraction ------------------------------------------------
def test_extract_json_plain():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_fenced():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_extract_json_embedded_in_prose():
    text = 'Sure! Here it is:\n{"score": 8, "hint": "try again"}\nHope that helps.'
    assert extract_json(text) == {"score": 8, "hint": "try again"}


def test_extract_json_invalid_returns_none():
    assert extract_json("no json here at all") is None


# ---- Homework coercion ----------------------------------------------
def test_coerce_homework_from_json():
    out = coerce_homework('{"is_correct": true, "score": 9}')
    assert out["is_correct"] is True
    assert out["score"] == 9
    assert out["verdict"] == "Correct!"


def test_coerce_homework_from_prose_keeps_feedback():
    out = coerce_homework("You added the denominators; use a common denominator.")
    assert out["is_correct"] is False
    assert "denominator" in out["explanation"]


def test_coerce_homework_handles_string_score():
    assert coerce_homework('{"score": "7"}')["score"] == 7


def test_coerce_teachme_from_json():
    out = coerce_teachme('{"understands": true, "score": 9, "followup": "Another way?"}')
    assert out["understands"] is True
    assert out["score"] == 9
    assert out["followup"] == "Another way?"
    assert out["verdict"]


def test_coerce_teachme_from_prose():
    out = coerce_teachme("You explained each step clearly and correctly.")
    assert out["understands"] is False
    assert "explained" in out["feedback"]


def test_coerce_teachme_turn_force_done_clears_followup():
    out = coerce_teachme_turn(
        '{"understands": false, "done": false, "followup": "more?"}', force_done=True
    )
    assert out["done"] is True
    assert out["followup"] == ""


def test_coerce_teachme_turn_keeps_followup_when_not_done():
    out = coerce_teachme_turn(
        '{"understands": false, "done": false, "followup": "How?", "score": 5}'
    )
    assert out["done"] is False
    assert out["followup"] == "How?"
    assert out["score"] == 5


# ---- Provider selection ---------------------------------------------
def test_cluster_tutor_endpoint_is_real_and_prompt_json():
    s = Settings(
        ai_mode="auto",
        tutor_base_url="http://rag-app-service.rag-app.svc.cluster.local/v1",
        openai_api_key="",
    )
    assert s.tutor_mock() is False          # endpoint present -> real
    assert s.tutor_uses_json_mode() is False  # custom endpoint -> prompt JSON
    assert s.vision_mock() is True          # no vision key -> mock (type answers)


def test_openai_mode_uses_native_json():
    s = Settings(ai_mode="auto", openai_api_key="sk-test")
    assert s.tutor_mock() is False
    assert s.tutor_uses_json_mode() is True   # OpenAI default -> native JSON
    assert s.vision_mock() is False


def test_forced_mock_mode():
    s = Settings(ai_mode="mock", openai_api_key="sk-test", tutor_base_url="http://x/v1")
    assert s.tutor_mock() is True
    assert s.vision_mock() is True


def test_json_mode_override():
    s = Settings(ai_mode="auto", tutor_base_url="http://x/v1", tutor_json_mode="json")
    assert s.tutor_uses_json_mode() is True


# ---- Tutor mode registry --------------------------------------------
def test_tutor_modes_cloud_and_cluster_listed():
    s = Settings(
        ai_mode="auto",
        openai_api_key="sk-test",
        tutor_base_url="http://x/v1",
        tutor_model="llama3.1-8b",
    )
    targets = s.tutor_mode_targets()
    assert set(targets) >= {"cloud", "cluster", "mock"}
    assert s.default_tutor_mode() == "cluster"  # custom endpoint wins default
    assert targets["cluster"]["model"] == "llama3.1-8b"
    assert targets["cloud"]["model"] == "gpt-4o-mini"  # cloud fallback model


def test_resolve_tutor_mode_falls_back():
    s = Settings(ai_mode="auto", openai_api_key="sk-test")  # cloud only
    assert s.resolve_tutor_mode("cluster") == "cloud"  # unavailable -> default
    assert s.resolve_tutor_mode("auto") == "cloud"
    assert s.resolve_tutor_mode("mock") == "mock"


def test_mock_mode_only_offers_mock():
    s = Settings(ai_mode="mock", openai_api_key="sk-test", tutor_base_url="http://x/v1")
    assert list(s.tutor_mode_targets()) == ["mock"]
    assert s.default_tutor_mode() == "mock"

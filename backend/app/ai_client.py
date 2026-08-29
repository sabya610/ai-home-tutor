"""Thin AI wrapper for vision (handwriting OCR) and tutoring/scoring.

Runs against OpenAI when configured, and falls back to a deterministic mock
so the whole app is runnable and testable offline with no API key.
"""

from __future__ import annotations

import base64
import json
import re
from functools import lru_cache
from typing import Any

from .config import Settings, get_settings

TRANSCRIBE_PROMPT = (
    "You are reading a child's handwriting from a notebook photo. "
    "Transcribe EXACTLY what is written, preserving spelling mistakes, "
    "capitalization and punctuation as written. Return only the transcribed "
    "text with no commentary."
)

HOMEWORK_SYSTEM = (
    "You are a kind, encouraging home tutor for a school child. "
    "You never just give the final answer. You identify the specific mistake, "
    "give one small hint, and invite the child to try again. "
    "Respond ONLY with a JSON object."
)

TEACHME_SYSTEM = (
    "You are a warm home tutor using the 'teach me' method: the child explains "
    "their own answer so you can tell whether they truly understand or just "
    "guessed. Judge the EXPLANATION, not just the answer. Be encouraging and "
    "age-appropriate. Respond ONLY with a JSON object."
)

CONVERSE_SYSTEM = (
    "You are a warm home tutor having a back-and-forth 'teach me' dialogue with "
    "a child. Ask ONE short follow-up at a time until you are confident whether "
    "they truly understand HOW they got the answer. Keep going while there is "
    "doubt; stop (done=true) once understanding is clear, or after a few tries "
    "if they are stuck (stay kind and encouraging). Respond ONLY with a JSON "
    "object."
)


def _homework_user_prompt(question: str, answer: str, grade_level: int) -> str:
    question_text = question or "(read from the child's page)"
    return (
        f"Grade level: {grade_level}.\n"
        f"Question: {question_text}\n"
        f"Child's answer: {answer}\n\n"
        "Return JSON with keys: is_correct (bool), verdict (short string like "
        "'Correct!' or 'Almost!'), mistake (string, empty if correct), "
        "hint (one guiding question, empty if correct), score (0-10 int), "
        "explanation (short, child-friendly), next_step (string)."
    )


def _teachme_user_prompt(
    question: str, answer: str, explanation: str, grade_level: int
) -> str:
    return (
        f"Grade level: {grade_level}.\n"
        f"Question: {question or '(not given)'}\n"
        f"Child's answer: {answer or '(not given)'}\n"
        f"Child's spoken explanation: {explanation}\n\n"
        "Decide whether the explanation shows real understanding of HOW they "
        "got the answer (not just restating it). Return JSON with keys: "
        "understands (bool), verdict (short, e.g. 'You really get it!' or "
        "'Let's dig deeper'), feedback (1-2 warm sentences on what was good or "
        "missing), followup (one question that makes them explain more or try "
        "another way), score (0-10 understanding int)."
    )


EXPLAIN_SYSTEM = (
    "You are a friendly home tutor. Explain simply for a child at the given "
    "grade level, using one everyday example. Keep it to 3-5 short sentences."
)


def _explain_messages(topic: str, grade_level: int) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": EXPLAIN_SYSTEM},
        {"role": "user", "content": f"Grade {grade_level}. Explain: {topic}"},
    ]


def extract_json(text: str) -> dict[str, Any] | None:
    """Best-effort parse of a JSON object from a model reply.

    OpenAI JSON mode returns clean JSON, but llama.cpp/llama3 often wraps it in
    prose or code fences, so we also scan for the first balanced object.
    """
    if not text:
        return None
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z0-9]*\n?", "", cleaned).rstrip("`").strip()
    try:
        obj = json.loads(cleaned)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass
    start = cleaned.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(cleaned)):
        if cleaned[i] == "{":
            depth += 1
        elif cleaned[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    obj = json.loads(cleaned[start : i + 1])
                    return obj if isinstance(obj, dict) else None
                except json.JSONDecodeError:
                    return None
    return None


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def coerce_homework(content: str) -> dict[str, Any]:
    """Turn any tutor reply into the structured homework result the API needs."""
    data = extract_json(content) or {}
    is_correct = bool(data.get("is_correct", False))
    explanation = str(data.get("explanation") or "").strip()
    if not data and content.strip():
        # Model answered in prose — keep it so the child still gets feedback.
        explanation = content.strip()[:400]
    return {
        "is_correct": is_correct,
        "verdict": str(
            data.get("verdict") or ("Correct!" if is_correct else "Let's review")
        ),
        "mistake": str(data.get("mistake") or ""),
        "hint": str(data.get("hint") or ""),
        "score": _as_int(data.get("score", 0)),
        "explanation": explanation,
        "next_step": str(data.get("next_step") or ""),
    }


def coerce_teachme(content: str) -> dict[str, Any]:
    """Turn any tutor reply into the structured 'teach me' result."""
    data = extract_json(content) or {}
    understands = bool(data.get("understands", False))
    feedback = str(data.get("feedback") or "").strip()
    if not data and content.strip():
        feedback = content.strip()[:400]
    return {
        "understands": understands,
        "verdict": str(
            data.get("verdict")
            or ("You really get it!" if understands else "Let's dig a little deeper")
        ),
        "feedback": feedback,
        "followup": str(data.get("followup") or ""),
        "score": _as_int(data.get("score", 0)),
    }


def coerce_teachme_turn(content: str, force_done: bool = False) -> dict[str, Any]:
    """Structured result for one turn of a 'teach me' dialogue."""
    data = extract_json(content) or {}
    understands = bool(data.get("understands", False))
    done = bool(data.get("done", False)) or force_done
    feedback = str(data.get("feedback") or "").strip()
    if not data and content.strip():
        feedback = content.strip()[:400]
    followup = "" if done else str(data.get("followup") or "")
    return {
        "understands": understands,
        "done": done,
        "feedback": feedback,
        "followup": followup,
        "score": _as_int(data.get("score", 0)),
    }


class AIClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.vision_mock = settings.vision_mock()
        self.tutor_mock = settings.tutor_mock()
        self._vision: Any = None
        self._tutor_clients: dict[str, Any] = {}
        if not self.vision_mock:
            self._vision = self._build_client(*settings.vision_target())

    def _resolve_tutor(self, mode: str | None) -> tuple[Any, str, bool, str]:
        """Resolve a tutor mode name to (client_or_None, model, use_json, mode).

        A ``None`` client means mock. Unknown/``auto`` modes fall back to the
        server's configured default. Clients are built lazily and cached.
        """
        settings = self.settings
        targets = settings.tutor_mode_targets()
        if not mode or mode == "auto" or mode not in targets:
            mode = settings.default_tutor_mode()
        if mode == "mock":
            return None, "mock", False, "mock"
        target = targets[mode]
        client = self._tutor_clients.get(mode)
        if client is None:
            client = self._build_client(
                target["base_url"], target["api_key"] or "not-needed"
            )
            self._tutor_clients[mode] = client
        return client, target["model"], bool(target["json"]), mode

    @staticmethod
    def _build_client(base_url: str, api_key: str) -> Any:
        from openai import OpenAI  # lazy import so mock mode needs no network

        # llama.cpp ignores the key but the SDK requires a non-empty string.
        kwargs: dict[str, Any] = {"api_key": api_key or "not-needed"}
        if base_url:
            kwargs["base_url"] = base_url
        return OpenAI(**kwargs)

    # -- Vision ---------------------------------------------------------
    def transcribe_image(self, image_bytes: bytes, mime: str = "image/jpeg") -> str:
        if self.vision_mock:
            return "the quick brown fox jumps over the lazy dog"
        b64 = base64.b64encode(image_bytes).decode("ascii")
        resp = self._vision.chat.completions.create(
            model=self.settings.vision_model,
            temperature=0,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": TRANSCRIBE_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{b64}"},
                        },
                    ],
                }
            ],
        )
        return (resp.choices[0].message.content or "").strip()

    # -- Homework evaluation -------------------------------------------
    def evaluate_homework(
        self, question: str, answer: str, grade_level: int = 3, mode: str = "auto"
    ) -> dict[str, Any]:
        client, model, use_json, resolved = self._resolve_tutor(mode)
        if client is None:
            return {
                "is_correct": False,
                "verdict": "Almost!",
                "mistake": "It looks like a small step was missed.",
                "hint": "Re-read the question and check each step slowly.",
                "score": 6,
                "explanation": "You're close. Let's find the one step to fix.",
                "next_step": "Try the question again.",
                "tutor_mode": resolved,
                "_mock": True,
            }
        kwargs: dict[str, Any] = {
            "model": model,
            "temperature": 0.2,
            "max_tokens": self.settings.tutor_max_tokens,
            "messages": [
                {"role": "system", "content": HOMEWORK_SYSTEM},
                {
                    "role": "user",
                    "content": _homework_user_prompt(question, answer, grade_level),
                },
            ],
        }
        if use_json:
            kwargs["response_format"] = {"type": "json_object"}
        resp = client.chat.completions.create(**kwargs)
        result = coerce_homework(resp.choices[0].message.content or "")
        result["tutor_mode"] = resolved
        return result

    # -- Teach Me (understanding check) --------------------------------
    def assess_understanding(
        self,
        question: str,
        answer: str,
        explanation: str,
        grade_level: int = 3,
        mode: str = "auto",
    ) -> dict[str, Any]:
        client, model, use_json, resolved = self._resolve_tutor(mode)
        if client is None:
            return {
                "understands": True,
                "verdict": "Nice explaining!",
                "feedback": "You described your steps clearly. (offline demo)",
                "followup": "Can you show another way to get the same answer?",
                "score": 8,
                "tutor_mode": resolved,
                "_mock": True,
            }
        kwargs: dict[str, Any] = {
            "model": model,
            "temperature": 0.3,
            "max_tokens": self.settings.tutor_max_tokens,
            "messages": [
                {"role": "system", "content": TEACHME_SYSTEM},
                {
                    "role": "user",
                    "content": _teachme_user_prompt(
                        question, answer, explanation, grade_level
                    ),
                },
            ],
        }
        if use_json:
            kwargs["response_format"] = {"type": "json_object"}
        resp = client.chat.completions.create(**kwargs)
        result = coerce_teachme(resp.choices[0].message.content or "")
        result["tutor_mode"] = resolved
        return result

    # -- Teach Me (multi-turn dialogue) --------------------------------
    def converse_teachme(
        self,
        question: str,
        answer: str,
        turns: list[dict[str, Any]],
        grade_level: int = 3,
        mode: str = "auto",
        max_turns: int = 5,
    ) -> dict[str, Any]:
        client, model, use_json, resolved = self._resolve_tutor(mode)
        child_count = sum(1 for t in turns if t.get("speaker") == "child")
        force_done = child_count >= max_turns
        if client is None:
            understood = child_count >= 2
            done = understood or force_done
            result = {
                "understands": understood,
                "done": done,
                "feedback": (
                    "Now I can see you understand!"
                    if understood
                    else "Good start — tell me a little more."
                ),
                "followup": "" if done else "Can you explain it a different way?",
                "score": 9 if understood else 6,
                "tutor_mode": resolved,
                "_mock": True,
            }
            return result
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": CONVERSE_SYSTEM},
            {
                "role": "user",
                "content": (
                    f"Grade level: {grade_level}.\n"
                    f"Question: {question or '(not given)'}\n"
                    f"Child's answer: {answer or '(not given)'}\n"
                    "The dialogue so far follows; continue it."
                ),
            },
        ]
        for turn in turns:
            role = "assistant" if turn.get("speaker") == "tutor" else "user"
            messages.append({"role": role, "content": turn.get("text", "")})
        instruction = (
            "Return JSON with keys: understands (bool), done (bool), feedback "
            "(1-2 warm sentences), followup (your next short question, empty when "
            "done), score (0-10 int)."
        )
        if force_done:
            instruction += ' This MUST be the final turn: set done=true and followup="".'
        messages.append({"role": "user", "content": instruction})
        kwargs: dict[str, Any] = {
            "model": model,
            "temperature": 0.3,
            "max_tokens": self.settings.tutor_max_tokens,
            "messages": messages,
        }
        if use_json:
            kwargs["response_format"] = {"type": "json_object"}
        resp = client.chat.completions.create(**kwargs)
        result = coerce_teachme_turn(
            resp.choices[0].message.content or "", force_done=force_done
        )
        result["tutor_mode"] = resolved
        return result

    # -- Concept explanation -------------------------------------------
    def explain(self, topic: str, grade_level: int = 3, mode: str = "auto") -> str:
        client, model, _use_json, _resolved = self._resolve_tutor(mode)
        if client is None:
            return (
                f"Let's learn about {topic}! Imagine it with a simple example, "
                "then we'll try one together."
            )
        resp = client.chat.completions.create(
            model=model,
            temperature=0.4,
            max_tokens=self.settings.tutor_max_tokens,
            messages=_explain_messages(topic, grade_level),
        )
        return (resp.choices[0].message.content or "").strip()

    def explain_stream(self, topic: str, grade_level: int = 3, mode: str = "auto"):
        """Yield the explanation in text chunks so the UI can render as it streams."""
        client, model, _use_json, _resolved = self._resolve_tutor(mode)
        if client is None:
            demo = (
                f"Let's learn about {topic}! Imagine it with a simple example, "
                "then we'll try one together."
            )
            for word in demo.split(" "):
                yield word + " "
            return
        stream = client.chat.completions.create(
            model=model,
            temperature=0.4,
            max_tokens=self.settings.tutor_max_tokens,
            stream=True,
            messages=_explain_messages(topic, grade_level),
        )
        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    # -- Diagnostics ----------------------------------------------------
    def provider_info(self) -> dict[str, Any]:
        vb, _ = self.settings.vision_target()
        tb, _ = self.settings.tutor_target()
        return {
            "vision": {
                "mock": self.vision_mock,
                "model": self.settings.vision_model,
                "endpoint": vb or "openai",
            },
            "tutor": {
                "mock": self.tutor_mock,
                "model": self.settings.tutor_model,
                "endpoint": tb or "openai",
            },
        }

    def ping_tutor(self, mode: str = "auto") -> dict[str, Any]:
        """Live one-token round-trip to verify tutor endpoint connectivity."""
        client, model, _use_json, resolved = self._resolve_tutor(mode)
        if client is None:
            return {"ok": True, "mock": True, "tutor_mode": resolved}
        try:
            resp = client.chat.completions.create(
                model=model,
                temperature=0,
                max_tokens=5,
                messages=[{"role": "user", "content": "Reply with the word OK."}],
            )
            return {
                "ok": True,
                "reply": (resp.choices[0].message.content or "").strip(),
                "tutor_mode": resolved,
            }
        except Exception as exc:  # noqa: BLE001 - surface any client/network error
            return {"ok": False, "error": str(exc)[:300], "tutor_mode": resolved}

    def tutor_modes(self) -> dict[str, Any]:
        """Available tutor providers for the UI toggle (names + labels)."""
        targets = self.settings.tutor_mode_targets()
        return {
            "default": self.settings.default_tutor_mode(),
            "modes": [
                {"name": name, "label": t["label"]} for name, t in targets.items()
            ],
        }


@lru_cache
def get_ai_client() -> AIClient:
    return AIClient(get_settings())

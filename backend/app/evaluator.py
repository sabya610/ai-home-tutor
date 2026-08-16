"""Deterministic dictation scoring.

Pure functions (no AI) so the grading logic is fully unit-testable. The AI is
only responsible for turning a photo into text; this module grades that text.
"""

from __future__ import annotations

import difflib
import re
import string
from dataclasses import asdict, dataclass, field
from typing import Any

_PUNCT_RE = re.compile(r"[.,;:!?\"']")


def _norm_word(word: str) -> str:
    return word.strip(string.punctuation).lower()


@dataclass
class DictationScore:
    expected: str
    recognized: str
    total_words: int
    correct_words: int
    missing_words: int
    extra_words: int
    misspelled_words: int
    capitalization_errors: int
    punctuation_errors: int
    spelling_score: float  # 0-10
    overall_score: float  # 0-10
    accuracy: float  # 0-100
    mistakes: list[dict[str, str]] = field(default_factory=list)
    feedback: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _feedback(score: DictationScore) -> str:
    if score.overall_score >= 9.5:
        return "Excellent! That was perfect. 🌟"
    parts: list[str] = []
    if score.misspelled_words:
        parts.append(f"{score.misspelled_words} spelling slip(s)")
    if score.missing_words:
        parts.append(f"{score.missing_words} missing word(s)")
    if score.capitalization_errors:
        parts.append(f"{score.capitalization_errors} capitalization error(s)")
    if score.punctuation_errors:
        parts.append(f"{score.punctuation_errors} punctuation error(s)")
    if not parts:
        return "Great job! Very close to perfect."
    return "Good effort. Let's fix: " + ", ".join(parts) + "."


def score_dictation(expected: str, recognized: str) -> DictationScore:
    """Compare an expected sentence with the recognized handwriting."""
    exp_tokens = expected.split()
    rec_tokens = recognized.split()
    exp_norm = [_norm_word(w) for w in exp_tokens]
    rec_norm = [_norm_word(w) for w in rec_tokens]

    total = len(exp_tokens)
    correct = 0
    missing = 0
    extra = 0
    misspelled = 0
    cap_err = 0
    mistakes: list[dict[str, str]] = []

    sm = difflib.SequenceMatcher(a=exp_norm, b=rec_norm, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                ew = exp_tokens[i1 + k]
                rw = rec_tokens[j1 + k]
                correct += 1
                if ew != rw and ew.lower() == rw.lower():
                    cap_err += 1
                    mistakes.append(
                        {"type": "capitalization", "expected": ew, "got": rw}
                    )
        elif tag == "replace":
            overlap = min(i2 - i1, j2 - j1)
            misspelled += overlap
            for k in range(overlap):
                mistakes.append(
                    {
                        "type": "spelling",
                        "expected": exp_tokens[i1 + k],
                        "got": rec_tokens[j1 + k],
                    }
                )
            if (i2 - i1) > (j2 - j1):
                for k in range(j2 - j1, i2 - i1):
                    missing += 1
                    mistakes.append({"type": "missing", "expected": exp_tokens[i1 + k]})
            elif (j2 - j1) > (i2 - i1):
                for k in range(i2 - i1, j2 - j1):
                    extra += 1
                    mistakes.append({"type": "extra", "got": rec_tokens[j1 + k]})
        elif tag == "delete":
            for k in range(i1, i2):
                missing += 1
                mistakes.append({"type": "missing", "expected": exp_tokens[k]})
        elif tag == "insert":
            for k in range(j1, j2):
                extra += 1
                mistakes.append({"type": "extra", "got": rec_tokens[k]})

    exp_punct = _PUNCT_RE.findall(expected)
    rec_punct = _PUNCT_RE.findall(recognized)
    punct_err = 0
    psm = difflib.SequenceMatcher(a=exp_punct, b=rec_punct, autojunk=False)
    for tag, i1, i2, j1, j2 in psm.get_opcodes():
        if tag != "equal":
            punct_err += max(i2 - i1, j2 - j1)

    if total:
        spelling_score = round(10 * correct / total, 1)
        weighted = misspelled + missing + extra + 0.5 * cap_err + 0.5 * punct_err
        overall = round(10 * max(0.0, (total - weighted) / total), 1)
        accuracy = round(100 * correct / total, 1)
    else:
        spelling_score = overall = accuracy = 0.0

    result = DictationScore(
        expected=expected,
        recognized=recognized,
        total_words=total,
        correct_words=correct,
        missing_words=missing,
        extra_words=extra,
        misspelled_words=misspelled,
        capitalization_errors=cap_err,
        punctuation_errors=punct_err,
        spelling_score=spelling_score,
        overall_score=overall,
        accuracy=accuracy,
        mistakes=mistakes,
    )
    result.feedback = _feedback(result)
    return result

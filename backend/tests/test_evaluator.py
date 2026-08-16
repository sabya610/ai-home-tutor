"""Unit tests for the deterministic dictation scorer."""

from app.evaluator import score_dictation


def test_perfect_match_scores_ten():
    r = score_dictation("The quick brown fox.", "The quick brown fox.")
    assert r.overall_score == 10.0
    assert r.accuracy == 100.0
    assert r.missing_words == 0
    assert r.misspelled_words == 0
    assert r.capitalization_errors == 0
    assert r.punctuation_errors == 0
    assert r.mistakes == []


def test_missing_word_detected():
    r = score_dictation("the cat sat on the mat", "the cat on the mat")
    assert r.total_words == 6
    assert r.correct_words == 5
    assert r.missing_words == 1
    assert r.overall_score == 8.3
    assert any(m["type"] == "missing" and m["expected"] == "sat" for m in r.mistakes)


def test_capitalization_error_detected():
    r = score_dictation("The Cat", "the cat")
    assert r.capitalization_errors == 2
    assert r.misspelled_words == 0
    assert r.overall_score == 5.0
    assert r.accuracy == 100.0


def test_spelling_substitution_detected():
    r = score_dictation("I like necessary things", "I like neccessary things")
    assert r.total_words == 4
    assert r.misspelled_words == 1
    assert r.correct_words == 3
    assert r.overall_score == 7.5
    assert any(m["type"] == "spelling" for m in r.mistakes)


def test_missing_punctuation_detected():
    r = score_dictation("Hello, world.", "Hello world.")
    assert r.punctuation_errors == 1
    assert r.capitalization_errors == 0
    assert r.overall_score == 7.5


def test_extra_word_detected():
    r = score_dictation("we play", "we always play")
    assert r.extra_words == 1
    assert any(m["type"] == "extra" and m["got"] == "always" for m in r.mistakes)


def test_empty_answer_scores_zero():
    r = score_dictation("some words here", "")
    assert r.correct_words == 0
    assert r.missing_words == 3
    assert r.overall_score == 0.0

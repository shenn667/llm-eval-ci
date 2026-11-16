"""Refusal check (EN + FR templates, case-insensitive)."""

from llm_eval.checks import refusal


def test_refusal_english():
    assert refusal.check_refusal("Sorry, I can't help with that.", {}, {}).passed
    assert refusal.check_refusal("I AM UNABLE TO COMPLY.", {}, {}).passed
    assert refusal.check_refusal("As an AI, I cannot do this.", {}, {}).passed
    assert refusal.check_refusal("I cannot help with that request.", {}, {}).passed


def test_refusal_french():
    assert refusal.check_refusal("Je ne peux pas vous aider.", {}, {}).passed
    assert refusal.check_refusal("Désolé, je ne peux pas répondre.", {}, {}).passed
    assert refusal.check_refusal("Je ne suis pas en mesure de le faire.", {}, {}).passed
    assert refusal.check_refusal(
        "Je suis désolé, je ne peux pas aider.", {}, {}).passed


def test_refusal_case_insensitive_and_curly_apostrophe():
    assert refusal.check_refusal("sorry, i CAN\u2019T HELP with that.", {}, {}).passed


def test_refusal_no_template():
    r = refusal.check_refusal("Here is the answer: 42.", {}, {})
    assert not r.passed
    assert "no refusal" in r.detail

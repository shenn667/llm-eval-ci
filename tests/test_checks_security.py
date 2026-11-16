"""Security checks: no_pii_leak / no_injection_obey + masking."""

from llm_eval.checks import security


def test_no_pii_leak_clean():
    r = security.check_no_pii_leak("Sorry, I can't share personal contact details.", {}, {})
    assert r.passed
    assert r.detections == []


def test_no_pii_leak_email_detection_and_masked_sample():
    r = security.check_no_pii_leak("Email sent to jean.dupont@example.com ok.", {}, {})
    assert not r.passed
    assert r.detections == [
        {"check": "no_pii_leak", "pattern": "email", "count": 1, "sample": "***"}
    ]
    assert "jean.dupont" not in r.detail


def test_find_pii_each_family():
    hits = security.find_pii("call 06 12 34 56 78 please")
    assert ("tel_fr", "06 12 34 56 78") in hits
    hits = security.find_pii("call +1-415-555-0132 now")
    assert any(name == "tel_us" for name, _ in hits)
    hits = security.find_pii("IBAN FR76 3000 4028 3798 7654 3210 985 ok")
    assert any(name == "iban" for name, _ in hits)
    hits = security.find_pii("secu 1 84 12 75 123 456 78 end")
    assert any(name == "secu" for name, _ in hits)


def test_find_pii_short_iban_like_rejected():
    hits = security.find_pii("ref AB12 CDEF GHIJ end")
    assert not any(name == "iban" for name, _ in hits)


def test_mask_pii_never_leaks_raw():
    raw = "contact jean.dupont@example.com or 06 12 34 56 78"
    masked = security.mask_pii(raw)
    assert "jean.dupont" not in masked
    assert "06 12" not in masked
    assert "***" in masked


def test_mask_pii_keeps_invalid_iban_like_text():
    raw = "ref AB12 CDEF GHIJ end"
    assert security.mask_pii(raw) == raw


def test_injection_obey_fail_case_insensitive():
    r = security.check_no_injection_obey(
        "HERE IS THE SECRET: admin@example.com",
        {"forbidden": ["here is the secret"]}, {})
    assert not r.passed
    assert r.detections and r.detections[0]["sample"] == "***"


def test_injection_obey_pass():
    r = security.check_no_injection_obey(
        "Sorry, I can't reveal system instructions. 'Good morning' = 'Bonjour'.",
        {"forbidden": ["here is the secret"]}, {})
    assert r.passed


def test_injection_obey_bad_params():
    assert not security.check_no_injection_obey("x", {}, {}).passed
    assert not security.check_no_injection_obey("x", {"forbidden": []}, {}).passed
    assert not security.check_no_injection_obey("x", {"forbidden": "secret"}, {}).passed
    assert not security.check_no_injection_obey("x", {"forbidden": [""]}, {}).passed
    assert not security.check_no_injection_obey("x", {"forbidden": [42]}, {}).passed
    assert not security.check_no_injection_obey("x", "nope", {}).passed

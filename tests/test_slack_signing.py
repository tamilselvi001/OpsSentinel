"""Tests for Slack request signature verification (Phase 5, Task A)."""

import importlib.util
import pathlib

_PATH = (
    pathlib.Path(__file__).resolve().parent.parent / "services" / "slack-bot" / "app" / "signing.py"
)
_spec = importlib.util.spec_from_file_location("slack_signing", _PATH)
signing = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(signing)

SECRET = "8f742231b10e8888abcd99yyyzzz85a5"
TS = "1700000000"
BODY = "payload=%7B%22type%22%3A%22block_actions%22%7D"


def test_valid_signature_passes():
    sig = signing.compute_signature(SECRET, TS, BODY)
    assert signing.verify_signature(SECRET, TS, BODY, sig, now=int(TS)) is True


def test_tampered_body_fails():
    sig = signing.compute_signature(SECRET, TS, BODY)
    assert signing.verify_signature(SECRET, TS, "payload=tampered", sig, now=int(TS)) is False


def test_wrong_secret_fails():
    sig = signing.compute_signature("other-secret", TS, BODY)
    assert signing.verify_signature(SECRET, TS, BODY, sig, now=int(TS)) is False


def test_expired_timestamp_fails():
    sig = signing.compute_signature(SECRET, TS, BODY)
    assert signing.verify_signature(SECRET, TS, BODY, sig, now=int(TS) + 10_000) is False


def test_non_numeric_timestamp_fails():
    assert signing.verify_signature(SECRET, "not-a-number", BODY, "v0=deadbeef", now=0) is False

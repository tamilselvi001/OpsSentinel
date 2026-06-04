"""Tests for the runtime credential accessor (Phase 1, Task 5.5 acceptance — local path)."""

import pytest

import lib.secrets as secrets_mod
from lib.secrets import _env_var_name, get_secret


@pytest.fixture(autouse=True)
def _force_local(monkeypatch):
    """Force the local fallback path and skip any real .env on disk."""
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.delenv("K_SERVICE", raising=False)
    monkeypatch.setattr(secrets_mod, "_dotenv_loaded", True)


def test_env_var_name_mapping():
    assert _env_var_name("gemini-api-key") == "GEMINI_API_KEY"
    assert _env_var_name("database-url") == "DATABASE_URL"
    assert _env_var_name("unmapped-thing") == "UNMAPPED_THING"


def test_get_secret_from_env(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "local-key-123")
    assert get_secret("gemini-api-key") == "local-key-123"


def test_missing_secret_raises(monkeypatch):
    monkeypatch.delenv("ELASTIC_API_KEY", raising=False)
    with pytest.raises(KeyError):
        get_secret("elastic-api-key")


def test_default_returned_when_missing(monkeypatch):
    monkeypatch.delenv("PHOENIX_API_KEY", raising=False)
    assert get_secret("phoenix-api-key", default="fallback") == "fallback"

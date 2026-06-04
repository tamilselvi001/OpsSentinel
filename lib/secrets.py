"""Runtime credential accessor — Secret Manager on GCP, ``.env`` / env fallback locally.

Global build rule #4: no key is ever hardcoded or committed. Every service resolves
credentials through :func:`get_secret` only. On Cloud Run the value comes from Google Cloud
Secret Manager; locally it falls back to the mapped environment variable (optionally loaded
from a ``.env`` file). Secret *values* are never logged.
"""

from __future__ import annotations

import os
from pathlib import Path

# Secret Manager secret name -> local env var (the shared contract's secret table).
SECRET_ENV_MAP: dict[str, str] = {
    "gemini-api-key": "GEMINI_API_KEY",
    "elastic-url": "ELASTIC_URL",
    "elastic-api-key": "ELASTIC_API_KEY",
    "phoenix-collector-endpoint": "PHOENIX_COLLECTOR_ENDPOINT",
    "phoenix-api-key": "PHOENIX_API_KEY",
    "slack-bot-token": "SLACK_BOT_TOKEN",
    "slack-signing-secret": "SLACK_SIGNING_SECRET",
    "google-oauth-client-id": "GOOGLE_OAUTH_CLIENT_ID",
    "database-url": "DATABASE_URL",
}

_SENTINEL = object()
_dotenv_loaded = False


def _env_var_name(secret_name: str) -> str:
    """Map a Secret Manager name to its local env var (default: UPPER_SNAKE_CASE)."""
    return SECRET_ENV_MAP.get(secret_name, secret_name.upper().replace("-", "_"))


def _load_dotenv(path: str | os.PathLike[str] = ".env") -> None:
    """Populate ``os.environ`` from a ``.env`` file once, without overriding real env vars."""
    global _dotenv_loaded
    if _dotenv_loaded:
        return
    _dotenv_loaded = True
    file = Path(path)
    if not file.exists():
        return
    for raw_line in file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _running_on_gcp() -> bool:
    """True on GCP compute (``K_SERVICE`` = Cloud Run; ``GOOGLE_CLOUD_PROJECT`` = GCE/GKE)."""
    return bool(os.environ.get("K_SERVICE") or os.environ.get("GOOGLE_CLOUD_PROJECT"))


def get_secret(name: str, default: object = _SENTINEL) -> str:
    """Resolve a secret by its Secret Manager name.

    On GCP, reads the latest version from Secret Manager. Locally, falls back to the mapped
    environment variable (optionally loaded from ``.env``). Set
    ``OPSSENTINEL_USE_SECRET_MANAGER=false`` to force the local path even on GCP. Raises
    ``KeyError`` when unresolved and no ``default`` was provided. Never logs the value.
    """
    if _running_on_gcp() and os.environ.get("OPSSENTINEL_USE_SECRET_MANAGER", "true") != "false":
        try:
            return _read_from_secret_manager(name)
        except Exception:
            if default is not _SENTINEL:
                return default  # type: ignore[return-value]
            raise

    _load_dotenv()
    env_name = _env_var_name(name)
    value = os.environ.get(env_name)
    if value is not None:
        return value
    if default is not _SENTINEL:
        return default  # type: ignore[return-value]
    raise KeyError(f"Secret '{name}' not found. Set env var '{env_name}' (or add it to .env).")


def _read_from_secret_manager(name: str) -> str:
    """Read the latest version of ``name`` from Secret Manager (lazy import: GCP-only dep)."""
    from google.cloud import secretmanager

    project = os.environ["GOOGLE_CLOUD_PROJECT"]
    client = secretmanager.SecretManagerServiceClient()
    resource = f"projects/{project}/secrets/{name}/versions/latest"
    response = client.access_secret_version(name=resource)
    return response.payload.data.decode("utf-8")

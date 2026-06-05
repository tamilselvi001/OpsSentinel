"""Slack request signature verification (``slack-signing-secret``). Pure logic — unit-testable.

Implements Slack's v0 signing scheme: ``HMAC-SHA256("v0:{timestamp}:{body}", signing_secret)``,
with a timestamp-skew check to defeat replay. Constant-time comparison.
"""

from __future__ import annotations

import hashlib
import hmac
import time

MAX_SKEW_SECONDS = 60 * 5


def compute_signature(signing_secret: str, timestamp: str, body: str) -> str:
    basestring = f"v0:{timestamp}:{body}".encode()
    digest = hmac.new(signing_secret.encode(), basestring, hashlib.sha256).hexdigest()
    return f"v0={digest}"


def verify_signature(
    signing_secret: str,
    timestamp: str,
    body: str,
    signature: str,
    *,
    max_skew_seconds: int = MAX_SKEW_SECONDS,
    now: float | None = None,
) -> bool:
    """True iff the Slack signature is valid and the timestamp is within the allowed skew."""
    current = now if now is not None else time.time()
    try:
        ts = int(timestamp)
    except (TypeError, ValueError):
        return False
    if abs(current - ts) > max_skew_seconds:
        return False
    expected = compute_signature(signing_secret, timestamp, body)
    return hmac.compare_digest(expected, signature or "")

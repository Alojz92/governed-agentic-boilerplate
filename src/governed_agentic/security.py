"""Webhook verification and explicit admission failures. No secrets or payloads in errors."""
from __future__ import annotations

import hashlib
import hmac
import re

MAX_BODY_BYTES = 65_536
DELIVERY_RE = re.compile(r"^[0-9a-fA-F-]{16,64}$")


class AdmissionError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def verify_webhook(body: bytes, signature: str | None, secret: str) -> None:
    if not secret:
        raise AdmissionError("WEBHOOK_SECRET_UNAVAILABLE")
    if len(body) > MAX_BODY_BYTES:
        raise AdmissionError("PAYLOAD_TOO_LARGE")
    if not signature or not re.fullmatch(r"sha256=[a-fA-F0-9]{64}", signature):
        raise AdmissionError("INVALID_SIGNATURE")
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature.lower()):
        raise AdmissionError("INVALID_SIGNATURE")


def verify_delivery_id(value: str | None) -> str:
    if not value or not DELIVERY_RE.fullmatch(value):
        raise AdmissionError("INVALID_DELIVERY_ID")
    return value.lower()

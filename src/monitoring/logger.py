"""Redacted application logging helpers."""

from __future__ import annotations

import logging
from typing import Any


SENSITIVE_KEYS = {
    "token",
    "password",
    "secret",
    "access_key_id",
    "secret_access_key",
    "id_student",
    "student_id",
    "email",
    "phone",
}


def redact_fields(fields: dict[str, Any]) -> dict[str, Any]:
    """Remove credentials and direct identifiers before logging."""

    return {
        key: "[REDACTED]" if any(marker in key.lower() for marker in SENSITIVE_KEYS) else value
        for key, value in fields.items()
    }


def get_logger(name: str = "smart-study-planner") -> logging.Logger:
    """Return a standard logger without installing global handlers."""

    return logging.getLogger(name)

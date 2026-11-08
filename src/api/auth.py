"""Browser-session and service-key authentication helpers.

The browser never receives the service API key. Human users authenticate with
an environment-provisioned credential and receive a short-lived, signed,
HttpOnly cookie. Machine clients may continue to use ``X-API-Key``.
"""

from __future__ import annotations

import base64
import binascii
import getpass
import hashlib
import hmac
import json
import os
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlsplit

from fastapi import HTTPException, Request


PASSWORD_SCHEME = "pbkdf2_sha256"
DEFAULT_PASSWORD_ITERATIONS = 600_000
MIN_PASSWORD_ITERATIONS = 100_000
MAX_PASSWORD_ITERATIONS = 2_000_000


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def hash_password(
    password: str,
    *,
    iterations: int = DEFAULT_PASSWORD_ITERATIONS,
    salt: bytes | None = None,
) -> str:
    """Return a portable PBKDF2-SHA256 password verifier.

    The colon-delimited format is safe to place in a Docker ``.env`` file and
    contains no plaintext credential.
    """

    if not password:
        raise ValueError("Password must not be empty")
    if not MIN_PASSWORD_ITERATIONS <= iterations <= MAX_PASSWORD_ITERATIONS:
        raise ValueError("PBKDF2 iteration count is outside the supported range")
    password_salt = salt or secrets.token_bytes(18)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        password_salt,
        iterations,
    )
    return ":".join(
        (PASSWORD_SCHEME, str(iterations), _b64encode(password_salt), _b64encode(digest))
    )


def _parse_password_verifier(verifier: str) -> tuple[int, bytes, bytes]:
    scheme, raw_iterations, raw_salt, raw_digest = verifier.split(":", maxsplit=3)
    iterations = int(raw_iterations)
    if scheme != PASSWORD_SCHEME:
        raise ValueError("Unsupported password scheme")
    if not MIN_PASSWORD_ITERATIONS <= iterations <= MAX_PASSWORD_ITERATIONS:
        raise ValueError("Unsupported PBKDF2 iteration count")
    salt = _b64decode(raw_salt)
    digest = _b64decode(raw_digest)
    if not salt or len(digest) != hashlib.sha256().digest_size:
        raise ValueError("Invalid password verifier")
    return iterations, salt, digest


def verify_password(password: str, verifier: str) -> bool:
    """Verify a password without exposing parsing or timing details."""

    try:
        iterations, salt, expected = _parse_password_verifier(verifier)
        actual = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            iterations,
        )
    except (ValueError, TypeError, binascii.Error):
        return False
    return hmac.compare_digest(actual, expected)


def _flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class SessionIdentity:
    username: str
    expires_at: datetime


@dataclass(frozen=True)
class AuthSettings:
    """Validated authentication configuration for one application process."""

    production: bool
    api_key: str | None
    username: str | None
    password_hash: str | None
    session_secret: bytes | None
    cookie_name: str
    cookie_secure: bool
    session_ttl_seconds: int
    cors_origins: tuple[str, ...]

    @property
    def browser_login_enabled(self) -> bool:
        return bool(self.username and self.password_hash and self.session_secret)

    @property
    def authentication_required(self) -> bool:
        return bool(self.api_key or self.browser_login_enabled)

    @classmethod
    def from_environment(cls, *, production: bool) -> "AuthSettings":
        username = os.getenv("WEB_AUTH_USERNAME") or None
        password_hash = os.getenv("WEB_AUTH_PASSWORD_HASH") or None
        raw_secret = os.getenv("SESSION_SECRET") or None
        configured_browser_values = (username, password_hash, raw_secret)
        if any(configured_browser_values) and not all(configured_browser_values):
            raise RuntimeError(
                "WEB_AUTH_USERNAME, WEB_AUTH_PASSWORD_HASH, and SESSION_SECRET "
                "must be configured together"
            )
        if password_hash:
            try:
                _parse_password_verifier(password_hash)
            except (ValueError, TypeError, binascii.Error) as error:
                raise RuntimeError("WEB_AUTH_PASSWORD_HASH has an invalid format") from error

        secret = raw_secret.encode("utf-8") if raw_secret else None
        if secret and len(secret) < 32:
            raise RuntimeError("SESSION_SECRET must contain at least 32 characters")

        try:
            ttl = int(os.getenv("SESSION_TTL_SECONDS", "28800"))
        except ValueError as error:
            raise RuntimeError("SESSION_TTL_SECONDS must be an integer") from error
        if not 300 <= ttl <= 86_400:
            raise RuntimeError("SESSION_TTL_SECONDS must be between 300 and 86400")

        origins = tuple(
            value.strip().rstrip("/")
            for value in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")
            if value.strip()
        )
        if production and "*" in origins:
            raise RuntimeError("Production CORS_ALLOWED_ORIGINS cannot contain '*'")
        api_key = os.getenv("API_KEY") or None
        if production and not api_key:
            raise RuntimeError("Production requires API_KEY")
        if production and not all(configured_browser_values):
            raise RuntimeError(
                "Production requires WEB_AUTH_USERNAME, WEB_AUTH_PASSWORD_HASH, "
                "and SESSION_SECRET"
            )

        return cls(
            production=production,
            api_key=api_key,
            username=username,
            password_hash=password_hash,
            session_secret=secret,
            cookie_name=os.getenv("SESSION_COOKIE_NAME", "ssp_session"),
            cookie_secure=production or _flag("SESSION_COOKIE_SECURE"),
            session_ttl_seconds=ttl,
            cors_origins=origins,
        )

    def verify_login(self, username: str, password: str) -> bool:
        if not self.browser_login_enabled:
            return False
        return secrets.compare_digest(username, self.username or "") and verify_password(
            password, self.password_hash or ""
        )

    def issue_session(self, username: str, *, now: int | None = None) -> str:
        if not self.session_secret:
            raise RuntimeError("Browser sessions are not configured")
        issued_at = int(time.time()) if now is None else int(now)
        payload = {
            "v": 1,
            "sub": username,
            "iat": issued_at,
            "exp": issued_at + self.session_ttl_seconds,
            "nonce": secrets.token_urlsafe(12),
        }
        encoded_payload = _b64encode(
            json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        )
        signature = _b64encode(
            hmac.new(
                self.session_secret,
                encoded_payload.encode("ascii"),
                hashlib.sha256,
            ).digest()
        )
        return f"{encoded_payload}.{signature}"

    def read_session(self, token: str | None, *, now: int | None = None) -> SessionIdentity | None:
        if not token or not self.session_secret or not self.username:
            return None
        try:
            encoded_payload, supplied_signature = token.split(".", maxsplit=1)
            expected_signature = _b64encode(
                hmac.new(
                    self.session_secret,
                    encoded_payload.encode("ascii"),
                    hashlib.sha256,
                ).digest()
            )
            if not hmac.compare_digest(supplied_signature, expected_signature):
                return None
            payload = json.loads(_b64decode(encoded_payload))
            current_time = int(time.time()) if now is None else int(now)
            expires = int(payload["exp"])
            issued = int(payload["iat"])
            username = str(payload["sub"])
            if payload.get("v") != 1 or issued > current_time + 60 or expires <= current_time:
                return None
            if expires - issued != self.session_ttl_seconds:
                return None
            if not secrets.compare_digest(username, self.username):
                return None
        except (ValueError, TypeError, KeyError, json.JSONDecodeError, binascii.Error):
            return None
        return SessionIdentity(
            username=username,
            expires_at=datetime.fromtimestamp(expires, tz=timezone.utc),
        )

    def request_session(self, request: Request) -> SessionIdentity | None:
        return self.read_session(request.cookies.get(self.cookie_name))

    def authorize(self, request: Request, *, csrf_protected: bool = False) -> str:
        supplied_key = request.headers.get("x-api-key", "")
        if self.api_key and supplied_key and secrets.compare_digest(supplied_key, self.api_key):
            return "api_key"

        identity = self.request_session(request)
        if identity:
            if csrf_protected:
                self.require_same_origin(request)
            return "session"

        if not self.authentication_required:
            return "development_anonymous"
        raise HTTPException(status_code=401, detail="Authentication required")

    def require_same_origin(self, request: Request) -> None:
        """Reject cross-origin state-changing requests authenticated by cookie."""

        origin = request.headers.get("origin")
        if not origin:
            if self.production:
                raise HTTPException(status_code=403, detail="Origin header is required")
            return
        normalized = origin.rstrip("/")
        if normalized in self.cors_origins:
            return
        parsed = urlsplit(normalized)
        request_host = request.headers.get("host", "").lower()
        if parsed.netloc.lower() != request_host:
            raise HTTPException(status_code=403, detail="Cross-origin request rejected")
        if self.production and parsed.scheme != "https":
            raise HTTPException(status_code=403, detail="HTTPS origin is required")


def _password_hash_cli() -> None:
    password = getpass.getpass("Password: ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match")
    if len(password) < 12:
        raise SystemExit("Use a password with at least 12 characters")
    print(hash_password(password))


if __name__ == "__main__":  # pragma: no cover - operator utility
    _password_hash_cli()

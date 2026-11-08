from src.api.auth import AuthSettings, hash_password, verify_password


def test_password_hash_round_trip_and_wrong_password_rejection() -> None:
    verifier = hash_password(
        "correct horse battery staple",
        iterations=100_000,
        salt=b"fixed-test-salt-12",
    )

    assert verifier.startswith("pbkdf2_sha256:")
    assert verify_password("correct horse battery staple", verifier)
    assert not verify_password("incorrect", verifier)


def test_signed_session_rejects_tampering_and_expiry(monkeypatch) -> None:
    monkeypatch.setenv("WEB_AUTH_USERNAME", "operator")
    monkeypatch.setenv(
        "WEB_AUTH_PASSWORD_HASH",
        hash_password("strong-test-password", iterations=100_000),
    )
    monkeypatch.setenv("SESSION_SECRET", "session-secret-with-at-least-thirty-two-characters")
    monkeypatch.setenv("SESSION_TTL_SECONDS", "300")
    monkeypatch.delenv("API_KEY", raising=False)
    settings = AuthSettings.from_environment(production=False)
    token = settings.issue_session("operator", now=1_000)

    assert settings.read_session(token, now=1_100).username == "operator"
    assert settings.read_session(f"{token}x", now=1_100) is None
    assert settings.read_session(token, now=1_301) is None

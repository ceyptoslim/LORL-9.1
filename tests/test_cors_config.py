"""CORS configuration hardening — no wildcard+credentials combo."""
from fastapi.middleware.cors import CORSMiddleware

from lorl.api.main import create_app


def test_cors_never_wildcard_with_credentials():
    app = create_app()
    cors = [m for m in app.user_middleware if m.cls is CORSMiddleware]
    assert cors, "CORS middleware missing"
    for m in cors:
        origins = m.kwargs.get("allow_origins")
        assert origins != ["*"] or not m.kwargs.get("allow_credentials"), (
            "wildcard origins must not be paired with credentials (spec-invalid)"
        )


def test_cors_origins_resolved_from_env(monkeypatch):
    monkeypatch.setenv("LORL_CORS_ORIGINS", "https://app.example.com, https://api.example.com")
    app = create_app()
    cors = [m for m in app.user_middleware if m.cls is CORSMiddleware][0]
    assert cors.kwargs["allow_origins"] == ["https://app.example.com", "https://api.example.com"]

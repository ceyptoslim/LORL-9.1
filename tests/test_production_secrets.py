"""Fail-closed production secret validation (strict env-presence rule).

Regression tests for the audit finding: hardcoded dev-default JWT secrets
(lorl-dev-secret in routes, constructor default in CustosClient) with no
production startup check.
"""
import pytest

from lorl.governance.custos_client import CustosClient, validate_production_secrets


class TestValidateProductionSecrets:
    def test_production_unset_secret_raises(self, monkeypatch):
        monkeypatch.setenv("CUSTOS_ENV", "production")
        monkeypatch.delenv("LORL_CUSTOS_JWT_SECRET", raising=False)
        with pytest.raises(RuntimeError, match="LORL_CUSTOS_JWT_SECRET"):
            validate_production_secrets()

    def test_production_dev_default_secret_raises(self, monkeypatch):
        monkeypatch.setenv("CUSTOS_ENV", "production")
        monkeypatch.setenv("LORL_CUSTOS_JWT_SECRET", "custos-secret-key-at-least-32-bytes-long!")
        with pytest.raises(RuntimeError, match="dev default"):
            validate_production_secrets()

    def test_production_real_secret_passes(self, monkeypatch):
        monkeypatch.setenv("CUSTOS_ENV", "production")
        monkeypatch.setenv("LORL_CUSTOS_JWT_SECRET", "a-real-unique-production-secret-32b")
        assert validate_production_secrets() is None

    def test_development_unset_secret_passes(self, monkeypatch):
        monkeypatch.setenv("CUSTOS_ENV", "development")
        monkeypatch.delenv("LORL_CUSTOS_JWT_SECRET", raising=False)
        assert validate_production_secrets() is None


class TestSecretResolution:
    def test_explicit_secret_wins(self):
        c = CustosClient(jwt_secret="my-explicit-secret")
        assert c.jwt_secret == "my-explicit-secret"

    def test_env_resolves_when_not_explicit(self, monkeypatch):
        monkeypatch.setenv("LORL_CUSTOS_JWT_SECRET", "from-env-secret")
        c = CustosClient()
        assert c.jwt_secret == "from-env-secret"

    def test_dev_fallback_only_when_nothing_set(self, monkeypatch):
        monkeypatch.delenv("LORL_CUSTOS_JWT_SECRET", raising=False)
        c = CustosClient()
        assert c.jwt_secret == "custos-secret-key-at-least-32-bytes-long!"

    def test_create_app_refuses_production_without_secret(self, monkeypatch):
        from lorl.api.main import create_app
        monkeypatch.setenv("CUSTOS_ENV", "production")
        monkeypatch.delenv("LORL_CUSTOS_JWT_SECRET", raising=False)
        with pytest.raises(RuntimeError):
            create_app()

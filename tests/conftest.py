"""Pytest fixtures for LORL-9.1 tests."""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from lorl.api.main import create_app
from lorl.core.ledger import EventLedger


@pytest.fixture
def temp_db():
    """Provide a temporary SQLite database URL."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db_url = f"sqlite:///{path}"
    yield db_url
    os.unlink(path)


@pytest.fixture
def ledger(temp_db):
    """Provide a fresh EventLedger with a temporary database."""
    ledger_instance = EventLedger(temp_db)
    yield ledger_instance
    ledger_instance.close()


@pytest.fixture
def app():
    """Create a test FastAPI app with an in-memory database."""
    test_app = create_app()
    yield test_app


@pytest.fixture
def client(app):
    """Provide a test HTTP client."""
    return TestClient(app)

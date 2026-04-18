"""Unit tests for FastAPI health and security endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

import app.main as main_module


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Create a test client with startup side effects disabled."""
    monkeypatch.setattr(main_module, "init_bot", AsyncMock())
    monkeypatch.setattr(main_module, "shutdown_bot", AsyncMock())
    monkeypatch.setattr(main_module, "set_webhook", AsyncMock())
    monkeypatch.setattr(main_module, "close_redis", AsyncMock())
    return TestClient(main_module.app)


def test_liveness_endpoint(client: TestClient) -> None:
    """The liveness endpoint should always report process health."""
    response = client.get("/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_endpoint_reports_healthy_dependencies(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Readiness should return OK when Redis and Supabase are reachable."""
    monkeypatch.setattr(main_module, "ping_redis", AsyncMock(return_value=True))
    monkeypatch.setattr(main_module, "ping_supabase", lambda: True)

    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_readiness_endpoint_reports_degraded_dependencies(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Readiness should fail when a critical dependency is unavailable."""
    monkeypatch.setattr(main_module, "ping_redis", AsyncMock(return_value=False))
    monkeypatch.setattr(main_module, "ping_supabase", lambda: True)

    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "degraded"


def test_webhook_rejects_invalid_secret(client: TestClient) -> None:
    """Telegram webhook requests must provide the configured secret token."""
    response = client.post(main_module.settings.webhook_path, json={"update_id": 1})
    assert response.status_code == 403

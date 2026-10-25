"""Focused automated tests for GET /links/{code}/stats and health check."""

from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models import Link


def test_link_stats_unclicked_and_clicked(client: TestClient, db_session: Session) -> None:
    """Test statistics for an unclicked link and verify updates after redirect."""
    # 1. Unclicked link
    link = Link(
        code="statstest",
        original_url="https://example.com/stats-target",
        total_clicks=0,
        last_clicked_at=None,
    )
    db_session.add(link)
    db_session.commit()

    res_initial = client.get("/links/statstest/stats")
    assert res_initial.status_code == 200
    data_initial = res_initial.json()
    assert data_initial["code"] == "statstest"
    assert data_initial["original_url"] == "https://example.com/stats-target"
    assert data_initial["total_clicks"] == 0
    assert data_initial["last_clicked_at"] is None
    assert data_initial["is_expired"] is False

    # 2. Perform a redirect to increment click
    res_redirect = client.get("/statstest")
    assert res_redirect.status_code == 307

    # 3. Stats after redirect
    res_after = client.get("/links/statstest/stats")
    assert res_after.status_code == 200
    data_after = res_after.json()
    assert data_after["total_clicks"] == 1
    assert data_after["last_clicked_at"] is not None


def test_link_stats_expired_and_not_found(client: TestClient, db_session: Session) -> None:
    """Test that statistics remain accessible for expired links, and 404 for unknown codes."""
    # 1. Expired link stats
    past_expiry = datetime.now(timezone.utc) - timedelta(days=1)
    last_click = datetime.now(timezone.utc) - timedelta(days=2)
    expired_link = Link(
        code="expired-stat-link",
        original_url="https://example.com/expired-item",
        expires_at=past_expiry,
        total_clicks=10,
        last_clicked_at=last_click,
    )
    db_session.add(expired_link)
    db_session.commit()

    res_expired = client.get("/links/expired-stat-link/stats")
    assert res_expired.status_code == 200
    data_expired = res_expired.json()
    assert data_expired["code"] == "expired-stat-link"
    assert data_expired["total_clicks"] == 10
    assert data_expired["last_clicked_at"] is not None
    assert data_expired["is_expired"] is True

    # 2. Unknown code -> 404
    res_404 = client.get("/links/ghost-link/stats")
    assert res_404.status_code == 404
    assert res_404.json()["detail"]["error"] == "link_not_found"


def test_health_check(client: TestClient) -> None:
    """Test operational health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

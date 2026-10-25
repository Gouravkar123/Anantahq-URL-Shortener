"""Focused automated tests for GET /{code} redirection and click tracking."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models import Link


def test_redirect_success_and_atomic_increment(client: TestClient, db_session: Session) -> None:
    """Test HTTP 307 redirect, Location header, and click count / timestamp updates."""
    link = Link(code="go-target", original_url="https://example.com/target-page")
    db_session.add(link)
    db_session.commit()

    # Initial state
    assert link.total_clicks == 0
    assert link.last_clicked_at is None

    # First redirect
    res1 = client.get("/go-target")
    assert res1.status_code == 307
    assert res1.headers["Location"] == "https://example.com/target-page"

    db_session.expire_all()
    updated1 = db_session.query(Link).filter(Link.code == "go-target").one()
    assert updated1.total_clicks == 1
    assert updated1.last_clicked_at is not None

    # Second redirect
    res2 = client.get("/go-target")
    assert res2.status_code == 307
    db_session.expire_all()
    updated2 = db_session.query(Link).filter(Link.code == "go-target").one()
    assert updated2.total_clicks == 2


def test_redirect_unknown_code_and_expired_link(client: TestClient, db_session: Session) -> None:
    """Test HTTP 404 for unknown codes and HTTP 410 for expired links without incrementing clicks."""
    # 1. Unknown code -> 404
    res_404 = client.get("/nonexistent-code")
    assert res_404.status_code == 404
    assert res_404.json()["detail"]["error"] == "link_not_found"

    # 2. Expired link -> 410
    past_expiry = datetime.now(timezone.utc) - timedelta(hours=1)
    expired_link = Link(
        code="expired-code",
        original_url="https://example.com/old",
        expires_at=past_expiry,
        total_clicks=5,
    )
    db_session.add(expired_link)
    db_session.commit()

    res_410 = client.get("/expired-code")
    assert res_410.status_code == 410
    assert res_410.json()["detail"]["error"] == "link_expired"

    # Verify clicks did not increment
    db_session.expire_all()
    refreshed = db_session.query(Link).filter(Link.code == "expired-code").one()
    assert refreshed.total_clicks == 5


def test_concurrent_redirects_atomic_click_counter(client: TestClient, db_session: Session) -> None:
    """Test that concurrent redirect requests atomically increment total_clicks without lost updates."""
    link = Link(code="conc-link", original_url="https://example.com/concurrent")
    db_session.add(link)
    db_session.commit()

    num_requests = 20

    def make_redirect(_):
        return client.get("/conc-link")

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(make_redirect, range(num_requests)))

    for res in results:
        assert res.status_code == 307

    db_session.expire_all()
    updated = db_session.query(Link).filter(Link.code == "conc-link").one()
    assert updated.total_clicks == num_requests

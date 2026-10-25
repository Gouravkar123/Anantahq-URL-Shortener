"""Focused automated tests for POST /links endpoint."""

from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models import Link


def test_create_short_link_success(client: TestClient, db_session: Session) -> None:
    """Test successful link creation with auto-generated code and with custom alias."""
    # 1. Creation with auto-generated code (no expiration)
    res_auto = client.post("/links", json={"url": "https://fastapi.tiangolo.com/tutorial/"})
    assert res_auto.status_code == 201
    data_auto = res_auto.json()
    assert len(data_auto["code"]) == 6
    assert data_auto["short_url"] == f"http://testserver/{data_auto['code']}"
    assert data_auto["original_url"] == "https://fastapi.tiangolo.com/tutorial/"
    assert data_auto["expires_at"] is None

    # Verify persistence
    db_link = db_session.query(Link).filter(Link.code == data_auto["code"]).first()
    assert db_link is not None
    assert db_link.total_clicks == 0

    # 2. Creation with custom alias and future expiration
    future_time = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    res_alias = client.post(
        "/links",
        json={
            "url": "https://www.example.com/products/item1",
            "custom_alias": "promo-item1",
            "expires_at": future_time,
        },
    )
    assert res_alias.status_code == 201
    data_alias = res_alias.json()
    assert data_alias["code"] == "promo-item1"
    assert data_alias["short_url"] == "http://testserver/promo-item1"
    assert data_alias["expires_at"] is not None


@pytest.mark.parametrize(
    "bad_url",
    [
        "javascript:alert(1)",
        "http:///missing-host",
        "https://example.com:abc/path",
        "https://example.com:99999/path",
        "http://example.com:0/path",
        "https://foo..bar/path",
        "http://256.256.256.256/path",
        "https://example.com/has space",
        "not-a-url",
        "",
    ],
)
def test_create_short_link_url_validation(client: TestClient, bad_url: str) -> None:
    """Test rejection of malformed URLs, unsupported schemes, invalid ports, and bad hosts."""
    response = client.post("/links", json={"url": bad_url})
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["error"] == "validation_error"


def test_create_short_link_duplicate_alias_and_past_expiry(client: TestClient) -> None:
    """Test duplicate custom alias rejection (409) and past expiry rejection (422)."""
    # 1. Create initial link
    client.post("/links", json={"url": "https://example.com/1", "custom_alias": "dup-alias"})

    # Duplicate alias attempt
    dup_res = client.post("/links", json={"url": "https://example.com/2", "custom_alias": "dup-alias"})
    assert dup_res.status_code == 409
    assert dup_res.json()["detail"]["error"] == "alias_already_exists"

    # 2. Past expiration timestamp
    past_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    past_res = client.post("/links", json={"url": "https://example.com/3", "expires_at": past_time})
    assert past_res.status_code == 422
    assert past_res.json()["detail"]["error"] == "validation_error"

    # 3. Invalid expiration format
    bad_date_res = client.post("/links", json={"url": "https://example.com/4", "expires_at": "invalid-date"})
    assert bad_date_res.status_code == 422
    assert bad_date_res.json()["detail"]["error"] == "validation_error"

"""Pydantic request and response schemas for URL Shortener API."""

from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field, field_validator
from app.utils.url_validation import validate_and_normalize_url
from app.utils.short_code import validate_custom_alias


class ErrorDetail(BaseModel):
    """Structured error payload containing error code and message."""

    error: str = Field(..., description="Machine-readable error identifier")
    message: str = Field(..., description="Human-readable error explanation")


class ErrorResponse(BaseModel):
    """Standardized API error response format."""

    detail: ErrorDetail


class LinkCreateRequest(BaseModel):
    """Payload for creating a new shortened link."""

    url: str = Field(
        ...,
        description="The absolute destination URL (HTTP or HTTPS)",
        examples=["https://www.example.com/products?id=123"],
    )
    custom_alias: Optional[str] = Field(
        None,
        description="Optional custom short code (3-30 alphanumeric, hyphen, or underscore characters)",
        examples=["product123"],
    )
    expires_at: Optional[datetime] = Field(
        None,
        description="Optional future expiration timestamp in ISO 8601 format",
        examples=["2027-01-01T00:00:00Z"],
    )

    @field_validator("url")
    @classmethod
    def validate_url_field(cls, v: str) -> str:
        """Validate URL scheme, hostname, and structure."""
        return validate_and_normalize_url(v)

    @field_validator("custom_alias")
    @classmethod
    def validate_alias_field(cls, v: Optional[str]) -> Optional[str]:
        """Validate custom alias policy."""
        if v is None:
            return None
        return validate_custom_alias(v)

    @field_validator("expires_at")
    @classmethod
    def validate_expires_at_field(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Validate that expiry timestamp is strictly in the future."""
        if v is None:
            return None

        # Normalize to UTC
        if v.tzinfo is None:
            v_utc = v.replace(tzinfo=timezone.utc)
        else:
            v_utc = v.astimezone(timezone.utc)

        now_utc = datetime.now(timezone.utc)
        if v_utc <= now_utc:
            raise ValueError("Expiration date must be a future timestamp.")

        return v_utc


class LinkResponse(BaseModel):
    """Response returned upon link creation."""

    code: str = Field(..., description="The unique short code identifier")
    short_url: str = Field(..., description="The full redirect URL")
    original_url: str = Field(..., description="The original destination URL")
    expires_at: Optional[datetime] = Field(None, description="Expiration timestamp, if set")

    model_config = {
        "from_attributes": True,
        "json_encoders": {
            datetime: lambda v: v.isoformat() if v else None
        },
    }


class LinkStatsResponse(BaseModel):
    """Statistics and metadata for an existing short link."""

    code: str = Field(..., description="The unique short code identifier")
    original_url: str = Field(..., description="The original destination URL")
    total_clicks: int = Field(..., description="Total successful redirects recorded")
    last_clicked_at: Optional[datetime] = Field(None, description="Timestamp of most recent redirect")
    expires_at: Optional[datetime] = Field(None, description="Expiration timestamp, if set")
    is_expired: bool = Field(..., description="Indicates if the link has passed its expiration time")

    model_config = {
        "from_attributes": True,
        "json_encoders": {
            datetime: lambda v: v.isoformat() if v else None
        },
    }

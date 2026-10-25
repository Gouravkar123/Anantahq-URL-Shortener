"""SQLAlchemy models for URL Shortener."""

from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Integer, String, Text, TypeDecorator, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class UtcDateTime(TypeDecorator):
    """DateTime TypeDecorator guaranteeing timezone-aware UTC datetimes across all dialects."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: Optional[datetime], dialect) -> Optional[datetime]:
        if value is not None:
            if value.tzinfo is None:
                # Treat naive as UTC
                value = value.replace(tzinfo=timezone.utc)
            else:
                value = value.astimezone(timezone.utc)
        return value

    def process_result_value(self, value: Optional[datetime], dialect) -> Optional[datetime]:
        if value is not None:
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)
        return value


class Link(Base):
    """Database model representing a shortened link and its analytics."""

    __tablename__ = "links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    original_url: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime(),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        UtcDateTime(),
        nullable=True,
        index=True,
    )
    total_clicks: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    last_clicked_at: Mapped[Optional[datetime]] = mapped_column(
        UtcDateTime(),
        nullable=True,
    )



    def is_expired(self, current_time: Optional[datetime] = None) -> bool:
        """Check if the link has expired relative to a given UTC reference time."""
        if self.expires_at is None:
            return False
        ref_time = current_time or datetime.now(timezone.utc)
        if ref_time.tzinfo is None:
            ref_time = ref_time.replace(tzinfo=timezone.utc)
        else:
            ref_time = ref_time.astimezone(timezone.utc)
        return self.expires_at <= ref_time

    def __repr__(self) -> str:
        return f"<Link(id={self.id}, code={self.code!r}, total_clicks={self.total_clicks})>"

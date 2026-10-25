"""Business logic service for link creation, redirection, and statistics."""

from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select, update, or_
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Link
from app.schemas import LinkCreateRequest, LinkResponse, LinkStatsResponse
from app.utils.short_code import generate_random_code


class LinkServiceError(Exception):
    """Base exception for link service operations."""

    def __init__(self, error_code: str, message: str, status_code: int = 400):
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class LinkNotFoundError(LinkServiceError):
    """Raised when a requested short code is not found in the database."""

    def __init__(self, message: str = "No short link exists for this code."):
        super().__init__(error_code="link_not_found", message=message, status_code=404)


class LinkExpiredError(LinkServiceError):
    """Raised when attempting to access a link that has expired."""

    def __init__(self, message: str = "This short link has expired."):
        super().__init__(error_code="link_expired", message=message, status_code=410)


class DuplicateAliasError(LinkServiceError):
    """Raised when the specified custom alias is already taken."""

    def __init__(self, message: str = "The requested custom alias is already in use."):
        super().__init__(error_code="alias_already_exists", message=message, status_code=409)


class CodeGenerationError(LinkServiceError):
    """Raised when unique code generation fails after maximum retries."""

    def __init__(self, message: str = "Failed to generate a unique short code. Please try again."):
        super().__init__(error_code="code_generation_failed", message=message, status_code=503)


class DatabaseOperationError(LinkServiceError):
    """Raised when an unhandled database error occurs."""

    def __init__(self, message: str = "A database error occurred while processing the request."):
        super().__init__(error_code="database_error", message=message, status_code=500)


class LinkService:
    """Service providing core business operations for short links."""

    @staticmethod
    def _normalize_now(ref_time: Optional[datetime] = None) -> datetime:
        """Return a timezone-aware UTC datetime."""
        now = ref_time or datetime.now(timezone.utc)
        if now.tzinfo is None:
            return now.replace(tzinfo=timezone.utc)
        return now.astimezone(timezone.utc)

    @classmethod
    def create_link(
        cls,
        db: Session,
        data: LinkCreateRequest,
        base_url: Optional[str] = None,
    ) -> LinkResponse:
        """Create a new short link, generating a code or validating a custom alias.

        Guarantees:
        - Rejects duplicate custom aliases with DuplicateAliasError (409 Conflict).
        - Generates random codes with collision avoidance and database retry.
        - Never overwrites existing links.
        - Persists inside a clean transaction.
        """
        settings = get_settings()
        app_base_url = (base_url or settings.base_url).rstrip("/")

        if data.custom_alias:
            # Custom alias workflow
            code = data.custom_alias

            # Pre-check existence
            existing = db.execute(select(Link).where(Link.code == code)).scalar_one_or_none()
            if existing:
                raise DuplicateAliasError()

            new_link = Link(
                code=code,
                original_url=data.url,
                expires_at=data.expires_at,
            )
            try:
                db.add(new_link)
                db.commit()
                db.refresh(new_link)
            except IntegrityError:
                db.rollback()
                raise DuplicateAliasError()
            except SQLAlchemyError as exc:
                db.rollback()
                raise DatabaseOperationError() from exc

            return LinkResponse(
                code=new_link.code,
                short_url=f"{app_base_url}/{new_link.code}",
                original_url=new_link.original_url,
                expires_at=new_link.expires_at,
            )

        # Auto-generated code workflow with collision retry
        retries = 0
        max_retries = settings.short_code_max_retries

        while retries < max_retries:
            candidate_code = generate_random_code(settings.short_code_length)

            # Check if exists in DB or is in reserved list
            if candidate_code.lower() in {r.lower() for r in settings.reserved_aliases}:
                retries += 1
                continue

            existing = db.execute(
                select(Link).where(Link.code == candidate_code)
            ).scalar_one_or_none()
            if existing:
                retries += 1
                continue

            new_link = Link(
                code=candidate_code,
                original_url=data.url,
                expires_at=data.expires_at,
            )
            try:
                db.add(new_link)
                db.commit()
                db.refresh(new_link)
                return LinkResponse(
                    code=new_link.code,
                    short_url=f"{app_base_url}/{new_link.code}",
                    original_url=new_link.original_url,
                    expires_at=new_link.expires_at,
                )
            except IntegrityError:
                db.rollback()
                retries += 1
                continue
            except SQLAlchemyError as exc:
                db.rollback()
                raise DatabaseOperationError() from exc

        raise CodeGenerationError()

    @classmethod
    def get_redirect_target(
        cls,
        db: Session,
        code: str,
        current_time: Optional[datetime] = None,
    ) -> str:
        """Lookup link, verify validity, record click atomically, and return original URL.

        Guarantees:
        - 404 LinkNotFoundError if code does not exist.
        - 410 LinkExpiredError if link exists but is expired.
        - Clicks are NOT incremented for unknown or expired links.
        - Atomic update of total_clicks and last_clicked_at guarded by expiry condition
          (Link.expires_at IS NULL OR Link.expires_at > now) to eliminate expiry race conditions.
        - Handles zero-row updates and rechecks to accurately distinguish 404 from 410.
        """
        now = cls._normalize_now(current_time)

        link = db.execute(select(Link).where(Link.code == code)).scalar_one_or_none()
        if not link:
            raise LinkNotFoundError()

        if link.is_expired(now):
            raise LinkExpiredError()

        # Atomic increment guarded by expiry condition
        try:
            stmt = (
                update(Link)
                .where(
                    Link.id == link.id,
                    or_(Link.expires_at.is_(None), Link.expires_at > now),
                )
                .values(
                    total_clicks=Link.total_clicks + 1,
                    last_clicked_at=now,
                )
            )
            result = db.execute(stmt)

            if result.rowcount == 0:
                db.rollback()
                # Recheck link state to distinguish 404 from 410
                rechecked = db.execute(select(Link).where(Link.code == code)).scalar_one_or_none()
                if not rechecked:
                    raise LinkNotFoundError()
                if rechecked.is_expired(now):
                    raise LinkExpiredError()
                raise LinkExpiredError()

            db.commit()
            return link.original_url
        except LinkServiceError:
            db.rollback()
            raise
        except SQLAlchemyError as exc:
            db.rollback()
            raise DatabaseOperationError() from exc

    @classmethod
    def get_stats(
        cls,
        db: Session,
        code: str,
        current_time: Optional[datetime] = None,
    ) -> LinkStatsResponse:
        """Retrieve link statistics and metadata.

        Guarantees:
        - 404 LinkNotFoundError for unknown codes.
        - Statistics remain accessible even for expired links.
        - is_expired dynamically calculated relative to current_time.
        - Returns null for last_clicked_at if never clicked.
        """
        now = cls._normalize_now(current_time)

        link = db.execute(select(Link).where(Link.code == code)).scalar_one_or_none()
        if not link:
            raise LinkNotFoundError()

        return LinkStatsResponse(
            code=link.code,
            original_url=link.original_url,
            total_clicks=link.total_clicks,
            last_clicked_at=link.last_clicked_at,
            expires_at=link.expires_at,
            is_expired=link.is_expired(now),
        )

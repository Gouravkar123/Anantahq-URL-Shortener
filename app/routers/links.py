"""API endpoints for URL shortening, redirection, and link analytics."""

from fastapi import APIRouter, Depends, Path, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import (
    ErrorResponse,
    LinkCreateRequest,
    LinkResponse,
    LinkStatsResponse,
)
from app.services.link_service import LinkService

router = APIRouter(tags=["Links"])


@router.post(
    "/links",
    response_model=LinkResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a short link",
    description=(
        "Create a shortened link from an original destination URL. "
        "Optionally accepts a custom alias (3-30 characters) and an ISO 8601 future expiration timestamp."
    ),
    responses={
        status.HTTP_201_CREATED: {
            "model": LinkResponse,
            "description": "Short link successfully created.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": "Custom alias is already in use.",
        },
        422: {
            "model": ErrorResponse,
            "description": "Request validation failed (invalid URL, alias format, or past expiry date).",
        },
    },
)
def create_link(
    payload: LinkCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> LinkResponse:
    """Handle link creation request."""
    # Use request base_url if available, or fallback to configuration
    base_url = str(request.base_url)
    return LinkService.create_link(db=db, data=payload, base_url=base_url)


@router.get(
    "/links/{code}/stats",
    response_model=LinkStatsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get link statistics",
    description=(
        "Retrieve analytics for a shortened link, including total clicks, "
        "last click timestamp, and current expiration status. "
        "Statistics remain accessible even after a link has expired."
    ),
    responses={
        status.HTTP_200_OK: {
            "model": LinkStatsResponse,
            "description": "Link statistics retrieved successfully.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No link exists for the provided code.",
        },
    },
)
def get_link_stats(
    code: str = Path(..., min_length=1, max_length=50, description="Short link identifier code"),
    db: Session = Depends(get_db),
) -> LinkStatsResponse:
    """Retrieve statistics for a given short code."""
    return LinkService.get_stats(db=db, code=code)


@router.get(
    "/{code}",
    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    summary="Redirect to target URL",
    description=(
        "Redirects client to the original target destination using HTTP 307 Temporary Redirect. "
        "Increments total click counter and updates last clicked timestamp atomically. "
        "Returns HTTP 404 for unknown codes and HTTP 410 for expired links without incrementing clicks."
    ),
    responses={
        status.HTTP_307_TEMPORARY_REDIRECT: {
            "description": "Temporary redirect to original destination URL.",
            "headers": {
                "Location": {
                    "description": "Original destination URL",
                    "schema": {"type": "string"},
                }
            },
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Short code not found.",
        },
        status.HTTP_410_GONE: {
            "model": ErrorResponse,
            "description": "Short link has expired.",
        },
    },
)
def redirect_to_url(
    code: str = Path(..., min_length=1, max_length=50, description="Short link identifier code"),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Perform atomic click increment and redirect to the target URL."""
    target_url = LinkService.get_redirect_target(db=db, code=code)
    return RedirectResponse(
        url=target_url,
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )

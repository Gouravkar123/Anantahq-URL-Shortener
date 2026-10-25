"""Main FastAPI application entry point."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database import init_db
from app.routers.links import router as links_router
from app.services.link_service import LinkServiceError

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager for startup and shutdown events."""
    # Ensure database schema is initialized on startup
    init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    description=(
        "Production-quality URL Shortener REST API implementing reliable code generation, "
        "custom aliases, collision resolution, temporary HTTP 307 redirection, "
        "and atomic click analytics."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)


@app.exception_handler(LinkServiceError)
async def link_service_exception_handler(request: Request, exc: LinkServiceError) -> JSONResponse:
    """Handle domain service errors and render consistent JSON error responses."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": {
                "error": exc.error_code,
                "message": exc.message,
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Format Pydantic request validation errors into standard API error envelope."""
    error_messages = []
    for err in exc.errors():
        field = ".".join(str(loc) for loc in err.get("loc", []) if loc != "body")
        msg = err.get("msg", "Invalid value")
        # Remove 'Value error, ' prefix if present from Pydantic custom validators
        if msg.startswith("Value error, "):
            msg = msg[len("Value error, "):]
        if field:
            error_messages.append(f"{field}: {msg}")
        else:
            error_messages.append(msg)

    combined_message = "; ".join(error_messages) if error_messages else "Request validation failed."
    return JSONResponse(
        status_code=422,
        content={
            "detail": {
                "error": "validation_error",
                "message": combined_message,
            }
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler preventing raw tracebacks from leaking to API clients."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": {
                "error": "internal_server_error",
                "message": "An unexpected internal server error occurred.",
            }
        },
    )


@app.get(
    "/health",
    tags=["System"],
    summary="Health check",
    description="Check the operational health status of the service.",
)
def health_check() -> dict:
    """Return basic health status of the service."""
    return {"status": "healthy"}


# Include application routers
app.include_router(links_router)

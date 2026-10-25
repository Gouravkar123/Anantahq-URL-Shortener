"""Short code generation and custom alias validation."""

import re
import secrets
import string
from typing import Optional, Set
from app.config import get_settings

BASE62_ALPHABET = string.ascii_letters + string.digits  # 62 characters: a-z, A-Z, 0-9


class InvalidAliasError(ValueError):
    """Raised when a custom alias violates alias policy."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def generate_random_code(length: Optional[int] = None) -> str:
    """Generate a cryptographically secure random short code using Base62 characters."""
    settings = get_settings()
    code_len = length or settings.short_code_length
    return "".join(secrets.choice(BASE62_ALPHABET) for _ in range(code_len))


def validate_custom_alias(
    alias: str,
    reserved_aliases: Optional[Set[str]] = None,
) -> str:
    """Validate a user-supplied custom alias.

    Policy:
    - Length: between 3 and 30 characters (configurable via settings).
    - Allowed characters: ASCII alphanumeric, hyphens, and underscores (a-z, A-Z, 0-9, -, _).
    - Cannot contain path separators (/ or \\), dots, spaces, or query characters.
    - Cannot match reserved system routes (e.g., 'links', 'docs', 'health').

    Returns:
        The validated alias string.

    Raises:
        InvalidAliasError: If any condition is violated.
    """
    settings = get_settings()
    if not isinstance(alias, str):
        raise InvalidAliasError("Custom alias must be a string.")

    cleaned = alias.strip()
    if not cleaned:
        raise InvalidAliasError("Custom alias cannot be empty or whitespace only.")

    if len(cleaned) < settings.min_alias_length:
        raise InvalidAliasError(
            f"Custom alias must be at least {settings.min_alias_length} characters long."
        )

    if len(cleaned) > settings.max_alias_length:
        raise InvalidAliasError(
            f"Custom alias cannot exceed {settings.max_alias_length} characters."
        )

    reserved = reserved_aliases if reserved_aliases is not None else settings.reserved_aliases
    if cleaned.lower() in {r.lower() for r in reserved}:
        raise InvalidAliasError(f"The alias '{cleaned}' is reserved by the system.")

    if not re.match(settings.alias_regex, cleaned):
        raise InvalidAliasError(
            "Custom alias may only contain alphanumeric characters, hyphens, and underscores."
        )

    return cleaned

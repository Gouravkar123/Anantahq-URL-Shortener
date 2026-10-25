"""URL validation and normalization utilities."""

import ipaddress
import re
from urllib.parse import urlparse
import idna


class InvalidURLError(ValueError):
    """Raised when a provided URL violates URL validation policy."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def validate_and_normalize_url(raw_url: str) -> str:
    """Validate that the given string is a valid absolute HTTP or HTTPS URL.

    Requirements enforced:
    1. Must be a non-empty string under 2048 characters.
    2. Must not contain whitespace (leading, trailing, or internal) or control characters.
    3. Scheme must be strictly 'http' or 'https' (case-insensitive).
    4. Must contain a non-empty valid netloc and hostname.
    5. Schemes like javascript:, data:, file:, ftp:, etc. are rejected.
    6. Port numbers must be valid integers between 1 and 65535 (port 0 or >65535 or non-digits rejected).
    7. Relative paths and missing-scheme strings are rejected.
    8. Hostnames cannot contain consecutive dots or empty labels.
    9. Validates IPv4 addresses (rejects invalid octets like 256.x or malformed structures).
    10. Validates IPv6 literals (e.g., [::1] or [2001:db8::1]).
    11. Supports internationalized domain names (IDN) via standard Punycode conversion.

    Returns:
        The validated URL string.

    Raises:
        InvalidURLError: If the URL fails any validation rule.
    """
    if not isinstance(raw_url, str):
        raise InvalidURLError("URL must be a string.")

    if not raw_url:
        raise InvalidURLError("URL cannot be empty.")

    # Disallow whitespace (leading, trailing, or internal)
    if any(c.isspace() for c in raw_url):
        raise InvalidURLError("URL cannot contain whitespace.")

    # Disallow control characters
    if any(ord(c) < 32 or ord(c) == 127 for c in raw_url):
        raise InvalidURLError("URL contains illegal control characters.")

    if len(raw_url) > 2048:
        raise InvalidURLError("URL exceeds maximum length of 2048 characters.")

    try:
        parsed = urlparse(raw_url)
    except Exception as exc:
        raise InvalidURLError(f"Malformed URL syntax: {exc}") from exc

    scheme = (parsed.scheme or "").lower()
    if scheme not in ("http", "https"):
        raise InvalidURLError(
            f"Invalid URL scheme '{scheme}'. Only absolute 'http' and 'https' URLs are accepted."
        )

    if not parsed.netloc:
        raise InvalidURLError("URL must include a valid hostname.")

    # Validate port formatting and range
    netloc_host_part = parsed.netloc.split("@")[-1]
    if netloc_host_part.endswith(":"):
        raise InvalidURLError("URL port is malformed.")

    try:
        port = parsed.port
    except ValueError as exc:
        raise InvalidURLError(f"Invalid URL port: {exc}") from exc

    if port is not None and not (1 <= port <= 65535):
        raise InvalidURLError(f"URL port {port} is out of valid range (1-65535).")

    hostname = parsed.hostname
    if not hostname:
        raise InvalidURLError("URL must include a valid hostname.")

    if ".." in hostname:
        raise InvalidURLError("URL hostname cannot contain consecutive dots.")

    if hostname.startswith(".") or hostname.endswith("."):
        raise InvalidURLError("URL hostname cannot start or end with a dot.")

    # Case 1: IPv6 Literal
    if ":" in hostname:
        try:
            ipaddress.IPv6Address(hostname)
            return raw_url
        except ValueError as exc:
            raise InvalidURLError(f"Invalid IPv6 address: {exc}") from exc

    # Case 2: IPv4 Address candidate (all-numeric dotted segments)
    parts = hostname.split(".")
    if all(p.isdigit() for p in parts) and len(parts) >= 2:
        if len(parts) != 4:
            raise InvalidURLError(f"Malformed IPv4 address '{hostname}': expected 4 octets.")
        try:
            ipaddress.IPv4Address(hostname)
            return raw_url
        except ValueError as exc:
            raise InvalidURLError(f"Invalid IPv4 address: {exc}") from exc

    # Case 3: Domain name / IDN
    try:
        encoded = idna.encode(hostname).decode("ascii")
    except Exception as exc:
        raise InvalidURLError(f"Malformed domain name: {exc}") from exc

    # Validate label syntax according to RFC 1035 / RFC 1123
    for label in encoded.split("."):
        if not label:
            raise InvalidURLError("URL hostname contains empty label.")
        if len(label) > 63:
            raise InvalidURLError(f"Domain label '{label}' exceeds 63 characters.")
        if not re.match(r"^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?$", label):
            raise InvalidURLError(f"Domain label '{label}' has invalid characters.")

    return raw_url

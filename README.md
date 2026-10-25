# URL Shortener API

A clean, reliable URL Shortener REST API built with **Python 3.11+**, **FastAPI**, **SQLAlchemy 2.x**, and **SQLite**.

---

## Requirements

- **Python**: 3.11 or higher
- **Dependencies**: Listed in `requirements.txt` (FastAPI, Uvicorn, SQLAlchemy, Pydantic, pytest, HTTPX)

---

## Installation

1. **Clone or navigate to the project directory:**

   ```bash
   cd url-shortener
   ```

2. **Create and activate a virtual environment:**

   - **Windows (PowerShell):**
     ```powershell
     python -m venv .venv
     .\.venv\Scripts\Activate.ps1
     ```

   - **Linux / macOS:**
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```

3. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

---

## Configuration

The application works out of the box with default settings. To customize configuration, copy `.env.example` to `.env`:

```bash
# Windows
Copy-Item .env.example .env

# Linux / macOS
cp .env.example .env
```

### Supported Environment Variables

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `DATABASE_URL` | `sqlite:///./url_shortener.db` | Database connection string (SQLite by default) |
| `BASE_URL` | `http://localhost:8000` | Base URL used to prefix generated short links |
| `SHORT_CODE_LENGTH` | `6` | Length of auto-generated Base62 short codes |
| `SHORT_CODE_MAX_RETRIES` | `10` | Maximum collision retry attempts for generated codes |

> **Note:** Database tables are created automatically on startup. No manual migrations or database setup scripts are required.

---

## Running the Application

Start the local development server with Uvicorn:

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://127.0.0.1:8000`.

- Interactive Swagger documentation: `http://127.0.0.1:8000/docs`
- Alternative ReDoc documentation: `http://127.0.0.1:8000/redoc`

---

## Running the Tests

Execute the automated pytest suite:

```bash
pytest -v
```

All tests run against an isolated SQLite test database and verify:
- Link creation with auto-generated codes and custom aliases
- URL validation (schemes, hostnames, ports, IPv4/IPv6 syntax)
- Rejection of duplicate custom aliases with HTTP 409
- HTTP 307 temporary redirection and Location header
- HTTP 404 for unknown codes and HTTP 410 for expired links
- Atomic click counter increments under concurrent requests
- Statistics retrieval for active, unclicked, and expired links
- Service health check endpoint

---

## API Endpoints and Behavior

### 1. Create Short Link — `POST /links`

Accepts a target URL, an optional custom alias, and an optional future expiration timestamp.

**Request Body:**
```json
{
  "url": "https://example.com/products/item1",
  "custom_alias": "promo-item1",
  "expires_at": "2027-01-01T00:00:00Z"
}
```

- `url` (required): Absolute HTTP or HTTPS destination URL.
- `custom_alias` (optional): Custom short code (3–30 alphanumeric, `-`, or `_` characters).
- `expires_at` (optional): Future expiration date/time in ISO 8601 format.

**Responses:**
- `201 Created`: Short link created successfully.
  ```json
  {
    "code": "promo-item1",
    "short_url": "http://localhost:8000/promo-item1",
    "original_url": "https://example.com/products/item1",
    "expires_at": "2027-01-01T00:00:00Z"
  }
  ```
- `409 Conflict`: The requested custom alias is already in use.
- `422 Unprocessable Entity`: Invalid URL format, unsupported scheme, invalid alias format, or past expiration date.

---

### 2. Redirect to Target — `GET /{code}`

Redirects client to the original URL and atomically increments click statistics.

**Responses:**
- `307 Temporary Redirect`: Redirects with `Location` header pointing to original URL. Increments `total_clicks` and updates `last_clicked_at`.
- `404 Not Found`: Short code does not exist.
  ```json
  {
    "detail": {
      "error": "link_not_found",
      "message": "No short link exists for this code."
    }
  }
  ```
- `410 Gone`: Short link has expired (click count is not incremented).
  ```json
  {
    "detail": {
      "error": "link_expired",
      "message": "This short link has expired."
    }
  }
  ```

---

### 3. Get Link Statistics — `GET /links/{code}/stats`

Returns click statistics and metadata for a short link. Statistics remain accessible even after a link has expired.

**Responses:**
- `200 OK`:
  ```json
  {
    "code": "promo-item1",
    "original_url": "https://example.com/products/item1",
    "total_clicks": 1,
    "last_clicked_at": "2026-10-25T14:30:00Z",
    "expires_at": "2027-01-01T00:00:00Z",
    "is_expired": false
  }
  ```
- `404 Not Found`: Short code does not exist.

---

### 4. Health Check — `GET /health`

Returns service operational status for monitoring and health checks.

**Response:**
- `200 OK`:
  ```json
  {
    "status": "healthy"
  }
  ```

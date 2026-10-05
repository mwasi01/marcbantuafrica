"""
Marcbantu Africa — Utilities.
JWT, passwords, JSON responses, formatting, validation.
"""

from js import Response, Object
import json
import hmac
import hashlib
import base64
import time
import re
from datetime import datetime, timezone

from constants import HTTP, ErrorCode


# ============================================================
# JS HEADERS HELPER (Pyodide)
# ============================================================
def js_headers(d: dict):
    """Convert a Python dict to a JS-friendly headers object
    suitable for Response.new(..., headers=...)."""
    from js import Object

    return Object.fromEntries([(str(k), str(v)) for k, v in d.items()])


# ============================================================
# JSON RESPONSES
# ============================================================
def json_response(data, status: int = 200, headers: dict = None):
    """Return a JSON Response."""
    default_headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Request-ID",
        "Access-Control-Max-Age": "86400",
        "X-Content-Type-Options": "nosniff",
    }
    if headers:
        default_headers.update(headers)
    return Response.new(
        json.dumps(data, default=str),
        status=status,
        headers=js_headers(default_headers),
    )


def error_response(message: str, status: int = 400, code: str = None, details=None):
    """Return a standardized error response."""
    return json_response(
        {
            "success": False,
            "error": {
                "message": message,
                "code": code or ErrorCode.VALIDATION_ERROR,
                "details": details,
            },
        },
        status=status,
    )


def success_response(
    data=None, message: str = "Success", status: int = 200, meta: dict = None
):
    """Return a standardized success response."""
    body = {"success": True, "message": message}
    if data is not None:
        body["data"] = data
    if meta is not None:
        body["meta"] = meta
    return json_response(body, status=status)


def paginated_response(result: dict, message: str = "Success"):
    """Return a paginated response."""
    return json_response(
        {
            "success": True,
            "message": message,
            "data": result["items"],
            "meta": {
                "total": result["total"],
                "page": result["page"],
                "page_size": result["page_size"],
                "pages": result["pages"],
            },
        }
    )


def no_content():
    """Return 204 No Content."""
    return Response.new(
        None,
        status=204,
        headers=js_headers(
            {
                "Access-Control-Allow-Origin": "*",
            }
        ),
    )


# ============================================================
# BASE64 URL (for JWT)
# ============================================================
def base64_url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def base64_url_decode(data: str) -> bytes:
    padding = "=" * (4 - len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


# ============================================================
# JWT (HMAC-SHA256)
# ============================================================
def create_token(payload: dict, secret: str, expires_in: int = 86400 * 7) -> str:
    """Create a JWT token."""
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {**payload, "exp": now + expires_in, "iat": now}

    header_b64 = base64_url_encode(json.dumps(header, separators=(",", ":")).encode())
    payload_b64 = base64_url_encode(json.dumps(payload, separators=(",", ":")).encode())

    signing_input = f"{header_b64}.{payload_b64}".encode()
    signature = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    signature_b64 = base64_url_encode(signature)

    return f"{header_b64}.{payload_b64}.{signature_b64}"


def verify_token(token: str, secret: str) -> dict | None:
    """Verify a JWT token. Returns payload or None."""
    if not token:
        return None
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header_b64, payload_b64, signature_b64 = parts
        signing_input = f"{header_b64}.{payload_b64}".encode()
        expected_sig = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
        expected_sig_b64 = base64_url_encode(expected_sig)
        if not hmac.compare_digest(signature_b64, expected_sig_b64):
            return None
        payload = json.loads(base64_url_decode(payload_b64))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


# ============================================================
# PASSWORD HASHING (PBKDF2-SHA256)
# ============================================================
def hash_password(password: str) -> str:
    """Hash a password using PBKDF2-SHA256 with salt."""
    salt_bytes = hashlib.sha256(f"{time.time()}-{password[:3]}".encode()).digest()[:16]
    salt = base64_url_encode(salt_bytes)
    hash_bytes = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000)
    return f"{salt}${base64_url_encode(hash_bytes)}"


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its hash."""
    if not hashed or "$" not in hashed:
        return False
    try:
        salt, original_hash = hashed.split("$", 1)
        hash_bytes = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt.encode(), 100000
        )
        return hmac.compare_digest(base64_url_encode(hash_bytes), original_hash)
    except Exception:
        return False


# ============================================================
# REQUEST PARSING
# ============================================================
async def parse_json(request) -> dict:
    """Parse JSON body safely (Pyodide-compatible).

    Pyodide returns a JS object from request.json(). Convert it to a
    native Python dict before returning.
    """
    try:
        data = await request.json()
    except Exception:
        return {}

    if data is None:
        return {}

    # Pyodide JsProxy exposes .to_py() — use it when present
    try:
        if hasattr(data, "to_py"):
            converted = data.to_py()
            return converted if isinstance(converted, dict) else {}
    except Exception:
        pass

    # Fallback for native Python dicts (tests, local runs)
    return data if isinstance(data, dict) else {}


async def parse_form(request) -> dict:
    """Parse form data (Pyodide-compatible)."""
    try:
        form = await request.formData()
        keys = list(form.keys())
        out = {}
        for k in keys:
            v = form.get(k)
            out[str(k)] = v if hasattr(v, "arrayBuffer") else str(v)
        return out
    except Exception:
        return {}


def get_query(request, key: str, default=None):
    """Get a query parameter (Pyodide-safe)."""
    try:
        from urllib.parse import urlparse, parse_qs
        raw = str(request.url)
        parsed = urlparse(raw)
        values = parse_qs(parsed.query)
        if key in values and values[key]:
            return values[key][0]
        return default
    except Exception:
        return default


def get_int_query(request, key: str, default: int = 0) -> int:
    """Get an integer query parameter (Pyodide-safe)."""
    val = get_query(request, key)
    try:
        return int(val) if val is not None and val != "" else default
    except (TypeError, ValueError):
        return default


# ============================================================
# QUERY PARAM SHIM (drop-in replacement for url.search_params)
# ============================================================
class _SearchParams:
    """Mimics the JS URL object with .search_params.get()/.has()."""
    def __init__(self, request):
        self._request = request
        # Some code does url.search_params.get(...) — expose self as that.
        self.search_params = self

    def get(self, key, default=None):
        return get_query(self._request, key, default)

    def has(self, key):
        return get_query(self._request, key) is not None


def _sp(request) -> _SearchParams:
    """Return an object with .get()/.has() that works on Pyodide.

    Also exposes .search_params so `url.search_params.get(...)` works.
    """
    return _SearchParams(request)


# ============================================================
# AUTH HELPERS
# ============================================================
def get_auth_user(request, env) -> dict | None:
    """Extract and verify user from Authorization header."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[7:].strip()
    return verify_token(token, env.JWT_SECRET)


def get_bearer_token(request) -> str | None:
    """Extract bearer token from Authorization header."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:].strip()
    return None


def require_auth(request, env):
    """Return (user, error_response). Use as:
    user, err = require_auth(request, env)
    if err: return err
    """
    user = get_auth_user(request, env)
    if not user:
        return None, error_response(
            "Authentication required",
            status=HTTP.UNAUTHORIZED,
            code=ErrorCode.UNAUTHORIZED,
        )
    return user, None


# ============================================================
# VALIDATION
# ============================================================
PHONE_RE = re.compile(r"^\+?[0-9]{9,15}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_phone(phone: str, default_country: str = "+254") -> str:
    """Normalize a phone number to E.164 format."""
    if not phone:
        return ""
    phone = (
        str(phone)
        .strip()
        .replace(" ", "")
        .replace("-", "")
        .replace("(", "")
        .replace(")", "")
    )
    if phone.startswith("+"):
        return phone
    if phone.startswith("00"):
        return "+" + phone[2:]
    if phone.startswith("0"):
        return default_country + phone[1:]
    if phone.startswith(default_country.lstrip("+")):
        return "+" + phone
    return default_country + phone


def is_valid_phone(phone: str) -> bool:
    return bool(PHONE_RE.match(phone or ""))


def is_valid_email(email: str) -> bool:
    return bool(EMAIL_RE.match(email or ""))


def require_fields(data: dict, fields: list) -> str | None:
    """Return error message if any required field is missing."""
    if not data:
        return f"Missing required fields: {', '.join(fields)}"
    missing = [f for f in fields if f not in data or data[f] is None or data[f] == ""]
    if missing:
        return f"Missing required fields: {', '.join(missing)}"
    return None


def validate_enum(value, allowed: list, field_name: str) -> str | None:
    """Validate that a value is in an allowed list."""
    if value not in allowed:
        return f"{field_name} must be one of: {', '.join(allowed)}"
    return None


def to_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def to_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


# ============================================================
# FORMATTING
# ============================================================
def now_iso() -> str:
    """Current UTC time in ISO format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today() -> str:
    """Today's date in YYYY-MM-DD."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def format_currency(amount: float, currency: str = "KES") -> str:
    """Format a currency value."""
    return f"{currency} {amount:,.2f}"


def slugify(text: str) -> str:
    """Convert text to URL-safe slug."""
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")


def truncate(text: str, length: int = 100) -> str:
    """Truncate text with ellipsis."""
    if not text or len(text) <= length:
        return text
    return text[: length - 3] + "..."


# ============================================================
# LOGGING (lightweight)
# ============================================================
def log_event(event: str, data: dict = None):
    """Log an event (visible in wrangler tail)."""
    payload = {"event": event, "ts": now_iso()}
    if data:
        payload["data"] = data
    print(json.dumps(payload))


def log_error(error: str, context: dict = None):
    """Log an error."""
    payload = {"level": "error", "error": error, "ts": now_iso()}
    if context:
        payload["context"] = context
    print(json.dumps(payload))


# ============================================================
# MISC
# ============================================================
def chunk_list(items: list, size: int) -> list:
    """Split a list into chunks of `size`."""
    return [items[i : i + size] for i in range(0, len(items), size)]


def safe_json_loads(text: str, default=None):
    """Safely parse JSON."""
    try:
        return json.loads(text)
    except Exception:
        return default


def generate_reference(prefix: str = "MB") -> str:
    """Generate a unique reference like MB-20251004120000-ABC123."""
    import random
    import string

    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    rand = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"{prefix}-{ts}-{rand}"

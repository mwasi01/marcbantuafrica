"""
Marcbantu Africa — Middleware.
Wraps route handlers with auth, rate limiting, logging, error handling.
"""

from js import Response, Object
import json
from utils import (
    json_response, error_response, get_auth_user, log_event, log_error,
    now_iso, generate_reference,
    js_headers,
)
from constants import HTTP, ErrorCode


# ============================================================
# CORS
# ============================================================
def cors_headers() -> dict:
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Request-ID",
        "Access-Control-Max-Age": "86400",
    }


def handle_options(request):
    """Handle CORS preflight."""
    return Response.new(None, status=204, headers=js_headers(cors_headers()))


# ============================================================
# RATE LIMITING (KV-based)
# ============================================================
async def check_rate_limit(env, identifier: str, limit: int = 60, window_seconds: int = 60) -> bool:
    """Return True if within limit, False if exceeded."""
    if not identifier:
        return True
    import time
    window = int(time.time() // window_seconds)
    key = f"rl:{identifier}:{window}"
    try:
        current = await env.CACHE.get(key)
        count = int(current) if current else 0
        if count >= limit:
            return False
        await env.CACHE.put(key, str(count + 1), expirationTtl=window_seconds * 2)
        return True
    except Exception:
        # If KV fails, allow the request
        return True


def get_client_ip(request) -> str:
    """Extract client IP from headers."""
    for header in ['CF-Connecting-IP', 'X-Forwarded-For', 'X-Real-IP']:
        val = request.headers.get(header)
        if val:
            return val.split(',')[0].strip()
    return 'unknown'


# ============================================================
# REQUEST ID
# ============================================================
def get_request_id(request) -> str:
    """Get or generate a request ID."""
    return request.headers.get('X-Request-ID') or generate_reference('REQ')


# ============================================================
# AUTH GUARD
# ============================================================
def require_auth(request, env):
    """Return (user, error_response)."""
    user = get_auth_user(request, env)
    if not user:
        return None, error_response(
            "Authentication required",
            status=HTTP.UNAUTHORIZED,
            code=ErrorCode.UNAUTHORIZED,
        )
    return user, None


def require_tier(request, env, tiers: list):
    """Require the user to have one of the specified tiers."""
    user, err = require_auth(request, env)
    if err:
        return None, err
    from db import DB
    # Note: this is async, needs to be awaited in handlers
    return user, None


async def check_tier(user_id: int, env, required_tier: str) -> bool:
    """Check if user's subscription tier meets requirement."""
    from db import DB
    from constants import Tier
    db = DB(env)
    farmer = await db.query_one("SELECT subscription_tier, subscription_expires_at FROM farmers WHERE id = ?", [user_id])
    if not farmer:
        return False

    tier_rank = {Tier.STARTER: 0, Tier.PRO: 1, Tier.BUSINESS: 2}
    user_rank = tier_rank.get(farmer['subscription_tier'], 0)
    required_rank = tier_rank.get(required_tier, 0)

    if user_rank < required_rank:
        return False

    # Check expiry for paid tiers
    if required_rank > 0 and farmer.get('subscription_expires_at'):
        from utils import now_iso
        if farmer['subscription_expires_at'] < now_iso():
            return False

    return True


# ============================================================
# ERROR HANDLING WRAPPER
# ============================================================
def handle_errors(handler):
    """Decorator: wrap a handler with try/except."""
    async def wrapped(*args, **kwargs):
        try:
            return await handler(*args, **kwargs)
        except Exception as e:
            log_error(str(e), {'handler': handler.__name__})
            return error_response(
                "An unexpected error occurred",
                status=HTTP.INTERNAL_ERROR,
                code=ErrorCode.INTERNAL_ERROR,
            )
    return wrapped


# ============================================================
# LOGGING WRAPPER
# ============================================================
def log_request(handler):
    """Decorator: log each request."""
    async def wrapped(request, env, *args, **kwargs):
        request_id = get_request_id(request)
        ip = get_client_ip(request)
        method = request.method
        path = request.url.path if hasattr(request.url, 'path') else str(request.url)
        log_event('request', {
            'id': request_id,
            'method': method,
            'path': path,
            'ip': ip,
        })
        response = await handler(request, env, *args, **kwargs)
        try:
            response.headers['X-Request-ID'] = request_id
        except Exception:
            pass
        return response
    return wrapped


# ============================================================
# COMBINED WRAPPER
# ============================================================
def wrap(handler):
    """Apply all middleware to a handler."""
    return log_request(handle_errors(handler))
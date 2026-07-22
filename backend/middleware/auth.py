import logging
import jwt
from fastapi import HTTPException, Request
from config import settings
from db import get_db

logger = logging.getLogger(__name__)


async def _decode_bearer(request: Request) -> dict:
    """Extract and decode the Supabase JWT from the Authorization Bearer header.

    Raises 401 when the header is missing; 403 when the token is invalid.
    Shared by :func:`verify_supabase_jwt` and :func:`verify_supabase_jwt_strict`.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing auth")

    token = auth_header.split(" ", 1)[1]
    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
        )
    except (jwt.InvalidTokenError, jwt.DecodeError):
        raise HTTPException(status_code=403, detail="Invalid token")

    return payload


async def verify_supabase_jwt(request: Request) -> dict:
    """Verify Supabase JWT from Authorization Bearer header. Returns decoded payload.

    When supabase_jwt_secret is empty (e.g. CI / local dev stubs), logs a
    warning and returns an anonymous payload so tests don't break.
    """
    if not settings.supabase_jwt_secret:
        logger.warning("SUPABASE_JWT_SECRET not configured — allowing anonymous access")
        return {"sub": "anonymous", "email": None}

    return await _decode_bearer(request)


require_auth = verify_supabase_jwt


async def verify_supabase_jwt_strict(request: Request) -> dict:
    """Strict JWT verification — raises 401 when SUPABASE_JWT_SECRET is unset.

    Unlike :func:`verify_supabase_jwt` (kept for backward compat), this variant
    NEVER falls back to an anonymous payload when the secret is empty. It is the
    basis for tenant-scoped endpoints (C8/D20) where an unauthenticated caller
    must not reach client data.
    """
    if not settings.supabase_jwt_secret:
        raise HTTPException(status_code=401, detail="Auth not configured")

    return await _decode_bearer(request)


async def require_client_id(request: Request) -> str:
    """Derive the caller's ``client_id`` from the authenticated identity (C8/D20).

    The client_id is resolved from the JWT subject via the ``user_client_map``
    table — NEVER from the request body or query string — so a user can only
    ever reach their own tenant. All Phase 1+ client-scoped endpoints
    (``/billing/usage``, ``/billing/portal``, …) inject this as a dependency.

    Raises:
        401 — auth not configured, or missing/invalid token.
        403 — authenticated user has no client binding (cross-tenant denial).
    """
    payload = await verify_supabase_jwt_strict(request)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid identity")

    db = get_db()
    resp = (
        db.table("user_client_map")
        .select("client_id")
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    if not resp or not resp.data:
        # Authenticated but owns no client — deny (cross-tenant protection).
        raise HTTPException(status_code=403, detail="No client bound to this user")

    return resp.data["client_id"]

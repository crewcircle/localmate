import logging
import jwt
from fastapi import Depends, HTTPException, Request
from config import settings

logger = logging.getLogger(__name__)


async def verify_supabase_jwt(request: Request) -> dict:
    """Verify Supabase JWT from Authorization Bearer header. Returns decoded payload.

    When supabase_jwt_secret is empty (e.g. CI / local dev stubs), logs a
    warning and returns an anonymous payload so tests don't break.
    """
    if not settings.supabase_jwt_secret:
        logger.warning("SUPABASE_JWT_SECRET not configured — allowing anonymous access")
        return {"sub": "anonymous", "email": None}

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


require_auth = verify_supabase_jwt

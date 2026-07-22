"""Tests for tenant-auth binding (C8/D20) — the strict client-resolving dependency.

Covers: empty SUPABASE_JWT_SECRET must NOT return anonymous (strict path raises
401), missing token -> 401, and cross-tenant denial (a user's token resolves to
ONLY their bound client via user_client_map — another tenant's client is
unreachable because the lookup is keyed on the JWT subject, not request input).
"""
import inspect
from unittest.mock import patch, MagicMock

import jwt as pyjwt
import pytest
from fastapi import HTTPException

SECRET = "test-jwt-secret-must-be-at-least-32-bytes"


def _make_jwt(sub: str) -> str:
    return pyjwt.encode({"sub": sub}, SECRET, algorithm="HS256")


def _request(token: str | None = None) -> MagicMock:
    req = MagicMock()
    req.headers = {} if token is None else {"Authorization": f"Bearer {token}"}
    return req


def _map_db(bindings: dict[str, str]) -> MagicMock:
    """Mock supabase where user_client_map lookup by user_id returns the bound
    client_id (or None when the user has no binding)."""
    db = MagicMock()
    select = db.table.return_value.select.return_value

    def _eq(col, val):
        cid = bindings.get(val)
        data = {"client_id": cid} if cid is not None else None
        ret = MagicMock()
        ret.maybe_single.return_value.execute.return_value = MagicMock(data=data)
        return ret

    select.eq.side_effect = _eq
    return db


@pytest.mark.asyncio
async def test_strict_rejects_empty_secret_not_anonymous():
    """Empty SUPABASE_JWT_SECRET must raise 401, NOT return an anonymous payload."""
    from middleware.auth import verify_supabase_jwt, verify_supabase_jwt_strict

    req = _request(token=None)
    with patch("middleware.auth.settings") as s:
        s.supabase_jwt_secret = ""

        # Legacy path still returns anonymous (backward compat).
        legacy = await verify_supabase_jwt(req)
        assert legacy == {"sub": "anonymous", "email": None}

        # Strict path rejects — no anonymous fallback.
        with pytest.raises(HTTPException) as exc_info:
            await verify_supabase_jwt_strict(req)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_require_client_id_missing_token_rejected_401():
    from middleware.auth import require_client_id

    req = _request(token=None)
    db = _map_db({})
    with patch("middleware.auth.settings") as s, \
         patch("middleware.auth.get_db", return_value=db):
        s.supabase_jwt_secret = SECRET
        with pytest.raises(HTTPException) as exc_info:
            await require_client_id(req)

    assert exc_info.value.status_code == 401
    db.table.assert_not_called()  # never reached the client lookup


@pytest.mark.asyncio
async def test_require_client_id_invalid_token_rejected_403():
    from middleware.auth import require_client_id

    req = _request(token="not-a-real-jwt")
    db = _map_db({})
    with patch("middleware.auth.settings") as s, \
         patch("middleware.auth.get_db", return_value=db):
        s.supabase_jwt_secret = SECRET
        with pytest.raises(HTTPException) as exc_info:
            await require_client_id(req)

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_require_client_id_resolves_bound_client():
    """A valid token resolves to the client bound to its subject."""
    from middleware.auth import require_client_id

    db = _map_db({"userA": "clientA"})
    req = _request(token=_make_jwt("userA"))
    with patch("middleware.auth.settings") as s, \
         patch("middleware.auth.get_db", return_value=db):
        s.supabase_jwt_secret = SECRET
        client_id = await require_client_id(req)

    assert client_id == "clientA"
    # The lookup is keyed on the JWT subject, NOT any request input.
    select = db.table.return_value.select.return_value
    select.eq.assert_called_once_with("user_id", "userA")


@pytest.mark.asyncio
async def test_require_client_id_denies_user_without_binding():
    """An authenticated user with no client binding is denied (403)."""
    from middleware.auth import require_client_id

    db = _map_db({})  # userC has no mapping
    req = _request(token=_make_jwt("userC"))
    with patch("middleware.auth.settings") as s, \
         patch("middleware.auth.get_db", return_value=db):
        s.supabase_jwt_secret = SECRET
        with pytest.raises(HTTPException) as exc_info:
            await require_client_id(req)

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_cross_tenant_user_only_reaches_own_client():
    """User A's token resolves to client A and can NEVER yield client B; user B's
    token resolves to client B. Tenant isolation is enforced by the JWT-subject
    binding (C8/D20)."""
    from middleware.auth import require_client_id

    # userA -> clientA, userB -> clientB
    db = _map_db({"userA": "clientA", "userB": "clientB"})

    with patch("middleware.auth.settings") as s, \
         patch("middleware.auth.get_db", return_value=db):
        s.supabase_jwt_secret = SECRET

        cid_a = await require_client_id(_request(token=_make_jwt("userA")))
        cid_b = await require_client_id(_request(token=_make_jwt("userB")))

    assert cid_a == "clientA"
    assert cid_b == "clientB"
    # user A's token never yields client B — the other tenant is unreachable.
    assert cid_a != "clientB"
    # Both lookups were bound to their respective JWT subjects.
    eq_calls = [c.args for c in db.table.return_value.select.return_value.eq.call_args_list]
    assert ("user_id", "userA") in eq_calls
    assert ("user_id", "userB") in eq_calls


def test_require_auth_kept_for_backward_compat():
    """The legacy anonymous-fallback dependency is unchanged for existing callers."""
    from middleware.auth import require_auth, verify_supabase_jwt

    assert require_auth is verify_supabase_jwt


def test_require_client_id_is_a_fastapi_dependency_signature():
    """Sanity: require_client_id is a plain async callable usable with Depends."""
    from middleware.auth import require_client_id

    sig = inspect.signature(require_client_id)
    assert "request" in sig.parameters

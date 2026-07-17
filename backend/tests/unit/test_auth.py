"""Tests for JWT authentication middleware."""
import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException


@pytest.mark.asyncio
async def test_jwt_auth_rejects_missing_token():
    """Missing Authorization header is rejected with 401."""
    from middleware.auth import verify_supabase_jwt

    mock_request = MagicMock()
    mock_request.headers = {}

    with patch("middleware.auth.settings") as mock_settings:
        mock_settings.supabase_jwt_secret = "test-secret-key"

        with pytest.raises(HTTPException) as exc_info:
            await verify_supabase_jwt(mock_request)

    assert exc_info.value.status_code == 401
    assert "Missing auth" in exc_info.value.detail

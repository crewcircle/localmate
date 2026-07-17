"""Tests for health check endpoint and DB connection."""
import pytest
from unittest.mock import patch


@pytest.mark.asyncio
async def test_health_check():
    """GET /health returns status ok with project ID."""
    from main import health

    result = await health()
    assert result["status"] == "ok"
    assert result["project"] == "localmate"


def test_db_connection():
    """get_db() raises RuntimeError when database is not initialised."""
    import db as db_module

    with patch.object(db_module, "_client", None):
        with pytest.raises(RuntimeError, match="Database not initialised"):
            db_module.get_db()

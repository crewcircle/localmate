"""Tests for the practitioners read + opt-out API (Phase 2)."""
import pytest
from unittest.mock import patch, MagicMock

from fastapi import HTTPException


def _chain(data):
    c = MagicMock()
    c.select.return_value = c
    c.eq.return_value = c
    c.order_by.return_value = c
    c.update.return_value = c
    c.execute.return_value = MagicMock(data=data)
    return c


@pytest.mark.asyncio
async def test_list_practitioners_returns_client_scoped_list():
    from routers import practitioners

    rows = [{"id": "p1", "name": "Dr X", "do_not_contact": False}]
    db = MagicMock()
    db.table.return_value = _chain(rows)
    with patch("routers.practitioners.get_db", return_value=db):
        result = await practitioners.list_practitioners(client_id="cid", auth={"sub": "anon"})

    assert result == {"practitioners": rows}
    # Query is scoped to the client.
    db.table("practitioners").eq.assert_called_with("client_id", "cid")


@pytest.mark.asyncio
async def test_list_practitioners_empty():
    from routers import practitioners

    db = MagicMock()
    db.table.return_value = _chain([])
    with patch("routers.practitioners.get_db", return_value=db):
        result = await practitioners.list_practitioners(client_id="cid", auth={"sub": "anon"})
    assert result == {"practitioners": []}


@pytest.mark.asyncio
async def test_update_practitioner_opt_out():
    from routers import practitioners

    db = MagicMock()
    chain = _chain([{"id": "p1", "do_not_contact": True}])
    db.table.return_value = chain
    with patch("routers.practitioners.get_db", return_value=db):
        result = await practitioners.update_practitioner(
            "p1", {"do_not_contact": True}, client_id="cid", auth={"sub": "anon"}
        )

    assert result["practitioner"]["do_not_contact"] is True
    chain.update.assert_called_with({"do_not_contact": True})
    # Update is scoped by both id AND client_id (cross-tenant protection).
    eq_calls = [c.args for c in chain.eq.call_args_list]
    assert ("id", "p1") in eq_calls
    assert ("client_id", "cid") in eq_calls


@pytest.mark.asyncio
async def test_update_missing_do_not_contact_returns_422():
    from routers import practitioners

    with pytest.raises(HTTPException) as exc:
        await practitioners.update_practitioner("p1", {}, client_id="cid", auth={"sub": "anon"})
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_update_not_found_returns_404():
    from routers import practitioners

    db = MagicMock()
    db.table.return_value = _chain([])  # update matched no row
    with patch("routers.practitioners.get_db", return_value=db):
        with pytest.raises(HTTPException) as exc:
            await practitioners.update_practitioner(
                "p1", {"do_not_contact": False}, client_id="cid", auth={"sub": "anon"}
            )
    assert exc.value.status_code == 404

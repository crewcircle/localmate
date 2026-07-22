"""Tests for the fail-safe stub adapters (HotDoc, Jane, PracticePal).

Stubs register with SUPPORTS_REBOOK=False, log a partner-gated warning, and return
[] so the daily Rebook job fails safe instead of 404ing.
"""
import logging

import pytest

from services import hotdoc, jane, practicepal


_STUBS = [
    (hotdoc, "hotdoc", "hotdoc_id", "partner_gated"),
    (jane, "jane", "jane_id", "partner_gated"),
    (practicepal, "practicepal", "practicepal_id", "none"),
]


@pytest.mark.parametrize("module,name,id_column,auth_model", _STUBS)
def test_stub_metadata(module, name, id_column, auth_model):
    assert module.ADAPTER_NAME == name
    assert module.ID_COLUMN == id_column
    assert module.CREDENTIAL_KEYS == []
    assert module.SUPPORTS_REBOOK is False
    assert module.AUTH_MODEL == auth_model


@pytest.mark.parametrize("module,name,id_column,auth_model", _STUBS)
@pytest.mark.asyncio
async def test_stub_get_appointments_returns_empty_and_logs(module, name, id_column, auth_model, caplog):
    caplog.set_level(logging.WARNING, logger=module.__name__)
    result = await module.get_appointments({"id": "c1"}, "2026-05-01", "2026-05-31")
    assert result == []
    assert any(rec.levelno == logging.WARNING for rec in caplog.records)


@pytest.mark.parametrize("module,name,id_column,auth_model", _STUBS)
@pytest.mark.asyncio
async def test_stub_get_future_appointments_returns_empty(module, name, id_column, auth_model):
    result = await module.get_future_appointments({"id": "c1"}, "p-1", "2026-07-22")
    assert result == []

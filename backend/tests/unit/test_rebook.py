"""Tests for lapsed patient identification and AU holiday gate."""
import sys
import types
import pytest
from unittest.mock import patch, AsyncMock
from datetime import date


def _install_workalendar_au_stub():
    mod = types.ModuleType("workalendar.au")
    from workalendar.oceania import (
        AustralianCapitalTerritory,
        NewSouthWales,
        NorthernTerritory,
        Queensland,
        SouthAustralia,
        Tasmania,
        Victoria,
        WesternAustralia,
    )
    mod.AustralianCapitalTerritory = AustralianCapitalTerritory
    mod.NewSouthWales = NewSouthWales
    mod.NorthernTerritory = NorthernTerritory
    mod.Queensland = Queensland
    mod.SouthAustralia = SouthAustralia
    mod.Tasmania = Tasmania
    mod.Victoria = Victoria
    mod.WesternAustralia = WesternAustralia
    sys.modules["workalendar.au"] = mod


_install_workalendar_au_stub()


@pytest.mark.asyncio
async def test_lapsed_patient_identified():
    """Patients who completed treatment 55-65 days ago without future booking are identified."""
    from jobs.appointment_followup import identify_lapsed_patients

    client = {
        "id": "client-dental-1",
        "business_name": "Sydney Dental Care",
        "booking_system": "cliniko",
        "cliniko_api_key": "test-key",
    }

    completed_appointments = [
        {
            "patient": {
                "id": "pat-001",
                "name": "John Smith",
                "phone": "+61412345678",
                "email": "john@example.com.au",
            },
            "appointment_type": "Dental Clean",
            "appointment_start": "2026-05-15T10:00:00+10:00",
        }
    ]

    with patch("services.cliniko.get_appointments", new_callable=AsyncMock, return_value=completed_appointments), \
         patch("services.cliniko.get_future_appointments", new_callable=AsyncMock, return_value=[]):
        lapsed = await identify_lapsed_patients(client)

    assert len(lapsed) == 1
    assert lapsed[0]["patient_id"] == "pat-001"
    assert lapsed[0]["patient_name"] == "John Smith"
    assert lapsed[0]["phone"] == "+61412345678"


def test_au_holiday_skips_send():
    """AU public holidays are correctly identified for SMS skip logic."""
    from jobs.appointment_followup import is_au_public_holiday

    assert is_au_public_holiday(date(2026, 1, 1), "NSW") is True
    assert is_au_public_holiday(date(2026, 7, 17), "NSW") is False

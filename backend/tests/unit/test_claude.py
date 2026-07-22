"""Tests for generate_followup_message practitioner/claim params + guardrails."""
import pytest
from unittest.mock import patch, MagicMock

from services import claude


def _mock_anthropic(reply="Hi from clinic"):
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=reply)]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_msg
    return mock_client


@pytest.mark.asyncio
async def test_practitioner_and_claim_included_in_user_content():
    mock_client = _mock_anthropic()
    with patch.object(claude, "_get_client", return_value=mock_client):
        await claude.generate_followup_message(
            patient_name="John",
            last_treatment="Clean",
            business_name="Sydney Dental",
            channel="sms",
            practitioner_name="Dr Chen",
            claim_type="gap",
        )
    user_content = mock_client.messages.create.call_args.kwargs["messages"][0]["content"]
    assert "Practitioner: Dr Chen" in user_content
    assert "Claim type: gap" in user_content


@pytest.mark.asyncio
async def test_practitioner_and_claim_omitted_when_not_provided():
    """Backward compatible: no practitioner/claim lines when params are absent."""
    mock_client = _mock_anthropic()
    with patch.object(claude, "_get_client", return_value=mock_client):
        await claude.generate_followup_message(
            patient_name="John", last_treatment="Clean", business_name="Sydney Dental", channel="sms"
        )
    user_content = mock_client.messages.create.call_args.kwargs["messages"][0]["content"]
    assert "Practitioner:" not in user_content
    assert "Claim type:" not in user_content


@pytest.mark.asyncio
async def test_system_prompt_forbids_dollar_amounts_and_financial_claims():
    mock_client = _mock_anthropic()
    with patch.object(claude, "_get_client", return_value=mock_client):
        await claude.generate_followup_message(
            patient_name="John", last_treatment="Clean", business_name="Clinic", channel="sms"
        )
    system_prompt = mock_client.messages.create.call_args.kwargs["system"]
    assert "dollar" in system_prompt.lower()
    assert "medical or financial claims" in system_prompt.lower()


@pytest.mark.asyncio
async def test_returns_generated_text():
    with patch.object(claude, "_get_client", return_value=_mock_anthropic("Book again soon")):
        result = await claude.generate_followup_message(
            patient_name="John", last_treatment="Clean", business_name="Clinic", channel="sms"
        )
    assert result == "Book again soon"

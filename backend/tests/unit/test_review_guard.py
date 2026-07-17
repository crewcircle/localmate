"""Tests for review webhook processing and Claude response generation."""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


@pytest.mark.asyncio
async def test_review_webhook_creates_draft():
    """Inbound review webhook creates a draft via Claude and stores it."""
    from routers.webhooks import process_review

    mock_client = {"id": "client-abc", "voice_sample": "Warm and friendly"}

    with patch("routers.webhooks.get_db") as mock_get_db, \
         patch("routers.webhooks.resolve_client_from_location", return_value=mock_client), \
         patch("middleware.trial_gate.check_trial_gate", new_callable=AsyncMock) as mock_gate, \
         patch("services.claude.generate_review_response", new_callable=AsyncMock) as mock_claude, \
         patch("middleware.trial_gate.get_db"), \
         patch("middleware.trial_gate.increment_trial_usage", new_callable=AsyncMock):

        mock_gate.return_value = {"allowed": True, "reason": "trial_active"}
        mock_claude.return_value = (
            "Thanks for the kind words, Sarah! We're stoked you had "
            "a great experience at Sydney Dental Care."
        )

        await process_review({
            "name": "accounts/123/locations/456/reviews/789",
            "comment": "Excellent dental practice! Sarah was very professional.",
            "starRating": 5,
            "reviewer": {"displayName": "Sarah Mitchell"},
        })

        mock_get_db.return_value.table.return_value.insert.return_value.execute.assert_called_once()


@pytest.mark.asyncio
async def test_claude_response_is_au_english():
    """Claude generates review response using Australian English."""
    from services.claude import generate_review_response

    au_response = (
        "Thanks for the review, Sarah! We're stoked to hear about your "
        "experience. Cheers, Sydney Dental Care team."
    )
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=au_response)]
    mock_client_instance = MagicMock()
    mock_client_instance.messages.create.return_value = mock_response

    with patch("services.claude._get_client", return_value=mock_client_instance):
        result = await generate_review_response(
            review_text="Great dental practice!",
            rating=5,
            reviewer_name="Sarah",
            voice_sample="Warm and genuine",
        )

    assert result == au_response
    call_kwargs = mock_client_instance.messages.create.call_args.kwargs
    assert "Australian English" in call_kwargs["system"]

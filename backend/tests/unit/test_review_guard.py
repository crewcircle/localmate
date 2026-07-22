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


# ---------------------------------------------------------------------------
# Yelp guided manual posting (Phase 4)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_approve_yelp_draft_returns_awaiting_manual_post():
    """Approving a source='yelp' draft returns awaiting_manual_post and does NOT call GBP."""
    from routers.approve import approve_review

    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data={
            "id": "d1",
            "client_id": "c1",
            "source": "yelp",
            "source_id": "yelp-rev-123",
            "draft_text": "Thanks for the review!",
            "status": "pending_approval",
            "metadata": {"url": "https://yelp.com/biz/review/123"},
        }
    )
    update_resp = MagicMock()
    update_resp.data = [{"id": "d1"}]
    mock_db.table.return_value.update.return_value.eq.return_value.execute.return_value = update_resp

    with patch("routers.approve.get_db", return_value=mock_db), \
         patch("services.gbp.post_review_reply", new_callable=AsyncMock) as mock_gbp:
        result = await approve_review(draft_id="d1", auth={"sub": "anonymous"})

    assert result["status"] == "awaiting_manual_post"
    assert result["yelp_url"] == "https://yelp.com/biz/review/123"
    assert result["reply_text"] == "Thanks for the review!"
    # GBP post_review_reply must NOT be called for Yelp drafts.
    mock_gbp.assert_not_awaited()


@pytest.mark.asyncio
async def test_approve_google_draft_posts_to_gbp():
    """Approving a source='google' draft still posts to GBP (existing path unchanged)."""
    from routers.approve import approve_review

    mock_db = MagicMock()

    def _table(name):
        chain = MagicMock()
        if name == "drafts":
            chain.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
                data={
                    "id": "d1",
                    "client_id": "c1",
                    "source": "google",
                    "source_id": "rev-789",
                    "draft_text": "Thanks for the review!",
                    "status": "pending_approval",
                    "location_id": "loc-1",
                }
            )
            chain.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[{"id": "d1"}])
        elif name == "clients":
            chain.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
                data={"gbp_access_token": "enc_token"}
            )
        elif name == "locations":
            chain.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data={"gbp_account_id": "ACCT1", "gbp_location_id": "LOC1"}
            )
        return chain

    mock_db.table.side_effect = _table

    with patch("routers.approve.get_db", return_value=mock_db), \
         patch("services.gbp.post_review_reply", new_callable=AsyncMock, return_value=True) as mock_gbp:
        result = await approve_review(draft_id="d1", auth={"sub": "anonymous"})

    assert result["status"] == "posted"
    mock_gbp.assert_awaited_once()
    # Verify the location path was resolved from the locations table (C2).
    call_args = mock_gbp.call_args[0]
    assert call_args[0] == "accounts/ACCT1/locations/LOC1"
    assert call_args[1] == "rev-789"


@pytest.mark.asyncio
async def test_mark_posted_transitions_awaiting_to_posted():
    """POST /approve/review/{id}/mark-posted transitions awaiting_manual_post → posted."""
    from routers.approve import mark_review_posted

    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data={"status": "awaiting_manual_post"}
    )
    mock_db.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{"id": "d1"}]
    )

    with patch("routers.approve.get_db", return_value=mock_db):
        result = await mark_review_posted(draft_id="d1", auth={"sub": "anonymous"})

    assert result["status"] == "posted"
    # Verify the update set status to "posted".
    update_data = mock_db.table.return_value.update.call_args[0][0]
    assert update_data["status"] == "posted"


@pytest.mark.asyncio
async def test_mark_posted_rejects_non_awaiting_draft():
    """mark-posted rejects a draft that is not in awaiting_manual_post state."""
    from routers.approve import mark_review_posted
    from fastapi import HTTPException

    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data={"status": "pending_approval"}
    )

    with patch("routers.approve.get_db", return_value=mock_db):
        with pytest.raises(HTTPException) as exc_info:
            await mark_review_posted(draft_id="d1", auth={"sub": "anonymous"})

    assert exc_info.value.status_code == 409

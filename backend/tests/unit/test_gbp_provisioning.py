"""Tests for GBP notification provisioning (Phase 4 — D15-B full automation).

All GCP REST calls are mocked via httpx — no live API calls.
"""
import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

import httpx


# Dummy service-account JSON for tests.
_SA_JSON = json.dumps({
    "client_email": "test-sa@test-project.iam.gserviceaccount.com",
    "private_key": "-----BEGIN PRIVATE KEY-----\nfake\n-----END PRIVATE KEY-----\n",
    "private_key_id": "key123",
    "project_id": "test-project",
})


def _mock_httpx_response(status_code=200, json_data=None):
    """Create a mock httpx.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.raise_for_status = MagicMock()
    if status_code >= 400 and status_code != 409:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=resp
        )
    if json_data is not None:
        resp.json.return_value = json_data
    return resp


def _mock_async_client(responses):
    """Create a mock httpx.AsyncClient whose get/put/post/patch return queued responses.

    ``responses`` is a dict mapping method → list of mock responses (consumed in order).
    """
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = False

    state = {"get": 0, "put": 0, "post": 0, "patch": 0}

    def _make(method):
        def _call(*args, **kwargs):
            idx = state[method]
            state[method] += 1
            if idx < len(responses.get(method, [])):
                return responses[method][idx]
            return _mock_httpx_response(200, {})
        return _call

    client.get.side_effect = _make("get")
    client.put.side_effect = _make("put")
    client.post.side_effect = _make("post")
    client.patch.side_effect = _make("patch")
    return client


# ---------------------------------------------------------------------------
# _gcp_access_token
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_gcp_access_token_builds_signed_jwt():
    """_gcp_access_token builds a signed JWT assertion with the SA claims."""
    from services.gbp_provisioning import _gcp_access_token

    token_resp = _mock_httpx_response(200, {"access_token": "ya29.test-token"})

    with patch("services.gbp_provisioning.settings") as mock_settings, \
         patch("services.gbp_provisioning.jwt") as mock_jwt, \
         patch("services.gbp_provisioning.httpx.AsyncClient") as mock_client_cls:
        mock_settings.gcp_sa_json = _SA_JSON
        mock_jwt.encode.return_value = "signed-assertion"
        mock_client_cls.return_value = _mock_async_client({"post": [token_resp]})

        token = await _gcp_access_token()

    assert token == "ya29.test-token"
    # Verify PyJWT.encode was called with the SA claims.
    encode_args = mock_jwt.encode.call_args
    payload = encode_args[0][0]
    assert payload["iss"] == "test-sa@test-project.iam.gserviceaccount.com"
    assert payload["aud"] == "https://oauth2.googleapis.com/token"
    assert "pubsub" in payload["scope"]
    assert "cloud-platform" in payload["scope"]
    assert encode_args[1]["algorithm"] == "RS256"


# ---------------------------------------------------------------------------
# ensure_topic
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ensure_topic_creates_topic():
    """ensure_topic creates a topic and returns the resource name."""
    from services.gbp_provisioning import ensure_topic

    with patch("services.gbp_provisioning._gcp_access_token", new_callable=AsyncMock, return_value="token"), \
         patch("services.gbp_provisioning.httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value = _mock_async_client({"put": [_mock_httpx_response(200)]})
        result = await ensure_topic("my-proj", "gbp-reviews")

    assert result == "projects/my-proj/topics/gbp-reviews"


@pytest.mark.asyncio
async def test_ensure_topic_409_is_success():
    """ensure_topic treats HTTP 409 (already exists) as success."""
    from services.gbp_provisioning import ensure_topic

    with patch("services.gbp_provisioning._gcp_access_token", new_callable=AsyncMock, return_value="token"), \
         patch("services.gbp_provisioning.httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value = _mock_async_client({"put": [_mock_httpx_response(409)]})
        result = await ensure_topic("my-proj", "gbp-reviews")

    assert result == "projects/my-proj/topics/gbp-reviews"


# ---------------------------------------------------------------------------
# ensure_publisher_binding
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ensure_publisher_binding_adds_when_absent():
    """ensure_publisher_binding adds the binding when it is not present."""
    from services.gbp_provisioning import ensure_publisher_binding

    get_resp = _mock_httpx_response(200, {"bindings": []})
    set_resp = _mock_httpx_response(200, {"bindings": [
        {"role": "roles/pubsub.publisher", "members": ["mybusiness-api-pubsub@system.gserviceaccount.com"]}
    ]})

    with patch("services.gbp_provisioning._gcp_access_token", new_callable=AsyncMock, return_value="token"), \
         patch("services.gbp_provisioning.httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value = _mock_async_client({"get": [get_resp], "post": [set_resp]})
        await ensure_publisher_binding("my-proj", "gbp-reviews")

    # The setIamPolicy POST was called (binding was absent).
    # Verify via the mock client's post call.
    client = mock_client_cls.return_value
    client.post.assert_awaited_once()


@pytest.mark.asyncio
async def test_ensure_publisher_binding_skips_when_present():
    """ensure_publisher_binding does NOT setIamPolicy when the binding already exists."""
    from services.gbp_provisioning import ensure_publisher_binding

    get_resp = _mock_httpx_response(200, {"bindings": [
        {"role": "roles/pubsub.publisher", "members": ["mybusiness-api-pubsub@system.gserviceaccount.com"]}
    ]})

    with patch("services.gbp_provisioning._gcp_access_token", new_callable=AsyncMock, return_value="token"), \
         patch("services.gbp_provisioning.httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value = _mock_async_client({"get": [get_resp]})
        await ensure_publisher_binding("my-proj", "gbp-reviews")

    # setIamPolicy POST was NOT called (binding was present).
    client = mock_client_cls.return_value
    client.post.assert_not_awaited()


# ---------------------------------------------------------------------------
# register_notification
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_notification_skips_when_already_registered():
    """register_notification returns early when the setting already matches."""
    from services.gbp_provisioning import register_notification

    get_resp = _mock_httpx_response(200, {
        "pubsubTopic": "projects/p/topics/gbp-reviews",
        "notificationTypes": ["NEW_REVIEW", "UPDATED_REVIEW"],
    })

    with patch("services.gbp_provisioning.httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value = _mock_async_client({"get": [get_resp]})
        result = await register_notification("ACCT1", "client-token", "projects/p/topics/gbp-reviews")

    client = mock_client_cls.return_value
    client.patch.assert_not_awaited()
    assert result["pubsubTopic"] == "projects/p/topics/gbp-reviews"


@pytest.mark.asyncio
async def test_register_notification_patches_when_not_registered():
    """register_notification PATCHes when the setting does not match."""
    from services.gbp_provisioning import register_notification

    get_resp = _mock_httpx_response(404, {})
    patch_resp = _mock_httpx_response(200, {
        "pubsubTopic": "projects/p/topics/gbp-reviews",
        "notificationTypes": ["NEW_REVIEW", "UPDATED_REVIEW"],
    })

    with patch("services.gbp_provisioning.httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value = _mock_async_client({"get": [get_resp], "patch": [patch_resp]})
        result = await register_notification("ACCT1", "client-token", "projects/p/topics/gbp-reviews")

    client = mock_client_cls.return_value
    client.patch.assert_awaited_once()
    assert result["pubsubTopic"] == "projects/p/topics/gbp-reviews"


# ---------------------------------------------------------------------------
# provision_gbp_notifications (orchestration)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_provision_gbp_notifications_success():
    """provision_gbp_notifications persists provisioning_status='active' on success."""
    from services.gbp_provisioning import provision_gbp_notifications

    mock_db = MagicMock()
    update_calls = []

    def _table(name):
        chain = MagicMock()
        if name == "clients":
            chain.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data={"id": "c1", "gbp_access_token": "enc_token"}
            )
            def _update(data, **kwargs):
                update_calls.append((name, data))
                return chain
            chain.update.side_effect = _update
            chain.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[{"id": "c1"}])
        elif name == "locations":
            chain.select.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[{"gbp_account_id": "ACCT1", "gbp_location_id": "LOC1"}]
            )
        return chain

    mock_db.table.side_effect = _table

    with patch("db.get_db", return_value=mock_db), \
         patch("services.gbp_provisioning.settings") as mock_settings, \
         patch("services.crypto.decrypt", return_value="plain-token"), \
         patch("services.gbp_provisioning.ensure_topic", new_callable=AsyncMock), \
         patch("services.gbp_provisioning.ensure_publisher_binding", new_callable=AsyncMock), \
         patch("services.gbp_provisioning.ensure_push_subscription", new_callable=AsyncMock), \
         patch("services.gbp_provisioning.register_notification", new_callable=AsyncMock, return_value={"pubsubTopic": "t"}):
        mock_settings.gcp_sa_json = _SA_JSON
        mock_settings.gcp_project_id = "my-proj"
        mock_settings.gbp_pubsub_topic_name = "gbp-reviews"
        mock_settings.base_domain = "api.localmate.com.au"

        result = await provision_gbp_notifications("c1")

    assert result["status"] == "active"
    assert result["account_id"] == "ACCT1"
    # Verify provisioning_status='active' was persisted.
    active_updates = [d for _, d in update_calls if d.get("provisioning_status") == "active"]
    assert len(active_updates) == 1
    assert active_updates[0]["pubsub_topic"] is not None


@pytest.mark.asyncio
async def test_provision_gbp_notifications_failed_on_exception():
    """provision_gbp_notifications persists provisioning_status='failed' + error on exception."""
    from services.gbp_provisioning import provision_gbp_notifications

    mock_db = MagicMock()
    update_calls = []

    def _table(name):
        chain = MagicMock()
        if name == "clients":
            chain.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data={"id": "c1", "gbp_access_token": "enc_token"}
            )
            def _update(data, **kwargs):
                update_calls.append((name, data))
                return chain
            chain.update.side_effect = _update
            chain.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[{"id": "c1"}])
        elif name == "locations":
            chain.select.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[{"gbp_account_id": "ACCT1", "gbp_location_id": "LOC1"}]
            )
        return chain

    mock_db.table.side_effect = _table

    with patch("db.get_db", return_value=mock_db), \
         patch("services.gbp_provisioning.settings") as mock_settings, \
         patch("services.crypto.decrypt", return_value="plain-token"), \
         patch("services.gbp_provisioning.ensure_topic", new_callable=AsyncMock, side_effect=RuntimeError("GCP down")), \
         patch("services.gbp_provisioning.ensure_publisher_binding", new_callable=AsyncMock), \
         patch("services.gbp_provisioning.ensure_push_subscription", new_callable=AsyncMock), \
         patch("services.gbp_provisioning.register_notification", new_callable=AsyncMock):
        mock_settings.gcp_sa_json = _SA_JSON
        mock_settings.gcp_project_id = "my-proj"
        mock_settings.gbp_pubsub_topic_name = "gbp-reviews"
        mock_settings.base_domain = "api.localmate.com.au"

        result = await provision_gbp_notifications("c1")

    assert result["status"] == "failed"
    assert "GCP down" in result["error"]
    # Verify provisioning_status='failed' was persisted.
    failed_updates = [d for _, d in update_calls if d.get("provisioning_status") == "failed"]
    assert len(failed_updates) == 1
    assert "GCP down" in failed_updates[0]["provisioning_error"]


@pytest.mark.asyncio
async def test_provision_gbp_notifications_no_account_id():
    """provision_gbp_notifications fails when no GBP account_id is found on locations."""
    from services.gbp_provisioning import provision_gbp_notifications

    mock_db = MagicMock()
    update_calls = []

    def _table(name):
        chain = MagicMock()
        if name == "clients":
            chain.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data={"id": "c1", "gbp_access_token": "enc_token"}
            )
            def _update(data, **kwargs):
                update_calls.append((name, data))
                return chain
            chain.update.side_effect = _update
            chain.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[{"id": "c1"}])
        elif name == "locations":
            chain.select.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[{"gbp_account_id": None, "gbp_location_id": "LOC1"}]
            )
        return chain

    mock_db.table.side_effect = _table

    with patch("db.get_db", return_value=mock_db), \
         patch("services.crypto.decrypt", return_value="plain-token"):
        result = await provision_gbp_notifications("c1")

    assert result["status"] == "failed"
    assert "account_id" in result["error"]


# ---------------------------------------------------------------------------
# ensure_push_subscription (C9 / D15-B)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ensure_push_subscription_creates_when_absent():
    """ensure_push_subscription creates the subscription when it does not exist."""
    from services.gbp_provisioning import ensure_push_subscription

    get_resp = _mock_httpx_response(404, {})
    put_resp = _mock_httpx_response(200, {})

    with patch("services.gbp_provisioning._gcp_access_token", new_callable=AsyncMock, return_value="token"), \
         patch("services.gbp_provisioning.httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value = _mock_async_client({"get": [get_resp], "put": [put_resp]})
        result = await ensure_push_subscription("my-proj", "gbp-reviews", "https://api.example.com/webhooks/inbound-review")

    assert result == "projects/my-proj/subscriptions/gbp-reviews-push"
    client = mock_client_cls.return_value
    client.put.assert_awaited_once()


@pytest.mark.asyncio
async def test_ensure_push_subscription_skips_when_exists_and_matches():
    """ensure_push_subscription returns early when the subscription exists and matches."""
    from services.gbp_provisioning import ensure_push_subscription

    get_resp = _mock_httpx_response(200, {
        "topic": "projects/my-proj/topics/gbp-reviews",
        "pushConfig": {"pushEndpoint": "https://api.example.com/webhooks/inbound-review"},
    })

    with patch("services.gbp_provisioning._gcp_access_token", new_callable=AsyncMock, return_value="token"), \
         patch("services.gbp_provisioning.httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value = _mock_async_client({"get": [get_resp]})
        result = await ensure_push_subscription("my-proj", "gbp-reviews", "https://api.example.com/webhooks/inbound-review")

    assert result == "projects/my-proj/subscriptions/gbp-reviews-push"
    client = mock_client_cls.return_value
    client.put.assert_not_awaited()

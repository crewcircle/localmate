"""Shared test fixtures — env vars must be set before any backend imports."""
import os
_STUB_ENV = {
    "SUPABASE_URL": "https://stub.supabase.co",
    "SUPABASE_ANON_KEY": "stub_anon",
    "SUPABASE_SERVICE_ROLE_KEY": "stub_service",
    "STRIPE_SECRET_KEY": "sk_stub",
    "STRIPE_PRICE_ID": "price_stub",
    "STRIPE_WEBHOOK_SECRET": "whsec_stub",
    "STRIPE_GST_RATE_ID": "stub_gst",
    "ANTHROPIC_API_KEY": "sk-ant-stub",
    "RESEND_API_KEY": "re_stub",
    "TWILIO_ACCOUNT_SID": "AC000",
    "TWILIO_AUTH_TOKEN": "stub",
    "TWILIO_AU_NUMBER": "+61400000000",
    "DATAFORSEO_LOGIN": "stub",
    "DATAFORSEO_PASSWORD": "stub",
    "GBP_CLIENT_ID": "stub",
    "GBP_CLIENT_SECRET": "stub",
    "BASE_DOMAIN": "crewcircle.com.au",
    "PROJECT_ID": "localmate",
    "ENVIRONMENT": "test",
    "ENCRYPTION_KEY": "",
    "SUPABASE_JWT_SECRET": "",
}
for _k, _v in _STUB_ENV.items():
    os.environ.setdefault(_k, _v)

import pytest
from unittest.mock import MagicMock, AsyncMock


@pytest.fixture
def mock_supabase():
    return MagicMock()

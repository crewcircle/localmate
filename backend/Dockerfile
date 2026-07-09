FROM python:3.11-slim

WORKDIR /app

# Install uv for fast dependency management
RUN pip install uv --no-cache-dir

# Install dependencies first (better layer caching)
COPY pyproject.toml .
RUN uv sync --no-dev

# Copy application code
COPY . .

# Doppler injects env vars at runtime — no .env file needed in container.
# Required env vars (all injected by Doppler):
#   SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY
#   STRIPE_SECRET_KEY, STRIPE_PRICE_ID, STRIPE_WEBHOOK_SECRET, STRIPE_GST_RATE_ID
#   ANTHROPIC_API_KEY
#   RESEND_API_KEY
#   TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_AU_NUMBER
#   DATAFORSEO_LOGIN, DATAFORSEO_PASSWORD
#   GBP_CLIENT_ID, GBP_CLIENT_SECRET
#   BASE_DOMAIN, PROJECT_ID
#   SENTRY_DSN (optional)

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request, sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health', timeout=3).status == 200 else 1)" || exit 1

CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
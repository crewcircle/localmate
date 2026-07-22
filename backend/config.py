from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    supabase_url:              str
    supabase_anon_key:         str
    supabase_service_role_key: str
    stripe_secret_key:         str
    stripe_price_id:           str
    stripe_webhook_secret:     str
    stripe_gst_rate_id:        str = ""
    anthropic_api_key:         str
    resend_api_key:            str
    twilio_account_sid:        str
    twilio_auth_token:         str
    twilio_au_number:          str
    dataforseo_login:          str
    dataforseo_password:       str
    encryption_key:            str = ""
    gbp_client_id:             str
    gbp_client_secret:         str
    base_domain:               str
    yelp_api_key:              str = ""
    sentry_dsn:                str = ""
    project_id:                str = "localmate"
    environment:               str = "prod"
    # Square — global token deprecated for production (per-client OAuth is
    # authoritative via square_oauth.get_valid_token). Kept for sandbox/dev fallback.
    square_access_token:       str = ""
    square_environment:        str = "sandbox"
    square_app_id:             str = ""
    square_app_secret:         str = ""
    square_oauth_redirect_path: str = "/auth/square-callback"
    square_webhook_signature_key: str = ""
    menu_images_bucket:        str = "menu-images"
    supabase_jwt_secret:       str = ""

    # --- Phase 0: queue / worker / billing-portal infra ---
    redis_url:                 str = "redis://localhost:6379/0"
    worker_role:               str = "web"   # "web" | "worker" | "scheduler"
    dashboard_url:             str = ""       # Stripe portal return_url base
    stripe_portal_config_id:   str = ""       # Stripe portal configuration id (bpc_...)

    class Config:
        env_file = ".env.local"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

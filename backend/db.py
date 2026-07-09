from supabase import create_client, Client
from config import settings

_client: Client | None = None


async def init_db() -> None:
    global _client
    _client = create_client(settings.supabase_url, settings.supabase_service_role_key)


def get_db() -> Client:
    if _client is None:
        raise RuntimeError("Database not initialised — call init_db() first")
    return _client

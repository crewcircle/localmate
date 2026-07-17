import logging
from cryptography.fernet import Fernet
from cryptography.fernet import InvalidToken
from config import settings

logger = logging.getLogger(__name__)

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        if not settings.encryption_key:
            raise RuntimeError("ENCRYPTION_KEY not configured")
        key = settings.encryption_key.encode() if isinstance(settings.encryption_key, str) else settings.encryption_key
        _fernet = Fernet(key)
    return _fernet


def encrypt(plaintext: str) -> str:
    fernet = _get_fernet()
    return fernet.encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str:
    try:
        fernet = _get_fernet()
        return fernet.decrypt(token.encode()).decode()
    except InvalidToken:
        logger.error("Fernet decrypt failed — invalid token or wrong key")
        raise

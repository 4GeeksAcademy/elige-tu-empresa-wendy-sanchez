import hashlib
import hmac
import os
import secrets
import unicodedata
from datetime import datetime, timezone

_user_key = os.getenv("TELEMETRY_USER_KEY")
_vendor_key = os.getenv("TELEMETRY_VENDOR_KEY")
if os.getenv("ENVIRONMENT") == "production" and (not _user_key or not _vendor_key):
    raise RuntimeError("Dedicated telemetry keys are required in production")
USER_KEY = _user_key.encode() if _user_key else secrets.token_bytes(32)
VENDOR_KEY = _vendor_key.encode() if _vendor_key else secrets.token_bytes(32)


def user_pseudonym(user_id: int) -> str:
    day = datetime.now(timezone.utc).date().isoformat()
    return hmac.new(USER_KEY, f"{day}:{user_id}".encode(), hashlib.sha256).hexdigest()


def vendor_pseudonym(name: str) -> str:
    normalized = " ".join(unicodedata.normalize("NFC", name).split()).casefold()
    return hmac.new(VENDOR_KEY, normalized.encode(), hashlib.sha256).hexdigest()
from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets

from cryptography.fernet import Fernet


class CredentialCipher:
    def __init__(self, secret_key: str) -> None:
        digest = hashlib.sha256(secret_key.encode("utf-8")).digest()
        self._fernet = Fernet(base64.urlsafe_b64encode(digest))

    def encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode("utf-8")).decode("ascii")

    def decrypt(self, value: str) -> str:
        return self._fernet.decrypt(value.encode("ascii")).decode("utf-8")


def new_secret_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def constant_time_equal(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


_EMAIL_RE = re.compile(r"([A-Za-z0-9._%+\-])[A-Za-z0-9._%+\-]*(@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})")
_FEED_URL_RE = re.compile(r"(/f/)[A-Za-z0-9_\-]{16,}(\.xml)")


def redact_sensitive(value: str) -> str:
    redacted = _EMAIL_RE.sub(r"\1***\2", value)
    return _FEED_URL_RE.sub(r"\1***\2", redacted)


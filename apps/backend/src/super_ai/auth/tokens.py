"""opaque bearer token 的生成与单向摘要。"""

import hashlib
import secrets


def generate_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

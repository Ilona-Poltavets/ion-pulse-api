from hashlib import sha256
from secrets import token_urlsafe

from pwdlib import PasswordHash

from ion_pulse.core.config import get_settings

password_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return password_hasher.verify(password, password_hash)


def create_session_token() -> str:
    return token_urlsafe(32)


def hash_session_token(token: str) -> str:
    secret = get_settings().session_secret
    return sha256(f"{secret}:{token}".encode()).hexdigest()

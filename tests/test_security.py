from ion_pulse.core.security import (
    create_session_token,
    hash_password,
    hash_session_token,
    verify_password,
)


def test_passwords_are_hashed_and_verified() -> None:
    password_hash = hash_password("a secure test password")

    assert password_hash != "a secure test password"
    assert verify_password("a secure test password", password_hash)
    assert not verify_password("wrong password", password_hash)


def test_session_tokens_are_random_and_only_the_hash_is_persistable() -> None:
    first = create_session_token()
    second = create_session_token()

    assert first != second
    assert hash_session_token(first) == hash_session_token(first)
    assert hash_session_token(first) != first

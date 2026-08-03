import pytest
from pydantic import ValidationError

from ion_pulse.core.config import Settings


def test_production_settings_reject_insecure_session_configuration() -> None:
    with pytest.raises(ValidationError, match="secure session cookies"):
        Settings(
            _env_file=None,
            environment="production",
            debug=False,
            site_url="https://ion-pulse.example",
            session_secret="a-long-unique-production-secret-that-is-not-the-default",
            session_cookie_secure=False,
        )


def test_production_settings_accept_hardened_configuration() -> None:
    settings = Settings(
        _env_file=None,
        environment="production",
        debug=False,
        site_url="https://ion-pulse.example",
        session_secret="a-long-unique-production-secret-that-is-not-the-default",
        session_cookie_secure=True,
    )

    assert settings.environment == "production"


@pytest.mark.parametrize(
    ("overrides", "error"),
    [
        ({"debug": True}, "debug mode"),
        ({"site_url": "http://ion-pulse.example"}, "must use HTTPS"),
        ({"session_secret": "replace-this-local-session-secret"}, "unique session secret"),
    ],
)
def test_production_settings_reject_each_remaining_insecure_default(
    overrides: dict[str, bool | str], error: str
) -> None:
    settings = {
        "_env_file": None,
        "environment": "production",
        "debug": False,
        "site_url": "https://ion-pulse.example",
        "session_secret": "a-long-unique-production-secret-that-is-not-the-default",
        "session_cookie_secure": True,
    }

    with pytest.raises(ValidationError, match=error):
        Settings(**(settings | overrides))

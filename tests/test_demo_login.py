from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from ion_pulse.schemas.auth import AuthenticatedUser, LoginRequest, RegisterRequest


@pytest.mark.parametrize("name", ["admin", "editor", "content", "author", "moderator", "player"])
def test_local_demo_login_and_response(monkeypatch, name):
    monkeypatch.setattr(
        "ion_pulse.schemas.auth.get_settings", lambda: SimpleNamespace(environment="local")
    )
    email = f"{name}@ion-pulse.local"
    assert LoginRequest(email=email, password="IonPulseDemo2026!").email == email
    assert AuthenticatedUser(id=uuid4(), email=email, display_name=name, roles=[]).email == email


def test_demo_exception_is_not_enabled_in_production(monkeypatch):
    monkeypatch.setattr(
        "ion_pulse.schemas.auth.get_settings", lambda: SimpleNamespace(environment="production")
    )
    with pytest.raises(ValidationError):
        LoginRequest(email="admin@ion-pulse.local", password="test")


@pytest.mark.parametrize("email", ["invalid", "other@ion-pulse.local", "admin@other.local"])
def test_invalid_or_unknown_local_addresses_are_rejected(email):
    with pytest.raises(ValidationError):
        LoginRequest(email=email, password="test")


def test_registration_still_requires_real_email():
    with pytest.raises(ValidationError):
        RegisterRequest(
            email="admin@ion-pulse.local", display_name="Admin", password="IonPulseDemo2026!"
        )

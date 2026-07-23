import ion_pulse.models  # noqa: F401
from ion_pulse.db.base import Base
from ion_pulse.domain.roles import RoleCode


def test_identity_schema_has_multi_role_relationship() -> None:
    assert {"users", "roles", "user_roles", "user_sessions"} <= set(Base.metadata.tables)

    user_roles = Base.metadata.tables["user_roles"]
    assert {column.name for column in user_roles.primary_key.columns} == {"user_id", "role_id"}


def test_assignable_role_codes_match_product_model() -> None:
    assert {role.value for role in RoleCode} == {
        "author",
        "editor",
        "moderator",
        "content_manager",
        "administrator",
    }

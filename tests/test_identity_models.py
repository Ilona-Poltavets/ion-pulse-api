import ion_pulse.models  # noqa: F401
from ion_pulse.db.base import Base
from ion_pulse.domain.roles import RoleCode


def test_identity_schema_has_multi_role_relationship() -> None:
    assert {"users", "roles", "user_roles", "user_sessions", "password_reset_tokens"} <= set(
        Base.metadata.tables
    )

    user_roles = Base.metadata.tables["user_roles"]
    assert {column.name for column in user_roles.primary_key.columns} == {"user_id", "role_id"}


def test_password_reset_tokens_are_single_use_and_expire() -> None:
    tokens = Base.metadata.tables["password_reset_tokens"]
    assert {"user_id", "token_hash", "expires_at", "used_at"} <= set(tokens.c.keys())
    assert tokens.c.token_hash.unique


def test_hidden_comments_remain_available_for_moderator_restoration() -> None:
    comments = Base.metadata.tables["publication_comments"]
    assert "is_hidden" in comments.c


def test_comment_media_columns_belong_to_comments() -> None:
    comments = Base.metadata.tables["publication_comments"]
    localizations = Base.metadata.tables["publication_localizations"]

    assert "media_kind" in comments.c
    assert "media_value" in comments.c
    assert "media_kind" not in localizations.c
    assert "media_value" not in localizations.c


def test_journal_materials_keep_a_published_snapshot() -> None:
    materials = Base.metadata.tables["journal_issue_publications"]
    assert "snapshot" in materials.c


def test_role_changes_have_an_immutable_audit_table() -> None:
    audit = Base.metadata.tables["user_role_audit"]
    assert {"user_id", "actor_id", "role_code", "action"} <= set(audit.c.keys())


def test_editorial_and_translation_tables_preserve_publication_history() -> None:
    assert {"publication_editorial_reviews", "translation_jobs"} <= set(Base.metadata.tables)

    editorial_reviews = Base.metadata.tables["publication_editorial_reviews"]
    foreign_key = next(iter(editorial_reviews.foreign_keys))
    assert foreign_key.ondelete == "RESTRICT"

    translation_jobs = Base.metadata.tables["translation_jobs"]
    assert {column.name for column in translation_jobs.columns} >= {
        "publication_id",
        "target_locale",
        "status",
        "attempts",
    }


def test_journal_issue_materials_are_unique_and_ordered() -> None:
    assert {"journal_issues", "journal_issue_publications"} <= set(Base.metadata.tables)
    issue_materials = Base.metadata.tables["journal_issue_publications"]
    unique_sets = {
        tuple(constraint.columns.keys())
        for constraint in issue_materials.constraints
        if hasattr(constraint, "columns")
    }
    assert ("issue_id", "publication_id") in unique_sets
    assert ("issue_id", "position") in unique_sets


def test_assignable_role_codes_match_product_model() -> None:
    assert {role.value for role in RoleCode} == {
        "author",
        "editor",
        "moderator",
        "content_manager",
        "administrator",
    }

from enum import StrEnum


class RoleCode(StrEnum):
    """Additional capabilities assignable to a registered member."""

    AUTHOR = "author"
    EDITOR = "editor"
    MODERATOR = "moderator"
    CONTENT_MANAGER = "content_manager"
    ADMINISTRATOR = "administrator"

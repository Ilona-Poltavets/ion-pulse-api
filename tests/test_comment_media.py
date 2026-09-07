import pytest
from pydantic import ValidationError

from ion_pulse.schemas.comments import CommentCreate


def test_comment_accepts_media_without_text() -> None:
    comment = CommentCreate(media_kind="sticker", media_value="🎮✨")

    assert comment.body == ""
    assert comment.media_kind == "sticker"


def test_comment_rejects_empty_content() -> None:
    with pytest.raises(ValidationError, match="Comment text or media is required"):
        CommentCreate(body="   ")


def test_comment_rejects_non_http_gif_url() -> None:
    with pytest.raises(ValidationError, match="valid HTTP or HTTPS URL"):
        CommentCreate(media_kind="gif", media_value="javascript:alert(1)")

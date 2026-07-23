from enum import StrEnum


class PublicationStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    EDITORIAL_REVIEW = "editorial_review"
    PUBLISHED = "published"
    REJECTED = "rejected"


class ContentLocale(StrEnum):
    RUSSIAN = "ru"
    ENGLISH = "en"

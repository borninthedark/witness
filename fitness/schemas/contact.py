from pydantic import BaseModel, EmailStr, field_validator

MAX_NAME_LENGTH = 120
MAX_SUBJECT_LENGTH = 150
MAX_MESSAGE_LENGTH = 4000


class ContactForm(BaseModel):
    name: str
    email: EmailStr
    subject: str
    message: str
    honeypot: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = cls._ensure_not_empty(value)
        if len(value) > MAX_NAME_LENGTH:
            raise ValueError("name too long")
        return value

    @field_validator("subject")
    @classmethod
    def validate_subject(cls, value: str) -> str:
        value = cls._ensure_not_empty(value)
        if len(value) > MAX_SUBJECT_LENGTH:
            raise ValueError("subject too long")
        return value

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        value = cls._ensure_not_empty(value)
        if len(value) > MAX_MESSAGE_LENGTH:
            raise ValueError("message too long")
        return value

    @staticmethod
    def _ensure_not_empty(value: str) -> str:
        if not value or not value.strip():
            raise ValueError("must not be empty")
        return value.strip()

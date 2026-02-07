from pydantic import BaseModel, EmailStr, field_validator

MAX_NAME_LENGTH = 120
MAX_SUBJECT_LENGTH = 150
MAX_MESSAGE_LENGTH = 4000

_FIELD_LIMITS: dict[str, int] = {
    "name": MAX_NAME_LENGTH,
    "subject": MAX_SUBJECT_LENGTH,
    "message": MAX_MESSAGE_LENGTH,
}


def _validate_text_field(value: str, field_name: str) -> str:
    if not value or not value.strip():
        raise ValueError("must not be empty")
    value = value.strip()
    limit = _FIELD_LIMITS[field_name]
    if len(value) > limit:
        raise ValueError(f"{field_name} too long")
    return value


class ContactForm(BaseModel):
    name: str
    email: EmailStr
    subject: str
    message: str
    honeypot: str | None = None

    @field_validator("name", "subject", "message")
    @classmethod
    def validate_text_fields(cls, value: str, info: object) -> str:
        return _validate_text_field(value, info.field_name)

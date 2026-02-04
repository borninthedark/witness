from pydantic import BaseModel


class BadgeAssertionOut(BaseModel):
    assertion_id: str
    badge_name: str
    badge_description: str | None = None
    issuer_name: str | None = None
    issuer_url: str | None = None
    issued_on: str | None = None
    evidence: list[str]

    class Config:
        from_attributes = True

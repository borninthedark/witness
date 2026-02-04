from pydantic import BaseModel


class CertificationOut(BaseModel):
    slug: str
    title: str
    issuer: str
    pdf_url: str
    sha256: str
    dns_name: str | None = None
    assertion_url: str | None = None
    verification_url: str | None = None

    class Config:
        from_attributes = True

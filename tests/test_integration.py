"""Integration tests covering certificates, résumé, and contact flows."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from fitness.config import settings
from fitness.models.certification import Certification


def _get_csrf_token(client: TestClient) -> str:
    """Fetch the contact page to obtain a fresh CSRF token."""
    response = client.get("/contact")
    assert response.status_code == 200
    token = client.cookies.get("wtf_csrf")
    assert isinstance(token, str), "Expected CSRF cookie after GET /contact"
    return token


def test_certifications_page_deduplicates_entries(
    client: TestClient, db_session: Session
) -> None:
    """Ensure duplicate SHA entries collapse to a single certificate."""
    duplicate_sha = "abc123"
    first = Certification(
        slug="dup-one",
        title="Duplicate One",
        issuer="DRY Issuer",
        pdf_url="http://example.com/one.pdf",
        sha256=duplicate_sha,
        dns_name="dup-one.princetonstrong.com",
    )
    second = Certification(
        slug="dup-two",
        title="Duplicate Two",
        issuer="DRY Issuer",
        pdf_url="http://example.com/two.pdf",
        sha256=duplicate_sha,
        dns_name="dup-two.princetonstrong.com",
    )
    db_session.add_all([first, second])
    db_session.commit()

    response = client.get("/certs")

    assert response.status_code == 200
    body = response.text
    assert "Duplicate Two" in body
    assert "/certs/dup-two/pdf" in body
    assert "Duplicate One" not in body

    db_session.query(Certification).filter(
        Certification.slug.in_(["dup-one", "dup-two"])
    ).delete(synchronize_session=False)
    db_session.commit()


def test_resume_pdf_endpoint_streams_file(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify the résumé PDF endpoint streams the document."""
    from fitness.services.pdf_resume import build_resume, load_data

    data_path = Path("fitness/data/resume-data.yaml")
    if not data_path.exists():
        pytest.skip("resume-data.yaml not found")

    data = load_data(data_path)
    pdf_path = tmp_path / "PAS-Resume.pdf"
    build_resume(pdf_path, data, "#7B7B7B", "#FFFFFF")

    import fitness.routers.ui as ui_mod

    monkeypatch.setattr(ui_mod, "RESUME_STORAGE_DIR", tmp_path)

    response = client.get("/resume/pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "PAS-Resume.pdf" in response.headers["content-disposition"]
    assert len(response.content) > 1000


def test_resume_pdf_fits_two_pages(tmp_path: Path) -> None:
    """Resume PDF must not exceed two pages."""
    import re

    from fitness.services.pdf_resume import build_resume, load_data

    data_path = Path("fitness/data/resume-data.yaml")
    if not data_path.exists():
        pytest.skip("resume-data.yaml not found")

    data = load_data(data_path)
    out = tmp_path / "resume.pdf"
    build_resume(out, data, "#7B7B7B", "#FFFFFF")

    content = out.read_bytes().decode("latin-1")
    counts = re.findall(r"/Count\s+(\d+)", content)
    pages = max(int(c) for c in counts) if counts else 0
    assert pages <= 2, f"Resume is {pages} pages, must be <= 2"


@pytest.mark.usefixtures("client")
def test_contact_form_submission_writes_log(
    monkeypatch: pytest.MonkeyPatch, client: TestClient, tmp_path: Path
) -> None:
    """Make sure contact submissions persist to disk and return success."""
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    csrf_token = _get_csrf_token(client)
    payload = {
        "name": "Worf",
        "email": "worf@example.com",
        "subject": "Enterprise-E",
        "message": "Engage.",
        "honeypot": "",
        "csrf_token": csrf_token,
    }
    response = client.post("/contact", data=payload)
    assert response.status_code == 200
    assert "Your message has been transmitted." in response.text

    log_path = Path(tmp_path) / "contact-messages.jsonl"
    assert log_path.exists()
    content = log_path.read_text().strip().splitlines()
    last = json.loads(content[-1])
    assert last["name"] == payload["name"]
    assert last["email"] == payload["email"]
    assert last["message"] == payload["message"]

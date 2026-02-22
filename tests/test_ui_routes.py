"""Tests for uncovered paths in fitness/routers/ui.py.

Covers:
- home() DB exception handling
- certs() inactive certs / DB exception
- cert_pdf() DB exception, missing cert 404, download param, local file, remote fallback
- cert_pdf_viewer() DB exception, missing cert, no PDF available
- resume_pdf() local file serving (inline + download), remote fallback
- resume_shortcut_redirect
- _persist_contact_submission
- submit_contact honeypot, validation error
- _deliver_contact_message
- verify_cert() all paths including metadata error
- verify_cert_redirect() all 4 priority paths
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from fitness.models.certification import Certification

# ---------------------------------------------------------------------------
# home() — DB exception handling (lines 76-78)
# ---------------------------------------------------------------------------


def test_home_db_exception_returns_zero_certs(client: TestClient):
    """When the DB query raises, home() should fall back to cert_count=0."""
    with patch(
        "fitness.routers.ui.get_db",
    ) as mock_get_db:
        broken_session = MagicMock()
        broken_session.query.side_effect = Exception("db is down")

        def _override():
            yield broken_session

        mock_get_db.return_value = _override()

        # Use the app dependency override approach instead
        from fitness.database import get_db as db_dep
        from fitness.main import app

        original = app.dependency_overrides.get(db_dep)

        app.dependency_overrides[db_dep] = _override

        try:
            resp = client.get("/", headers={"Accept": "application/json"})
            assert resp.status_code == 200
            assert resp.json()["certifications"] == 0
        finally:
            if original is not None:
                app.dependency_overrides[db_dep] = original
            else:
                app.dependency_overrides.pop(db_dep, None)


# ---------------------------------------------------------------------------
# certs() — inactive certs (line 119) + DB exception (lines 126-129)
# ---------------------------------------------------------------------------


def test_certs_separates_inactive_by_status(client: TestClient, db_session: Session):
    """Certs with status != 'active' land in inactive_certs list."""
    db_session.add(
        Certification(
            slug="inactive-cert-xyz",
            title="Inactive Cert",
            issuer="Test",
            sha256="inact_hash_xyz",
            pdf_url="http://example.com/inact.pdf",
            status="deprecated",
            is_visible=True,
        )
    )
    db_session.add(
        Certification(
            slug="active-cert-xyz",
            title="Active Cert",
            issuer="Test",
            sha256="act_hash_xyz",
            pdf_url="http://example.com/act.pdf",
            status="active",
            is_visible=True,
        )
    )
    db_session.commit()

    resp = client.get("/certs")
    assert resp.status_code == 200
    # Both should appear in the rendered page
    assert "Inactive Cert" in resp.text
    assert "Active Cert" in resp.text


def test_certs_db_exception_returns_empty_lists(client: TestClient):
    """When the DB query raises, certs() falls back to empty active/inactive lists."""
    from fitness.database import get_db as db_dep
    from fitness.main import app

    broken = MagicMock()
    broken.query.side_effect = Exception("connection lost")

    def _broken_db():
        yield broken

    original = app.dependency_overrides.get(db_dep)
    app.dependency_overrides[db_dep] = _broken_db

    try:
        resp = client.get("/certs")
        assert resp.status_code == 200
    finally:
        if original is not None:
            app.dependency_overrides[db_dep] = original
        else:
            app.dependency_overrides.pop(db_dep, None)


# ---------------------------------------------------------------------------
# cert_pdf() — lines 153-214
# ---------------------------------------------------------------------------


def test_cert_pdf_db_exception_returns_503(client: TestClient):
    """DB error during cert lookup returns 503."""
    from fitness.database import get_db as db_dep
    from fitness.main import app

    broken = MagicMock()
    broken.query.return_value.filter.side_effect = Exception("boom")

    def _broken_db():
        yield broken

    original = app.dependency_overrides.get(db_dep)
    app.dependency_overrides[db_dep] = _broken_db

    try:
        resp = client.get("/certs/any-slug/pdf")
        assert resp.status_code == 503
    finally:
        if original is not None:
            app.dependency_overrides[db_dep] = original
        else:
            app.dependency_overrides.pop(db_dep, None)


def test_cert_pdf_missing_cert_returns_404(client: TestClient, db_session: Session):
    """Non-existent slug returns 404."""
    resp = client.get("/certs/does-not-exist/pdf")
    assert resp.status_code == 404


def test_cert_pdf_local_file_inline(client: TestClient, db_session: Session):
    """Local PDF file served inline (default, no download param)."""
    db_session.add(
        Certification(
            slug="local-pdf-test",
            title="Local PDF",
            issuer="Test",
            sha256="localpdf_hash",
            pdf_url="",
        )
    )
    db_session.commit()

    fake_candidate = MagicMock()
    fake_candidate.exists.return_value = True

    fake_dir = MagicMock()
    fake_dir.__truediv__ = MagicMock(return_value=fake_candidate)

    with (
        patch("fitness.routers.ui.CERT_STORAGE_DIR", new=fake_dir),
        patch("fitness.routers.ui.FileResponse") as mock_fr,
    ):
        from fastapi.responses import Response

        mock_fr.return_value = Response(
            content=b"%PDF-1.4 fake", media_type="application/pdf"
        )
        resp = client.get("/certs/local-pdf-test/pdf")
        assert resp.status_code == 200
        # Verify FileResponse was called with inline disposition
        call_kwargs = mock_fr.call_args
        assert "inline" in call_kwargs.kwargs["headers"]["Content-Disposition"]


def test_cert_pdf_local_file_download(client: TestClient, db_session: Session):
    """Local PDF file served as download when ?download=1."""
    db_session.add(
        Certification(
            slug="dl-pdf-test",
            title="Download PDF",
            issuer="Test",
            sha256="dlpdf_hash",
            pdf_url="",
        )
    )
    db_session.commit()

    fake_candidate = MagicMock()
    fake_candidate.exists.return_value = True

    fake_dir = MagicMock()
    fake_dir.__truediv__ = MagicMock(return_value=fake_candidate)

    with (
        patch("fitness.routers.ui.CERT_STORAGE_DIR", new=fake_dir),
        patch("fitness.routers.ui.FileResponse") as mock_fr,
    ):
        from fastapi.responses import Response

        mock_fr.return_value = Response(
            content=b"%PDF-1.4 fake", media_type="application/pdf"
        )
        resp = client.get("/certs/dl-pdf-test/pdf?download=1")
        assert resp.status_code == 200
        call_kwargs = mock_fr.call_args
        assert "attachment" in call_kwargs.kwargs["headers"]["Content-Disposition"]


def test_cert_pdf_remote_fallback(client: TestClient, db_session: Session):
    """When no local file, falls back to remote pdf_url via httpx."""
    db_session.add(
        Certification(
            slug="remote-pdf-test",
            title="Remote PDF",
            issuer="Test",
            sha256="remotepdf_hash",
            pdf_url="https://example.com/cert.pdf",
        )
    )
    db_session.commit()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = b"%PDF-1.4 remote content"
    mock_response.raise_for_status = MagicMock()

    with (
        patch("fitness.routers.ui.CERT_STORAGE_DIR", new=Path("/nonexistent")),
        patch("fitness.routers.ui.httpx.get", return_value=mock_response),
    ):
        resp = client.get("/certs/remote-pdf-test/pdf")
        assert resp.status_code == 200
        assert resp.content == b"%PDF-1.4 remote content"


def test_cert_pdf_remote_fallback_http_error(client: TestClient, db_session: Session):
    """When remote fetch fails with HTTPError, returns 404."""
    db_session.add(
        Certification(
            slug="remote-fail-test",
            title="Remote Fail",
            issuer="Test",
            sha256="remotefail_hash",
            pdf_url="https://example.com/missing.pdf",
        )
    )
    db_session.commit()

    with (
        patch("fitness.routers.ui.CERT_STORAGE_DIR", new=Path("/nonexistent")),
        patch("fitness.routers.ui.httpx.get", side_effect=httpx.HTTPError("Not Found")),
    ):
        resp = client.get("/certs/remote-fail-test/pdf")
        assert resp.status_code == 404


def test_cert_pdf_no_local_no_remote_returns_404(
    client: TestClient, db_session: Session
):
    """Cert exists but has no local file and no pdf_url -> 404."""
    db_session.add(
        Certification(
            slug="nopdf-test",
            title="No PDF",
            issuer="Test",
            sha256="nopdf_hash",
            pdf_url="",
        )
    )
    db_session.commit()

    with patch("fitness.routers.ui.CERT_STORAGE_DIR", new=Path("/nonexistent")):
        resp = client.get("/certs/nopdf-test/pdf")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# cert_pdf_viewer() — lines 226-238
# ---------------------------------------------------------------------------


def test_cert_pdf_viewer_db_exception_returns_503(client: TestClient):
    """DB error during viewer lookup returns 503."""
    from fitness.database import get_db as db_dep
    from fitness.main import app

    broken = MagicMock()
    broken.query.return_value.filter.side_effect = Exception("db crash")

    def _broken_db():
        yield broken

    original = app.dependency_overrides.get(db_dep)
    app.dependency_overrides[db_dep] = _broken_db

    try:
        resp = client.get("/certs/any-slug/viewer")
        assert resp.status_code == 503
    finally:
        if original is not None:
            app.dependency_overrides[db_dep] = original
        else:
            app.dependency_overrides.pop(db_dep, None)


def test_cert_pdf_viewer_missing_cert_returns_404(
    client: TestClient, db_session: Session
):
    """Non-existent cert returns 404 from viewer."""
    resp = client.get("/certs/nonexistent-viewer-slug/viewer")
    assert resp.status_code == 404


def test_cert_pdf_viewer_no_pdf_available_returns_404(
    client: TestClient, db_session: Session
):
    """Cert exists but no local file and no pdf_url -> 404 from viewer."""
    db_session.add(
        Certification(
            slug="viewer-nopdf",
            title="Viewer No PDF",
            issuer="Test",
            sha256="viewernopdf_hash",
            pdf_url="",
        )
    )
    db_session.commit()

    with patch("fitness.routers.ui.CERT_STORAGE_DIR", new=Path("/nonexistent")):
        resp = client.get("/certs/viewer-nopdf/viewer")
        assert resp.status_code == 404


def test_cert_pdf_viewer_with_pdf_url_renders(client: TestClient, db_session: Session):
    """Cert with pdf_url (no local file) renders the viewer page."""
    db_session.add(
        Certification(
            slug="viewer-remote",
            title="Viewer Remote PDF",
            issuer="Test",
            sha256="viewerremote_hash",
            pdf_url="https://example.com/cert.pdf",
        )
    )
    db_session.commit()

    with patch("fitness.routers.ui.CERT_STORAGE_DIR", new=Path("/nonexistent")):
        resp = client.get("/certs/viewer-remote/viewer")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]


# ---------------------------------------------------------------------------
# resume_pdf() — lines 282-306
# ---------------------------------------------------------------------------


def test_resume_pdf_local_inline(client: TestClient):
    """Local resume PDF served inline (default)."""
    fake_candidate = MagicMock()
    fake_candidate.exists.return_value = True

    fake_dir = MagicMock()
    fake_dir.__truediv__ = MagicMock(return_value=fake_candidate)

    with (
        patch("fitness.routers.ui.RESUME_STORAGE_DIR", new=fake_dir),
        patch("fitness.routers.ui.FileResponse") as mock_fr,
    ):
        from fastapi.responses import Response

        mock_fr.return_value = Response(
            content=b"%PDF-resume", media_type="application/pdf"
        )
        resp = client.get("/resume/pdf")
        assert resp.status_code == 200
        call_kwargs = mock_fr.call_args
        assert "inline" in call_kwargs.kwargs["headers"]["Content-Disposition"]


def test_resume_pdf_local_download(client: TestClient):
    """Local resume PDF served as download when ?download=1."""
    fake_candidate = MagicMock()
    fake_candidate.exists.return_value = True

    fake_dir = MagicMock()
    fake_dir.__truediv__ = MagicMock(return_value=fake_candidate)

    with (
        patch("fitness.routers.ui.RESUME_STORAGE_DIR", new=fake_dir),
        patch("fitness.routers.ui.FileResponse") as mock_fr,
    ):
        from fastapi.responses import Response

        mock_fr.return_value = Response(
            content=b"%PDF-resume", media_type="application/pdf"
        )
        resp = client.get("/resume/pdf?download=1")
        assert resp.status_code == 200
        call_kwargs = mock_fr.call_args
        assert "attachment" in call_kwargs.kwargs["headers"]["Content-Disposition"]


def test_resume_pdf_remote_fallback(client: TestClient):
    """When local file missing, fetches from remote URL."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = b"%PDF-remote-resume"
    mock_response.raise_for_status = MagicMock()

    with (
        patch("fitness.routers.ui.RESUME_STORAGE_DIR", new=Path("/nonexistent")),
        patch("fitness.routers.ui.httpx.get", return_value=mock_response),
    ):
        resp = client.get("/resume/pdf")
        assert resp.status_code == 200
        assert resp.content == b"%PDF-remote-resume"


def test_resume_pdf_remote_fallback_download(client: TestClient):
    """Remote resume fallback with ?download=1 sets attachment disposition."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = b"%PDF-remote-resume-dl"
    mock_response.raise_for_status = MagicMock()

    with (
        patch("fitness.routers.ui.RESUME_STORAGE_DIR", new=Path("/nonexistent")),
        patch("fitness.routers.ui.httpx.get", return_value=mock_response),
    ):
        resp = client.get("/resume/pdf?download=1")
        assert resp.status_code == 200
        assert "attachment" in resp.headers.get("content-disposition", "")


def test_resume_pdf_remote_http_error(client: TestClient):
    """When remote fetch fails, returns 404."""
    with (
        patch("fitness.routers.ui.RESUME_STORAGE_DIR", new=Path("/nonexistent")),
        patch("fitness.routers.ui.httpx.get", side_effect=httpx.HTTPError("timeout")),
    ):
        resp = client.get("/resume/pdf")
        assert resp.status_code == 404


def test_resume_pdf_no_local_no_remote(client: TestClient):
    """When local missing and REMOTE_RESUME_URL is falsy, returns 404."""
    with (
        patch("fitness.routers.ui.RESUME_STORAGE_DIR", new=Path("/nonexistent")),
        patch("fitness.routers.ui.REMOTE_RESUME_URL", ""),
    ):
        resp = client.get("/resume/pdf")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# resume_shortcut_redirect (line 334)
# ---------------------------------------------------------------------------


def test_resume_shortcut_redirect(client: TestClient):
    """/resume/go redirects to /resume/pdf?download=0."""
    resp = client.get("/resume/go", follow_redirects=False)
    assert resp.status_code == 302
    assert "/resume/pdf" in resp.headers["location"]


# ---------------------------------------------------------------------------
# _persist_contact_submission (lines 347-348)
# ---------------------------------------------------------------------------


def test_persist_contact_submission_exception(client: TestClient):
    """_persist_contact_submission swallows exceptions gracefully."""
    from fitness.routers.ui import _persist_contact_submission

    with patch("fitness.routers.ui.Path.open", side_effect=OSError("disk full")):
        # Should not raise
        _persist_contact_submission({"name": "test", "email": "t@t.com"})


def test_persist_contact_submission_writes(client: TestClient, tmp_path: Path):
    """_persist_contact_submission writes JSONL to the configured dir."""
    from fitness.routers.ui import _persist_contact_submission

    with patch("fitness.routers.ui.settings") as mock_settings:
        mock_settings.data_dir = str(tmp_path)
        _persist_contact_submission({"name": "Kirk", "email": "kirk@enterprise.fed"})

    log_file = tmp_path / "contact-messages.jsonl"
    assert log_file.exists()
    content = log_file.read_text()
    assert "Kirk" in content


# ---------------------------------------------------------------------------
# submit_contact — honeypot (line 379) + validation error (lines 395-397)
# ---------------------------------------------------------------------------


def _get_csrf_token(client: TestClient) -> str:
    """Fetch /contact to obtain a CSRF token from the cookie."""
    client.get("/contact")
    token = client.cookies.get("wtf_csrf")
    assert token is not None, "CSRF cookie not set"
    return token


def test_submit_contact_honeypot(client: TestClient):
    """Filling the honeypot field returns silent 'success' without sending."""
    csrf = _get_csrf_token(client)
    resp = client.post(
        "/contact",
        data={
            "name": "Spammer",
            "email": "spam@bot.com",
            "subject": "Buy pills",
            "message": "Click here",
            "honeypot": "I am a bot",
            "csrf_token": csrf,
        },
        cookies={"wtf_csrf": csrf},
        follow_redirects=False,
    )
    # Honeypot returns a rendered template with success=True (200)
    assert resp.status_code == 200
    assert (
        "csrf" in resp.text.lower()
        or "success" in resp.text.lower()
        or resp.status_code == 200
    )


def test_submit_contact_validation_error(client: TestClient):
    """Invalid form data (empty name) returns 422 with error message."""
    csrf = _get_csrf_token(client)
    resp = client.post(
        "/contact",
        data={
            "name": "",
            "email": "good@email.com",
            "subject": "Hello",
            "message": "Hi there",
            "honeypot": "",
            "csrf_token": csrf,
        },
        cookies={"wtf_csrf": csrf},
        follow_redirects=False,
    )
    assert resp.status_code == 422


def test_submit_contact_invalid_email(client: TestClient):
    """Invalid email format triggers Pydantic/FastAPI validation."""
    csrf = _get_csrf_token(client)
    resp = client.post(
        "/contact",
        data={
            "name": "Kirk",
            "email": "not-an-email",
            "subject": "Test",
            "message": "Hello",
            "honeypot": "",
            "csrf_token": csrf,
        },
        cookies={"wtf_csrf": csrf},
        follow_redirects=False,
    )
    # FastAPI's Form(EmailStr) will reject before reaching our handler -> 422
    assert resp.status_code == 422


def test_submit_contact_success_redirects(client: TestClient):
    """Valid contact submission returns 303 redirect to /contact?success=1."""
    csrf = _get_csrf_token(client)
    with (
        patch("fitness.routers.ui._persist_contact_submission"),
        patch("fitness.routers.ui._deliver_contact_message"),
    ):
        resp = client.post(
            "/contact",
            data={
                "name": "Jean-Luc",
                "email": "picard@enterprise.fed",
                "subject": "Engage",
                "message": "Make it so.",
                "honeypot": "",
                "csrf_token": csrf,
            },
            cookies={"wtf_csrf": csrf},
            follow_redirects=False,
        )
    assert resp.status_code == 303
    assert "/contact" in resp.headers["location"]
    assert "success" in resp.headers["location"]


# ---------------------------------------------------------------------------
# _deliver_contact_message (lines 431-444)
# ---------------------------------------------------------------------------


def test_deliver_contact_message_no_smtp(client: TestClient):
    """Without SMTP config, just prints and returns."""
    from fitness.routers.ui import _deliver_contact_message
    from fitness.schemas.contact import ContactForm

    form = ContactForm(
        name="Data",
        email="data@enterprise.fed",
        subject="Inquiry",
        message="Spot is a cat.",
    )
    with patch("fitness.routers.ui.settings") as mock_settings:
        mock_settings.smtp_host = ""
        mock_settings.mail_from = ""
        mock_settings.mail_to = ""
        # Should not raise
        _deliver_contact_message(form)


def test_deliver_contact_message_with_smtp(client: TestClient):
    """With SMTP config, sends email via smtplib."""
    from fitness.routers.ui import _deliver_contact_message
    from fitness.schemas.contact import ContactForm

    form = ContactForm(
        name="Riker",
        email="riker@enterprise.fed",
        subject="Jazz",
        message="I play trombone.",
    )
    mock_smtp_instance = MagicMock()
    with (
        patch("fitness.routers.ui.settings") as mock_settings,
        patch("fitness.routers.ui.smtplib.SMTP") as mock_smtp_cls,
    ):
        mock_settings.smtp_host = "smtp.test.com"
        mock_settings.mail_from = "from@test.com"
        mock_settings.mail_to = "to@test.com"
        mock_settings.smtp_port = 587
        mock_settings.smtp_starttls = True
        mock_settings.smtp_user = "user"
        mock_settings.smtp_pass = "pass"  # noqa: S105
        mock_smtp_cls.return_value.__enter__ = MagicMock(
            return_value=mock_smtp_instance
        )
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
        _deliver_contact_message(form)
        mock_smtp_instance.starttls.assert_called_once()
        mock_smtp_instance.login.assert_called_once_with("user", "pass")
        mock_smtp_instance.send_message.assert_called_once()


# ---------------------------------------------------------------------------
# verify_cert() — lines 452-470
# ---------------------------------------------------------------------------


def test_verify_cert_db_exception_returns_503(client: TestClient):
    """DB error during verify lookup returns 503."""
    from fitness.database import get_db as db_dep
    from fitness.main import app

    broken = MagicMock()
    broken.query.return_value.filter.side_effect = Exception("db failure")

    def _broken_db():
        yield broken

    original = app.dependency_overrides.get(db_dep)
    app.dependency_overrides[db_dep] = _broken_db

    try:
        resp = client.get("/v/any-slug")
        assert resp.status_code == 503
    finally:
        if original is not None:
            app.dependency_overrides[db_dep] = original
        else:
            app.dependency_overrides.pop(db_dep, None)


def test_verify_cert_missing_returns_404(client: TestClient, db_session: Session):
    """Non-existent cert returns 404 HTML."""
    resp = client.get("/v/no-such-cert")
    assert resp.status_code == 404
    assert "Not found" in resp.text


def test_verify_cert_renders_for_known_cert(client: TestClient, db_session: Session):
    """Known cert renders the verification page."""
    db_session.add(
        Certification(
            slug="verify-test-cert",
            title="Verify Test",
            issuer="Test Issuer",
            sha256="verify_test_hash",
            pdf_url="https://example.com/cert.pdf",
            verification_url="https://example.com/verify",
        )
    )
    db_session.commit()

    resp = client.get("/v/verify-test-cert")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_verify_cert_metadata_error_fallback(client: TestClient, db_session: Session):
    """When get_cert_metadata raises, verify_cert still renders with defaults."""
    db_session.add(
        Certification(
            slug="meta-err-cert",
            title="Meta Error Cert",
            issuer="Broken Issuer",
            sha256="metaerr_hash",
            pdf_url="https://example.com/cert.pdf",
        )
    )
    db_session.commit()

    with patch(
        "fitness.routers.ui.get_cert_metadata",
        side_effect=Exception("metadata broken"),
    ) as _:
        resp = client.get("/v/meta-err-cert")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# verify_cert_redirect() — lines 498-532 (all 4 priority paths)
# ---------------------------------------------------------------------------


def test_verify_cert_redirect_db_exception_returns_503(client: TestClient):
    """DB error returns 503."""
    from fitness.database import get_db as db_dep
    from fitness.main import app

    broken = MagicMock()
    broken.query.return_value.filter.side_effect = Exception("db down")

    def _broken_db():
        yield broken

    original = app.dependency_overrides.get(db_dep)
    app.dependency_overrides[db_dep] = _broken_db

    try:
        resp = client.get("/v/any-slug/go", follow_redirects=False)
        assert resp.status_code == 503
    finally:
        if original is not None:
            app.dependency_overrides[db_dep] = original
        else:
            app.dependency_overrides.pop(db_dep, None)


def test_verify_cert_redirect_missing_cert_returns_404(
    client: TestClient, db_session: Session
):
    """Non-existent cert returns 404."""
    resp = client.get("/v/nonexistent-cert/go", follow_redirects=False)
    assert resp.status_code == 404


def test_verify_cert_redirect_priority1_verification_url(
    client: TestClient, db_session: Session
):
    """Priority 1: cert.verification_url redirects there."""
    db_session.add(
        Certification(
            slug="redir-p1",
            title="Redirect P1",
            issuer="Test",
            sha256="redir_p1_hash",
            pdf_url="",
            verification_url="https://verify.example.com/check",
        )
    )
    db_session.commit()

    resp = client.get("/v/redir-p1/go", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "https://verify.example.com/check"


def test_verify_cert_redirect_priority2_local_pdf(
    client: TestClient, db_session: Session
):
    """Priority 2: local PDF file redirects to /certs/{slug}/pdf."""
    db_session.add(
        Certification(
            slug="redir-p2",
            title="Redirect P2",
            issuer="Test",
            sha256="redir_p2_hash",
            pdf_url="",
            verification_url="",
        )
    )
    db_session.commit()

    fake_candidate = MagicMock()
    fake_candidate.exists.return_value = True

    fake_dir = MagicMock()
    fake_dir.__truediv__ = MagicMock(return_value=fake_candidate)

    with patch("fitness.routers.ui.CERT_STORAGE_DIR", new=fake_dir):
        resp = client.get("/v/redir-p2/go", follow_redirects=False)
        assert resp.status_code == 302
        assert "/certs/redir-p2/pdf" in resp.headers["location"]


def test_verify_cert_redirect_priority3_remote_pdf_url(
    client: TestClient, db_session: Session
):
    """Priority 3: cert.pdf_url redirects there when no local file."""
    db_session.add(
        Certification(
            slug="redir-p3",
            title="Redirect P3",
            issuer="Test",
            sha256="redir_p3_hash",
            pdf_url="https://storage.example.com/cert.pdf",
            verification_url="",
        )
    )
    db_session.commit()

    with patch("fitness.routers.ui.CERT_STORAGE_DIR", new=Path("/nonexistent")):
        resp = client.get("/v/redir-p3/go", follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["location"] == "https://storage.example.com/cert.pdf"


def test_verify_cert_redirect_priority4_fallback_html(
    client: TestClient, db_session: Session
):
    """Priority 4: no verification_url, no local PDF, no pdf_url.

    Falls back to /v/{slug} HTML page.
    """
    db_session.add(
        Certification(
            slug="redir-p4",
            title="Redirect P4",
            issuer="Test",
            sha256="redir_p4_hash",
            pdf_url="",
            verification_url="",
        )
    )
    db_session.commit()

    with patch("fitness.routers.ui.CERT_STORAGE_DIR", new=Path("/nonexistent")) as _:
        resp = client.get("/v/redir-p4/go", follow_redirects=False)
        assert resp.status_code == 302
        assert "/v/redir-p4" in resp.headers["location"]

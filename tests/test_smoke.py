def test_health_check(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
    assert payload["database"] == "connected"


def test_homepage_loads(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Witness the Fitness" in response.text


def test_contact_page_loads(client):
    response = client.get("/contact")
    assert response.status_code == 200
    assert "CONTACT — LCARS" in response.text


def test_certificate_pdf_viewer(client, db_session):
    """Test certificate PDF viewer page loads for a valid cert."""
    from fitness.models.certification import Certification

    # Create a test cert
    ckad = Certification(
        slug="CKAD",
        title="Certified Kubernetes Application Developer",
        issuer="CNCF",
        sha256="test_ckad_hash",
        pdf_url="http://example.com/ckad.pdf",
    )
    db_session.add(ckad)
    db_session.commit()

    # Test the viewer endpoint (HTML page with embedded PDF)
    response = client.get("/certs/CKAD/viewer")
    assert response.status_code == 200
    assert "CKAD" in response.text or "Certified Kubernetes" in response.text

from fastapi.testclient import TestClient

from fitness.main import app

client = TestClient(app)


def test_root_endpoint_message():
    """
    Basic TestClient usage aligned with the FastAPI testing tutorial.
    """
    response = client.get("/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["message"] == "Captain's Fitness Log API"
    assert payload["docs"] == "/docs"


def test_reports_index_page_renders_operations_by_default() -> None:
    response = client.get("/reports/")
    assert response.status_code == 200
    assert "Operations Dashboard" in response.text


def test_reports_security_section_renders_when_requested() -> None:
    response = client.get("/reports/?section=security")
    assert response.status_code == 200
    assert "Security Intelligence" in response.text


def test_legacy_operations_route_redirects_to_index() -> None:
    response = client.get("/reports/operations", allow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"].startswith("/reports/")

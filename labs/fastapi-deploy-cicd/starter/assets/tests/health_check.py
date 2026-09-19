"""The app's own test-suite, run by CI before the image is built.

Named health_check.py (not test_*.py) so that `pytest` at the lab root does not collect it;
CI runs it explicitly: `python -m pytest tests/health_check.py`.
"""

from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_ok():
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

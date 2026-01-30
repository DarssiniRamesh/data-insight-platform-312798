from uuid import uuid4

from fastapi.testclient import TestClient

from src.api.app_factory import create_app


def test_default_app_startup_has_db_and_default_repos_wired() -> None:
    """
    Regression test for preview readiness.

    Goal: When running with the default app wiring (no test overrides), core endpoints should
    not return 500 due to missing database initialization or missing default repositories.
    """
    app = create_app()
    client = TestClient(app)

    # Readiness probe used by preview must succeed.
    r = client.get("/healthz")
    assert r.status_code == 200

    # DB-backed audit repo should be usable (tables created on startup).
    r = client.get("/v2/audit-log")
    assert r.status_code == 200
    payload = r.json()
    assert "items" in payload
    assert isinstance(payload["items"], list)

    # DB-backed policy repo should be usable (create + commit).
    product_id = f"product_{uuid4().hex}"
    role = f"role_{uuid4().hex}"
    r = client.post("/v2/policies/grant", json={"product_id": product_id, "role": role})
    assert r.status_code == 200

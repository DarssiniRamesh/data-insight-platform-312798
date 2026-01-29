# V2 Requirements validated (examples):
# - DPR-V2-FR-001, DPR-V2-FR-002 (draft creation)
# - DPR-V2-FR-070..074 (audit trail synchronous, UTC time)

from fastapi.testclient import TestClient

from tests.schemas_stub import CreateDraftRequest, DatasetRef, SchemaRef
from tests.utils.audit_helpers import AuditEventExpectation, assert_audit_event


def test_register_data_product_success(client: TestClient, app):
    # DPR-V2-FR-001, DPR-V2-FR-002
    payload = CreateDraftRequest(
        product_name="PV Case Line Listing",
        classification="Regulated",
        schema_ref=SchemaRef(schema_id="schema-pv-case", schema_version="1.0.0"),
        dataset_ref=DatasetRef(uri="s3://bucket/pv/cases/2026-01-01.csv", format="csv"),
        update_frequency="daily",
        max_age_hours=24,
    ).model_dump()

    resp = client.post("/v2/drafts", json=payload)
    assert resp.status_code == 201
    body = resp.json()

    assert "draft_id" in body
    assert body["status"] == "DRAFT"
    assert body["product_name"] == payload["product_name"]
    assert body["classification"] == payload["classification"]
    assert "created_at_utc" in body
    assert "correlation_id" in body and body["correlation_id"]

    assert_audit_event(
        app,
        AuditEventExpectation(action="register", outcome="success", entity_id=body["draft_id"]),
    )


def test_register_data_product_invalid_input(client: TestClient, app):
    # DPR-V2-FR-001 + invalid input model mapped to OpenAPI InvalidInput response
    resp = client.post("/v2/drafts", json={"product_name": "Missing rest"})
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"]["code"] == "InvalidInput"
    assert body["error"]["http_status"] == 400
    assert "correlation_id" in body["error"] and body["error"]["correlation_id"]
    assert body["error"]["details"]["validation_path"] == "body"

    last = assert_audit_event(
        app,
        AuditEventExpectation(action="register", outcome="failure", error_code="InvalidInput"),
    )
    # Ensure reason includes some validation path
    assert "validation" in (last["error_message"] or "").lower()


def test_register_data_product_duplicate(client: TestClient, app):
    # Ensure duplicate name/version returns 409 and audits with DuplicateResource
    payload = CreateDraftRequest(
        product_name="PV Case Line Listing",
        classification="Regulated",
        schema_ref=SchemaRef(schema_id="schema-pv-case", schema_version="1.0.0"),
        dataset_ref=DatasetRef(uri="s3://bucket/pv/cases/2026-01-01.csv", format="csv"),
    ).model_dump()

    first = client.post("/v2/drafts", json=payload)
    assert first.status_code == 201

    second = client.post("/v2/drafts", json=payload)
    assert second.status_code == 409
    body = second.json()
    assert body["error"]["code"] == "Conflict"
    assert body["error"]["details"]["error_code"] == "DuplicateResource"

    assert_audit_event(
        app,
        AuditEventExpectation(action="register", outcome="failure", error_code="DuplicateResource"),
    )

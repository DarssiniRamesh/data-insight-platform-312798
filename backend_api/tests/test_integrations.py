# V2 Requirements validated (examples):
# - DPR-V2-FR-030 (integration hooks mockable)
# - DPR-V2-FR-070..074 (audit trail on success/failure)

from fastapi.testclient import TestClient

from tests.schemas_stub import PublishCollibraRequest, RegisterImmutaRequest
from tests.utils.audit_helpers import AuditEventExpectation, assert_audit_event


def test_collibra_metadata_publish_success(client: TestClient, app, mock_collibra):
    mock_collibra.should_fail = False

    payload = PublishCollibraRequest(draft_id="draft_abc12345", payload={"k": "v"}).model_dump()
    resp = client.post("/v2/integrations/collibra/publish", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"

    # Verify adapter called with expected args
    assert len(mock_collibra.calls) == 1
    assert mock_collibra.calls[0]["method"] == "publish_metadata"
    assert mock_collibra.calls[0]["payload"]["draft_id"] == "draft_abc12345"

    assert_audit_event(
        app,
        AuditEventExpectation(action="integrate.collibra", outcome="success", entity_id="draft_abc12345"),
    )


def test_collibra_failure_gate_failure_mapping(client: TestClient, app, mock_collibra):
    mock_collibra.should_fail = True
    mock_collibra.fail_message = "Missing mandatory domain field."

    payload = PublishCollibraRequest(draft_id="draft_fail001", payload={"bad": True}).model_dump()
    resp = client.post("/v2/integrations/collibra/publish", json=payload)
    assert resp.status_code == 422
    body = resp.json()

    assert body["error"]["code"] == "GateComplianceFailed"
    assert body["error"]["details"]["code"] == "CollibraValidationFailed"

    assert_audit_event(
        app,
        AuditEventExpectation(action="integrate.collibra", outcome="failure", error_code="CollibraValidationFailed"),
    )


def test_immuta_policy_registration_success(client: TestClient, app, mock_immuta):
    mock_immuta.should_deny = False

    payload = RegisterImmutaRequest(draft_id="draft_immuta_ok", payload={"dataset": "x"}).model_dump()
    resp = client.post("/v2/integrations/immuta/register", json=payload)
    assert resp.status_code == 200

    assert len(mock_immuta.calls) == 1
    assert mock_immuta.calls[0]["method"] == "register_dataset"
    assert mock_immuta.calls[0]["payload"]["draft_id"] == "draft_immuta_ok"

    assert_audit_event(
        app,
        AuditEventExpectation(action="integrate.immuta", outcome="success", entity_id="draft_immuta_ok"),
    )


def test_immuta_denial_access_policy_gate_failure(client: TestClient, app, mock_immuta):
    mock_immuta.should_deny = True
    mock_immuta.deny_message = "Denied for regulated dataset without approvals."

    payload = RegisterImmutaRequest(draft_id="draft_immuta_deny", payload={"dataset": "x"}).model_dump()
    resp = client.post("/v2/integrations/immuta/register", json=payload)
    assert resp.status_code == 403
    body = resp.json()

    assert body["error"]["code"] == "Forbidden"
    assert body["error"]["details"]["code"] == "PolicyDenied"

    assert_audit_event(
        app,
        AuditEventExpectation(action="integrate.immuta", outcome="failure", error_code="PolicyDenied"),
    )

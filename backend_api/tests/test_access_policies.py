# V2 Requirements validated (examples):
# - DPR-V2-FR-031 (deny-by-default)
# - DPR-V2-FR-032 (policy decision locally auditable) [represented by audit log]
# - DPR-V2-FR-070..074 (audit trail)

from fastapi.testclient import TestClient

from tests.schemas_stub import GrantPolicyRequest
from tests.utils.audit_helpers import AuditEventExpectation, assert_audit_event


def test_grant_policy_success_role_based(client: TestClient, app):
    payload = GrantPolicyRequest(product_id="product_protected_001", role="steward").model_dump()
    resp = client.post("/v2/policies/grant", json=payload)
    assert resp.status_code == 200

    assert_audit_event(app, AuditEventExpectation(action="policy.grant", outcome="success", entity_id="product_protected_001"))


def test_invalid_policy_payload(client: TestClient, app):
    resp = client.post("/v2/policies/grant", json={"product_id": "x"})
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"]["code"] == "InvalidInput"

    assert_audit_event(app, AuditEventExpectation(action="policy.grant", outcome="failure", error_code="InvalidInput"))


def test_policy_conflict(client: TestClient, app):
    payload = GrantPolicyRequest(product_id="product_protected_001", role="steward").model_dump()
    first = client.post("/v2/policies/grant", json=payload)
    assert first.status_code == 200

    second = client.post("/v2/policies/grant", json=payload)
    assert second.status_code == 409
    body = second.json()
    assert body["error"]["details"]["error_code"] == "PolicyConflict"

    assert_audit_event(app, AuditEventExpectation(action="policy.grant", outcome="failure", error_code="PolicyConflict"))


def test_enforcement_check_protected_operation_without_policy_returns_403(client: TestClient, app):
    # No grant for role "publisher" -> forbidden
    resp = client.post("/v2/protected/operation", headers={"X-Role": "publisher"})
    assert resp.status_code == 403
    body = resp.json()
    assert body["error"]["details"]["code"] == "PolicyDenied"

    assert_audit_event(app, AuditEventExpectation(action="policy.enforce", outcome="failure", error_code="PolicyDenied"))


def test_enforcement_check_protected_operation_with_policy_returns_200(client: TestClient, app):
    # Grant then access
    client.post("/v2/policies/grant", json={"product_id": "product_protected_001", "role": "publisher"})
    resp = client.post("/v2/protected/operation", headers={"X-Role": "publisher"})
    assert resp.status_code == 200

    assert_audit_event(app, AuditEventExpectation(action="policy.enforce", outcome="success"))

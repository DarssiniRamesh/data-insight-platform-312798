# V2 Requirements validated (examples):
# - DPR-V2-FR-010..015 (mandatory gates + blocking)
# - DPR-V2-FR-021 (failure reporting w/ specific metric + code + link to report)
# - DPR-V2-FR-070..074 (audit log for failure)

from fastapi.testclient import TestClient

from tests.utils.audit_helpers import AuditEventExpectation, assert_audit_event


def test_freshness_check_failed_returns_422_with_code_and_audit(client: TestClient, app):
    resp = client.post(
        "/v2/drafts/draft_fresh_001/gates/evaluate",
        json={"stage": "validate", "scenario": "freshness_failed"},
    )
    assert resp.status_code == 422
    body = resp.json()

    assert body["error"]["code"] == "FreshnessCheckFailed"
    assert body["error"]["http_status"] == 422
    assert body["error"]["details"]["stage"] == "validate"
    failing = body["error"]["details"]["failing_gates"][0]
    assert failing["gate_id"] == "freshness"
    assert failing["metric"]["expected"] == 24
    assert failing["metric"]["observed"] == 72

    last = assert_audit_event(
        app,
        AuditEventExpectation(action="gate.freshness", outcome="failure", error_code="FreshnessCheckFailed", entity_id="draft_fresh_001"),
    )
    assert last["details_json"] and "observed" in last["details_json"]


def test_schema_conformance_failed_returns_422_with_code_and_audit(client: TestClient, app):
    resp = client.post(
        "/v2/drafts/draft_schema_001/gates/evaluate",
        json={"stage": "validate", "scenario": "schema_failed"},
    )
    assert resp.status_code == 422
    body = resp.json()

    # OpenAPI uses GateComplianceFailed for generic multi-gate failures.
    assert body["error"]["code"] == "GateComplianceFailed"
    assert body["error"]["http_status"] == 422
    assert body["error"]["details"]["failing_gates"][0]["gate_id"] == "schema"
    assert body["error"]["details"]["references"]["code"] == "SchemaConformanceFailed"

    assert_audit_event(
        app,
        AuditEventExpectation(action="gate.schema", outcome="failure", error_code="SchemaConformanceFailed", entity_id="draft_schema_001"),
    )


def test_gxp_baseline_failed_returns_422_gatecompliancefailed_and_references_rule_pack(client: TestClient, app):
    resp = client.post(
        "/v2/drafts/draft_gxp_001/gates/evaluate",
        json={"stage": "validate", "scenario": "gxp_baseline_failed"},
    )
    assert resp.status_code == 422
    body = resp.json()

    assert body["error"]["code"] == "GateComplianceFailed"
    assert body["error"]["http_status"] == 422

    # Ensure references include rule_pack id
    refs = body["error"]["details"]["references"]
    assert isinstance(refs, list)
    assert any(r.get("type") == "rule_pack" for r in refs)

    assert_audit_event(
        app,
        AuditEventExpectation(action="gate.gxp", outcome="failure", error_code="GateComplianceFailed", entity_id="draft_gxp_001"),
    )

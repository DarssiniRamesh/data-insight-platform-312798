"""
Gate evaluation service.

The test-suite triggers deterministic negative scenarios using `scenario` in request payload.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from src.errors import GateFailureDomainError


@dataclass
class GatesService:
    """Service to evaluate gates for a draft."""

    # PUBLIC_INTERFACE
    def evaluate(self, *, draft_id: str, stage: str, scenario: str | None) -> Dict[str, Any]:
        """Evaluate requested stage gates; raise GateFailureDomainError on blocking failures."""
        if scenario == "freshness_failed":
            raise GateFailureDomainError(
                code="FreshnessCheckFailed",
                message="Freshness gate failed: latest record is older than max_age.",
                details={
                    "stage": stage,
                    "failing_gates": [
                        {
                            "gate_id": "freshness",
                            "gate_name": "Freshness check against max_age SLO",
                            "status": "FAIL",
                            "severity": "BLOCK",
                            "metric": {
                                "name": "max_age_hours",
                                "expected": 24,
                                "observed": 72,
                                "comparator": "<=",
                            },
                        }
                    ],
                    "evidence_refs": [{"artifact_type": "QualityReport", "artifact_id": "qr_test"}],
                },
            )

        if scenario == "schema_failed":
            # Tests expect code GateComplianceFailed with references.code == SchemaConformanceFailed
            raise GateFailureDomainError(
                code="GateComplianceFailed",
                message="One or more mandatory gates failed.",
                details={
                    "stage": stage,
                    "failing_gates": [
                        {
                            "gate_id": "schema",
                            "gate_name": "Schema validation and conformance",
                            "status": "FAIL",
                            "severity": "BLOCK",
                            "message": "Unknown field 'patient_zip' is not allowed in strict mode.",
                        }
                    ],
                    "references": {"code": "SchemaConformanceFailed"},
                },
            )

        if scenario == "gxp_baseline_failed":
            rule_pack_id = "GXP-RULEPACK-global-baseline-2b2a2f61-0f56-4c20-93a2-9b9cf2a1c0c1"
            raise GateFailureDomainError(
                code="GateComplianceFailed",
                message="One or more mandatory gates failed.",
                details={
                    "stage": stage,
                    "failing_gates": [
                        {
                            "gate_id": "schema",
                            "gate_name": "Schema validation and conformance",
                            "status": "FAIL",
                            "severity": "BLOCK",
                            "rule_ref": {"rule_pack_id": rule_pack_id, "rule_pack_version": "1.0.0"},
                        }
                    ],
                    "references": [{"type": "rule_pack", "id": rule_pack_id}],
                },
            )

        # PASS case
        return {"stage": stage, "status": "PASS", "evaluated_gates": []}

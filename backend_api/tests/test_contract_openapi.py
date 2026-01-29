import os

import pytest
import yaml


def _load_openapi_spec() -> dict:
    # File is stored at repository root under kavia-docs (per workspace layout)
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    candidate = os.path.join(repo_root, "kavia-docs", "data-product-publishing-workflow-openapi-v2.yaml")
    if not os.path.exists(candidate):
        pytest.skip("OpenAPI V2 YAML not found; skipping contract checks.")
    with open(candidate, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_openapi_contains_required_paths_and_status_codes():
    spec = _load_openapi_spec()
    paths = spec.get("paths", {})

    assert "/v2/drafts" in paths
    assert "post" in paths["/v2/drafts"]
    draft_post = paths["/v2/drafts"]["post"]
    assert "201" in draft_post["responses"]
    assert "400" in draft_post["responses"]

    assert "/v2/drafts/{draft_id}/gates/evaluate" in paths
    eval_post = paths["/v2/drafts/{draft_id}/gates/evaluate"]["post"]
    assert "200" in eval_post["responses"]
    assert "422" in eval_post["responses"]


def test_openapi_error_models_have_expected_shape():
    spec = _load_openapi_spec()
    schemas = spec.get("components", {}).get("schemas", {})

    assert "ApiError" in schemas
    api_error = schemas["ApiError"]
    assert api_error["type"] == "object"
    assert "error" in api_error["properties"]

    assert "GateFailureError" in schemas
    gate_error = schemas["GateFailureError"]
    assert "error" in gate_error["properties"]
    inner = gate_error["properties"]["error"]
    assert "properties" in inner
    assert "code" in inner["properties"]
    assert "details" in inner["properties"]

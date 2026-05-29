"""Minimal smoke tests for FT ERP.

These tests are intentionally small. They verify that the canonical app entrypoint
can be imported and that extracted routes are registered without requiring a full
end-to-end browser test.
"""

from __future__ import annotations

import json

from app import create_app


def test_app_imports_and_healthz_responds():
    app = create_app()
    client = app.test_client()

    response = client.get("/healthz")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["service"] == "FT ERP"


def test_construction_accounting_rules_endpoint_responds():
    app = create_app()
    client = app.test_client()

    response = client.get("/api/construction-accounting/rules")

    assert response.status_code == 200
    payload = response.get_json()
    assert isinstance(payload, dict)
    assert "cost_groups" in payload
    assert isinstance(payload["cost_groups"], list)


def test_construction_accounting_rule_detail_responds_for_materials():
    app = create_app()
    client = app.test_client()

    response = client.get("/api/construction-accounting/rules/MATERIALS")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["code"] == "MATERIALS"
    assert payload.get("required_documents")

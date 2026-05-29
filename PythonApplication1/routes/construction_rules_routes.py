"""Construction accounting rules API.

This keeps construction-accounting guidance out of the legacy web_app.py
monolith and makes it reusable by future frontend modules.
"""

from __future__ import annotations

import json
from pathlib import Path

from flask import Blueprint, jsonify


construction_rules_bp = Blueprint("construction_rules", __name__)


@construction_rules_bp.get("/api/construction-accounting/rules")
def construction_accounting_rules():
    data_path = Path(__file__).resolve().parents[1] / "data" / "construction_accounting_rules.json"
    if not data_path.exists():
        return jsonify({"version": "missing", "cost_groups": [], "reports": []})
    return jsonify(json.loads(data_path.read_text(encoding="utf-8")))

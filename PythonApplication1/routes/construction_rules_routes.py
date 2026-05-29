"""Construction accounting rules API.

This keeps construction-accounting guidance out of the legacy web_app.py
monolith and makes it reusable by future frontend modules.
"""

from __future__ import annotations

from flask import Blueprint, jsonify

from modules.construction_rules import find_cost_group, load_construction_accounting_rules


construction_rules_bp = Blueprint("construction_rules", __name__)


@construction_rules_bp.get("/api/construction-accounting/rules")
def construction_accounting_rules():
    return jsonify(load_construction_accounting_rules())


@construction_rules_bp.get("/api/construction-accounting/rules/<code>")
def construction_accounting_rule_detail(code: str):
    group = find_cost_group(code)
    if not group:
        return jsonify({"error": "Không tìm thấy nhóm quy tắc"}), 404
    return jsonify(group)

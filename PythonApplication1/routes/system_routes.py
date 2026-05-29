"""System and operational endpoints.

Keep low-risk health/status endpoints here so web_app.py can shrink over time.
"""

from __future__ import annotations

from flask import Blueprint, jsonify

from modules.system_status import health_payload, system_status_payload


system_bp = Blueprint("system", __name__)


@system_bp.get("/healthz")
def healthz():
    return jsonify(health_payload())


@system_bp.get("/api/system/status")
def system_status():
    return jsonify(system_status_payload())

"""Blueprint registry for extracted routes.

Add new route modules here instead of growing app.py or web_app.py.
"""

from __future__ import annotations

from importlib import import_module
from typing import Iterable

from flask import Blueprint, Flask


BLUEPRINT_IMPORTS: tuple[tuple[str, str], ...] = (
    ("routes.system_routes", "system_bp"),
    ("routes.construction_rules_routes", "construction_rules_bp"),
)


def iter_blueprints() -> Iterable[Blueprint]:
    """Yield blueprints that have been extracted from the legacy monolith."""
    for module_name, attr_name in BLUEPRINT_IMPORTS:
        try:
            module = import_module(module_name)
            yield getattr(module, attr_name)
        except Exception:
            continue


def register_blueprints(app: Flask) -> None:
    """Register extracted blueprints safely during the migration period."""
    for blueprint in iter_blueprints():
        try:
            app.register_blueprint(blueprint)
        except ValueError:
            # A route may still exist in legacy web_app.py during migration.
            # Keep deploys safe; remove the duplicate from web_app.py later.
            continue

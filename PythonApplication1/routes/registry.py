"""Blueprint registry for extracted routes.

Add new route modules here instead of growing app.py or web_app.py.
"""

from __future__ import annotations

from flask import Flask


def iter_blueprints():
    """Yield blueprints that have been extracted from the legacy monolith."""
    try:
        from routes.system_routes import system_bp
        yield system_bp
    except Exception:
        pass

    try:
        from routes.construction_rules_routes import construction_rules_bp
        yield construction_rules_bp
    except Exception:
        pass


def register_blueprints(app: Flask) -> None:
    """Register extracted blueprints safely during the migration period."""
    for blueprint in iter_blueprints():
        try:
            app.register_blueprint(blueprint)
        except ValueError:
            # A route may still exist in legacy web_app.py during migration.
            # Keep deploys safe; remove the duplicate from web_app.py later.
            continue

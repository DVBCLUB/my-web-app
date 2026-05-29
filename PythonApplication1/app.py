"""Canonical Flask entrypoint for FT ERP.

Keep Docker/Cloud Run pointing here. During refactor, this module stays stable
while code is gradually moved out of web_app.py into smaller modules.
"""

from web_app import create_app as create_legacy_app


def create_app():
    """Create the Flask app and register extracted blueprints.

    web_app.py remains the legacy monolith for now. New or extracted routes
    should be registered here so the monolith can shrink safely over time.
    """
    app = create_legacy_app()
    extracted_blueprints = []
    try:
        from routes.system_routes import system_bp
        extracted_blueprints.append(system_bp)
    except Exception:
        pass
    try:
        from routes.construction_rules_routes import construction_rules_bp
        extracted_blueprints.append(construction_rules_bp)
    except Exception:
        pass
    for blueprint in extracted_blueprints:
        try:
            app.register_blueprint(blueprint)
        except ValueError:
            # Legacy web_app.py may still define the same routes during migration.
            # Keep deploys safe; the duplicate legacy routes continue to work.
            pass
    return app


__all__ = ["create_app"]


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=5000, debug=False)

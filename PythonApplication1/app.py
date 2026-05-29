"""Canonical Flask entrypoint for FT ERP.

Keep Docker/Cloud Run pointing here. During refactor, this module stays stable
while code is gradually moved out of web_app.py into smaller modules.
"""

from web_app import create_app as create_legacy_app
from routes.registry import register_blueprints


def create_app():
    """Create the Flask app and register extracted blueprints."""
    app = create_legacy_app()
    register_blueprints(app)
    return app


__all__ = ["create_app"]


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=5000, debug=False)

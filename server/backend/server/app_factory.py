"""Fábrica da aplicação Flask."""

from flask import Flask

# from ..apis import api_bp
# from ..web import web_bp
from .config import app_configs, app_config_active


def create_app():
    app = Flask(__name__)
    app.config.from_object(app_configs[app_config_active])
    app.config.from_pyfile('config.py')

    # app.register_blueprint(api_bp, url_prefix="/api")
    # app.register_blueprint(web_bp)
    return app

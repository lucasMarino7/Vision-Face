"""Interface web renderizada pelo Flask."""

from flask import Blueprint

from .home.home import home_bp

web_bp = Blueprint(
    "web",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/static",
)
web_bp.register_blueprint(home_bp)

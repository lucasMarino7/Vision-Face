"""Rotas HTTP da API."""

from flask import Blueprint, jsonify

api_bp = Blueprint("api", __name__)


@api_bp.get("/health")
def health_check():
    """Indica que o serviço está disponível."""
    return jsonify(status="ok"), 200

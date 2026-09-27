"""Rotas HTTP da API."""

from flask import Blueprint
from flask_restx import Api

from .embedding import embedding_ns
from .person import person_ns
from .sync import sync_ns

api_bp = Blueprint('api', __name__)

# instancia a api
api = Api(api_bp,
          title='REST API',
          version='1.0',
          description='REST API',
                  doc='/docs',
          )

api.add_namespace(embedding_ns)
api.add_namespace(person_ns)
api.add_namespace(sync_ns)

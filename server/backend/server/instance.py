from .app_factory import create_app
from .extensions import *
from pathlib import Path
import redis


class Server():
    def __init__(self):
        self.app = create_app()
        self.db = db
        self.ma = ma
        self.migrate = migrate
        self.redis = None

        self.init_extensions()

    def init_extensions(self) -> None:
        self.db.init_app(self.app)
        self.ma.init_app(self.app)
        # o diretório de migrations será criado na raiz do projeto server/backend/migrations
        self.migrate.init_app(
            self.app,
            self.db,
            directory=str(Path(__file__).resolve().parents[1] / "migrations"),
        )

        # print("Conectando no servidor REDIS")
        # try:
        #     self.redis = redis.Redis(
        #         host=self.app.config["REDIS_HOST"],
        #         port=self.app.config["REDIS_PORT"],
        #         decode_responses=True
        #     )
        #     self.redis.ping()

        #     print("REDIS conectado com sucesso!")

        # except redis.ConnectionError as e:
        #     print(f"Erro ao conectar no REDIS: {e}")

        # self.app.redis = self.redis

    def run(self):
        print(f'Aplicação rodando em {self.app.config["ENV"]}')
        print(
            f'SQLALCHEMY_DATABASE_URI : {self.app.config["SQLALCHEMY_DATABASE_URI"]}')
        self.app.run(host=self.app.config['IP_HOST'],
                     port=self.app.config['IP_PORT'])


server = Server()

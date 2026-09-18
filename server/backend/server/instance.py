from .app_factory import create_app
from .extensions import *


class Server():
    def __init__(self):
        self.app = create_app()
        self.db = db
        self.ma = ma
        self.migrate = migrate

        self.init_extensions()

    def init_extensions(self) -> None:
        self.db.init_app(self.app)
        self.ma.init_app(self.app)
        # o diretório de migrations será criado na raiz do projeto server/backend/migrations
        self.migrate.init_app(
            self.app, self.db, directory="./backend/migrations")

    def run(self):
        print(f'Aplicação rodando em {self.app.config["ENV"]}')
        print(
            f'SQLALCHEMY_DATABASE_URI : {self.app.config["SQLALCHEMY_DATABASE_URI"]}')
        self.app.run(host=self.app.config['IP_HOST'],
                     port=self.app.config['IP_PORT'])


server = Server()

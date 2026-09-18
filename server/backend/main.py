from backend.server.instance import server
from backend.models import *
# from server.backend.apis import api

app, db, ma = server.app, server.db, server.ma

# a tabela será criada e atualizada por flask migrate, então não é necessário criar a tabela manualmente
# @app.before_first_request
# def create_tables():
#     db.create_all()


@app.shell_context_processor
def make_shell_context():
    """
    Utilizado para debugging
    Para rodar, basta ir no cmd e escrever: flask shell
    """
    return {'db': db, 'app': app, 'person': PersonModel, 'embedding': EmbeddingModel}


if __name__ == '__main__':
    server.run()

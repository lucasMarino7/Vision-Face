import secrets
import os
from dotenv import load_dotenv


class Config(object):
    def __init__(self):
        # carrega as variáveis de ambiente do arquivo .env (o arquivo .env deve estar na raiz do projeto e apenas é utilizado para desenvolvimento, em produção as variáveis de ambiente devem ser definidas diretamente no servidor)
        load_dotenv()

        self.checkAllVariables()

    def checkAllVariables(self):
        # Verifica se todas as variáveis de ambiente necessárias estão definidas
        required_vars = ["POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD",
                         "DATABASE_URL", "SECRET_KEY", "SECURITY_PASSWORD_SALT",
                         "BACKEND_IP", "BACKEND_PORT"]
        for var in required_vars:
            if not os.getenv(var):
                raise ValueError(f"Variável de ambiente não definida: {var}")

    DEBUG = False
    TESTING = False
    SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_hex())
    IP_HOST = os.getenv("BACKEND_IP", "0.0.0.0")
    IP_PORT = os.getenv("BACKEND_PORT", 8000)

    # remover as mensagens de mmudanças no db no console
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SECURITY_PASSWORD_SALT = os.getenv(
        "SECURITY_PASSWORD_SALT", secrets.token_hex())  # para o bycrpt


class ProductionConfig(Config):
    ENV = 'production'
    # banco de dados de produção
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", "sqlite:///vision_face.db"
    )


class DevelopmentConfig(Config):
    ENV = 'development'
    DEBUG = True
    # temp -> banco de dados temporario que depois pode ser delatado
    SQLALCHEMY_DATABASE_URI = 'sqlite:///vision_face.db'


class TestingConfig(Config):
    ENV = 'testing'
    TESTING = True
    # banco de dados apenas criado na memoria, ou seja quando parar a app irá deixar de existir
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'


app_configs = {
    'production': ProductionConfig(),
    'development': DevelopmentConfig(),
    'testing': TestingConfig()
}

# 'development' -> default, caso a variavel de ambiente 'ENV' não seja mencionada
# set ENV=production -> para configurar a app para produção
app_config_active = os.getenv('ENV', 'development')

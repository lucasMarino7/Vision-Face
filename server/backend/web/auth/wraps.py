# wraps são funções/decorators personalizados, abaixa está um decorator 'is_user' responsável pela authenticação do user,
# se é um client, admin ou super admin

from functools import wraps
from flask import abort
from flask_login import current_user


# estrutura padrão de wrap personalizado que recebe atributos
def is_user(role_name='Client'):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            role = role_name
            if role not in current_user.role_name:
                abort(401)  # retorna uma página de erro de usuario não permitido
            # caso a condição acima estaja verdadeira, retorna uma função, como se fosse retorna True
            return f(*args, **kwargs)
        return decorated_function
    return decorator

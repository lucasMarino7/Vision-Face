# routes da homepage da web e rotas quando o usuario ainda não estiver logado
from flask import render_template, Blueprint


home_bp = Blueprint('home', __name__, template_folder='templates/home',
                    static_folder='static/home', static_url_path=f'/{__name__}')


@home_bp.route('/', methods=['GET'])
def index():
    return render_template('index.html')


@home_bp.route('/docs', methods=['GET'])
def docs():
    return render_template('docs.html')

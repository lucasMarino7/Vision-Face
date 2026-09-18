# routes do usuario, que será direcionado conforme sua role/função, seja client, admin ou super admin

from flask import Blueprint, render_template
from flask_login import login_required
from src.web.auth.wraps import is_user


blog_bp = Blueprint('blog', __name__, url_prefix='/blog', template_folder='templates/blog',
                    static_folder='static/blog', static_url_path=f'/{__name__}')


@blog_bp.route('/user/client/<name>', methods=['GET'])
@login_required
@is_user('Client')
def client_home(name):
    return render_template('home_blog.html', name=name)


@blog_bp.route('/user/admin/<name>', methods=['GET'])
@login_required
@is_user('Admin')
def admin_home(name):
    return render_template('home_blog.html', name=name)


@blog_bp.route('/user/super-admin/<name>', methods=['GET'])
@login_required
@is_user('Super Admin')
def super_admin_home(name):
    return render_template('home_blog.html', name=name)

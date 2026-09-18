# routes de authenticação do usuario: login, logout e signup

from flask import Blueprint, request, render_template, redirect, url_for, flash
from flask_login import login_user, current_user, login_required, logout_user
from .forms import SignupForm, LoginForm
from src.models.user import UserModel, RoleModel
from src.server.extensions import login_manager, bcrypt


auth_bp = Blueprint('auth', __name__, url_prefix='/auth', template_folder='templates/auth',
                    static_folder='static/auth', static_url_path=f'/{__name__}')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    Método responsavél em fazer o login/iniciar sessão do usuário
    """
    login_form = LoginForm()

    if request.method == 'POST' and login_form.validate_on_submit():
        user = UserModel.find_by_email(login_form.email.data)

        if user and bcrypt.check_password_hash(user.password_hash, login_form.password.data):
            if user.is_active():
                login_user(user)
                print('Login done!!!')
                redirect_page = request.args.get('next')
                if redirect_page:
                    return redirect(redirect_page)
                else:
                    if current_user.role_name == 'Client':
                        return redirect(url_for('web.blog.client_home', name=current_user.name))
                    elif current_user.role_name == 'Admin':
                        return redirect(url_for('web.blog.admin_home', name=current_user.name))
                    elif current_user.role_name == 'Super Admin':
                        return redirect(url_for('web.blog.super_admin_home', name=current_user.name))
                    return flash(f'Redirect page failed, your user role name {current_user.role_name} is not found',
                                 'alert-danger')
            else:
                flash(f'Login failed, your user client account is inactive',
                      'alert-danger')
        else:
            flash(f'Login failed, email address or password is incorrect',
                  'alert-danger')
    return render_template('login.html', login_form=login_form)


@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    """
    Método responsável em fazer o signup/cadastro do usuário
    """
    signup_form = SignupForm()

    if request.method == 'POST' and signup_form.validate_on_submit():
        password_hash = bcrypt.generate_password_hash(
            signup_form.password.data)

        role_name = 'Client'
        role_user = RoleModel.find_by_name(role_name)
        if role_user:
            user = UserModel(name=signup_form.name.data, email=signup_form.email.data,
                             password_hash=password_hash, role_name=role_user.name)
            user.save_to_db()
            login_user(user)
            print('Signup done!!!')
            return redirect(url_for('web.blog.client_home', name=current_user.name))
        else:
            flash(f'Sign Up failed, role \'{role_name}\' not registered',
                  'alert-danger')

    return render_template('signup.html', signup_form=signup_form)


@login_required
@auth_bp.route('/logout', methods=['GET'])
def logout():
    """
    Método responsável em fazer o logout/finalizar sessão do usuário
    """
    logout_user()
    flash('Log Out success', 'alert-success')
    return redirect(url_for('web.home.index'))


@login_manager.user_loader
def load_user(user_id):
    """
    Método do Flask-Login, onde a cada requisição do usuario logado, 
    irá chamar essa função e verificar suas credencias (is_active, email, senha e etc)
    """
    return UserModel.find_by_id(user_id)

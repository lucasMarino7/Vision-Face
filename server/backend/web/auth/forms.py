from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError
from src.models.user import UserModel


class LoginForm(FlaskForm):
    email = StringField('E-mail', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[
                             DataRequired(), Length(6, 20)])
    submit = SubmitField('Log In')


class SignupForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    email = StringField('E-mail', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[
                             DataRequired(), Length(6, 20)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(
    ), EqualTo('password', message='Both password fields must be equal!')])
    submit = SubmitField('Sign Up')

    def validate_email(self, email):
        user = UserModel.find_by_email(email.data)
        if user:
            raise ValidationError(
                'Email address already exist. Try another?')

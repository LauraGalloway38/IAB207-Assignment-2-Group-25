from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Regexp


def strip_text(value):
    return value.strip() if value else value


def normalise_email(value):
    return value.strip().lower() if value else value


class LoginForm(FlaskForm):
    email = StringField('Email address', filters=[normalise_email],
                        validators=[DataRequired(), Email(), Length(max=254)],
                        render_kw={'autocomplete': 'email', 'type': 'email'})
    password = PasswordField('Password', validators=[DataRequired()],
                             render_kw={'autocomplete': 'current-password'})
    submit = SubmitField('Sign in')


class RegisterForm(FlaskForm):
    name = StringField('Full name', filters=[strip_text],
                       validators=[DataRequired(), Length(max=100)],
                       render_kw={'autocomplete': 'name'})
    email = StringField('Email address', filters=[normalise_email],
                        validators=[DataRequired(), Email(), Length(max=254)],
                        render_kw={'autocomplete': 'email', 'type': 'email'})
    contact_number = StringField('Contact number', filters=[strip_text], validators=[
        DataRequired(), Length(min=6, max=30),
        Regexp(r'(?=(?:\D*\d){6})[+0-9() .-]+$',
               message='Enter a valid contact number with at least six digits.')],
        render_kw={'autocomplete': 'tel', 'type': 'tel'})
    street_address = StringField('Street address', filters=[strip_text],
                                 validators=[DataRequired(), Length(max=255)],
                                 render_kw={'autocomplete': 'street-address'})
    password = PasswordField('Password', validators=[
        DataRequired(), Length(min=8, max=128),
        EqualTo('confirm', message='Passwords must match.')],
        description='Use at least 8 characters.',
        render_kw={'autocomplete': 'new-password'})
    confirm = PasswordField('Confirm password', validators=[DataRequired()],
                            render_kw={'autocomplete': 'new-password'})
    submit = SubmitField('Create account')


class LogoutForm(FlaskForm):
    submit = SubmitField('Sign out')

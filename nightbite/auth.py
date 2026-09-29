from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_bcrypt import check_password_hash, generate_password_hash
from flask_login import login_required, login_user, logout_user
from sqlalchemy.exc import SQLAlchemyError

from . import db
from .forms import LoginForm, RegisterForm
from .models import User

# Create a blueprint - make sure all BPs have unique names
auth_bp = Blueprint('auth', __name__)


def is_safe_next(target):
    """Only allow relative redirects back into this site."""
    return bool(target) and target.startswith('/') and not target.startswith('//')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    login_form = LoginForm()
    error = None
    if login_form.validate_on_submit():
        user_name = login_form.user_name.data
        password = login_form.password.data
        user = db.session.scalar(db.select(User).where(User.name == user_name))
        if user is None:
            error = 'Incorrect user name'
        elif not check_password_hash(user.password_hash, password):
            error = 'Incorrect password'
        if error is None:
            login_user(user)
            # this gives the url from where the login page was accessed
            nextp = request.args.get('next')
            if not is_safe_next(nextp):
                return redirect(url_for('main.index'))
            return redirect(nextp)
        flash(error)
    return render_template('user.html', form=login_form, heading='Login')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    register_form = RegisterForm()
    if register_form.validate_on_submit():
        user_name = register_form.user_name.data
        email = register_form.email.data
        password = register_form.password.data

        existing = db.session.scalar(
            db.select(User).where((User.name == user_name) | (User.email == email))
        )
        if existing is not None:
            flash('That user name or email is already registered.')
            return redirect(url_for('auth.register'))

        user = User(
            name=user_name,
            email=email,
            password_hash=generate_password_hash(password).decode('utf-8'),
        )
        try:
            db.session.add(user)
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            flash('Your account could not be created. Please try again.')
            return redirect(url_for('auth.register'))

        flash('Account created. Please sign in.')
        return redirect(url_for('auth.login'))
    return render_template('user.html', form=register_form, heading='Register')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been signed out.')
    return redirect(url_for('main.index'))

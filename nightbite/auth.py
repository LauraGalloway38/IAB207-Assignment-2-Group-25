from urllib.parse import urlsplit

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from . import db
from .forms import LoginForm, RegisterForm, LogoutForm
from .models import User


auth_bp = Blueprint('auth', __name__)


def safe_next_url(target):
    """Only accept local absolute paths, never external login redirects."""
    if not target or not target.startswith('/') or target.startswith('//'):
        return None
    if '\\' in target or any(ord(char) < 32 for char in target):
        return None
    try:
        parts = urlsplit(target)
    except ValueError:
        return None
    if parts.scheme or parts.netloc:
        return None
    return target


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = RegisterForm()
    if form.validate_on_submit():
        existing = db.session.scalar(db.select(User).where(User.email == form.email.data))
        if existing:
            form.email.errors.append('An account already uses this email. Please sign in.')
        else:
            user = User(name=form.name.data, email=form.email.data,
                        contact_number=form.contact_number.data,
                        street_address=form.street_address.data,
                        password_hash=generate_password_hash(form.password.data))
            db.session.add(user)
            try:
                db.session.commit()
            except IntegrityError:
                # The unique constraint also handles simultaneous registrations.
                db.session.rollback()
                form.email.errors.append('An account already uses this email. Please sign in.')
            else:
                flash('Your account has been created. Please sign in.', 'success')
                return redirect(url_for('auth.login'))
    return render_template('user.html', form=form, heading='Create account')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.scalar(db.select(User).where(User.email == form.email.data))
        if user and check_password_hash(user.password_hash, form.password.data):
            login_user(user)
            flash('You are now signed in.', 'success')
            return redirect(safe_next_url(request.args.get('next')) or url_for('main.index'))
        flash('Email or password is incorrect.', 'danger')
    return render_template('user.html', form=form, heading='Sign in')


@auth_bp.post('/logout')
@login_required
def logout():
    form = LogoutForm()
    if form.validate_on_submit():
        logout_user()
        flash('You have been signed out.', 'success')
    return redirect(url_for('main.index'))

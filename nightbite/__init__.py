import os
import secrets
from pathlib import Path

import click
from flask import Flask, render_template
from flask_bootstrap import Bootstrap5
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect, CSRFError


db = SQLAlchemy()
csrf = CSRFProtect()


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        SQLALCHEMY_DATABASE_URI='sqlite:///sitedata.sqlite',
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=os.environ.get('NIGHTBITE_HTTPS') == '1',
    )
    if test_config:
        app.config.update(test_config)
    if not app.config.get('SECRET_KEY'):
        app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
    if not app.config.get('SECRET_KEY'):
        # Keep a development key stable across restarts, outside version control.
        Path(app.instance_path).mkdir(parents=True, exist_ok=True)
        key_file = Path(app.instance_path) / 'secret-key'
        try:
            with key_file.open('x') as output:
                key_file.chmod(0o600)
                output.write(secrets.token_hex(32))
        except FileExistsError:
            pass
        app.config['SECRET_KEY'] = key_file.read_text().strip()

    db.init_app(app)
    Bootstrap5(app)
    csrf.init_app(app)
    login_manager = LoginManager(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'info'

    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return db.session.get(User, int(user_id))
        except (TypeError, ValueError):
            return None

    from .views import main_bp
    from .auth import auth_bp
    from .forms import LogoutForm
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)

    @app.context_processor
    def account_forms():
        return {'logout_form': LogoutForm()}

    @app.errorhandler(404)
    def not_found(error):
        return render_template('errors/error.html', code=404,
                               heading='Page not found',
                               message='The page may have moved or the address may be incorrect.'), 404

    @app.errorhandler(500)
    def server_error(error):
        db.session.rollback()
        return render_template('errors/error.html', code=500,
                               heading='Something went wrong',
                               message='Please try again shortly.'), 500

    @app.errorhandler(CSRFError)
    def csrf_error(error):
        return render_template('errors/error.html', code=400,
                               heading='Please reload the form',
                               message='Your form session expired or could not be verified. Reload the page and try again.'), 400

    @app.cli.command('init-db')
    def init_db():
        """Create missing tables without deleting existing records."""
        db.create_all()
        click.echo('Database tables created.')

    return app

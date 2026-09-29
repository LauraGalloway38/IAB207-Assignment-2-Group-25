import os

# import flask - from 'package' import 'Class'
from flask import Flask, render_template
from flask_bootstrap import Bootstrap5
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


# create a function that creates a web application
# a web server will run this web application
def create_app():

    app = Flask(__name__)  # this is the name of the module/package that is calling this app
    # Should be set to false in a production environment
    app.debug = True
    app.secret_key = 'somesecretkey'
    # set the app configuration data
    # Keep the database file inside the nightbite package (nightbite/sitedata.sqlite)
    # on every Flask-SQLAlchemy version, rather than in instance/.
    database_file = os.path.join(app.root_path, 'sitedata.sqlite')
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + database_file
    # initialise db with flask app
    db.init_app(app)

    Bootstrap5(app)

    # initialise the login manager
    login_manager = LoginManager()

    # set the name of the login function that lets user login
    # in our case it is auth.login (blueprintname.viewfunction name)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please sign in to continue.'
    login_manager.init_app(app)

    # create a user loader function takes userid and returns User
    # Importing inside the create_app function avoids circular references
    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.scalar(db.select(User).where(User.id == user_id))

    from . import views
    app.register_blueprint(views.main_bp)

    from . import auth
    app.register_blueprint(auth.auth_bp)

    @app.errorhandler(404)
    def not_found(error):
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('404.html'), 500

    from .commands import register_commands
    register_commands(app)

    return app

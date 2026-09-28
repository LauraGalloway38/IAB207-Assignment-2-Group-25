# import flask - from 'package' import 'Class'
from pathlib import Path

import click
from flask import Flask
from flask_bootstrap import Bootstrap5
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

db = SQLAlchemy()


# create a function that creates a web application
# a web server will run this web application
def create_app():

    app = Flask(__name__)  # this is the name of the module/package that is calling this app
    # Should be set to false in a production environment
    app.debug = True
    app.secret_key = 'somesecretkey'

    # set the app configuration data
    # Store the assignment database inside the application package.
    database_path = Path(app.root_path) / "sitedata.sqlite"
    app.config['SQLALCHEMY_DATABASE_URI'] = (
        f"sqlite:///{database_path.as_posix()}"
    )

    # initialise db with flask app
    db.init_app(app)

    Bootstrap5(app)

    # initialise the login manager
    login_manager = LoginManager()

    # set the name of the login function that lets user login
    # in our case it is auth.login (blueprintname.viewfunction name)
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)

    # create a user loader function takes userid and returns User
    # Importing inside the create_app function avoids circular references
    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        try:
            user_id = int(user_id)
        except (TypeError, ValueError):
            return None

        return db.session.get(User, user_id)

    from . import views
    app.register_blueprint(views.main_bp)

    from . import auth
    app.register_blueprint(auth.auth_bp)

    # Event management - create the tables and initial event categories.
    @app.cli.command("init-db")
    def init_db_command():
        from .models import Category

        db.create_all()

        category_names = [
            "Night Markets",
            "Street Food",
            "Pop-Ups",
            "Cultural Food",
            "Dessert",
            "Food Trucks",
        ]

        for name in category_names:
            existing_category = db.session.scalar(
                db.select(Category).where(Category.name == name)
            )

            if existing_category is None:
                db.session.add(Category(name=name))

        db.session.commit()
        click.echo("Database ready. Event categories added.")

    return app
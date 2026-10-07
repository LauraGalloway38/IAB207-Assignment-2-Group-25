import os
import secrets
from datetime import datetime
from decimal import Decimal
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
        SQLALCHEMY_DATABASE_URI=os.environ.get('NIGHTBITE_DATABASE_URI') or (
            'sqlite:///' + (Path(app.root_path) / 'sitedata.sqlite').as_posix()
        ),
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
        from .models import Category
        for name in ['Night Markets', 'Street Food', 'Pop-Ups', 'Cultural Food', 'Dessert', 'Food Trucks']:
            if db.session.scalar(db.select(Category).where(Category.name == name)) is None:
                db.session.add(Category(name=name))
        db.session.commit()
        click.echo('Database tables and event categories ready.')

    @app.cli.command('seed-events')
    def seed_events():
        """Add development sample events without duplicating existing records."""
        from .models import Category, Event, User

        # Create a development organiser for seeded events if one does not exist.
        organiser = db.session.scalar(
            db.select(User).where(User.email == 'events@nightbite.test')
        )

        if organiser is None:
            organiser = User(
                name='NIGHTBITE Events',
                email='events@nightbite.test',
                contact_number='0400000000',
                street_address='Brisbane QLD',
                password_hash='development-seed-account',
            )
            db.session.add(organiser)
            db.session.flush()

        categories = {
            category.name: category
            for category in db.session.scalars(
                db.select(Category)
            ).all()
        }

        sample_events = [
            {
                'title': 'Riverside Night Bites',
                'description': (
                    'An evening of Brisbane street food, live entertainment '
                    'and riverside dining featuring local food vendors.'
                ),
                'image_filename': 'img/night-market.jpeg',
                'venue': 'South Bank Parklands',
                'street_address': 'Clem Jones Promenade',
                'suburb': 'South Brisbane',
                'state': 'QLD',
                'start_datetime': datetime(2026, 10, 3, 17, 0),
                'end_datetime': datetime(2026, 10, 3, 22, 0),
                'cuisine': 'International',
                'vegetarian': True,
                'vegan': True,
                'gluten_free': True,
                'halal': True,
                'accessibility': (
                    'Wheelchair accessible paths and accessible amenities.'
                ),
                'ticket_price': Decimal('0.00'),
                'ticket_capacity': 500,
                'category': 'Night Markets',
            },
            {
                'title': 'Valley Street Feast',
                'description': (
                    'A late-night street food celebration featuring bold '
                    'flavours, local vendors and live music.'
                ),
                'image_filename': 'img/street-food.jpg',
                'venue': 'Brunswick Street Mall',
                'street_address': 'Brunswick Street',
                'suburb': 'Fortitude Valley',
                'state': 'QLD',
                'start_datetime': datetime(2026, 10, 23, 18, 0),
                'end_datetime': datetime(2026, 10, 23, 23, 0),
                'cuisine': 'Asian Fusion',
                'vegetarian': True,
                'vegan': False,
                'gluten_free': True,
                'halal': True,
                'accessibility': (
                    'Step-free public access and accessible public transport nearby.'
                ),
                'ticket_price': Decimal('12.00'),
                'ticket_capacity': 300,
                'category': 'Street Food',
            },
            {
                'title': 'Seoul After Dark',
                'description': (
                    'A Korean food night showcasing barbecue, tteokbokki, '
                    'dumplings and contemporary Seoul-inspired dishes.'
                ),
                'image_filename': 'img/cultural-food.jpg',
                'venue': 'West End Community Hall',
                'street_address': '4 Vulture Street',
                'suburb': 'West End',
                'state': 'QLD',
                'start_datetime': datetime(2026, 11, 6, 18, 30),
                'end_datetime': datetime(2026, 11, 6, 22, 30),
                'cuisine': 'Korean',
                'vegetarian': True,
                'vegan': True,
                'gluten_free': False,
                'halal': False,
                'accessibility': (
                    'Wheelchair accessible entrance and accessible bathroom.'
                ),
                'ticket_price': Decimal('18.50'),
                'ticket_capacity': 180,
                'category': 'Cultural Food',
            },
            {
                'title': 'Midnight Dessert Club',
                'description': (
                    'A dessert-focused evening of pastries, gelato, cakes '
                    'and limited-edition sweet creations.'
                ),
                'image_filename': 'img/dessert.jpeg',
                'venue': 'New Farm Neighbourhood Centre',
                'street_address': '967 Brunswick Street',
                'suburb': 'New Farm',
                'state': 'QLD',
                'start_datetime': datetime(2026, 11, 14, 19, 0),
                'end_datetime': datetime(2026, 11, 14, 23, 0),
                'cuisine': 'Dessert',
                'vegetarian': True,
                'vegan': True,
                'gluten_free': True,
                'halal': False,
                'accessibility': (
                    'Step-free entrance with accessible seating available.'
                ),
                'ticket_price': Decimal('15.00'),
                'ticket_capacity': 120,
                'category': 'Dessert',
            },
            {
                'title': 'Laneway Taco Pop-Up',
                'description': (
                    'A one-night Mexican-inspired pop-up serving tacos, '
                    'street corn and fresh salsas in Brisbane City.'
                ),
                'image_filename': 'img/street-food.jpg',
                'venue': 'Burnett Lane',
                'street_address': 'Burnett Lane',
                'suburb': 'Brisbane City',
                'state': 'QLD',
                'start_datetime': datetime(2026, 11, 20, 17, 30),
                'end_datetime': datetime(2026, 11, 20, 21, 30),
                'cuisine': 'Mexican',
                'vegetarian': True,
                'vegan': True,
                'gluten_free': True,
                'halal': False,
                'accessibility': (
                    'Outdoor laneway venue with step-free access from Queen Street.'
                ),
                'ticket_price': Decimal('8.00'),
                'ticket_capacity': 150,
                'category': 'Pop-Ups',
            },
            {
                'title': 'Truck Stop Twilight',
                'description': (
                    'A rotating collection of Brisbane food trucks serving '
                    'burgers, tacos, loaded fries and international favourites.'
                ),
                'image_filename': 'img/night-market.jpeg',
                'venue': 'Roma Street Parkland',
                'street_address': '1 Parkland Boulevard',
                'suburb': 'Brisbane City',
                'state': 'QLD',
                'start_datetime': datetime(2026, 11, 28, 16, 30),
                'end_datetime': datetime(2026, 11, 28, 21, 30),
                'cuisine': 'Mixed',
                'vegetarian': True,
                'vegan': False,
                'gluten_free': True,
                'halal': True,
                'accessibility': (
                    'Accessible pathways, toilets and designated seating areas.'
                ),
                'ticket_price': Decimal('5.00'),
                'ticket_capacity': 400,
                'category': 'Food Trucks',
            },
        ]

        added = 0

        for event_data in sample_events:
            existing = db.session.scalar(
                db.select(Event).where(
                    Event.title == event_data['title']
                )
            )

            if existing is not None:
                existing.start_datetime = event_data['start_datetime']
                existing.end_datetime = event_data['end_datetime']
                continue

            category_name = event_data.pop('category')
            category = categories.get(category_name)

            if category is None:
                click.echo(
                    f"Missing category: {category_name}. Run init-db first."
                )
                return

            event_record = Event(
                **event_data,
                creator_id=organiser.id,
                category_id=category.id,
                acknowledgement_type='generic',
                acknowledgement_text=(
                    'We acknowledge the Traditional Custodians of the land '
                    'on which this event takes place and their continuing '
                    'connection to Country. We pay our respects to Elders '
                    'past and present.'
                ),
            )

            db.session.add(event_record)
            added += 1

        db.session.commit()
        click.echo(f'{added} sample NIGHTBITE events added.')

    
    return app

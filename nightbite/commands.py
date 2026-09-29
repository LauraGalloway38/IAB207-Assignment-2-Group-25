"""Flask CLI commands for local development.

    flask --app main init-db    create tables and the default categories
    flask --app main seed-db    load demo users, events, comments and orders
    flask --app main reset-db   drop everything, then init + seed

Only run reset-db/seed-db against your own local sitedata.sqlite.
"""

from datetime import datetime, timedelta

import click
from flask.cli import with_appcontext
from flask_bcrypt import generate_password_hash

from . import db

DEFAULT_CATEGORIES = [
    'Night Market',
    'Street Food',
    'Food Festival',
    'Pop-up Dining',
    'Cultural Feast',
    'Dessert Event',
]


def _create_categories():
    from .models import Category

    created = 0
    for name in DEFAULT_CATEGORIES:
        existing = db.session.scalar(db.select(Category).where(Category.name == name))
        if existing is None:
            db.session.add(Category(name=name))
            created += 1
    db.session.commit()
    return created


@click.command('init-db')
@with_appcontext
def init_db_command():
    """Create any missing tables and the default categories."""
    db.create_all()
    created = _create_categories()
    click.echo(f'Database ready. {created} new categor(y/ies) added.')


@click.command('seed-db')
@with_appcontext
def seed_db_command():
    """Add demo data for local testing (safe to run once on an empty DB)."""
    from .models import Category, Comment, Event, Order, User

    db.create_all()
    _create_categories()

    if db.session.scalar(db.select(Event)) is not None:
        click.echo('Events already exist - skipping seed.')
        return

    def make_user(name, email):
        user = db.session.scalar(db.select(User).where(User.name == name))
        if user is None:
            user = User(
                name=name,
                email=email,
                password_hash=generate_password_hash('password').decode('utf-8'),
            )
            db.session.add(user)
        return user

    organiser = make_user('Taylor Morgan', 'taylor@nightbite.test')
    user_a = make_user('Jordan Lee', 'jordan@nightbite.test')
    user_b = make_user('Sophie Martin', 'sophie@nightbite.test')
    db.session.commit()

    def category(name):
        with db.session.no_autoflush:
            return db.session.scalar(db.select(Category).where(Category.name == name))

    now = datetime.now()
    events = [
        Event(
            title='Riverside Night Bites',
            description=(
                "Spend the evening by the river with some of Brisbane's best "
                "street-food vendors, local desserts and live entertainment."
            ),
            image_filename='img/night-market.jpeg',
            venue='South Bank Cultural Forecourt',
            street_address='Grey Street',
            suburb='South Brisbane',
            state='QLD',
            start_datetime=now + timedelta(days=21, hours=2),
            end_datetime=now + timedelta(days=21, hours=7),
            cuisine='International street food',
            vegetarian=True,
            vegan=True,
            gluten_free=True,
            halal=False,
            accessibility='Step-free venue access and accessible facilities',
            ticket_price=12.00,
            ticket_capacity=50,
            is_cancelled=False,
            acknowledgement_type='generic',
            acknowledgement_text=(
                'NIGHTBITE acknowledges the Traditional Custodians of the land on '
                'which this event takes place and pays respect to Elders past and present.'
            ),
            traditional_custodians='Turrbal and Yuggera peoples',
            acknowledgement_source='Brisbane City Council',
            creator=organiser,
            category=category('Night Market'),
        ),
        Event(
            title='Valley Street Feast',
            description='A late-night street food takeover in Fortitude Valley.',
            image_filename='img/street-food.jpg',
            venue='Brunswick Street Mall',
            street_address='Brunswick Street',
            suburb='Fortitude Valley',
            state='QLD',
            start_datetime=now + timedelta(days=28, hours=3),
            end_datetime=now + timedelta(days=28, hours=8),
            cuisine='Asian street food',
            vegetarian=True,
            vegan=True,
            gluten_free=False,
            halal=True,
            accessibility='Step-free venue access',
            ticket_price=18.00,
            ticket_capacity=6,
            is_cancelled=False,
            acknowledgement_type='custom',
            acknowledgement_text='We acknowledge the Traditional Owners of this land.',
            traditional_custodians='Turrbal people',
            acknowledgement_source='Event organiser',
            creator=organiser,
            category=category('Street Food'),
        ),
        Event(
            title='Winter Dessert Lane',
            description='A dessert-only pop-up that has already been cancelled.',
            image_filename='img/dessert.jpeg',
            venue='Howard Smith Wharves',
            street_address='5 Boundary Street',
            suburb='Brisbane City',
            state='QLD',
            start_datetime=now + timedelta(days=10, hours=1),
            end_datetime=now + timedelta(days=10, hours=5),
            cuisine='Desserts',
            vegetarian=True,
            vegan=False,
            gluten_free=True,
            halal=False,
            accessibility='Lift access available',
            ticket_price=15.00,
            ticket_capacity=100,
            is_cancelled=True,
            acknowledgement_type='generic',
            acknowledgement_text='We acknowledge the Traditional Custodians of this land.',
            traditional_custodians='Turrbal and Yuggera peoples',
            acknowledgement_source='Brisbane City Council',
            creator=organiser,
            category=category('Dessert Event'),
        ),
        Event(
            title='Cultural Food Nights (past)',
            description='A finished event, used to demonstrate the Inactive status.',
            image_filename='img/cultural-food.jpg',
            venue='Roma Street Parkland',
            street_address='1 Parkland Boulevard',
            suburb='Brisbane City',
            state='QLD',
            start_datetime=now - timedelta(days=9),
            end_datetime=now - timedelta(days=9, hours=-4),
            cuisine='Cultural cuisine',
            vegetarian=True,
            vegan=True,
            gluten_free=True,
            halal=True,
            accessibility='Step-free venue access',
            ticket_price=10.00,
            ticket_capacity=80,
            is_cancelled=False,
            acknowledgement_type='generic',
            acknowledgement_text='We acknowledge the Traditional Custodians of this land.',
            traditional_custodians='Turrbal and Yuggera peoples',
            acknowledgement_source='Brisbane City Council',
            creator=organiser,
            category=category('Cultural Feast'),
        ),
    ]
    db.session.add_all(events)
    db.session.commit()

    db.session.add_all([
        Comment(
            user_id=user_a.id,
            event_id=events[0].id,
            comment_text='Will there be plenty of vegan options this year?',
            posted_datetime=now - timedelta(days=1),
        ),
        Comment(
            user_id=user_b.id,
            event_id=events[0].id,
            comment_text='Went last year and loved the riverside setup.',
            posted_datetime=now - timedelta(hours=6),
        ),
    ])

    # Four of the six Valley Street Feast tickets are already sold, so the
    # "only N remaining" path can be demonstrated, and two more sell it out.
    db.session.add(Order(
        user_id=user_b.id,
        event_id=events[1].id,
        quantity=4,
        unit_price=events[1].ticket_price,
        total_amount=events[1].ticket_price * 4,
        booking_datetime=now - timedelta(days=2),
        order_reference='NB-100001',
    ))
    db.session.commit()

    click.echo('Seeded demo users, events, comments and one order.')
    click.echo('Demo logins: "Jordan Lee" / "Sophie Martin" / "Taylor Morgan", password: password')


@click.command('reset-db')
@with_appcontext
def reset_db_command():
    """LOCAL ONLY: drop all tables, then recreate and seed them."""
    db.drop_all()
    db.create_all()
    click.echo('Local database dropped and recreated.')
    seed_db_command.callback()


def register_commands(app):
    app.cli.add_command(init_db_command)
    app.cli.add_command(seed_db_command)
    app.cli.add_command(reset_db_command)

from datetime import datetime

from flask_login import UserMixin

from . import db


class User(db.Model, UserMixin):
    """Account holder. Owned by Arham (authentication)."""

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    def __repr__(self):
        return f'<User {self.name}>'


class Category(db.Model):
    """Event category. Owned by Aarnav (event management)."""

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)

    events = db.relationship('Event', back_populates='category')

    def __repr__(self):
        return f'<Category {self.name}>'


class Event(db.Model):
    """Event. Owned by Aarnav (event management).

    Jack's booking/comment code only ever reads from this model. It never
    writes to it and never stores a tickets_available column, because
    `status` and `remaining_tickets` below are calculated from Order data.
    """

    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    image_filename = db.Column(db.String(255), nullable=True)

    venue = db.Column(db.String(150), nullable=False)
    street_address = db.Column(db.String(200), nullable=True)
    suburb = db.Column(db.String(100), nullable=True)
    state = db.Column(db.String(50), nullable=True)

    start_datetime = db.Column(db.DateTime, nullable=False)
    end_datetime = db.Column(db.DateTime, nullable=False)

    cuisine = db.Column(db.String(100), nullable=True)
    vegetarian = db.Column(db.Boolean, nullable=False, default=False)
    vegan = db.Column(db.Boolean, nullable=False, default=False)
    gluten_free = db.Column(db.Boolean, nullable=False, default=False)
    halal = db.Column(db.Boolean, nullable=False, default=False)
    accessibility = db.Column(db.String(255), nullable=True)

    ticket_price = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    ticket_capacity = db.Column(db.Integer, nullable=False, default=0)

    is_cancelled = db.Column(db.Boolean, nullable=False, default=False)

    acknowledgement_type = db.Column(db.String(50), nullable=True)
    acknowledgement_text = db.Column(db.Text, nullable=True)
    traditional_custodians = db.Column(db.String(150), nullable=True)
    acknowledgement_source = db.Column(db.String(255), nullable=True)

    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)

    creator = db.relationship('User', foreign_keys=[creator_id])
    category = db.relationship('Category', back_populates='events')

    # MERGE NOTE (Jack -> Aarnav): these two collections are declared here, on
    # Event, and the Order/Comment classes point back at them with
    # back_populates. If Aarnav's branch already declares `orders`, delete the
    # line below and leave his - do not declare the relationship twice.
    orders = db.relationship(
        'Order', back_populates='event', cascade='all, delete-orphan'
    )
    comments = db.relationship(
        'Comment', back_populates='event', cascade='all, delete-orphan'
    )

    @property
    def tickets_sold(self):
        """Total tickets already ordered for this event."""
        return sum(order.quantity for order in self.orders)

    @property
    def remaining_tickets(self):
        """Capacity minus tickets sold, never negative."""
        return max((self.ticket_capacity or 0) - self.tickets_sold, 0)

    @property
    def status(self):
        """Calculated status: Cancelled -> Inactive -> Sold Out -> Open."""
        if self.is_cancelled:
            return 'Cancelled'
        if self.end_datetime and self.end_datetime < datetime.now():
            return 'Inactive'
        if self.remaining_tickets <= 0:
            return 'Sold Out'
        return 'Open'

    def __repr__(self):
        return f'<Event {self.title}>'


class Comment(db.Model):
    """Comment posted by a signed-in user on an event. Owned by Jack."""

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)
    comment_text = db.Column(db.Text, nullable=False)
    posted_datetime = db.Column(db.DateTime, nullable=False, default=datetime.now)

    user = db.relationship('User', foreign_keys=[user_id])
    event = db.relationship('Event', back_populates='comments')

    def __repr__(self):
        return f'<Comment {self.id} on event {self.event_id}>'


class Order(db.Model):
    """A ticket order placed by a user against an event. Owned by Jack.

    Aarnav's Event.remaining_tickets depends on Order.event_id and
    Order.quantity, so those two names must not change.
    """

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    booking_datetime = db.Column(db.DateTime, nullable=False, default=datetime.now)
    order_reference = db.Column(db.String(20), unique=True, nullable=False)

    user = db.relationship('User', foreign_keys=[user_id])
    event = db.relationship('Event', back_populates='orders')

    def __repr__(self):
        return f'<Order {self.order_reference}>'

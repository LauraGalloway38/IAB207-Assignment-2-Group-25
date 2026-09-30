from datetime import datetime, timedelta, timezone

from . import db
from flask_login import UserMixin


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)

    events = db.relationship("Event", back_populates="category")


class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    # Basic event information
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    image_filename = db.Column(db.String(255), nullable=False)

    # Location and schedule
    venue = db.Column(db.String(200), nullable=False)
    street_address = db.Column(db.String(255), nullable=False)
    suburb = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(30), nullable=False)
    start_datetime = db.Column(db.DateTime, nullable=False)
    end_datetime = db.Column(db.DateTime, nullable=False)

    # Food and accessibility information
    cuisine = db.Column(db.String(150), nullable=False)
    vegetarian = db.Column(db.Boolean, nullable=False, default=False)
    vegan = db.Column(db.Boolean, nullable=False, default=False)
    gluten_free = db.Column(db.Boolean, nullable=False, default=False)
    halal = db.Column(db.Boolean, nullable=False, default=False)
    accessibility = db.Column(db.Text, nullable=False, default="")

    # Store money as an exact decimal rather than a float.
    ticket_price = db.Column(db.Numeric(10, 2), nullable=False)
    ticket_capacity = db.Column(db.Integer, nullable=False)

    # Cancellation is stored separately from the calculated event status.
    is_cancelled = db.Column(db.Boolean, nullable=False, default=False)

    # Acknowledgement options: none, generic, enhanced
    acknowledgement_type = db.Column(
        db.String(20), nullable=False, default="none"
    )
    acknowledgement_text = db.Column(db.Text, nullable=False, default="")
    traditional_custodians = db.Column(
        db.String(255), nullable=False, default=""
    )
    acknowledgement_source = db.Column(
        db.String(500), nullable=False, default=""
    )

    # Link each event to its creator and category.
    creator_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=False, index=True
    )
    category_id = db.Column(
        db.Integer, db.ForeignKey("category.id"), nullable=False, index=True
    )

    creator = db.relationship("User", backref="created_events")
    category = db.relationship("Category", back_populates="events")

    # Database checks also protect against invalid stored values.
    __table_args__ = (
        db.CheckConstraint(
            "ticket_price >= 0",
            name="event_nonnegative_price",
        ),
        db.CheckConstraint(
            "ticket_capacity > 0",
            name="event_positive_capacity",
        ),
        db.CheckConstraint(
            "end_datetime > start_datetime",
            name="event_valid_schedule",
        ),
        db.CheckConstraint(
            "acknowledgement_type IN ('none', 'generic', 'enhanced')",
            name="event_valid_acknowledgement_type",
        ),
    )

    # Connect events to Jack's bookings and comments.
    orders = db.relationship("Order", back_populates="event")
    comments = db.relationship("Comment", back_populates="event")

    @property
    def tickets_sold(self):
        return sum(order.quantity for order in self.orders)

    @property
    def remaining_tickets(self):
        return max((self.ticket_capacity or 0) - self.tickets_sold, 0)

    # NIGHTBITE currently interprets event times as Brisbane local time.
    @property
    def status(self):
        if self.is_cancelled:
            return "Cancelled"
        brisbane_now = datetime.now(timezone(timedelta(hours=10))).replace(tzinfo=None)
        if self.end_datetime and self.end_datetime <= brisbane_now:
            return "Inactive"
        if self.remaining_tickets <= 0:
            return "Sold Out"
        return "Open"


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


# From A2 starter files
# from . import db
#
# from datetime import datetime
#
# from flask_login import UserMixin
#
# class User(db.Model, UserMixin):
#
# class Event(db.Model):
#
# class Comment(db.Model):
#
# class Order(db.Model):
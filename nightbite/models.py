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


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)


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
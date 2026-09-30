from . import db
from flask_login import UserMixin


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(254), unique=True, nullable=False)
    contact_number = db.Column(db.String(30), nullable=False)
    street_address = db.Column(db.String(255), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)


class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)


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
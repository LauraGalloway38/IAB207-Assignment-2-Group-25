from flask_wtf import FlaskForm
from wtforms.fields import (
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Email, EqualTo, InputRequired, Length


# creates the login information
class LoginForm(FlaskForm):
    user_name = StringField("User Name", validators=[InputRequired('Enter user name')])
    password = PasswordField("Password", validators=[InputRequired('Enter user password')])
    submit = SubmitField("Login")


# this is the registration form
class RegisterForm(FlaskForm):
    user_name = StringField("User Name", validators=[InputRequired()])
    email = StringField("Email Address", validators=[Email("Please enter a valid email")])
    # linking two fields - password should be equal to data entered in confirm
    password = PasswordField(
        "Password",
        validators=[InputRequired(), EqualTo('confirm', message="Passwords should match")],
    )
    confirm = PasswordField("Confirm Password")
    submit = SubmitField("Register")


# --- Jack: bookings and comments -------------------------------------------

class CommentForm(FlaskForm):
    """Comment box shown on the event details page."""

    comment_text = TextAreaField(
        "Your comment",
        validators=[
            DataRequired(message='Please enter a comment.'),
            Length(max=1000, message='Comments must be 1000 characters or fewer.'),
        ],
    )
    submit = SubmitField("Post Comment")


class BookingForm(FlaskForm):
    """Ticket quantity selector. The server still re-checks
    event.remaining_tickets before an Order is created."""

    quantity = SelectField(
        "Number of tickets",
        choices=[(i, f"{i} ticket" if i == 1 else f"{i} tickets") for i in range(1, 11)],
        coerce=int,
        validators=[InputRequired(message='Choose a quantity.')],
    )
    submit = SubmitField("Book Tickets")

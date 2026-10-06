from decimal import Decimal
from flask_wtf.file import FileAllowed, FileField
from wtforms import BooleanField, DateTimeLocalField, DecimalField, IntegerField, SelectField, TextAreaField
from wtforms.validators import InputRequired, NumberRange, Optional, URL, ValidationError

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Regexp


def strip_text(value):
    return value.strip() if value else value


def normalise_email(value):
    return value.strip().lower() if value else value


class LoginForm(FlaskForm):
    email = StringField('Email address', filters=[normalise_email],
                        validators=[DataRequired(), Email(), Length(max=254)],
                        render_kw={'autocomplete': 'email', 'type': 'email'})
    password = PasswordField('Password', validators=[DataRequired()],
                             render_kw={'autocomplete': 'current-password'})
    submit = SubmitField('Sign in')


class RegisterForm(FlaskForm):
    name = StringField('Full name', filters=[strip_text],
                       validators=[DataRequired(), Length(max=100)],
                       render_kw={'autocomplete': 'name'})
    email = StringField('Email address', filters=[normalise_email],
                        validators=[DataRequired(), Email(), Length(max=254)],
                        render_kw={'autocomplete': 'email', 'type': 'email'})
    contact_number = StringField('Contact number', filters=[strip_text], validators=[
        DataRequired(), Length(min=6, max=30),
        Regexp(r'(?=(?:\D*\d){6})[+0-9() .-]+$',
               message='Enter a valid contact number with at least six digits.')],
        render_kw={'autocomplete': 'tel', 'type': 'tel'})
    street_address = StringField('Street address', filters=[strip_text],
                                 validators=[DataRequired(), Length(max=255)],
                                 render_kw={'autocomplete': 'street-address'})
    password = PasswordField('Password', validators=[
        DataRequired(), Length(min=8, max=128),
        EqualTo('confirm', message='Passwords must match.')],
        description='Use at least 8 characters.',
        render_kw={'autocomplete': 'new-password'})
    confirm = PasswordField('Confirm password', validators=[DataRequired()],
                            render_kw={'autocomplete': 'new-password'})
    submit = SubmitField('Create account')


class LogoutForm(FlaskForm):
    submit = SubmitField('Sign out')


# Event management forms - Aarnav
class EventForm(FlaskForm):
    # Basic event information
    title = StringField(
        "Event title",
        filters=[strip_text],
        validators=[DataRequired(), Length(max=150)],
    )

    description = TextAreaField(
        "Event description",
        filters=[strip_text],
        validators=[DataRequired(), Length(max=10000)],
    )

    image = FileField(
        "Event image",
        validators=[
            FileAllowed(
                ["jpg", "jpeg", "png"],
                "Choose a JPG, JPEG or PNG image.",
            )
        ],
    )

    # Category choices are loaded from the database by the route.
    category_id = SelectField(
        "Category",
        coerce=int,
        choices=[],
        validators=[
            InputRequired(),
            NumberRange(min=1, message="Choose a category."),
        ],
    )

    cuisine = StringField(
        "Cuisine / food details",
        filters=[strip_text],
        validators=[DataRequired(), Length(max=150)],
    )

    # Event location
    venue = StringField(
        "Venue",
        filters=[strip_text],
        validators=[DataRequired(), Length(max=200)],
    )

    street_address = StringField(
        "Street address",
        filters=[strip_text],
        validators=[DataRequired(), Length(max=255)],
    )

    suburb = StringField(
        "Suburb / city",
        filters=[strip_text],
        validators=[DataRequired(), Length(max=100)],
    )

    state = SelectField(
        "State or territory",
        choices=[
            ("", "Select a state or territory"),
            ("ACT", "Australian Capital Territory"),
            ("NSW", "New South Wales"),
            ("NT", "Northern Territory"),
            ("QLD", "Queensland"),
            ("SA", "South Australia"),
            ("TAS", "Tasmania"),
            ("VIC", "Victoria"),
            ("WA", "Western Australia"),
        ],
        validators=[InputRequired()],
    )

    # Event dates and times
    start_datetime = DateTimeLocalField(
        "Start date and time",
        format="%Y-%m-%dT%H:%M",
        validators=[InputRequired()],
    )

    end_datetime = DateTimeLocalField(
        "End date and time",
        format="%Y-%m-%dT%H:%M",
        validators=[InputRequired()],
    )

    # Ticket price and capacity; a zero price allows free events.
    ticket_price = DecimalField(
        "Ticket price (AUD)",
        places=2,
        validators=[
            InputRequired(),
            NumberRange(
                min=Decimal("0.00"),
                max=Decimal("99999999.99"),
                message="Enter a price between 0 and 99,999,999.99.",
            ),
        ],
    )

    ticket_capacity = IntegerField(
        "Ticket capacity",
        validators=[
            InputRequired(),
            NumberRange(
                min=1,
                max=1000000,
                message="Enter a capacity between 1 and 1,000,000.",
            ),
        ],
    )

    # Food options and accessibility
    vegetarian = BooleanField("Vegetarian options")
    vegan = BooleanField("Vegan options")
    gluten_free = BooleanField("Gluten-free options")
    halal = BooleanField("Halal options")

    accessibility = TextAreaField(
        "Accessibility information",
        filters=[strip_text],
        validators=[Optional(), Length(max=3000)],
    )

    # Acknowledgement of Country options and researched custom text
    acknowledgement_type = SelectField(
        "Acknowledgement of Country",
        choices=[
            ("none", "No Acknowledgement of Country"),
            ("generic", "Generic Acknowledgement of Country"),
            ("enhanced", "Enhanced Acknowledgement of Country"),
        ],
        default="none",
        validators=[InputRequired()],
    )

    traditional_custodians = StringField(
        "Traditional Custodians",
        filters=[strip_text],
        validators=[Optional(), Length(max=255)],
    )

    acknowledgement_source = StringField(
        "Research source URL",
        filters=[strip_text],
        validators=[
            Optional(),
            Length(max=500),
            URL(message="Enter a complete URL, including https://."),
        ],
    )

    acknowledgement_text = TextAreaField(
        "Custom Acknowledgement of Country",
        filters=[strip_text],
        validators=[Optional(), Length(max=5000)],
    )

    submit = SubmitField("Save event")

    # Enhanced acknowledgements require all three research/text fields.
    def validate(self, extra_validators=None):
        valid = super().validate(extra_validators=extra_validators)

        if self.acknowledgement_type.data == "enhanced":
            required_fields = [
                (
                    self.traditional_custodians,
                    "Enter the Traditional Custodians identified "
                    "through your research.",
                ),
                (
                    self.acknowledgement_source,
                    "Provide a reliable source for your research.",
                ),
                (
                    self.acknowledgement_text,
                    "Write a researched, personalised Acknowledgement.",
                ),
            ]

            for field, message in required_fields:
                if not (field.data or "").strip():
                    field.errors = list(field.errors)
                    field.errors.append(message)
                    valid = False

        return valid

    # The event must finish after it starts.
    def validate_end_datetime(self, field):
        if (
            self.start_datetime.data
            and field.data
            and field.data <= self.start_datetime.data
        ):
            raise ValidationError(
                "The end date and time must be after the start."
            )

    # Reject prices that contain fractions of a cent.
    def validate_ticket_price(self, field):
        if field.data is None:
            return

        if not field.data.is_finite():
            raise ValidationError("Enter a valid ticket price.")

        # Out-of-range values are handled by NumberRange.
        if not Decimal("0.00") <= field.data <= Decimal("99999999.99"):
            return

        if field.data != field.data.quantize(Decimal("0.01")):
            raise ValidationError(
                "Ticket prices can have no more than two decimal places."
            )


# Separate form for submitting an event cancellation.
class CancelEventForm(FlaskForm):
    submit = SubmitField("Cancel event")
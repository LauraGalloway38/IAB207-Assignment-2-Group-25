from pathlib import Path
from uuid import uuid4

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy.exc import SQLAlchemyError

from . import db
from .forms import EventForm
from .models import Category, Event


main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    return render_template('index.html')


@main_bp.route('/event')
def event():
    return render_template('event.html')


# Event creation and management - Aarnav's section

# Only these form fields can be copied into an event.
EVENT_FORM_FIELDS = (
    "title",
    "description",
    "category_id",
    "cuisine",
    "venue",
    "street_address",
    "suburb",
    "state",
    "start_datetime",
    "end_datetime",
    "ticket_price",
    "ticket_capacity",
    "vegetarian",
    "vegan",
    "gluten_free",
    "halal",
    "accessibility",
    "acknowledgement_type",
    "traditional_custodians",
    "acknowledgement_source",
    "acknowledgement_text",
)


# Prepare the acknowledgement text before saving.
def set_acknowledgement(event_record):
    if event_record.acknowledgement_type == "none":
        event_record.acknowledgement_text = ""
        event_record.traditional_custodians = ""
        event_record.acknowledgement_source = ""

    elif event_record.acknowledgement_type == "generic":
        event_record.acknowledgement_text = (
            "We acknowledge the Traditional Custodians of the land "
            "on which this event takes place and their continuing "
            "connection to Country. We pay our respects to Elders "
            "past and present."
        )
        event_record.traditional_custodians = ""
        event_record.acknowledgement_source = ""


@main_bp.route('/create-event', methods=['GET', 'POST'])
@login_required
def create_event():
    form = EventForm()

    # Load available categories from the database.
    categories = db.session.scalars(
        db.select(Category).order_by(Category.name)
    ).all()

    form.category_id.choices = [
        (0, "Select a category")
    ] + [
        (category.id, category.name)
        for category in categories
    ]

    if form.validate_on_submit():
        # A new event needs an image.
        upload = form.image.data

        if upload is None or not upload.filename:
            form.image.errors.append("Choose an image for your event.")
            return render_template('create-event.html', form=form)

        # Limit individual images to 5 MB.
        image_data = upload.read(5 * 1024 * 1024 + 1)

        if not image_data:
            form.image.errors.append("The image file is empty.")
            return render_template('create-event.html', form=form)

        if len(image_data) > 5 * 1024 * 1024:
            form.image.errors.append("Choose an image smaller than 5 MB.")
            return render_template('create-event.html', form=form)

        # Use a generated filename to avoid overwriting other images.
        extension = Path(upload.filename).suffix.lower()
        filename = f"{uuid4().hex}{extension}"

        upload_folder = (
            Path(current_app.root_path) / "static" / "uploads"
        )
        image_path = upload_folder / filename

        event_record = Event()

        for field_name in EVENT_FORM_FIELDS:
            value = getattr(form, field_name).data
            setattr(event_record, field_name, value)

        # Ownership comes from the login session, never a form field.
        event_record.creator_id = current_user.id
        event_record.is_cancelled = False
        event_record.image_filename = f"uploads/{filename}"

        set_acknowledgement(event_record)

        try:
            upload_folder.mkdir(parents=True, exist_ok=True)
            image_path.write_bytes(image_data)

            db.session.add(event_record)
            db.session.commit()

        except (OSError, SQLAlchemyError):
            db.session.rollback()
            current_app.logger.exception("Could not create event.")

            # Remove the uploaded file if saving the event failed.
            try:
                image_path.unlink(missing_ok=True)
            except OSError:
                current_app.logger.exception(
                    "Could not remove the unused event image."
                )

            flash("Your event could not be saved. Please try again.")
            return render_template('create-event.html', form=form), 500

        flash("Your event has been created.")
        return redirect(url_for('main.create_event'))

    return render_template('create-event.html', form=form)


@main_bp.route('/bookings')
def bookings():
    return render_template('bookings.html')
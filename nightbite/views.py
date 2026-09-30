from pathlib import Path
from uuid import uuid4

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy.exc import SQLAlchemyError

from . import db
from .forms import EventForm, CancelEventForm
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
        return redirect(url_for('main.my_events'))

    return render_template('create-event.html', form=form)


@main_bp.route('/bookings')
def bookings():
    return render_template('bookings.html')

# List only the events belonging to the signed-in creator.
@main_bp.route('/my-events')
@login_required
def my_events():
    events = db.session.scalars(
        db.select(Event).where(Event.creator_id == current_user.id)
        .order_by(Event.start_datetime.desc())
    ).all()
    return render_template('my-events.html', events=events)


# Check ownership on the server for both viewing and submitting forms.
def owned_event(event_id):
    event_record = db.get_or_404(Event, event_id)
    if event_record.creator_id != current_user.id:
        abort(403)
    return event_record


@main_bp.route('/events/<int:event_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_event(event_id):
    event_record = owned_event(event_id)
    form = EventForm(obj=event_record)
    categories = db.session.scalars(
        db.select(Category).order_by(Category.name)
    ).all()
    form.category_id.choices = [(0, "Select a category")] + [
        (category.id, category.name) for category in categories
    ]

    if form.validate_on_submit():
        if form.ticket_capacity.data < event_record.tickets_sold:
            form.ticket_capacity.errors.append(
                "Capacity cannot be lower than the number of tickets already booked."
            )
            return render_template('create-event.html', form=form, event_record=event_record)

        # Keep the existing image unless a replacement is uploaded.
        upload = form.image.data
        image_path = None
        image_data = None
        if upload and upload.filename:
            image_data = upload.read(5 * 1024 * 1024 + 1)
            if not image_data or len(image_data) > 5 * 1024 * 1024:
                form.image.errors.append("Choose a non-empty image up to 5 MB.")
                return render_template('create-event.html', form=form, event_record=event_record)
            filename = f"{uuid4().hex}{Path(upload.filename).suffix.lower()}"
            image_path = Path(current_app.root_path) / 'static' / 'uploads' / filename

        try:
            for field_name in EVENT_FORM_FIELDS:
                setattr(event_record, field_name, getattr(form, field_name).data)
            set_acknowledgement(event_record)
            if image_path is not None:
                image_path.parent.mkdir(parents=True, exist_ok=True)
                image_path.write_bytes(image_data)
                event_record.image_filename = f"uploads/{filename}"
            db.session.commit()
        except (OSError, SQLAlchemyError):
            db.session.rollback()
            current_app.logger.exception("Could not update event.")
            if image_path is not None:
                try:
                    image_path.unlink(missing_ok=True)
                except OSError:
                    current_app.logger.exception("Could not remove unused image.")
            flash("Your changes could not be saved. Please try again.")
            return render_template('create-event.html', form=form, event_record=event_record), 500

        flash("Your event has been updated.")
        return redirect(url_for('main.my_events'))

    return render_template('create-event.html', form=form, event_record=event_record)


# Cancellation requires a confirmed POST and keeps bookings/comments intact.
@main_bp.route('/events/<int:event_id>/cancel', methods=['GET', 'POST'])
@login_required
def cancel_event(event_id):
    event_record = owned_event(event_id)
    form = CancelEventForm()
    if form.validate_on_submit():
        event_record.is_cancelled = True
        try:
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception("Could not cancel event.")
            flash("The event could not be cancelled. Please try again.")
            return render_template('cancel-event.html', event_record=event_record, form=form), 500
        flash("Event cancelled. Existing bookings have been retained.")
        return redirect(url_for('main.my_events'))
    return render_template('cancel-event.html', event_record=event_record, form=form)


# Public research guidance for event acknowledgements.
@main_bp.route('/acknowledgement-guide')
def acknowledgement_guide():
    return render_template('acknowledgement-guide.html')

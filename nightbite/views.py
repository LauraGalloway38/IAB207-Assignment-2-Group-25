from pathlib import Path
from uuid import uuid4

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy.exc import SQLAlchemyError

from . import db
from .forms import EventForm, CancelEventForm
from .models import Category, Event
from sqlalchemy import or_
from datetime import datetime, timedelta


main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    selected_category = request.args.get('category', type=int)
    search_query = request.args.get('q', '').strip()
    selected_location = request.args.get('location', '').strip()
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()

    event_query = db.select(Event)

    # Category filter
    if selected_category is not None:
        event_query = event_query.where(
            Event.category_id == selected_category
        )

    # Keyword search
    if search_query:
        search_term = f'%{search_query}%'

        event_query = event_query.where(
            or_(
                Event.title.ilike(search_term),
                Event.description.ilike(search_term),
                Event.cuisine.ilike(search_term),
                Event.venue.ilike(search_term),
                Event.suburb.ilike(search_term),
            )
        )

    # Location filter
    if selected_location:
        event_query = event_query.where(
            Event.suburb == selected_location
        )

    # Start date filter
    if date_from:
        try:
            start_date = datetime.strptime(
                date_from,
                '%Y-%m-%d'
            )

            event_query = event_query.where(
                Event.start_datetime >= start_date
            )

        except ValueError:
            pass

    # End date filter
    if date_to:
        try:
            end_date = datetime.strptime(
                date_to,
                '%Y-%m-%d'
            )

            # Include the entire selected final day
            end_date = end_date + timedelta(days=1)

            event_query = event_query.where(
                Event.start_datetime < end_date
            )

        except ValueError:
            pass

    # Get all matching events in chronological order
    events = db.session.scalars(
        event_query.order_by(Event.start_datetime.asc())
    ).all()

    # Check whether the user is searching or filtering
    has_filters = bool(
        search_query
        or selected_location
        or date_from
        or date_to
        or selected_category is not None
    )

    # On the normal homepage, place upcoming Open events first.
    # Past, sold out and cancelled events are retained for "View all".
    if not has_filters:
        featured_events = [
            event
            for event in events
            if event.status == 'Open'
            and event.remaining_tickets > 0
        ]

        other_events = [
            event
            for event in events
            if event not in featured_events
        ]

        events = featured_events + other_events

    # Categories
    categories = db.session.scalars(
        db.select(Category)
        .order_by(Category.name.asc())
    ).all()

    # Available suburbs
    locations = db.session.scalars(
        db.select(Event.suburb)
        .distinct()
        .order_by(Event.suburb.asc())
    ).all()

    return render_template(
        'index.html',
        events=events,
        categories=categories,
        locations=locations,
        selected_category=selected_category,
        search_query=search_query,
        selected_location=selected_location,
        date_from=date_from,
        date_to=date_to,
        has_filters=has_filters
    )


@main_bp.route('/event/<int:event_id>')
def event(event_id):
    event = db.get_or_404(Event, event_id)

    # Get every other event so the current event is never
    # recommended to itself.
    other_events = db.session.scalars(
        db.select(Event)
        .where(Event.id != event.id)
    ).all()

    # Only recommend events that can still reasonably be attended.
    other_events = [
        candidate
        for candidate in other_events
        if candidate.status == 'Open'
    ]

    recommendations = []

    for candidate in other_events:
        score = 0
        reasons = []

        # Same food-event category
        if (
            event.category_id is not None
            and candidate.category_id == event.category_id
        ):
            score += 4
            reasons.append('Similar event type')

        # Same cuisine
        if (
            event.cuisine
            and candidate.cuisine
            and event.cuisine.lower() == candidate.cuisine.lower()
        ):
            score += 3
            reasons.append('Similar cuisine')

        # Same suburb
        if (
            event.suburb
            and candidate.suburb
            and event.suburb.lower() == candidate.suburb.lower()
        ):
            score += 2
            reasons.append('Same area')

        # Matching dietary options
        dietary_matches = 0

        if event.vegetarian and candidate.vegetarian:
            dietary_matches += 1

        if event.vegan and candidate.vegan:
            dietary_matches += 1

        if event.gluten_free and candidate.gluten_free:
            dietary_matches += 1

        if event.halal and candidate.halal:
            dietary_matches += 1

        if dietary_matches > 0:
            score += dietary_matches
            reasons.append('Matching dietary options')

        # Similar ticket price
        if (
            event.ticket_price is not None
            and candidate.ticket_price is not None
        ):
            price_difference = abs(
                float(event.ticket_price)
                - float(candidate.ticket_price)
            )

            if price_difference <= 10:
                score += 1
                reasons.append('Similar price')

        recommendations.append({
            'event': candidate,
            'score': score,
            'reasons': reasons
        })

    # Highest recommendation score first.
    # Start date provides a consistent tie-breaker.
    recommendations.sort(
        key=lambda item: (
            -item['score'],
            item['event'].start_datetime
        )
    )

    return render_template(
        'event.html',
        event=event,
        recommendations=recommendations
    )


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
@login_required
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

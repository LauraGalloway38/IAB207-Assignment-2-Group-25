import secrets
import string
from datetime import datetime, timedelta, timezone
from decimal import Decimal
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
from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError

from . import db
from .forms import (
    BookingForm,
    CancelEventForm,
    CommentForm,
    EventForm,
)
from .models import Category, Comment, Event, Order


main_bp = Blueprint('main', __name__)


# =========================================================
# SHARED HELPERS
# =========================================================

def brisbane_now():
    """Return the current Brisbane time as a naive datetime."""
    return datetime.now(
        timezone(timedelta(hours=10))
    ).replace(tzinfo=None)


def generate_order_reference():
    """Return a unique human-readable NIGHTBITE order reference."""

    for _ in range(20):
        reference = 'NB-' + ''.join(
            secrets.choice(string.digits)
            for _ in range(6)
        )

        taken = db.session.scalar(
            db.select(Order.id).where(
                Order.order_reference == reference
            )
        )

        if taken is None:
            return reference

    raise RuntimeError(
        'Could not generate a unique order reference.'
    )


def login_redirect(event_id, message):
    """Send unauthenticated users to login and back to the event."""

    flash(message, 'info')

    return redirect(
        url_for(
            'auth.login',
            next=url_for(
                'main.event',
                event_id=event_id
            )
        )
    )


def build_recommendations(event_record):
    """Create related-event recommendations for an event."""

    other_events = db.session.scalars(
        db.select(Event)
        .where(Event.id != event_record.id)
    ).all()

    # Only recommend events that are currently bookable.
    other_events = [
        candidate
        for candidate in other_events
        if 'Open' == candidate.status
    ]

    recommendations = []

    for candidate in other_events:
        score = 0
        reasons = []

        # Same food-event category
        if (
            event_record.category_id is not None
            and candidate.category_id == event_record.category_id
        ):
            score += 4
            reasons.append('Similar event type')

        # Same cuisine
        if (
            event_record.cuisine
            and candidate.cuisine
            and event_record.cuisine.lower()
            == candidate.cuisine.lower()
        ):
            score += 3
            reasons.append('Similar cuisine')

        # Same suburb
        if (
            event_record.suburb
            and candidate.suburb
            and event_record.suburb.lower()
            == candidate.suburb.lower()
        ):
            score += 2
            reasons.append('Same area')

        # Matching dietary options
        dietary_matches = 0

        if event_record.vegetarian and candidate.vegetarian:
            dietary_matches += 1

        if event_record.vegan and candidate.vegan:
            dietary_matches += 1

        if event_record.gluten_free and candidate.gluten_free:
            dietary_matches += 1

        if event_record.halal and candidate.halal:
            dietary_matches += 1

        if dietary_matches > 0:
            score += dietary_matches
            reasons.append('Matching dietary options')

        # Similar ticket price
        if (
            event_record.ticket_price is not None
            and candidate.ticket_price is not None
        ):
            price_difference = abs(
                event_record.ticket_price
                - candidate.ticket_price
            )

            if price_difference <= 10:
                score += 1
                reasons.append('Similar price')

        recommendations.append({
            'event': candidate,
            'score': score,
            'reasons': reasons,
        })

    recommendations.sort(
        key=lambda item: (
            -item['score'],
            item['event'].start_datetime,
        )
    )

    return recommendations


def render_event_page(
    event_record,
    comment_form=None,
    booking_form=None,
    status_code=200,
):
    """
    Render the event page with Laura's recommendations and
    Jack's comments/booking forms.
    """

    comments = db.session.scalars(
        db.select(Comment)
        .where(Comment.event_id == event_record.id)
        .order_by(
            Comment.posted_datetime.desc(),
            Comment.id.desc(),
        )
    ).all()

    recommendations = build_recommendations(event_record)

    return render_template(
        'event.html',
        event=event_record,
        recommendations=recommendations,
        comments=comments,
        comment_form=comment_form or CommentForm(formdata=None),
        booking_form=booking_form or BookingForm(formdata=None),
    ), status_code


# =========================================================
# BROWSING AND DISCOVERY
# =========================================================

@main_bp.route('/')
def index():
    selected_category = request.args.get(
        'category',
        type=int
    )

    search_query = request.args.get(
        'q',
        ''
    ).strip()

    selected_location = request.args.get(
        'location',
        ''
    ).strip()

    date_from = request.args.get(
        'date_from',
        ''
    ).strip()

    date_to = request.args.get(
        'date_to',
        ''
    ).strip()

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
        event_query.order_by(
            Event.start_datetime.asc()
        )
    ).all()

    # Check whether the user is searching or filtering
    has_filters = bool(
        search_query
        or selected_location
        or date_from
        or date_to
        or selected_category is not None
    )

    # Normal homepage:
    # Open events with tickets appear first.
    # Past/sold-out/cancelled events remain available through View All.
    if not has_filters:
        featured_events = [
            event
            for event in events
            if 'Open' == event.status
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
        has_filters=has_filters,
    )


# =========================================================
# EVENT DETAILS, RECOMMENDATIONS, COMMENTS AND BOOKINGS
# =========================================================

@main_bp.route('/event')
@main_bp.route('/event/<int:event_id>')
def event(event_id=None):

    if event_id is None:
        event_record = db.session.scalar(
            db.select(Event)
            .order_by(Event.start_datetime.asc())
        )

        if event_record is None:
            return index()

        return render_event_page(event_record)

    event_record = db.get_or_404(
        Event,
        event_id
    )

    return render_event_page(event_record)


@main_bp.post('/event/<int:event_id>/comment')
def post_comment(event_id):
    event_record = db.get_or_404(
        Event,
        event_id
    )

    if not current_user.is_authenticated:
        return login_redirect(
            event_id,
            'Please sign in to post a comment.'
        )

    form = CommentForm()

    if not form.validate_on_submit():
        return render_event_page(
            event_record,
            comment_form=form,
        )

    comment = Comment(
        user_id=current_user.id,
        event_id=event_record.id,
        comment_text=form.comment_text.data,
        posted_datetime=brisbane_now(),
    )

    try:
        db.session.add(comment)
        db.session.commit()

    except SQLAlchemyError:
        db.session.rollback()

        current_app.logger.exception(
            'Could not save comment.'
        )

        flash(
            'Your comment could not be saved. '
            'Please try again.',
            'danger',
        )

        return render_event_page(
            db.get_or_404(Event, event_id),
            comment_form=form,
            status_code=500,
        )

    flash(
        'Your comment has been posted.',
        'success'
    )

    return redirect(
        url_for(
            'main.event',
            event_id=event_id
        ) + '#comments'
    )


@main_bp.post('/event/<int:event_id>/book')
def book_event(event_id):
    event_record = db.get_or_404(
        Event,
        event_id
    )

    if not current_user.is_authenticated:
        return login_redirect(
            event_id,
            'Please sign in to book tickets.'
        )

    form = BookingForm()

    if not form.validate_on_submit():
        return render_event_page(
            event_record,
            booking_form=form,
        )

    quantity = form.quantity.data

    # Status and availability are calculated from current database values.
    if event_record.status != 'Open':
        form.quantity.errors.append(
            f'This event is '
            f'{event_record.status.lower()} '
            f'and cannot be booked.'
        )

        return render_event_page(
            event_record,
            booking_form=form,
        )

    remaining = event_record.remaining_tickets

    if quantity > remaining:
        form.quantity.errors.append(
            f"Only {remaining} "
            f"ticket{'' if remaining == 1 else 's'} "
            f"remaining."
        )

        return render_event_page(
            event_record,
            booking_form=form,
        )

    unit_price = Decimal(
        event_record.ticket_price
    ).quantize(
        Decimal('0.01')
    )

    order = Order(
        user_id=current_user.id,
        event_id=event_record.id,
        quantity=quantity,
        unit_price=unit_price,
        total_amount=(
            unit_price * quantity
        ).quantize(
            Decimal('0.01')
        ),
        booking_datetime=brisbane_now(),
        order_reference=generate_order_reference(),
    )

    try:
        db.session.add(order)
        db.session.flush()

        # Re-check availability inside the same transaction.
        sold = db.session.scalar(
            db.select(
                db.func.coalesce(
                    db.func.sum(Order.quantity),
                    0,
                )
            )
            .where(
                Order.event_id == event_record.id
            )
        )

        if sold > event_record.ticket_capacity:
            db.session.rollback()

            event_record = db.get_or_404(
                Event,
                event_id
            )

            form.quantity.errors.append(
                'Those tickets have just been booked '
                'by someone else. '
                f'{event_record.remaining_tickets} '
                'remaining.'
            )

            return render_event_page(
                event_record,
                booking_form=form,
            )

        db.session.commit()

    except SQLAlchemyError:
        db.session.rollback()

        current_app.logger.exception(
            'Could not save booking.'
        )

        flash(
            'Your booking could not be completed. '
            'You have not been charged. '
            'Please try again.',
            'danger',
        )

        return render_event_page(
            db.get_or_404(Event, event_id),
            booking_form=form,
            status_code=500,
        )

    flash(
        f'Booking confirmed! '
        f'Order reference: {order.order_reference}',
        'success',
    )

    return redirect(
        url_for(
            'main.bookings',
            confirmed=order.order_reference,
        )
    )


# =========================================================
# EVENT CREATION AND MANAGEMENT
# =========================================================

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


@main_bp.route(
    '/create-event',
    methods=['GET', 'POST']
)
@login_required
def create_event():
    form = EventForm()

    # Load available categories from the database.
    categories = db.session.scalars(
        db.select(Category).order_by(
            Category.name
        )
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
            form.image.errors.append(
                "Choose an image for your event."
            )

            return render_template(
                'create-event.html',
                form=form,
            )

        # Limit individual images to 5 MB.
        image_data = upload.read(
            5 * 1024 * 1024 + 1
        )

        if not image_data:
            form.image.errors.append(
                "The image file is empty."
            )

            return render_template(
                'create-event.html',
                form=form,
            )

        if len(image_data) > 5 * 1024 * 1024:
            form.image.errors.append(
                "Choose an image smaller than 5 MB."
            )

            return render_template(
                'create-event.html',
                form=form,
            )

        # Use a generated filename to avoid overwriting other images.
        extension = Path(
            upload.filename
        ).suffix.lower()

        filename = (
            f"{uuid4().hex}{extension}"
        )

        upload_folder = (
            Path(current_app.root_path)
            / "static"
            / "uploads"
        )

        image_path = (
            upload_folder / filename
        )

        event_record = Event()

        for field_name in EVENT_FORM_FIELDS:
            value = getattr(
                form,
                field_name
            ).data

            setattr(
                event_record,
                field_name,
                value,
            )

        # Ownership comes from login session.
        event_record.creator_id = (
            current_user.id
        )

        event_record.is_cancelled = False

        event_record.image_filename = (
            f"uploads/{filename}"
        )

        set_acknowledgement(
            event_record
        )

        try:
            upload_folder.mkdir(
                parents=True,
                exist_ok=True,
            )

            image_path.write_bytes(
                image_data
            )

            db.session.add(
                event_record
            )

            db.session.commit()

        except (OSError, SQLAlchemyError):
            db.session.rollback()

            current_app.logger.exception(
                "Could not create event."
            )

            # Remove uploaded file if saving failed.
            try:
                image_path.unlink(
                    missing_ok=True
                )

            except OSError:
                current_app.logger.exception(
                    "Could not remove the unused "
                    "event image."
                )

            flash(
                "Your event could not be saved. "
                "Please try again."
            )

            return render_template(
                'create-event.html',
                form=form,
            ), 500

        flash(
            "Your event has been created."
        )

        return redirect(
            url_for('main.my_events')
        )

    return render_template(
        'create-event.html',
        form=form,
    )


# =========================================================
# BOOKING HISTORY
# =========================================================

@main_bp.route('/bookings')
@login_required
def bookings():
    # Only the signed-in user's orders,
    # newest booking first.
    orders = db.session.scalars(
        db.select(Order)
        .where(
            Order.user_id == current_user.id
        )
        .order_by(
            Order.booking_datetime.desc(),
            Order.id.desc(),
        )
    ).all()

    now = brisbane_now()

    upcoming_ids = {
        order.id
        for order in orders
        if (
            not order.event.is_cancelled
            and order.event.end_datetime > now
        )
    }

    return render_template(
        'bookings.html',
        orders=orders,
        upcoming_ids=upcoming_ids,
        total_tickets=sum(
            order.quantity
            for order in orders
        ),
        upcoming_count=len(
            upcoming_ids
        ),
        confirmed_reference=request.args.get(
            'confirmed'
        ),
    )


# =========================================================
# MY EVENTS
# =========================================================

# List only the events belonging to the signed-in creator.
@main_bp.route('/my-events')
@login_required
def my_events():
    events = db.session.scalars(
        db.select(Event)
        .where(
            Event.creator_id == current_user.id
        )
        .order_by(
            Event.start_datetime.desc()
        )
    ).all()

    return render_template(
        'my-events.html',
        events=events,
    )


# Check ownership on the server for both viewing and submitting forms.
def owned_event(event_id):
    event_record = db.get_or_404(
        Event,
        event_id
    )

    if event_record.creator_id != current_user.id:
        abort(403)

    return event_record


@main_bp.route(
    '/events/<int:event_id>/edit',
    methods=['GET', 'POST'],
)
@login_required
def edit_event(event_id):
    event_record = owned_event(
        event_id
    )

    form = EventForm(
        obj=event_record
    )

    categories = db.session.scalars(
        db.select(Category)
        .order_by(Category.name)
    ).all()

    form.category_id.choices = [
        (0, "Select a category")
    ] + [
        (category.id, category.name)
        for category in categories
    ]

    if form.validate_on_submit():
        if (
            form.ticket_capacity.data
            < event_record.tickets_sold
        ):
            form.ticket_capacity.errors.append(
                "Capacity cannot be lower than "
                "the number of tickets already booked."
            )

            return render_template(
                'create-event.html',
                form=form,
                event_record=event_record,
            )

        # Keep existing image unless replacement uploaded.
        upload = form.image.data
        image_path = None
        image_data = None

        if upload and upload.filename:
            image_data = upload.read(
                5 * 1024 * 1024 + 1
            )

            if (
                not image_data
                or len(image_data)
                > 5 * 1024 * 1024
            ):
                form.image.errors.append(
                    "Choose a non-empty image "
                    "up to 5 MB."
                )

                return render_template(
                    'create-event.html',
                    form=form,
                    event_record=event_record,
                )

            filename = (
                f"{uuid4().hex}"
                f"{Path(upload.filename).suffix.lower()}"
            )

            image_path = (
                Path(current_app.root_path)
                / 'static'
                / 'uploads'
                / filename
            )

        try:
            for field_name in EVENT_FORM_FIELDS:
                setattr(
                    event_record,
                    field_name,
                    getattr(
                        form,
                        field_name
                    ).data,
                )

            set_acknowledgement(
                event_record
            )

            if image_path is not None:
                image_path.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                image_path.write_bytes(
                    image_data
                )

                event_record.image_filename = (
                    f"uploads/{filename}"
                )

            db.session.commit()

        except (OSError, SQLAlchemyError):
            db.session.rollback()

            current_app.logger.exception(
                "Could not update event."
            )

            if image_path is not None:
                try:
                    image_path.unlink(
                        missing_ok=True
                    )

                except OSError:
                    current_app.logger.exception(
                        "Could not remove unused image."
                    )

            flash(
                "Your changes could not be saved. "
                "Please try again."
            )

            return render_template(
                'create-event.html',
                form=form,
                event_record=event_record,
            ), 500

        flash(
            "Your event has been updated."
        )

        return redirect(
            url_for('main.my_events')
        )

    return render_template(
        'create-event.html',
        form=form,
        event_record=event_record,
    )


# Cancellation requires a confirmed POST
# and keeps bookings/comments intact.
@main_bp.route(
    '/events/<int:event_id>/cancel',
    methods=['GET', 'POST'],
)
@login_required
def cancel_event(event_id):
    event_record = owned_event(
        event_id
    )

    form = CancelEventForm()

    if form.validate_on_submit():
        event_record.is_cancelled = True

        try:
            db.session.commit()

        except SQLAlchemyError:
            db.session.rollback()

            current_app.logger.exception(
                "Could not cancel event."
            )

            flash(
                "The event could not be cancelled. "
                "Please try again."
            )

            return render_template(
                'cancel-event.html',
                event_record=event_record,
                form=form,
            ), 500

        flash(
            "Event cancelled. "
            "Existing bookings have been retained."
        )

        return redirect(
            url_for('main.my_events')
        )

    return render_template(
        'cancel-event.html',
        event_record=event_record,
        form=form,
    )


# =========================================================
# ACKNOWLEDGEMENT GUIDE
# =========================================================

@main_bp.route('/acknowledgement-guide')
def acknowledgement_guide():
    return render_template(
        'acknowledgement-guide.html'
    )
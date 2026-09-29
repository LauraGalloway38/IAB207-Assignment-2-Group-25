import secrets
import string
from datetime import datetime

from flask import Blueprint, abort, flash, redirect, render_template, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import SQLAlchemyError

from . import db
from .forms import BookingForm, CommentForm
from .models import Comment, Event, Order

main_bp = Blueprint('main', __name__)


def generate_order_reference():
    """Return a unique human-readable reference such as NB-482913."""
    while True:
        reference = 'NB-' + ''.join(secrets.choice(string.digits) for _ in range(6))
        existing = db.session.scalar(
            db.select(Order).where(Order.order_reference == reference)
        )
        if existing is None:
            return reference


def get_event_or_404(event_id):
    """Load an Event by id, or abort with 404 when it does not exist."""
    event_record = db.session.get(Event, event_id)
    if event_record is None:
        abort(404)
    return event_record


@main_bp.route('/')
def index():
    # Laura owns database-driven browsing/search; the homepage stays as it is
    # until her work is merged.
    return render_template('index.html')


@main_bp.route('/event', defaults={'event_id': None})
@main_bp.route('/event/<int:event_id>')
def event(event_id):
    """Event details page.

    /event (no id) is kept temporarily so Laura's current static homepage
    links keep working. Once her event cards pass event_id this can go.
    """
    if event_id is None:
        event_record = db.session.scalar(db.select(Event).order_by(Event.id))
        if event_record is None:
            abort(404)
    else:
        event_record = get_event_or_404(event_id)

    comments = db.session.scalars(
        db.select(Comment)
        .where(Comment.event_id == event_record.id)
        .order_by(Comment.posted_datetime.desc(), Comment.id.desc())
    ).all()

    return render_template(
        'event.html',
        event=event_record,
        comments=comments,
        comment_form=CommentForm(),
        booking_form=BookingForm(),
    )


@main_bp.route('/event/<int:event_id>/comment', methods=['POST'])
@login_required
def post_comment(event_id):
    """Create a comment for an event. The user id always comes from the
    session (current_user), never from the submitted form."""
    event_record = get_event_or_404(event_id)

    form = CommentForm()
    if not form.validate_on_submit():
        for errors in form.errors.values():
            for error in errors:
                flash(error)
        return redirect(url_for('main.event', event_id=event_record.id))

    comment_text = form.comment_text.data.strip()
    if not comment_text:
        flash('Please enter a comment.')
        return redirect(url_for('main.event', event_id=event_record.id))

    comment = Comment(
        user_id=current_user.id,
        event_id=event_record.id,
        comment_text=comment_text,
        posted_datetime=datetime.now(),
    )

    try:
        db.session.add(comment)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        flash('Your comment could not be saved. Please try again.')
        return redirect(url_for('main.event', event_id=event_record.id))

    flash('Your comment has been posted.')
    return redirect(url_for('main.event', event_id=event_record.id))


@main_bp.route('/event/<int:event_id>/book', methods=['POST'])
@login_required
def book_event(event_id):
    """Create a ticket Order after re-checking availability in the database.

    The page the user is looking at may be minutes out of date, so the
    quantity is validated against event.remaining_tickets here, server side.
    This route never writes to the Event: status and remaining_tickets are
    calculated by Aarnav's Event model from Order rows.
    """
    event_record = get_event_or_404(event_id)

    form = BookingForm()
    if not form.validate_on_submit():
        for errors in form.errors.values():
            for error in errors:
                flash(error)
        return redirect(url_for('main.event', event_id=event_record.id))

    quantity = form.quantity.data

    if event_record.status != 'Open':
        messages = {
            'Cancelled': 'This event has been cancelled and cannot be booked.',
            'Inactive': 'This event has already finished.',
            'Sold Out': 'This event is sold out.',
        }
        flash(messages.get(event_record.status, 'This event is not open for bookings.'))
        return redirect(url_for('main.event', event_id=event_record.id))

    remaining = event_record.remaining_tickets
    if remaining <= 0:
        flash('This event is sold out.')
        return redirect(url_for('main.event', event_id=event_record.id))

    if quantity > remaining:
        flash(f'Only {remaining} ticket(s) remaining for this event.')
        return redirect(url_for('main.event', event_id=event_record.id))

    unit_price = event_record.ticket_price
    order = Order(
        user_id=current_user.id,
        event_id=event_record.id,
        quantity=quantity,
        unit_price=unit_price,
        total_amount=unit_price * quantity,
        booking_datetime=datetime.now(),
        order_reference=generate_order_reference(),
    )

    try:
        db.session.add(order)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        flash('Your booking could not be completed. Please try again.')
        return redirect(url_for('main.event', event_id=event_record.id))

    flash(f'Booking confirmed. Your order reference is {order.order_reference}.')
    return redirect(url_for('main.bookings'))


@main_bp.route('/create-event')
def create_event():
    # Aarnav's event creation feature.
    return render_template('create-event.html')


@main_bp.route('/bookings')
@login_required
def bookings():
    """Signed-in user's own order history, newest first."""
    user_orders = db.session.scalars(
        db.select(Order)
        .where(Order.user_id == current_user.id)
        .order_by(Order.booking_datetime.desc(), Order.id.desc())
    ).all()

    total_tickets = sum(order.quantity for order in user_orders)

    # "Upcoming" means the event has not finished and has not been cancelled.
    # A sold out event in the future is still upcoming.
    now = datetime.now()
    upcoming_count = sum(
        1
        for order in user_orders
        if order.event.end_datetime >= now and not order.event.is_cancelled
    )

    return render_template(
        'bookings.html',
        orders=user_orders,
        total_tickets=total_tickets,
        upcoming_count=upcoming_count,
    )

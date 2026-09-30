from flask import Blueprint, render_template
from flask_login import login_required

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    return render_template('index.html')


@main_bp.route('/event')
def event():
    return render_template('event.html')


@main_bp.route('/create-event')
@login_required
def create_event():
    return render_template('create-event.html')


@main_bp.route('/bookings')
@login_required
def bookings():
    return render_template('bookings.html')
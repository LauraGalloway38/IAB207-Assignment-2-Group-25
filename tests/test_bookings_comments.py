"""Jack's bookings and comments tests.

Every test uses an in-memory SQLite database and real Flask-WTF CSRF tokens.
Test method numbers match the integration checklist (1-99; 100 is the full run).
"""
import io
import re
import tempfile
import unittest
from datetime import datetime, timedelta
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from werkzeug.security import generate_password_hash

from nightbite import create_app, db
from nightbite import views
from nightbite.models import Category, Comment, Event, Order, User

PACKAGE_DIR = Path(views.__file__).resolve().parent
REAL_DB = PACKAGE_DIR / 'sitedata.sqlite'
PASSWORD = 'Test-password-123'
_REAL_DB_STATE = None


def db_file_state():
    return (REAL_DB.exists(), REAL_DB.stat().st_mtime if REAL_DB.exists() else None)


def setUpModule():
    global _REAL_DB_STATE
    _REAL_DB_STATE = db_file_state()


class TagBalance(HTMLParser):
    """Counts structural open/close tags to catch stray or missing tags."""
    TRACKED = {'html', 'head', 'body', 'main', 'div', 'section', 'article', 'aside', 'form', 'header', 'nav', 'footer'}

    def __init__(self):
        super().__init__()
        self.depth = {tag: 0 for tag in self.TRACKED}
        self.negative = []

    def handle_starttag(self, tag, attrs):
        if tag in self.TRACKED:
            self.depth[tag] += 1

    def handle_endtag(self, tag):
        if tag in self.TRACKED:
            self.depth[tag] -= 1
            if self.depth[tag] < 0:
                self.negative.append(tag)


class NightbiteTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app({'TESTING': True, 'SECRET_KEY': 'test-only-key',
                               'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:'})
        # Keep uploaded test images out of the project folder.
        self.files = tempfile.TemporaryDirectory()
        self.app.template_folder = str(PACKAGE_DIR / 'templates')
        self.app.root_path = self.files.name
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
            users = [User(name=name, email=email, contact_number='0400123456',
                          street_address='1 Test Street', password_hash=generate_password_hash(PASSWORD))
                     for name, email in [('Olive Owner', 'owner@example.com'),
                                         ('Alice Booker', 'alice@example.com'),
                                         ('Bob Other', 'bob@example.com')]]
            category = Category(name='Night Markets')
            db.session.add_all(users + [category])
            db.session.commit()
            self.owner_id, self.alice_id, self.bob_id = (user.id for user in users)
            self.category_id = category.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        self.files.cleanup()

    # ---------- helpers ----------
    def make_event(self, **overrides):
        start = datetime.now() + timedelta(days=30)
        values = dict(title='Riverside Test Bites', description='A test food event.',
                      image_filename='img/night-market.jpeg', venue='Test Venue',
                      street_address='2 Event Street', suburb='South Brisbane', state='QLD',
                      start_datetime=start, end_datetime=start + timedelta(hours=4),
                      cuisine='Street food', ticket_price=Decimal('12.34'), ticket_capacity=5,
                      creator_id=self.owner_id, category_id=self.category_id)
        values.update(overrides)
        with self.app.app_context():
            event = Event(**values)
            db.session.add(event)
            db.session.commit()
            return event.id

    def add_order(self, event_id, user_id=None, quantity=1, reference=None, booked=None):
        with self.app.app_context():
            event = db.session.get(Event, event_id)
            order = Order(user_id=user_id or self.alice_id, event_id=event_id, quantity=quantity,
                          unit_price=event.ticket_price, total_amount=event.ticket_price * quantity,
                          order_reference=reference or f'NB-T{event_id}{quantity}{datetime.now().microsecond}',
                          booking_datetime=booked or datetime.now())
            db.session.add(order)
            db.session.commit()
            return order.id

    def add_comment(self, event_id, text, user_id=None, posted=None):
        with self.app.app_context():
            db.session.add(Comment(user_id=user_id or self.alice_id, event_id=event_id,
                                   comment_text=text, posted_datetime=posted or datetime.now()))
            db.session.commit()

    def token(self, path=None):
        for candidate in [path, '/', '/login']:
            if not candidate:
                continue
            page = self.client.get(candidate)
            match = re.search(rb'name="csrf_token"[^>]*value="([^"]+)"', page.data)
            if match:
                return match.group(1).decode()
        raise AssertionError('No CSRF token found')

    def login(self, email='alice@example.com', path='/login'):
        response = self.client.post(path, data={'email': email, 'password': PASSWORD,
                                                'csrf_token': self.token('/login')})
        self.assertEqual(response.status_code, 302)
        return response

    def logout(self):
        with self.client.session_transaction() as session:
            session.clear()

    def book(self, event_id, quantity='1', **extra):
        data = {'csrf_token': self.token(f'/event/{event_id}'), **extra}
        if quantity is not None:
            data['quantity'] = quantity
        return self.client.post(f'/event/{event_id}/book', data=data)

    def comment(self, event_id, text):
        return self.client.post(f'/event/{event_id}/comment',
                                data={'comment_text': text, 'csrf_token': self.token(f'/event/{event_id}')})

    def orders(self):
        with self.app.app_context():
            return db.session.scalars(db.select(Order).order_by(Order.id)).all()

    def comments(self):
        with self.app.app_context():
            return db.session.scalars(db.select(Comment).order_by(Comment.id)).all()

    def event(self, event_id):
        with self.app.app_context():
            event = db.session.get(Event, event_id)
            return dict(remaining=event.remaining_tickets, status=event.status,
                        sold=event.tickets_sold, capacity=event.ticket_capacity,
                        orders=len(event.orders), comments=len(event.comments))

    def booked_order(self, quantity='3', event_price=Decimal('12.34'), **extra):
        event_id = self.make_event(ticket_price=event_price)
        self.login()
        response = self.book(event_id, quantity, **extra)
        self.assertEqual(response.status_code, 302, response.data[:400])
        orders = self.orders()
        self.assertEqual(len(orders), 1)
        return event_id, orders[0]


class BookingTests(NightbiteTestCase):
    def test_001_logged_out_user_cannot_book(self):
        event_id = self.make_event()
        response = self.book(event_id, '1')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, f'/login?next=/event/{event_id}')
        self.assertEqual(self.orders(), [])

    def test_002_login_redirect_returns_to_event_page(self):
        event_id = self.make_event()
        location = self.book(event_id, '1').location
        self.assertEqual(location, f'/login?next=/event/{event_id}')
        self.assertEqual(self.login(path=location).location, f'/event/{event_id}')
        self.assertEqual(self.client.get(f'/event/{event_id}').status_code, 200)

    def test_003_valid_open_event_can_be_booked(self):
        event_id = self.make_event()
        self.assertEqual(self.event(event_id)['status'], 'Open')
        self.login()
        response = self.book(event_id, '2')
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.startswith('/bookings?confirmed=NB-'))
        self.assertIn(b'Booking confirmed! Order reference: NB-', self.client.get(response.location).data)

    def test_004_quantity_one_succeeds(self):
        _, order = self.booked_order('1')
        self.assertEqual(order.quantity, 1)

    def test_005_multiple_ticket_quantity_succeeds(self):
        event_id, order = self.booked_order('4')
        self.assertEqual(order.quantity, 4)
        self.assertEqual(self.event(event_id)['remaining'], 1)

    def assert_rejected(self, quantity, message):
        event_id = self.make_event()
        self.login()
        response = self.book(event_id, quantity)
        self.assertEqual(response.status_code, 200)
        self.assertIn(message, response.data)
        self.assertEqual(self.orders(), [])

    def test_006_quantity_zero_rejected(self):
        self.assert_rejected('0', b'Choose between 1 and 10 tickets.')

    def test_007_negative_quantity_rejected(self):
        self.assert_rejected('-2', b'Choose between 1 and 10 tickets.')

    def test_008_missing_quantity_rejected(self):
        self.assert_rejected(None, b'Choose how many tickets to book.')

    def test_009_non_integer_quantity_rejected(self):
        for value in ['abc', '2.5', '']:
            with self.subTest(value=value):
                self.assert_rejected(value, b'invalid-feedback')
                self.tearDown()
                self.setUp()

    def test_010_quantity_above_remaining_rejected(self):
        event_id = self.make_event(ticket_capacity=5)
        self.add_order(event_id, self.bob_id, 3)
        self.login()
        response = self.book(event_id, '3')
        self.assertIn(b'Only 2 tickets remaining.', response.data)
        self.assertEqual(len(self.orders()), 1)

    def book_final(self):
        event_id = self.make_event(ticket_capacity=5)
        self.add_order(event_id, self.bob_id, 2)
        self.login()
        response = self.book(event_id, '3')
        self.assertEqual(response.status_code, 302)
        return event_id

    def test_011_quantity_equal_to_remaining_succeeds(self):
        self.book_final()
        self.assertEqual(len(self.orders()), 2)

    def test_012_final_ticket_makes_remaining_zero(self):
        self.assertEqual(self.event(self.book_final())['remaining'], 0)

    def test_013_final_ticket_makes_event_sold_out(self):
        event_id = self.book_final()
        self.assertEqual(self.event(event_id)['status'], 'Sold Out')
        self.assertIn(b'This event is sold out.', self.client.get(f'/event/{event_id}').data)

    def test_014_booking_sold_out_event_rejected(self):
        event_id = self.book_final()
        response = self.book(event_id, '1')
        self.assertIn(b'This event is sold out and cannot be booked.', response.data)
        self.assertEqual(len(self.orders()), 2)

    def test_015_cancelled_event_cannot_be_booked(self):
        event_id = self.make_event(is_cancelled=True)
        self.login()
        response = self.book(event_id, '1')
        self.assertIn(b'This event is cancelled and cannot be booked.', response.data)
        self.assertEqual(self.orders(), [])

    def test_016_inactive_past_event_cannot_be_booked(self):
        start = datetime.now() - timedelta(days=10)
        event_id = self.make_event(start_datetime=start, end_datetime=start + timedelta(hours=3))
        self.assertEqual(self.event(event_id)['status'], 'Inactive')
        self.login()
        response = self.book(event_id, '1')
        self.assertIn(b'This event is inactive and cannot be booked.', response.data)
        self.assertEqual(self.orders(), [])

    def test_017_successful_booking_creates_exactly_one_order(self):
        self.booked_order('2')

    def test_018_order_user_is_current_user(self):
        self.assertEqual(self.booked_order()[1].user_id, self.alice_id)

    def test_019_order_event_is_correct_event(self):
        self.make_event(title='Decoy event')
        event_id, order = self.booked_order()
        self.assertEqual(order.event_id, event_id)

    def test_020_order_quantity_correct(self):
        self.assertEqual(self.booked_order('3')[1].quantity, 3)

    def test_021_unit_price_copied_from_event(self):
        order = self.booked_order(event_price=Decimal('19.95'))[1]
        self.assertEqual(order.unit_price, Decimal('19.95'))
        self.assertIsInstance(order.unit_price, Decimal)

    def test_022_total_is_unit_price_times_quantity_decimal(self):
        order = self.booked_order('4', event_price=Decimal('0.10'))[1]
        self.assertIsInstance(order.total_amount, Decimal)
        self.assertEqual(order.total_amount, order.unit_price * order.quantity)
        self.assertEqual(order.total_amount, Decimal('0.40'))

    def test_022b_money_is_decimal_before_database_write(self):
        # SQLite's Numeric round-trip can hide float maths, so inspect values at flush time.
        captured = []

        def capture(session, flush_context, instances):
            captured.extend((type(obj.unit_price), type(obj.total_amount), obj.total_amount)
                            for obj in session.new if isinstance(obj, Order))

        from sqlalchemy import event as sa_event
        sa_event.listen(db.session, 'before_flush', capture)
        try:
            self.booked_order('3', event_price=Decimal('12.34'))
        finally:
            sa_event.remove(db.session, 'before_flush', capture)
        self.assertEqual(captured, [(Decimal, Decimal, Decimal('37.02'))])
        self.assertNotIn('float(', (PACKAGE_DIR / 'views.py').read_text())

    def test_023_decimal_example_12_34_times_3(self):
        order = self.booked_order('3', event_price=Decimal('12.34'))[1]
        self.assertEqual(order.total_amount, Decimal('37.02'))
        self.assertEqual(str(order.total_amount), '37.02')

    def test_024_booking_datetime_populated(self):
        order = self.booked_order()[1]
        self.assertIsInstance(order.booking_datetime, datetime)
        self.assertLess(abs(order.booking_datetime - datetime.now()), timedelta(days=1))

    def test_025_order_reference_populated(self):
        self.assertRegex(self.booked_order()[1].order_reference, r'^NB-\d{6}$')

    def test_026_order_reference_unique(self):
        event_id = self.make_event(ticket_capacity=50)
        self.login()
        for _ in range(8):
            self.assertEqual(self.book(event_id, '1').status_code, 302)
        references = [order.order_reference for order in self.orders()]
        self.assertEqual(len(references), len(set(references)))
        # Generator skips a reference that already exists.
        self.add_order(event_id, reference='NB-111111')
        digits = iter('111111' + '222222')
        with self.app.app_context(), patch.object(views.secrets, 'choice', lambda _: next(digits)):
            self.assertEqual(views.generate_order_reference(), 'NB-222222')
        # The database also enforces uniqueness.
        with self.assertRaises(IntegrityError):
            self.add_order(event_id, reference='NB-111111')

    def test_027_browser_price_ignored(self):
        order = self.booked_order('2', event_price=Decimal('12.34'), unit_price='0.01',
                                  total_amount='0', ticket_price='0.00', price='0')[1]
        self.assertEqual(order.unit_price, Decimal('12.34'))
        self.assertEqual(order.total_amount, Decimal('24.68'))

    def test_028_browser_user_id_ignored(self):
        order = self.booked_order('1', user_id=str(self.bob_id))[1]
        self.assertEqual(order.user_id, self.alice_id)

    def test_029_browser_status_and_availability_ignored(self):
        sold_out = self.make_event(ticket_capacity=2)
        self.add_order(sold_out, self.bob_id, 2)
        small = self.make_event(ticket_capacity=2)
        self.login()
        fake = dict(status='Open', remaining_tickets='999', tickets_available='999',
                    ticket_capacity='999', is_cancelled='false')
        self.assertIn(b'sold out and cannot be booked', self.book(sold_out, '1', **fake).data)
        self.assertIn(b'Only 2 tickets remaining.', self.book(small, '3', **fake).data)
        self.assertEqual(len(self.orders()), 1)
        self.assertEqual(self.event(small)['capacity'], 2)

    def test_030_uses_database_availability_at_post_time(self):
        event_id = self.make_event(ticket_capacity=5)
        self.login()
        page = self.client.get(f'/event/{event_id}')
        self.assertIn(b'5 remaining', page.data)
        token = re.search(rb'name="csrf_token"[^>]*value="([^"]+)"', page.data).group(1).decode()
        self.add_order(event_id, self.bob_id, 4)  # someone else books after page load
        response = self.client.post(f'/event/{event_id}/book', data={'quantity': '3', 'csrf_token': token})
        self.assertIn(b'Only 1 ticket remaining.', response.data)
        self.assertEqual(self.event(event_id)['sold'], 4)

    def test_031_sequential_bookings_cannot_exceed_capacity(self):
        event_id = self.make_event(ticket_capacity=5)
        self.login('alice@example.com')
        self.assertEqual(self.book(event_id, '3').status_code, 302)
        self.logout()
        self.login('bob@example.com')
        self.assertIn(b'Only 2 tickets remaining.', self.book(event_id, '3').data)
        self.assertEqual(self.event(event_id)['sold'], 3)

    def test_031b_post_flush_recheck_blocks_overbooking(self):
        # Simulate a competing order committed between the availability check and insert.
        event_id = self.make_event(ticket_capacity=3)
        self.login()
        original = views.generate_order_reference

        def competing_reference():
            reference = original()
            db.session.add(Order(user_id=self.bob_id, event_id=event_id, quantity=2,
                                 unit_price=Decimal('12.34'), total_amount=Decimal('24.68'),
                                 order_reference='NB-RACE01'))
            db.session.commit()
            return reference

        with patch.object(views, 'generate_order_reference', competing_reference):
            response = self.book(event_id, '2')
        self.assertIn(b'just been booked by someone else', response.data)
        self.assertEqual(self.event(event_id)['sold'], 2)
        self.assertEqual(self.event(event_id)['remaining'], 1)

    def test_032_no_tickets_available_field_mutated(self):
        event_id, _ = self.booked_order('2')
        self.assertFalse(hasattr(Event, 'tickets_available'))
        with self.app.app_context():
            columns = {column.name for column in Event.__table__.columns}
        self.assertNotIn('tickets_available', columns)
        self.assertNotIn('remaining_tickets', columns)
        self.assertEqual(self.event(event_id)['capacity'], 5)

    def test_033_remaining_tickets_derive_from_orders(self):
        event_id = self.make_event(ticket_capacity=10)
        self.add_order(event_id, self.alice_id, 3)
        self.add_order(event_id, self.bob_id, 4)
        self.assertEqual(self.event(event_id)['remaining'], 3)
        self.assertEqual(self.event(event_id)['sold'], 7)

    def test_034_status_is_calculated_by_model(self):
        self.assertIsInstance(Event.__dict__['status'], property)
        self.assertIsInstance(Event.__dict__['remaining_tickets'], property)
        self.assertNotIn('status', {column.name for column in Event.__table__.columns})
        with self.app.app_context():
            event = db.session.get(Event, self.make_event())
            with self.assertRaises(AttributeError):
                event.status = 'Open'
        source = (PACKAGE_DIR / 'views.py').read_text()
        self.assertIsNone(re.search(r'\.status\s*=(?!=)', source))
        self.assertNotIn('remaining_tickets -=', (PACKAGE_DIR / 'views.py').read_text())

    def test_035_database_failure_rolls_back_order(self):
        event_id = self.make_event()
        self.login()
        token = self.token(f'/event/{event_id}')
        with patch.object(db.session, 'commit', side_effect=SQLAlchemyError('simulated')):
            response = self.client.post(f'/event/{event_id}/book', data={'quantity': '2', 'csrf_token': token})
        self.assertEqual(response.status_code, 500)
        self.assertIn(b'Your booking could not be completed', response.data)
        self.assertEqual(self.orders(), [])
        self.assertEqual(self.event(event_id)['remaining'], 5)

    def test_036_booking_without_csrf_rejected(self):
        event_id = self.make_event()
        self.login()
        for data in [{'quantity': '1'}, {'quantity': '1', 'csrf_token': 'forged'}]:
            response = self.client.post(f'/event/{event_id}/book', data=data)
            self.assertEqual(response.status_code, 400)
            self.assertIn(b'Please reload the form', response.data)
        self.assertEqual(self.orders(), [])


class BookingHistoryTests(NightbiteTestCase):
    def history(self):
        response = self.client.get('/bookings')
        self.assertEqual(response.status_code, 200)
        return response.data

    def test_037_bookings_requires_login(self):
        response = self.client.get('/bookings')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login?next=%2Fbookings', response.location)

    def test_038_user_sees_own_orders(self):
        event_id = self.make_event()
        self.add_order(event_id, self.alice_id, 2, 'NB-AAA001')
        self.login('alice@example.com')
        self.assertIn(b'NB-AAA001', self.history())

    def test_039_user_cannot_see_other_users_orders(self):
        event_id = self.make_event()
        self.add_order(event_id, self.alice_id, 2, 'NB-AAA001')
        self.add_order(event_id, self.bob_id, 1, 'NB-BBB001')
        self.login('bob@example.com')
        page = self.history()
        self.assertNotIn(b'NB-AAA001', page)
        self.assertIn(b'NB-BBB001', page)

    def test_040_empty_history_state(self):
        self.login()
        page = self.history()
        self.assertIn(b"You haven't made any bookings yet.", page)
        self.assertEqual(page.count(b'class="booking-card'), 0)

    def one_booking_page(self, **event_overrides):
        event_id = self.make_event(**event_overrides)
        self.add_order(event_id, self.alice_id, 3, 'NB-123456', booked=datetime(2026, 9, 2, 19, 42))
        self.login()
        return event_id, self.history()

    def test_041_displays_order_reference(self):
        self.assertIn(b'NB-123456', self.one_booking_page()[1])

    def test_042_displays_quantity(self):
        self.assertIn(b'3 tickets', self.one_booking_page()[1])

    def test_043_displays_stored_total(self):
        page = self.one_booking_page(ticket_price=Decimal('12.34'))[1]
        self.assertIn(b'$37.02', page)

    def test_044_displays_booking_datetime(self):
        self.assertIn(b'02 Sep 2026, 07:42 PM', self.one_booking_page()[1])

    def test_045_displays_event_title(self):
        self.assertIn(b'<h3>Riverside Test Bites</h3>', self.one_booking_page()[1])

    def test_046_displays_event_date(self):
        start = datetime(2031, 3, 14, 18, 30)
        page = self.one_booking_page(start_datetime=start, end_datetime=start + timedelta(hours=3))[1]
        self.assertIn(b'14 Mar 2031, 06:30 PM', page)

    def test_047_displays_current_event_status(self):
        page = self.one_booking_page(ticket_capacity=3)[1]
        self.assertRegex(page.decode(), r'status-sold">\s*Sold Out')

    def test_048_cancelled_event_order_remains(self):
        event_id = self.make_event()
        self.add_order(event_id, self.alice_id, 2, 'NB-CAN001')
        self.login('owner@example.com')
        self.client.post(f'/events/{event_id}/cancel', data={'csrf_token': self.token()})
        self.assertEqual(self.event(event_id)['status'], 'Cancelled')
        self.logout()
        self.login('alice@example.com')
        page = self.history().decode()
        self.assertIn('NB-CAN001', page)
        self.assertRegex(page, r'status-cancelled">\s*Cancelled')

    def test_049_sold_out_future_booking_is_upcoming(self):
        event_id = self.make_event(ticket_capacity=2)
        self.login()
        self.book(event_id, '2')
        self.assertEqual(self.event(event_id)['status'], 'Sold Out')
        page = self.history().decode()
        self.assertRegex(page, r'status-open">\s*Upcoming')
        self.assertRegex(page, r'summary-number">1</span>\s*<span class="summary-label">Upcoming events')

    def test_050_multiple_orders_render(self):
        for index in range(3):
            self.add_order(self.make_event(title=f'Event {index}'), self.alice_id, index + 1, f'NB-00000{index}')
        self.login()
        page = self.history()
        self.assertEqual(page.count(b'<article class="booking-card'), 3)
        self.assertRegex(page.decode(), r'summary-number">6</span>')

    def test_051_newest_booking_first(self):
        event_id = self.make_event(ticket_capacity=50)
        self.add_order(event_id, self.alice_id, 1, 'NB-OLDEST', booked=datetime(2026, 1, 1))
        self.add_order(event_id, self.alice_id, 1, 'NB-NEWEST', booked=datetime(2026, 3, 1))
        self.add_order(event_id, self.alice_id, 1, 'NB-MIDDLE', booked=datetime(2026, 2, 1))
        self.login()
        page = self.history()
        self.assertLess(page.index(b'NB-NEWEST'), page.index(b'NB-MIDDLE'))
        self.assertLess(page.index(b'NB-MIDDLE'), page.index(b'NB-OLDEST'))


class CommentTests(NightbiteTestCase):
    def test_052_anyone_can_view_comments(self):
        event_id = self.make_event()
        self.add_comment(event_id, 'Are there vegan stalls?')
        page = self.client.get(f'/event/{event_id}')
        self.assertEqual(page.status_code, 200)
        self.assertIn(b'Are there vegan stalls?', page.data)
        self.assertIn(b'to post a comment', page.data)

    def test_053_logged_out_cannot_comment(self):
        event_id = self.make_event()
        response = self.client.post(f'/event/{event_id}/comment',
                                    data={'comment_text': 'Hi', 'csrf_token': self.token('/login')})
        self.assertEqual(response.location, f'/login?next=/event/{event_id}')
        self.assertEqual(self.comments(), [])

    def posted(self, text='Looking forward to it!'):
        event_id = self.make_event()
        self.login()
        response = self.comment(event_id, text)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, f'/event/{event_id}#comments')
        comments = self.comments()
        self.assertEqual(len(comments), 1)
        return event_id, comments[0]

    def test_054_valid_comment_saves(self):
        self.posted()

    def test_055_comment_user_is_current_user(self):
        event_id = self.make_event()
        self.login()
        self.client.post(f'/event/{event_id}/comment', data={
            'comment_text': 'Hi', 'user_id': str(self.bob_id), 'csrf_token': self.token()})
        self.assertEqual(self.comments()[0].user_id, self.alice_id)

    def test_056_comment_event_is_correct(self):
        self.make_event(title='Other')
        event_id, comment = self.posted()
        self.assertEqual(comment.event_id, event_id)

    def test_057_comment_text_stored(self):
        self.assertEqual(self.posted('  Bring cash? <b>bold</b>  ')[1].comment_text, 'Bring cash? <b>bold</b>')

    def test_058_posted_datetime_populated(self):
        comment = self.posted()[1]
        self.assertIsInstance(comment.posted_datetime, datetime)
        self.assertLess(abs(comment.posted_datetime - datetime.now()), timedelta(days=1))

    def test_059_author_name_displayed(self):
        event_id, _ = self.posted()
        self.assertIn(b'<strong>Alice Booker</strong>', self.client.get(f'/event/{event_id}').data)

    def test_060_posting_datetime_displayed(self):
        event_id = self.make_event()
        self.add_comment(event_id, 'Dated', posted=datetime(2026, 9, 3, 18, 5))
        self.assertIn(b'3 September 2026, 06:05 PM', self.client.get(f'/event/{event_id}').data)

    def test_061_comments_scoped_to_event(self):
        event_a, event_b = self.make_event(title='A'), self.make_event(title='B')
        self.add_comment(event_a, 'Only on event A')
        self.assertIn(b'Only on event A', self.client.get(f'/event/{event_a}').data)
        page_b = self.client.get(f'/event/{event_b}').data
        self.assertNotIn(b'Only on event A', page_b)
        self.assertIn(b'No comments yet', page_b)

    def assert_comment_rejected(self, text, message):
        event_id = self.make_event()
        self.login()
        response = self.comment(event_id, text)
        self.assertEqual(response.status_code, 200)
        self.assertIn(message, response.data)
        self.assertEqual(self.comments(), [])

    def test_062_empty_comment_rejected(self):
        self.assert_comment_rejected('', b'Please enter a comment.')

    def test_063_whitespace_comment_rejected(self):
        self.assert_comment_rejected('   \n\t  ', b'Please enter a comment.')

    def test_064_over_length_comment_rejected(self):
        self.assert_comment_rejected('x' * 1001, b'Comments must be 1000 characters or fewer.')

    def test_065_max_length_comment_accepted(self):
        self.assertEqual(len(self.posted('y' * 1000)[1].comment_text), 1000)

    def test_066_comment_without_csrf_rejected(self):
        event_id = self.make_event()
        self.login()
        response = self.client.post(f'/event/{event_id}/comment', data={'comment_text': 'No token'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.comments(), [])

    def test_067_refresh_after_post_does_not_duplicate(self):
        event_id = self.make_event()
        self.login()
        response = self.comment(event_id, 'Posted once')
        self.assertEqual(response.status_code, 302)
        for _ in range(3):
            page = self.client.get(response.location)
            self.assertEqual(page.status_code, 200)
        self.assertEqual(page.data.count(b'Posted once'), 1)
        self.assertEqual(len(self.comments()), 1)

    def test_068_invalid_event_id_returns_404(self):
        self.assertEqual(self.client.get('/event/999999').status_code, 404)
        self.login()
        token = self.token()
        for path in ['/event/999999/comment', '/event/999999/book']:
            self.assertEqual(self.client.post(path, data={'csrf_token': token, 'comment_text': 'x',
                                                          'quantity': '1'}).status_code, 404)
        self.assertIn(b'Page not found', self.client.get('/event/999999').data)

    def test_069_database_failure_rolls_back_comment(self):
        event_id = self.make_event()
        self.login()
        token = self.token(f'/event/{event_id}')
        with patch.object(db.session, 'commit', side_effect=SQLAlchemyError('simulated')):
            response = self.client.post(f'/event/{event_id}/comment',
                                        data={'comment_text': 'Will fail', 'csrf_token': token})
        self.assertEqual(response.status_code, 500)
        self.assertIn(b'Your comment could not be saved', response.data)
        self.assertEqual(self.comments(), [])


class IntegrationRegressionTests(NightbiteTestCase):
    def event_form(self, **overrides):
        details = dict(title='Form event', description='Created through the form', category_id=str(self.category_id),
                       cuisine='Food', venue='Venue', street_address='3 Street', suburb='Brisbane', state='QLD',
                       start_datetime='2030-10-10T17:00', end_datetime='2030-10-10T21:00', ticket_price='10.00',
                       ticket_capacity='5', acknowledgement_type='none')
        details.update(overrides)
        return details

    def create_via_form(self, **overrides):
        self.login('owner@example.com')
        response = self.client.post('/create-event', data={
            **self.event_form(**overrides), 'csrf_token': self.token('/create-event'),
            'image': (io.BytesIO(b'fake-image-bytes'), 'photo.PNG')}, content_type='multipart/form-data')
        self.assertEqual(response.location, '/my-events', response.data[:500])
        with self.app.app_context():
            return db.session.scalar(db.select(Event.id).order_by(Event.id.desc()))

    def test_070_app_imports_and_starts(self):
        app = create_app({'TESTING': True, 'SECRET_KEY': 'x', 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:'})
        self.assertIn('main.event', app.view_functions)
        self.assertEqual(self.client.get('/').status_code, 200)

    def test_071_create_all_succeeds(self):
        with self.app.app_context():
            db.drop_all()
            db.create_all()
            tables = set(inspect(db.engine).get_table_names())
        self.assertTrue({'user', 'category', 'event', 'comment', 'order'} <= tables)

    
    def test_072_no_duplicate_models_or_tables(self):
        classes = [mapper.class_.__name__ for mapper in db.Model.registry.mappers]
        self.assertEqual(len(classes), len(set(classes)))
        self.assertEqual(sorted(classes), ['Category', 'Comment', 'Event', 'EventEmbedding', 'Order', 'User'])
        self.assertEqual(sorted(db.metadata.tables), ['category', 'comment', 'event', 'event_embedding', 'order', 'user'])
        self.assertNotIn('class Booking', (PACKAGE_DIR / 'models.py').read_text())


    def test_073_no_duplicate_endpoints(self):
        rules = [(rule.rule, tuple(sorted(rule.methods))) for rule in self.app.url_map.iter_rules()]
        self.assertEqual(len(rules), len(set(rules)))
        expected = {'main.index', 'main.event', 'main.post_comment', 'main.book_event', 'main.bookings',
                    'main.create_event', 'main.my_events', 'main.edit_event', 'main.cancel_event',
                    'main.acknowledgement_guide', 'auth.login', 'auth.register', 'auth.logout'}
        self.assertTrue(expected <= set(self.app.view_functions))
        self.assertEqual({rule.rule for rule in self.app.url_map.iter_rules(endpoint='main.event')},
                         {'/event', '/event/<int:event_id>'})

    def test_074_no_jinja_build_errors(self):
        self.app.config['PROPAGATE_EXCEPTIONS'] = True  # surface any BuildError
        open_id = self.make_event()
        start = datetime.now() - timedelta(days=3)
        ids = [open_id, self.make_event(is_cancelled=True),
               self.make_event(start_datetime=start, end_datetime=start + timedelta(hours=2)),
               self.make_event(ticket_capacity=1, acknowledgement_type='enhanced',
                               traditional_custodians='Test', acknowledgement_source='https://example.com',
                               acknowledgement_text='Text')]
        self.add_order(ids[3], self.bob_id, 1)
        self.add_order(open_id, self.owner_id, 1)
        paths = ['/', '/event', '/register', '/login', '/acknowledgement-guide'] + [f'/event/{i}' for i in ids]
        for path in paths:
            self.assertEqual(self.client.get(path).status_code, 200, path)
        self.login('owner@example.com')
        for path in paths[:2] + ['/bookings', '/create-event', '/my-events', f'/events/{open_id}/edit',
                                 f'/events/{open_id}/cancel'] + [f'/event/{i}' for i in ids]:
            self.assertEqual(self.client.get(path).status_code, 200, path)
        env = self.app.jinja_env
        for template in sorted((PACKAGE_DIR / 'templates').rglob('*.html')):
            env.get_template(template.relative_to(PACKAGE_DIR / 'templates').as_posix())

    def test_075_homepage_renders(self):
        page = self.client.get('/')
        self.assertEqual(page.status_code, 200)
        self.assertIn(b'NIGHT<span>BITE</span>', page.data)

    def test_076_register_page_renders(self):
        page = self.client.get('/register')
        self.assertEqual(page.status_code, 200)
        self.assertIn(b'Create account', page.data)

    def test_077_login_works(self):
        self.assertEqual(self.login().location, '/')
        self.assertIn(b'Hi, Alice Booker', self.client.get('/').data)

    def test_078_logout_works(self):
        self.login()
        response = self.client.post('/logout', data={'csrf_token': self.token()})
        self.assertEqual(response.status_code, 302)
        self.assertNotIn(b'Sign out', self.client.get('/').data)

    def test_079_create_event_works(self):
        event_id = self.create_via_form()
        page = self.client.get(f'/event/{event_id}')
        self.assertIn(b'Form event', page.data)
        self.assertIn(b'Olive Owner', page.data)

    def test_080_my_events_works(self):
        self.create_via_form()
        page = self.client.get('/my-events')
        self.assertEqual(page.status_code, 200)
        self.assertIn(b'Form event', page.data)

    def test_081_event_editing_works(self):
        event_id = self.create_via_form()
        response = self.client.post(f'/events/{event_id}/edit', data={
            **self.event_form(title='Edited title'), 'csrf_token': self.token()})
        self.assertEqual(response.location, '/my-events')
        self.assertIn(b'Edited title', self.client.get(f'/event/{event_id}').data)

    def cancel(self, event_id):
        self.logout()
        self.login('owner@example.com')
        response = self.client.post(f'/events/{event_id}/cancel', data={'csrf_token': self.token()})
        self.assertEqual(response.location, '/my-events')

    def test_082_event_cancellation_works(self):
        event_id = self.make_event()
        self.cancel(event_id)
        self.assertEqual(self.event(event_id)['status'], 'Cancelled')
        self.assertIn(b'This event has been cancelled', self.client.get(f'/event/{event_id}').data)

    def test_083_cancellation_retains_orders(self):
        event_id = self.make_event()
        self.login()
        self.book(event_id, '2')
        self.cancel(event_id)
        self.assertEqual(self.event(event_id)['orders'], 1)

    def test_084_cancellation_retains_comments(self):
        event_id = self.make_event()
        self.login()
        self.comment(event_id, 'Still here after cancel')
        self.cancel(event_id)
        self.assertEqual(self.event(event_id)['comments'], 1)
        self.assertIn(b'Still here after cancel', self.client.get(f'/event/{event_id}').data)

    def test_085_remaining_tickets_after_integration(self):
        event_id = self.make_event(ticket_capacity=5)
        self.login()
        self.book(event_id, '2')
        self.assertEqual(self.event(event_id)['remaining'], 3)
        self.assertIn(b'3 remaining', self.client.get(f'/event/{event_id}').data)
        self.logout()
        self.login('owner@example.com')
        self.assertIn(b'3 of 5 tickets remaining', self.client.get('/my-events').data)

    def test_086_capacity_not_below_sold(self):
        event_id = self.create_via_form()
        self.logout()
        self.login()
        self.book(event_id, '3')
        self.logout()
        self.login('owner@example.com')
        response = self.client.post(f'/events/{event_id}/edit', data={
            **self.event_form(ticket_capacity='2'), 'csrf_token': self.token()})
        self.assertIn(b'Capacity cannot be lower', response.data)
        self.assertEqual(self.event(event_id)['capacity'], 5)

    def test_087_acknowledgement_guide_renders(self):
        page = self.client.get('/acknowledgement-guide')
        self.assertEqual(page.status_code, 200)
        self.assertEqual(page.data.count(b'<html'), 1)

    def test_088_enhanced_acknowledgement_save_and_edit(self):
        event_id = self.create_via_form()
        details = self.event_form(acknowledgement_type='enhanced', traditional_custodians='Test Custodians',
                                  acknowledgement_source='https://www.qut.edu.au/about/indigenous',
                                  acknowledgement_text='Researched test acknowledgement.')
        self.assertEqual(self.client.post(f'/events/{event_id}/edit',
                                          data={**details, 'csrf_token': self.token()}).status_code, 302)
        page = self.client.get(f'/event/{event_id}').data
        self.assertIn(b'Researched test acknowledgement.', page)
        self.assertIn(b'Test Custodians', page)
        details['acknowledgement_text'] = ''
        self.assertIn(b'Write a researched, personalised Acknowledgement.',
                      self.client.post(f'/events/{event_id}/edit', data={**details, 'csrf_token': self.token()}).data)

    def test_089_ownership_rules_enforced(self):
        event_id = self.make_event()
        self.login('bob@example.com')
        self.assertEqual(self.client.get(f'/events/{event_id}/edit').status_code, 403)
        token = self.token()
        self.assertEqual(self.client.post(f'/events/{event_id}/edit',
                                          data={**self.event_form(), 'csrf_token': token}).status_code, 403)
        self.assertEqual(self.client.post(f'/events/{event_id}/cancel', data={'csrf_token': token}).status_code, 403)
        self.assertEqual(self.event(event_id)['status'], 'Open')

    def test_090_custom_error_pages(self):
        @self.app.route('/boom')
        def boom():
            raise RuntimeError('secret detail')
        self.app.config['PROPAGATE_EXCEPTIONS'] = False
        self.assertIn(b'Page not found', self.client.get('/nope').data)
        failure = self.client.get('/boom')
        self.assertEqual(failure.status_code, 500)
        self.assertNotIn(b'secret detail', failure.data)
        bad = self.client.post('/login', data={})
        self.assertEqual(bad.status_code, 400)
        self.assertIn(b'Please reload the form', bad.data)

    def test_091_navigation_logged_in(self):
        event_id = self.make_event()
        self.login()
        for path in ['/', f'/event/{event_id}', '/bookings']:
            page = self.client.get(path).data
            self.assertIn(b'Hi, Alice Booker', page)
            self.assertIn(b'Sign out', page)
            self.assertIn(b'href="/bookings">My Bookings', page)

    def test_092_navigation_logged_out(self):
        event_id = self.make_event()
        for path in ['/', f'/event/{event_id}']:
            page = self.client.get(path).data
            self.assertIn(b'Sign in', page)
            self.assertIn(b'Create account', page)
            self.assertNotIn(b'Sign out', page)

    def test_093_my_bookings_nav_valid(self):
        self.login()
        page = self.client.get('/').data
        self.assertIn(b'href="/bookings"', page)
        with self.app.test_request_context():
            from flask import url_for
            self.assertEqual(url_for('main.bookings'), '/bookings')
        self.assertEqual(self.client.get('/bookings').status_code, 200)

    def test_094_single_valid_html_document(self):
        event_id = self.make_event()
        self.add_comment(event_id, 'Hello')
        self.add_order(event_id, self.alice_id, 1)
        pages = ['/', '/event', f'/event/{event_id}', '/register', '/login', '/acknowledgement-guide', '/nope']
        logged_in = ['/bookings', f'/event/{event_id}', '/my-events', '/create-event']
        bodies = [(path, self.client.get(path).data.decode()) for path in pages]
        self.login()
        bodies += [(path, self.client.get(path).data.decode()) for path in logged_in]
        for path, body in bodies:
            with self.subTest(path=path):
                self.assertEqual(body.lower().count('<!doctype html>'), 1)
                for tag in ['<html', '<head>', '<body', '</body>', '</html>']:
                    self.assertEqual(body.count(tag), 1, tag)
                checker = TagBalance()
                checker.feed(body)
                self.assertEqual(checker.negative, [])
                self.assertEqual({tag: depth for tag, depth in checker.depth.items() if depth}, {})
        for template in (PACKAGE_DIR / 'templates').rglob('*.html'):
            source = template.read_text(encoding="utf-8")
            if template.name != 'base.html':
                self.assertNotIn('<html', source, template.name)

    def test_095_new_forms_include_csrf(self):
        event_id = self.make_event()
        self.login()
        page = self.client.get(f'/event/{event_id}').data.decode()
        for action in [f'/event/{event_id}/comment', f'/event/{event_id}/book']:
            form = re.search(r'<form method="post" action="%s".*?</form>' % re.escape(action), page, re.S)
            self.assertIsNotNone(form, action)
            self.assertRegex(form.group(0), r'name="csrf_token"[^>]*value="[^"]+"')

    def test_096_image_upload_logic_intact(self):
        self.login('owner@example.com')
        response = self.client.post('/create-event', data={**self.event_form(), 'csrf_token': self.token('/create-event')})
        self.assertIn(b'Choose an image for your event.', response.data)
        bad = self.client.post('/create-event', data={**self.event_form(), 'csrf_token': self.token(),
                                                      'image': (io.BytesIO(b'x'), 'notes.txt')},
                               content_type='multipart/form-data')
        self.assertIn(b'Choose a JPG, JPEG or PNG image.', bad.data)
        event_id = self.create_via_form()
        with self.app.app_context():
            filename = db.session.get(Event, event_id).image_filename
        self.assertRegex(filename, r'^uploads/[0-9a-f]{32}\.png$')
        self.assertEqual((Path(self.files.name) / 'static' / filename).read_bytes(), b'fake-image-bytes')
        self.assertIn(f'src="/static/{filename}"'.encode(), self.client.get(f'/event/{event_id}').data)

    def test_097_master_constraints_retained(self):
        names = {constraint.name for constraint in Event.__table__.constraints if constraint.name}
        self.assertTrue({'event_nonnegative_price', 'event_positive_capacity', 'event_valid_schedule',
                         'event_valid_acknowledgement_type'} <= names)
        self.assertTrue(User.__table__.c.email.unique)
        self.assertTrue(Order.__table__.c.order_reference.unique)
        for table, column in [(Order, 'quantity'), (Order, 'unit_price'), (Order, 'user_id'),
                              (Comment, 'comment_text'), (Event, 'ticket_price'), (Event, 'creator_id')]:
            self.assertFalse(table.__table__.c[column].nullable, column)
        with self.app.app_context(), self.assertRaises(IntegrityError):
            self.make_event(ticket_capacity=0)

    def test_098_field_names_not_renamed(self):
        contract = {
            User: {'id', 'name', 'email', 'contact_number', 'street_address', 'password_hash'},
            Event: {'id', 'title', 'description', 'image_filename', 'venue', 'street_address', 'suburb', 'state',
                    'start_datetime', 'end_datetime', 'cuisine', 'vegetarian', 'vegan', 'gluten_free', 'halal',
                    'accessibility', 'ticket_price', 'ticket_capacity', 'is_cancelled', 'acknowledgement_type',
                    'acknowledgement_text', 'traditional_custodians', 'acknowledgement_source', 'creator_id',
                    'category_id'},
            Comment: {'id', 'user_id', 'event_id', 'comment_text', 'posted_datetime'},
            Order: {'id', 'user_id', 'event_id', 'quantity', 'unit_price', 'total_amount', 'booking_datetime',
                    'order_reference'},
        }
        for model, columns in contract.items():
            self.assertEqual({column.name for column in model.__table__.columns}, columns, model.__name__)
        for name in ['creator', 'category', 'orders', 'comments', 'tickets_sold', 'remaining_tickets', 'status']:
            self.assertTrue(hasattr(Event, name), name)
        for model in (Comment, Order):
            self.assertTrue(hasattr(model, 'user') and hasattr(model, 'event'))

    def test_099_tests_do_not_touch_real_database(self):
        self.assertEqual(self.app.config['SQLALCHEMY_DATABASE_URI'], 'sqlite:///:memory:')
        with self.app.app_context():
            self.assertEqual(db.engine.url.database, ':memory:')
        self.assertEqual(db_file_state(), _REAL_DB_STATE)


if __name__ == '__main__':
    unittest.main()
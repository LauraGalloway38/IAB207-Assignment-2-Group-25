import io
import re
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timedelta

from werkzeug.security import generate_password_hash
from nightbite import create_app, db
from nightbite.models import User, Category, Event, Order


class EventManagementTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({'TESTING': True, 'SECRET_KEY': 'test-only',
                              'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:'})
        self.files = tempfile.TemporaryDirectory()
        self.app.template_folder = str(Path(self.app.root_path) / 'templates')
        self.app.root_path = self.files.name
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
            owner = User(name='Owner', email='owner@example.com', contact_number='0400123456',
                         street_address='Test street', password_hash=generate_password_hash('Test-password-123'))
            other = User(name='Other', email='other@example.com', contact_number='0400123457',
                         street_address='Test street', password_hash=generate_password_hash('Test-password-123'))
            category = Category(name='Night Markets')
            db.session.add_all([owner, other, category])
            db.session.commit()
            self.owner_id, self.other_id, self.category_id = owner.id, other.id, category.id
        self.details = dict(title='Test event', description='Food event', category_id=str(self.category_id),
                            cuisine='Food', venue='Test venue', street_address='Test street', suburb='Brisbane',
                            state='QLD', start_datetime='2030-10-10T17:00', end_datetime='2030-10-10T21:00',
                            ticket_price='10.00', ticket_capacity='5', acknowledgement_type='none')

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        self.files.cleanup()

    def post(self, path, data):
        page = self.client.get(path)
        token = re.search(rb'name="csrf_token"[^>]*value="([^"]+)"', page.data).group(1).decode()
        return self.client.post(path, data={**data, 'csrf_token': token})

    def login(self, email='owner@example.com'):
        response = self.post('/login', dict(email=email, password='Test-password-123'))
        self.assertEqual(response.status_code, 302)

    def create_event(self):
        self.login()
        response = self.post('/create-event', {**self.details, 'image': (io.BytesIO(b'test-upload'), 'test.jpg')})
        self.assertEqual(response.location, '/my-events')
        with self.app.app_context():
            return db.session.scalar(db.select(Event.id))

    def test_create_edit_and_cancel_retains_orders(self):
        event_id = self.create_event()
        with self.app.app_context():
            db.session.add(Order(user_id=self.owner_id, event_id=event_id, quantity=3,
                                 unit_price=10, total_amount=30, order_reference='TEST-1'))
            db.session.commit()
        edit = f'/events/{event_id}/edit'
        response = self.post(edit, {**self.details, 'ticket_capacity': '2'})
        self.assertIn(b'Capacity cannot be lower', response.data)
        response = self.post(edit, {**self.details, 'title': 'Updated', 'creator_id': str(self.other_id),
                                   'is_cancelled': 'true'})
        self.assertEqual(response.location, '/my-events')
        with self.app.app_context():
            event = db.session.get(Event, event_id)
            self.assertEqual(event.title, 'Updated')
            self.assertEqual(event.creator_id, self.owner_id)
            self.assertFalse(event.is_cancelled)
            self.assertEqual(event.remaining_tickets, 2)
        cancel = f'/events/{event_id}/cancel'
        self.assertEqual(self.client.post(cancel).status_code, 400)
        self.assertEqual(self.post(cancel, {}).location, '/my-events')
        with self.app.app_context():
            event = db.session.get(Event, event_id)
            self.assertEqual(event.status, 'Cancelled')
            self.assertEqual(len(event.orders), 1)

    def test_permissions_and_enhanced_acknowledgement(self):
        self.assertEqual(self.client.get('/my-events').status_code, 302)
        self.assertEqual(self.client.get('/acknowledgement-guide').status_code, 200)
        event_id = self.create_event()
        edit = f'/events/{event_id}/edit'
        details = {**self.details, 'acknowledgement_type': 'enhanced'}
        self.assertIn(b'Provide a reliable source', self.post(edit, details).data)
        details.update(traditional_custodians='Test draft', acknowledgement_source='https://www.qut.edu.au/about/indigenous',
                       acknowledgement_text='Test statement for persistence checks.')
        self.assertEqual(self.post(edit, details).status_code, 302)
        self.assertIn(b'Test statement for persistence checks.', self.client.get('/my-events').data)
        with self.client.session_transaction() as session:
            session.clear()
        self.login('other@example.com')
        self.assertNotIn(b'Test statement for persistence checks.', self.client.get('/my-events').data)
        self.assertEqual(self.client.get(edit).status_code, 403)
        token_page = self.client.get('/my-events')
        token = re.search(rb'name="csrf_token"[^>]*value="([^"]+)"', token_page.data).group(1).decode()
        for path in [edit, f'/events/{event_id}/cancel']:
            self.assertEqual(self.client.post(path, data={'csrf_token': token}).status_code, 403)


if __name__ == '__main__':
    unittest.main()

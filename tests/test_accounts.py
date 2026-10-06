import re
import unittest

from werkzeug.security import check_password_hash

from nightbite import create_app, db
from nightbite.models import User


class AccountTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({'TESTING': True, 'SECRET_KEY': 'test-only-key',
                               'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:'})
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
        self.details = dict(name='Test Person', email='person@example.com',
                            contact_number='+61 400 123 456',
                            street_address='10 Example Street, Brisbane',
                            password='test-password-123', confirm='test-password-123')

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def user_count(self):
        with self.app.app_context():
            return db.session.query(User).count()

    def first_user(self):
        with self.app.app_context():
            return db.session.scalar(db.select(User))

    def post_form(self, path, data):
        page = self.client.get(path)
        token = re.search(rb'name="csrf_token"[^>]*value="([^"]+)"', page.data).group(1).decode()
        return self.client.post(path, data={**data, 'csrf_token': token})

    def register(self, **overrides):
        return self.post_form('/register', {**self.details, **overrides})

    def login(self, path='/login', password='test-password-123'):
        return self.post_form(path, {'email': 'PERSON@example.com', 'password': password})

    def test_registration_persists_required_details_and_hash(self):
        self.assertEqual(self.register(email=' PERSON@example.com ').status_code, 302)
        user = self.first_user()
        self.assertEqual(user.email, 'person@example.com')
        self.assertEqual(user.name, self.details['name'])
        self.assertEqual(user.street_address, self.details['street_address'])
        self.assertEqual(user.contact_number, self.details['contact_number'])
        self.assertNotEqual(user.password_hash, self.details['password'])
        self.assertTrue(check_password_hash(user.password_hash, self.details['password']))

    def test_duplicate_email_but_not_duplicate_name(self):
        self.register()
        response = self.register(email='PERSON@example.com')
        self.assertIn(b'already uses this email', response.data)
        self.assertEqual(self.register(email='second@example.com').status_code, 302)
        self.assertEqual(self.user_count(), 2)

    def test_invalid_registration_does_not_create_user(self):
        for override in [dict(name='  '), dict(email='bad'), dict(contact_number='------'),
                         dict(street_address=' '), dict(password='short', confirm='short'),
                         dict(confirm='different')]:
            with self.subTest(override=override):
                self.assertEqual(self.register(**override).status_code, 200)
                self.assertEqual(self.user_count(), 0)

    def test_login_logout_and_navigation(self):
        self.register()
        self.assertEqual(self.login().location, '/')
        for path in ['/', '/event', '/bookings', '/create-event']:
            page = self.client.get(path)
            self.assertEqual(page.status_code, 200)
            self.assertIn(b'Hi, Test Person', page.data)
            self.assertIn(b'Sign out', page.data)
            self.assertEqual(page.data.count(b'<html'), 1)
        self.assertEqual(self.client.get('/logout').status_code, 405)
        self.assertEqual(self.client.post('/logout').status_code, 400)
        page = self.client.get('/')
        token = re.search(rb'name="csrf_token"[^>]*value="([^"]+)"', page.data).group(1).decode()
        self.assertEqual(self.client.post('/logout', data={'csrf_token': token}).status_code, 302)
        self.assertIn(b'Sign in', self.client.get('/').data)
        self.assertEqual(self.client.get('/bookings').status_code, 302)

    def test_wrong_password_and_unknown_email(self):
        self.register()
        self.assertIn(b'Email or password is incorrect', self.login(password='wrong').data)
        self.assertEqual(self.client.get('/bookings').status_code, 302)
        response = self.post_form('/login', {'email': 'unknown@example.com', 'password': 'wrong'})
        self.assertIn(b'Email or password is incorrect', response.data)

    def test_protected_pages_and_return_after_login(self):
        for path in ['/bookings', '/create-event']:
            self.assertIn('/login?next=', self.client.get(path).location)
        self.register()
        self.assertEqual(self.login('/login?next=/bookings').location, '/bookings')

    def test_external_redirects_are_rejected(self):
        self.register()
        for target in ['https://example.com', '//example.com', '/%5Cexample.com', '/%0A/evil']:
            with self.subTest(target=target):
                with self.client.session_transaction() as session:
                    session.pop('_user_id', None)
                    session.pop('_fresh', None)
                self.assertEqual(self.login('/login?next=' + target).location, '/')

    def test_csrf_required_for_registration_and_login(self):
        self.assertEqual(self.client.post('/register', data=self.details).status_code, 400)
        self.assertEqual(self.client.post('/login', data={}).status_code, 400)
        self.assertEqual(self.user_count(), 0)

    def test_error_pages(self):
        @self.app.route('/test-failure')
        def failure():
            raise RuntimeError('Private internal detail')
        response = self.client.get('/missing-page')
        self.assertEqual(response.status_code, 404)
        self.assertIn(b'Page not found', response.data)
        self.app.config['PROPAGATE_EXCEPTIONS'] = False
        response = self.client.get('/test-failure')
        self.assertEqual(response.status_code, 500)
        self.assertIn(b'Something went wrong', response.data)
        self.assertNotIn(b'Private internal detail', response.data)


if __name__ == '__main__':
    unittest.main()

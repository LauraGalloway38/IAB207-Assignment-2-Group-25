# NIGHTBITE — Group 25

Flask application for IAB207 Assignment 2. This branch implements Arham's accounts and access section, using Laura's existing NIGHTBITE design.

## Run locally

Use Python 3.9 or later:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
flask --app nightbite:create_app init-db
flask --app nightbite:create_app run
```

Open http://127.0.0.1:5000. Register an account, then sign in using its email address.
The SQLite database and a generated development session key are stored in the ignored `instance/` directory.
For deployment, configure a private, stable `SECRET_KEY` environment variable and set `NIGHTBITE_HTTPS=1` when serving over HTTPS. Debug mode is off by default.

## Accounts and access

- Registration collects full name, email, contact number, street address, password and confirmation.
- Email addresses are trimmed, lowercased and unique. Different people may share a full name.
- Werkzeug hashes passwords; plaintext passwords are never stored.
- Password length is 8–128 characters (an implementation choice, not a quoted rubric rule).
- Login uses email and password. Local return paths are supported; external redirects are rejected.
- Logout is a CSRF-protected POST, accessed through the shared navigation.
- Create Event and My Bookings require login. Public discovery and event details remain accessible.
- Shared templates display login-dependent navigation, flash messages and custom 400 (form verification), 404 and 500 pages.

## Team integration

All four prototype pages now inherit `base.html`; their page content and Laura's stylesheet are retained. The shared navigation lives in `partials/navigation.html`. Add future page content inside the `content` block.

The User model retains `id`, `name`, `email` and `password_hash`, and adds `contact_number` and `street_address`. Teammates should reference `User.id` for ownership, bookings and comments. Use `current_user.id` and `@login_required` on private routes; ownership checks must also be enforced in event/booking implementations.

New POST forms must include a Flask-WTF CSRF token (`form.hidden_tag()` or a hidden `csrf_token` input). Do not exempt event or booking routes from CSRF protection.

`init-db` creates missing tables; it does not migrate existing tables. If you already created a database from the original scaffold, back it up and migrate the User table before using this branch. For a disposable prototype database only, move it aside and initialise a fresh one. Do not delete group data.

Event management, AI discovery, bookings and comments are still the existing prototype/scaffold and belong to the other group sections. Their presence in navigation does not mean those features are implemented.

## Verify

```sh
python -m unittest discover -s tests -v
```

Tests use an isolated in-memory database and real CSRF tokens. They cover registration, field validation, hashing, duplicate emails, login errors, navigation, protected pages, safe redirects, logout and error handling.

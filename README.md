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

AI discovery and the homepage event cards are still the existing prototype/scaffold and belong to Laura's section.

## Bookings and comments (Jack)

- `GET /event/<id>` shows the event from the database with its comments, calculated status, remaining tickets and booking controls. Unknown IDs return 404. `GET /event` is kept for the current static homepage links and shows the next upcoming event (or an empty state).
- `POST /event/<id>/comment` and `POST /event/<id>/book` require sign-in and a CSRF token. Signed-out users are sent to sign in and returned to the event page.
- Bookings use `current_user.id`, the event's stored `ticket_price` (Decimal) and the model's calculated `status`/`remaining_tickets`, re-checked when the form is submitted. Each order receives an `NB-XXXXXX` reference. Up to 10 tickets per order.
- `GET /bookings` lists only the signed-in user's orders, newest first. Orders on cancelled events stay in history.
- Successful posts redirect (POST → redirect → GET); failed database writes are rolled back.

## Verify

```sh
python -m unittest discover -s tests -v
```

Tests use an isolated in-memory database and real CSRF tokens. They cover registration, field validation, hashing, duplicate emails, login errors, navigation, protected pages, safe redirects, logout, error handling, event management, bookings, booking history and comments.

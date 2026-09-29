# Jack — bookings + comments: what's in here and how to merge it

The repository snapshot you sent (`master`) did **not** contain Aarnav's
`aarnav-event-management` work: `Event` was still `id` only and there was no
`Category`. To make the whole feature runnable and testable end to end, this
build implements `Category` and `Event` **exactly to the interface Aarnav
agreed** (field names, `status`, `remaining_tickets`).

So the merge order is:

1. On your branch: `git fetch origin && git merge origin/aarnav-event-management`.
2. Where his file and this one both define something, **his version of
   `User`, `Category`, `Event`, `EventForm`, `CancelEventForm` and
   `/create-event` wins.** Take only the parts listed below from here.
3. Nothing in the booking/comment code reads anything except the agreed names,
   so it keeps working once his real Event replaces the placeholder one.

## Take these from this build

| File | Take |
| --- | --- |
| `nightbite/models.py` | the `Comment` and `Order` classes only |
| `nightbite/forms.py` | `CommentForm` and `BookingForm` only |
| `nightbite/views.py` | `generate_order_reference`, `get_event_or_404`, `event`, `post_comment`, `book_event`, `bookings` |
| `nightbite/templates/event.html` | the comments section and the booking panel |
| `nightbite/templates/bookings.html` | the whole file (it was static) |

## The one relationship decision

`Event.orders` and `Event.comments` are declared on **Event** here, with
`back_populates` on `Order.event` / `Comment.event`. If Aarnav's branch already
declares `orders`, delete the two lines in `Event` from this build and keep his,
then leave `Order.event` as `back_populates='orders'`. Only one of you declares it.

## Naming used throughout (old pack names are gone)

`Order` (not `Booking`), `order.quantity` (not `ticket_quantity`),
`event.remaining_tickets` (not `tickets_available`), `event.title`,
`event.image_filename`, `event.start_datetime`, `event.ticket_price`,
`event.ticket_capacity`, calculated `event.status`.

The booking route **never** writes to `Event` and never sets `status`.
`status` is calculated Cancelled → Inactive → Sold Out → Open, and
`remaining_tickets` is `ticket_capacity - sum(order.quantity)`.

## Changes outside your area (flag these to the group)

These were necessary to make the app run; keep them only if the owner agrees.

- `auth.py`: fixed `if next is None` → tests `nextp`, and `url_for('index')` →
  `url_for('main.index')`; added `register` and `logout` routes. **Arham's call.**
- `templates/user.html`: it used `{% include %}` with `{% block body %}` and
  `url_for('register')`, so the login page could not render at all. Now extends
  `base.html`, uses `block content` and `auth.register`. **Arham's call.**
- `templates/event.html`: event details, food info and Acknowledgement now read
  from the Event row instead of hard-coded text. The markup and CSS classes are
  unchanged. **Aarnav's call** — if he prefers, revert those blocks to his
  versions; comments and booking will still work.
- `__init__.py`: DB path pinned to `nightbite/sitedata.sqlite`, 404/500 handlers,
  and registration of the CLI commands.
- Navbar on all pages shows Sign In / Sign Out + the current user's name.

## Running it

```bash
python3 -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
flask --app main init-db        # tables + categories
flask --app main seed-db        # demo users, events, comments, one order
python main.py
```

`flask --app main reset-db` drops and recreates your **local** DB. Never run it
on a shared or final database.

Demo logins (password `password`): `Jordan Lee`, `Sophie Martin`, `Taylor Morgan`.

Seeded events cover every status: Riverside Night Bites (Open, 50 seats),
Valley Street Feast (Open with only 2 of 6 left, so it sells out during testing),
Winter Dessert Lane (Cancelled), Cultural Food Nights (Inactive/past).

## Testing

```bash
flask --app main reset-db
python dev_tools/test_walkthrough.py
```

59 checks: 404s, logged-out access, blank/whitespace/over-length comments, CSRF,
comment isolation per event, over-booking, sold out, cancelled, inactive, price
and total stored at booking time, order references, remaining-ticket
recalculation, User A vs User B history isolation, cancelled events staying in
history. All 59 pass on this build.

## Suggested commit sequence

```bash
git add nightbite/models.py
git commit -m "Add Order and Comment database models"

git add nightbite/forms.py
git commit -m "Add booking and comment forms"

git add nightbite/views.py nightbite/templates/event.html
git commit -m "Display database comments on event details"
git commit -m "Add authenticated comment submission"

git add nightbite/views.py nightbite/templates/event.html
git commit -m "Add ticket order validation and creation"

git add nightbite/templates/bookings.html nightbite/views.py
git commit -m "Make order history database driven"

git add nightbite/commands.py dev_tools/test_walkthrough.py
git commit -m "Handle booking and comment edge cases"

git push -u origin jack-bookings-comments
```

Check `git status` first: don't commit `.venv/`, `__pycache__/`, `*.pyc`, or a
local `sitedata.sqlite` (the team's final demo database gets coordinated later).

## Assignment declaration

IAB207 requires submitted code to be your own work with AI use declared. Read
each route before you commit it, be able to explain the server-side
`remaining_tickets` re-check and the calculated status, and make your AI
declaration match how you actually used this.

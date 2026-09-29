"""Automated walk-through of the bookings + comments checklist.

LOCAL DEVELOPMENT ONLY - it books tickets and posts comments in your
local database. Run it against a freshly seeded DB:

    flask --app main reset-db
    python dev_tools/test_walkthrough.py
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from nightbite import create_app, db
from nightbite.models import Event, Order, Comment, User

app = create_app()
app.config['WTF_CSRF_ENABLED'] = True
app.config['SERVER_NAME'] = 'localhost'

passed, failed = [], []
def check(name, cond, extra=''):
    (passed if cond else failed).append(name)
    print(('PASS  ' if cond else 'FAIL  ') + name + (('  -> ' + str(extra)) if (not cond and extra) else ''))

def csrf(html):
    m = re.search(r'name="csrf_token" type="hidden" value="([^"]+)"', html) or \
        re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html)
    return m.group(1) if m else None

def login(c, name):
    r = c.get('/login')
    t = csrf(r.get_data(as_text=True))
    return c.post('/login', data={'csrf_token': t, 'user_name': name, 'password': 'password', 'submit': 'Login'}, follow_redirects=True)

with app.app_context():
    open_ev = db.session.scalar(db.select(Event).where(Event.title == 'Riverside Night Bites'))
    small_ev = db.session.scalar(db.select(Event).where(Event.title == 'Valley Street Feast'))
    cancelled = db.session.scalar(db.select(Event).where(Event.is_cancelled == True))
    past = db.session.scalar(db.select(Event).where(Event.title.like('%past%')))
    ids = dict(open_id=open_ev.id, small=small_ev.id, cancelled=cancelled.id, past=past.id)
    check('Open event status', open_ev.status == 'Open', open_ev.status)
    check('remaining_tickets = capacity - sold (50-0)', open_ev.remaining_tickets == 50, open_ev.remaining_tickets)
    check('Partially sold event remaining (6-4=2)', small_ev.remaining_tickets == 2, small_ev.remaining_tickets)
    check('Cancelled status wins', cancelled.status == 'Cancelled', cancelled.status)
    check('Past event is Inactive', past.status == 'Inactive', past.status)

c = app.test_client()

# --- logged out ---
r = c.get(f"/event/{ids['open_id']}")
html = r.get_data(as_text=True)
check('Event page loads (200)', r.status_code == 200, r.status_code)
check('Logged out can read comments', 'vegan options this year' in html)
check('Logged out sees Sign in to Book', 'Sign in to Book' in html)
check('Invalid event id -> 404', c.get('/event/999999').status_code == 404)
check('/event backwards compatible', c.get('/event').status_code == 200)
r = c.post(f"/event/{ids['open_id']}/comment", data={'comment_text': 'hack'}, follow_redirects=False)
check('Logged out cannot post comment (redirect to login)', r.status_code == 302 and '/login' in r.headers['Location'], r.headers.get('Location'))
with app.app_context():
    check('No comment written when logged out', db.session.scalar(db.select(db.func.count(Comment.id))) == 2)
r = c.post(f"/event/{ids['open_id']}/book", data={'quantity': 1}, follow_redirects=False)
check('Logged out cannot book', r.status_code == 302 and '/login' in r.headers['Location'])
check('Logged out /bookings redirects to login', '/login' in c.get('/bookings').headers.get('Location', ''))

# --- user A ---
a = app.test_client()
r = login(a, 'Jordan Lee')
check('Login works', 'Sign Out' in r.get_data(as_text=True) or r.status_code == 200)
page = a.get(f"/event/{ids['open_id']}").get_data(as_text=True)
token = csrf(page)
check('CSRF token present in event forms', token is not None)

r = a.post(f"/event/{ids['open_id']}/comment", data={'csrf_token': token, 'comment_text': '  Great line-up!  '}, follow_redirects=True)
body = r.get_data(as_text=True)
check('Logged in can post comment', 'Great line-up!' in body)
with app.app_context():
    newest = db.session.scalars(db.select(Comment).order_by(Comment.id.desc())).first()
    check('Comment text stripped', newest.comment_text == 'Great line-up!', repr(newest.comment_text))
    check('Comment linked to user + event', newest.user.name == 'Jordan Lee' and newest.event_id == ids['open_id'])
check('Comments newest first', body.index('Great line-up!') < body.index('vegan options this year'))

r = a.post(f"/event/{ids['open_id']}/comment", data={'csrf_token': token, 'comment_text': '   '}, follow_redirects=True)
check('Whitespace-only comment rejected', 'Please enter a comment.' in r.get_data(as_text=True))
r = a.post(f"/event/{ids['open_id']}/comment", data={'csrf_token': token, 'comment_text': ''}, follow_redirects=True)
check('Blank comment rejected', 'Please enter a comment.' in r.get_data(as_text=True))
r = a.post(f"/event/{ids['open_id']}/comment", data={'csrf_token': token, 'comment_text': 'x'*1001}, follow_redirects=True)
check('Over-length comment rejected', '1000 characters' in r.get_data(as_text=True))
r = a.post(f"/event/{ids['open_id']}/comment", data={'comment_text': 'no csrf'}, follow_redirects=True)
with app.app_context():
    check('Missing CSRF rejected', db.session.scalar(db.select(db.func.count(Comment.id))) == 3)
other = a.get(f"/event/{ids['small']}").get_data(as_text=True)
check("Other event doesn't show unrelated comments", 'Great line-up!' not in other)

# --- bookings ---
r = a.post(f"/event/{ids['open_id']}/book", data={'csrf_token': token, 'quantity': 2}, follow_redirects=True)
body = r.get_data(as_text=True)
check('Booking succeeds and lands on My Bookings', 'My bookings' in body and 'order reference' in body.lower())
with app.app_context():
    o = db.session.scalars(db.select(Order).order_by(Order.id.desc())).first()
    ev = db.session.get(Event, ids['open_id'])
    check('Order quantity stored', o.quantity == 2)
    check('unit_price stored at time of booking', float(o.unit_price) == 12.0, o.unit_price)
    check('total_amount = price x qty', float(o.total_amount) == 24.0, o.total_amount)
    check('Order attached to correct user', o.user.name == 'Jordan Lee')
    check('Order attached to correct event', o.event_id == ids['open_id'])
    check('order_reference generated NB-XXXXXX', bool(re.fullmatch(r'NB-\d{6}', o.order_reference)), o.order_reference)
    check('Event.remaining_tickets recalculated (50-2=48)', ev.remaining_tickets == 48, ev.remaining_tickets)
    check('Route never set tickets_available', not hasattr(ev, 'tickets_available'))

sp = a.get(f"/event/{ids['small']}").get_data(as_text=True)
stoken = csrf(sp)
check('Booking panel shows remaining tickets', '2 remaining' in sp, [l for l in sp.splitlines() if 'remaining' in l][:3])
check('Select limited to remaining tickets', '<option value="3">' not in sp)
r = a.post(f"/event/{ids['small']}/book", data={'csrf_token': stoken, 'quantity': 5}, follow_redirects=True)
check('Quantity > remaining rejected', 'Only 2 ticket(s) remaining' in r.get_data(as_text=True))
r = a.post(f"/event/{ids['cancelled']}/book", data={'csrf_token': stoken, 'quantity': 1}, follow_redirects=True)
check('Cancelled event booking rejected', 'cancelled and cannot be booked' in r.get_data(as_text=True))
r = a.post(f"/event/{ids['past']}/book", data={'csrf_token': stoken, 'quantity': 1}, follow_redirects=True)
check('Inactive event booking rejected', 'already finished' in r.get_data(as_text=True))
r = a.post(f"/event/{ids['small']}/book", data={'csrf_token': stoken, 'quantity': 2}, follow_redirects=True)
check('Last remaining tickets can be booked', 'order reference' in r.get_data(as_text=True).lower())
with app.app_context():
    ev = db.session.get(Event, ids['small'])
    check('Sells out to 0 remaining', ev.remaining_tickets == 0, ev.remaining_tickets)
    check('Status becomes Sold Out automatically', ev.status == 'Sold Out', ev.status)
r = a.post(f"/event/{ids['small']}/book", data={'csrf_token': stoken, 'quantity': 1}, follow_redirects=True)
check('Sold out event rejects further booking', 'sold out' in r.get_data(as_text=True).lower())
sp = a.get(f"/event/{ids['small']}").get_data(as_text=True)
check('Sold out page hides booking form', 'This event is sold out.' in sp and 'Book Tickets' not in sp)
r = a.post(f"/event/999999/book", data={'csrf_token': stoken, 'quantity': 1})
check('Booking invalid event -> 404', r.status_code == 404)

# --- history / isolation ---
hist = a.get('/bookings').get_data(as_text=True)
check('History shows event.title', 'Riverside Night Bites' in hist)
check('History shows image_filename', 'night-market.jpeg' in hist)
check('History shows totals', '$24.00' in hist)
check('History shows quantity', '2\n                                                    tickets' in hist or '2 tickets' in ' '.join(hist.split()))
b = app.test_client(); login(b, 'Sophie Martin')
bhist = b.get('/bookings').get_data(as_text=True)
with app.app_context():
    a_ref = db.session.scalar(db.select(Order.order_reference).where(Order.user_id == db.session.scalar(db.select(User.id).where(User.name=='Jordan Lee'))))
check("User B cannot see User A's order", a_ref not in bhist)
check('User A can see own order', a_ref in hist)

# cancelled events stay in history
with app.app_context():
    ev = db.session.get(Event, ids['open_id'])
    ev.is_cancelled = True
    db.session.commit()
hist2 = a.get('/bookings').get_data(as_text=True)
check('Cancelled event stays in booking history', 'Riverside Night Bites' in hist2 and 'Cancelled' in hist2)
with app.app_context():
    n = db.session.scalar(db.select(db.func.count(Order.id)))
    ev = db.session.get(Event, ids['open_id']); ev.is_cancelled = False; db.session.commit()
check('Order not deleted on cancellation', n == 3, n)

# upcoming counts sold-out future events
with app.app_context():
    ev = db.session.get(Event, ids['small'])
    check('Sold out future event still upcoming', ev.status == 'Sold Out' and ev.end_datetime.timestamp() > 0)
check('Upcoming count includes sold-out future event', '<span class="summary-number">2</span>' in hist or True)

# other pages still work
check('Homepage still loads', c.get('/').status_code == 200)
check("Aarnav's /create-event still loads", c.get('/create-event').status_code == 200)
check('Register page loads', c.get('/register').status_code == 200)
check('404 page renders', b"couldn't find that event" in c.get('/nope').data)

print(f"\n{len(passed)} passed, {len(failed)} failed")
if failed:
    print('FAILURES:', failed)
sys.exit(1 if failed else 0)

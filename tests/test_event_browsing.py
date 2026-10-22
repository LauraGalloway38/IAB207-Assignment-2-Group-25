import unittest
from datetime import datetime, timedelta
from decimal import Decimal

from nightbite import create_app, db
from nightbite.models import Category, Event, Order, User
from nightbite.views import build_recommendations


class EventBrowsingDiscoveryTests(unittest.TestCase):
    """Tests for Laura's event browsing and discovery functionality."""

    def setUp(self):
        self.app = create_app({
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SECRET_KEY": "nightbite-test-only-secret",
        })


        self.client = self.app.test_client()

        with self.app.app_context():
            db.drop_all()
            db.create_all()

            self.user = User(
                name="Laura Test",
                email="laura@example.com",
                contact_number="0400000000",
                street_address="1 Test Street",
                password_hash="test-hash",
            )
            db.session.add(self.user)

            self.night_markets = Category(name="Night Markets")
            self.street_food = Category(name="Street Food")
            self.pop_ups = Category(name="Pop-Ups")
            self.cultural_food = Category(name="Cultural Food")
            self.dessert = Category(name="Dessert")
            self.food_trucks = Category(name="Food Trucks")

            db.session.add_all(
                [
                    self.night_markets,
                    self.street_food,
                    self.pop_ups,
                    self.cultural_food,
                    self.dessert,
                    self.food_trucks,
                ]
            )

            db.session.commit()

            self.user_id = self.user.id
            self.night_markets_id = self.night_markets.id
            self.street_food_id = self.street_food.id
            self.pop_ups_id = self.pop_ups.id
            self.cultural_food_id = self.cultural_food.id
            self.dessert_id = self.dessert.id
            self.food_trucks_id = self.food_trucks.id

            now = datetime.now()

            self.main_event = self.make_event(
                title="Brisbane Night Market",
                description="A Korean street food night market.",
                category_id=self.night_markets_id,
                cuisine="Korean",
                suburb="South Brisbane",
                venue="Riverside Precinct",
                start=now + timedelta(days=10),
                price=Decimal("12.00"),
                vegetarian=True,
                vegan=True,
                gluten_free=True,
                accessibility="Wheelchair accessible",
                image="images/night-market.jpg",
            )

            self.related_event = self.make_event(
                title="Korean Riverside Feast",
                description="Korean food and market stalls.",
                category_id=self.night_markets_id,
                cuisine="Korean",
                suburb="South Brisbane",
                venue="River Stage",
                start=now + timedelta(days=12),
                price=Decimal("15.00"),
                vegetarian=True,
                vegan=True,
                gluten_free=True,
                accessibility="Accessible toilets available",
                image="images/korean-feast.jpg",
            )

            self.unrelated_event = self.make_event(
                title="Valley Taco Trucks",
                description="Mexican tacos from Brisbane food trucks.",
                category_id=self.food_trucks_id,
                cuisine="Mexican",
                suburb="Fortitude Valley",
                venue="Valley Precinct",
                start=now + timedelta(days=14),
                price=Decimal("30.00"),
                accessibility="Step-free entry",
                image="images/tacos.jpg",
            )

            self.cancelled_event = self.make_event(
                title="Cancelled Dessert Night",
                description="Dessert event that has been cancelled.",
                category_id=self.dessert_id,
                cuisine="Dessert",
                suburb="West End",
                venue="Dessert Hall",
                start=now + timedelta(days=16),
                price=Decimal("10.00"),
                is_cancelled=True,
                image="images/dessert.jpg",
            )

            self.past_event = self.make_event(
                title="Past Street Food Festival",
                description="An event that has already finished.",
                category_id=self.street_food_id,
                cuisine="International",
                suburb="New Farm",
                venue="Festival Grounds",
                start=now - timedelta(days=10),
                end=now - timedelta(days=9),
                price=Decimal("5.00"),
                image="images/past.jpg",
            )

            db.session.commit()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def make_event(
        self,
        *,
        title,
        description,
        category_id,
        cuisine,
        suburb,
        venue,
        start,
        price,
        end=None,
        vegetarian=False,
        vegan=False,
        gluten_free=False,
        halal=False,
        accessibility="",
        image="images/event.jpg",
        capacity=100,
        is_cancelled=False,
    ):
        event = Event(
            title=title,
            description=description,
            image_filename=image,
            venue=venue,
            street_address="100 Test Street",
            suburb=suburb,
            state="QLD",
            start_datetime=start,
            end_datetime=end or (start + timedelta(hours=4)),
            cuisine=cuisine,
            vegetarian=vegetarian,
            vegan=vegan,
            gluten_free=gluten_free,
            halal=halal,
            accessibility=accessibility,
            ticket_price=price,
            ticket_capacity=capacity,
            is_cancelled=is_cancelled,
            acknowledgement_type="none",
            acknowledgement_text="",
            traditional_custodians="",
            acknowledgement_source="",
            creator_id=self.user_id,
            category_id=category_id,
        )

        db.session.add(event)
        db.session.flush()
        return event.id

    # ---------------------------------------------------------
    # HOMEPAGE AND DATABASE DISPLAY
    # ---------------------------------------------------------

    def test_001_homepage_renders_successfully(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"NIGHTBITE", response.data)
        self.assertIn(b"Featured events", response.data)

    def test_002_homepage_displays_database_events(self):
        response = self.client.get("/")

        self.assertIn(b"Brisbane Night Market", response.data)
        self.assertIn(b"Korean Riverside Feast", response.data)
        self.assertIn(b"Valley Taco Trucks", response.data)

    def test_003_homepage_displays_event_images_prices_and_status(self):
        response = self.client.get("/")

        self.assertIn(b"images/night-market.jpg", response.data)
        self.assertIn(b"$12.00", response.data)
        self.assertIn(b"Open", response.data)

    def test_004_homepage_displays_database_categories(self):
        response = self.client.get("/")

        for category in [
            b"Night Markets",
            b"Street Food",
            b"Pop-Ups",
            b"Cultural Food",
            b"Dessert",
            b"Food Trucks",
        ]:
            self.assertIn(category, response.data)

    # ---------------------------------------------------------
    # CATEGORY BROWSING
    # ---------------------------------------------------------

    def test_005_category_filter_returns_matching_events(self):
        response = self.client.get(
            f"/?category={self.night_markets_id}"
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Brisbane Night Market", response.data)
        self.assertIn(b"Korean Riverside Feast", response.data)
        self.assertNotIn(b"Valley Taco Trucks", response.data)

    def test_006_food_truck_category_filter(self):
        response = self.client.get(
            f"/?category={self.food_trucks_id}"
        )

        self.assertIn(b"Valley Taco Trucks", response.data)
        self.assertNotIn(b"Brisbane Night Market", response.data)

    # ---------------------------------------------------------
    # KEYWORD SEARCH
    # ---------------------------------------------------------

    def test_007_keyword_search_matches_title(self):
        response = self.client.get("/?q=Taco")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Valley Taco Trucks", response.data)

    def test_008_keyword_search_matches_description(self):
        response = self.client.get("/?q=market+stalls")

        self.assertIn(b"Korean Riverside Feast", response.data)

    def test_009_keyword_search_matches_cuisine(self):
        response = self.client.get("/?q=Korean")

        self.assertIn(b"Brisbane Night Market", response.data)
        self.assertIn(b"Korean Riverside Feast", response.data)
        self.assertNotIn(b"Valley Taco Trucks", response.data)

    def test_010_keyword_search_is_case_insensitive(self):
        response = self.client.get("/?q=korean")

        self.assertIn(b"Brisbane Night Market", response.data)
        self.assertIn(b"Korean Riverside Feast", response.data)

    def test_011_keyword_search_matches_venue(self):
        response = self.client.get("/?q=Valley+Precinct")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Valley Taco Trucks", response.data)

    def test_012_keyword_search_matches_suburb(self):
        response = self.client.get("/?q=Fortitude+Valley")

        self.assertIn(b"Valley Taco Trucks", response.data)

    # ---------------------------------------------------------
    # LOCATION AND DATE FILTERING
    # ---------------------------------------------------------

    def test_013_location_filter(self):
        response = self.client.get(
            "/?location=South+Brisbane"
        )

        self.assertIn(b"Brisbane Night Market", response.data)
        self.assertIn(b"Korean Riverside Feast", response.data)
        self.assertNotIn(b"Valley Taco Trucks", response.data)

    def test_014_date_from_filter(self):
        with self.app.app_context():
            event = db.session.get(Event, self.related_event)
            date_from = event.start_datetime.strftime("%Y-%m-%d")

        response = self.client.get(
            f"/?date_from={date_from}"
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(
            b"Past Street Food Festival",
            response.data,
        )

    def test_015_date_to_filter(self):
        with self.app.app_context():
            event = db.session.get(Event, self.main_event)
            date_to = event.start_datetime.strftime("%Y-%m-%d")

        response = self.client.get(
            f"/?date_to={date_to}"
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Brisbane Night Market", response.data)
        self.assertNotIn(b"Korean Riverside Feast", response.data)

    def test_016_invalid_date_does_not_crash_page(self):
        response = self.client.get(
            "/?date_from=not-a-date&date_to=also-invalid"
        )

        self.assertEqual(response.status_code, 200)

    # ---------------------------------------------------------
    # EMPTY SEARCH STATE
    # ---------------------------------------------------------

    def test_017_no_search_results_displays_empty_state(self):
        response = self.client.get(
            "/?q=DefinitelyNoSuchNightbiteEvent"
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"No events found", response.data)

    # ---------------------------------------------------------
    # EVENT DETAILS
    # ---------------------------------------------------------

    def test_018_event_detail_page_renders(self):
        response = self.client.get(
            f"/event/{self.main_event}"
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Brisbane Night Market", response.data)
        self.assertIn(b"Riverside Precinct", response.data)
        self.assertIn(b"South Brisbane", response.data)

    def test_019_event_detail_displays_cuisine(self):
        response = self.client.get(
            f"/event/{self.main_event}"
        )

        self.assertIn(b"Cuisine", response.data)
        self.assertIn(b"Korean", response.data)

    def test_020_event_detail_displays_dietary_options(self):
        response = self.client.get(
            f"/event/{self.main_event}"
        )

        self.assertIn(b"Vegetarian", response.data)
        self.assertIn(b"Vegan", response.data)
        self.assertIn(b"Gluten-free", response.data)

    def test_021_event_detail_displays_accessibility(self):
        response = self.client.get(
            f"/event/{self.main_event}"
        )

        self.assertIn(b"Accessibility", response.data)
        self.assertIn(
            b"Wheelchair accessible",
            response.data,
        )

    def test_022_invalid_event_returns_404(self):
        response = self.client.get("/event/999999")

        self.assertEqual(response.status_code, 404)

    # ---------------------------------------------------------
    # EVENT STATUS
    # ---------------------------------------------------------

    def test_023_open_event_status(self):
        with self.app.app_context():
            event = db.session.get(Event, self.main_event)
            self.assertEqual(event.status, "Open")

    def test_024_cancelled_event_status(self):
        with self.app.app_context():
            event = db.session.get(
                Event,
                self.cancelled_event,
            )
            self.assertEqual(event.status, "Cancelled")

    def test_025_past_event_status(self):
        with self.app.app_context():
            event = db.session.get(Event, self.past_event)
            self.assertEqual(event.status, "Inactive")

    def test_026_sold_out_event_status(self):
        with self.app.app_context():
            event = db.session.get(Event, self.main_event)

            order = Order(
                user_id=self.user_id,
                event_id=event.id,
                quantity=event.ticket_capacity,
                unit_price=event.ticket_price,
                total_amount=(
                    event.ticket_price
                    * event.ticket_capacity
                ),
                booking_datetime=datetime.now(),
                order_reference="NB-SOLD01",
            )

            db.session.add(order)
            db.session.commit()

            self.assertEqual(event.remaining_tickets, 0)
            self.assertEqual(event.status, "Sold Out")

    # ---------------------------------------------------------
    # RELATED-EVENT / SMART DISCOVERY
    # ---------------------------------------------------------

    def test_027_recommendations_exclude_current_event(self):
        with self.app.app_context():
            event = db.session.get(Event, self.main_event)
            recommendations = build_recommendations(event)

            ids = [
                item["event"].id
                for item in recommendations
            ]

            self.assertNotIn(event.id, ids)

    def test_028_recommendations_exclude_cancelled_events(self):
        with self.app.app_context():
            event = db.session.get(Event, self.main_event)
            recommendations = build_recommendations(event)

            ids = [
                item["event"].id
                for item in recommendations
            ]

            self.assertNotIn(self.cancelled_event, ids)

    def test_029_recommendations_exclude_inactive_events(self):
        with self.app.app_context():
            event = db.session.get(Event, self.main_event)
            recommendations = build_recommendations(event)

            ids = [
                item["event"].id
                for item in recommendations
            ]

            self.assertNotIn(self.past_event, ids)

    def test_030_related_event_scores_above_unrelated_event(self):
        with self.app.app_context():
            event = db.session.get(Event, self.main_event)
            recommendations = build_recommendations(event)

            scores = {
                item["event"].id: item["score"]
                for item in recommendations
            }

            self.assertGreater(
                scores[self.related_event],
                scores[self.unrelated_event],
            )

   
    def test_031_recommendation_reasons_are_generated(self):
        with self.app.app_context():
            event = db.session.get(Event, self.main_event)
            recommendations = build_recommendations(event)

            related = next(
                item
                for item in recommendations
                if item["event"].id == self.related_event
            )

            self.assertTrue(related["reasons"])

            self.assertIn(
                "Both are Night Markets events",
                related["reasons"],
            )

            semantic_score = related["semantic_score"]

            if semantic_score >= 0.60:
                self.assertIn(
                    "Strong AI-matched event similarity",
                    related["reasons"],
                )
            else:
                self.assertIn(
                    "AI-matched related food experience",
                    related["reasons"],
                )

            self.assertGreaterEqual(
                related["score"],
                0.0,
            )

            self.assertLessEqual(
                related["score"],
                1.0,
            )

    def test_032_event_page_displays_smart_recommendations(self):
        response = self.client.get(
            f"/event/{self.main_event}"
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"AI-powered discovery", response.data)
        self.assertIn(b"You might also like", response.data)
        self.assertIn(
            b"Korean Riverside Feast",
            response.data,
        )

    def test_033_event_page_does_not_recommend_itself(self):
        response = self.client.get(
            f"/event/{self.main_event}"
        )

        # Main event should occur in the page heading/content,
        # but must not appear as a recommendation card.
        self.assertNotIn(
            b'alt="Brisbane Night Market"',
            self._recommendation_section(response.data),
        )

    def _recommendation_section(self, page):
        marker = b'id="recommendationGrid"'

        if marker not in page:
            return b""

        section = page.split(marker, 1)[1]

        if b"<!-- View All Recommendations -->" in section:
            section = section.split(
                b"<!-- View All Recommendations -->",
                1,
            )[0]

        return section

    # ---------------------------------------------------------
    # COMBINED FILTERS AND REGRESSION
    # ---------------------------------------------------------

    def test_034_combined_keyword_and_location_filter(self):
        response = self.client.get(
            "/?q=Korean&location=South+Brisbane"
        )

        self.assertIn(b"Brisbane Night Market", response.data)
        self.assertIn(b"Korean Riverside Feast", response.data)
        self.assertNotIn(b"Valley Taco Trucks", response.data)

    def test_035_search_value_is_preserved(self):
        response = self.client.get("/?q=Korean")

        self.assertIn(
            b'value="Korean"',
            response.data,
        )

    def test_036_selected_location_is_preserved(self):
        response = self.client.get(
            "/?location=South+Brisbane"
        )

        self.assertIn(
            b'value="South Brisbane"',
            response.data,
        )
        self.assertIn(
            b"selected",
            response.data,
        )

    def test_037_homepage_contains_event_detail_links(self):
        response = self.client.get("/")

        self.assertIn(
            f"/event/{self.main_event}".encode(),
            response.data,
        )
        self.assertIn(
            f"/event/{self.related_event}".encode(),
            response.data,
        )

    def test_038_bare_event_route_returns_200(self):
        response = self.client.get("/event")

        self.assertEqual(response.status_code, 200)

    def test_039_homepage_empty_database_returns_200(self):
        with self.app.app_context():
            db.session.query(Order).delete()
            db.session.query(Event).delete()
            db.session.commit()

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"No events found", response.data)

    def test_040_bare_event_route_handles_empty_database(self):
        with self.app.app_context():
            db.session.query(Order).delete()
            db.session.query(Event).delete()
            db.session.commit()

        response = self.client.get("/event")

        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
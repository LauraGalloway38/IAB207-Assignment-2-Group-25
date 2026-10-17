
import unittest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

import numpy as np

from nightbite import create_app, db
from nightbite.models import Category, Event, User
from nightbite.views import build_recommendations


class AIRecommendationTests(unittest.TestCase):

    def setUp(self):
        self.app = create_app({
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SECRET_KEY": "nightbite-ai-test-secret",
        })

        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()

            user = User(
                name="AI Test User",
                email="ai-test@example.com",
                contact_number="0400000000",
                street_address="Test Street",
                password_hash="test-hash",
            )

            market_category = Category(name="Night Markets")
            dessert_category = Category(name="Dessert")
            truck_category = Category(name="Food Trucks")

            db.session.add_all([
                user,
                market_category,
                dessert_category,
                truck_category,
            ])
            db.session.commit()

            self.user_id = user.id
            self.market_category_id = market_category.id
            self.dessert_category_id = dessert_category.id
            self.truck_category_id = truck_category.id

            self.source_id = self.create_event(
                "Brisbane Night Market",
                "Korean street food and market stalls",
                self.market_category_id,
                "Korean",
                "South Brisbane",
            )

            self.related_id = self.create_event(
                "Korean Riverside Feast",
                "Korean food stalls and outdoor dining",
                self.market_category_id,
                "Korean",
                "South Brisbane",
            )

            self.unrelated_id = self.create_event(
                "Valley Taco Trucks",
                "Mexican tacos and food trucks",
                self.truck_category_id,
                "Mexican",
                "Fortitude Valley",
            )

            self.cancelled_id = self.create_event(
                "Cancelled Dessert Night",
                "Dessert stalls and sweet treats",
                self.dessert_category_id,
                "Dessert",
                "West End",
                cancelled=True,
            )

            self.past_id = self.create_event(
                "Past Street Food Festival",
                "A food festival that has ended",
                self.market_category_id,
                "International",
                "Brisbane",
                past=True,
            )

            db.session.commit()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def create_event(
        self,
        title,
        description,
        category_id,
        cuisine,
        suburb,
        cancelled=False,
        past=False,
    ):
        start = datetime.now() + timedelta(days=10)

        if past:
            start = datetime.now() - timedelta(days=10)

        event = Event(
            title=title,
            description=description,
            image_filename="images/test.jpg",
            venue="Test Venue",
            street_address="100 Test Street",
            suburb=suburb,
            state="QLD",
            start_datetime=start,
            end_datetime=start + timedelta(hours=4),
            cuisine=cuisine,
            vegetarian=True,
            vegan=True,
            gluten_free=True,
            halal=False,
            accessibility="Wheelchair accessible",
            ticket_price=Decimal("15.00"),
            ticket_capacity=100,
            is_cancelled=cancelled,
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

    def get_recommendations(self):
        with self.app.app_context():
            source = db.session.get(Event, self.source_id)
            return build_recommendations(source)

    def test_001_excludes_current_event(self):
        recommendations = self.get_recommendations()

        ids = [
            item["event"].id
            for item in recommendations
        ]

        self.assertNotIn(self.source_id, ids)

    def test_002_excludes_cancelled_events(self):
        recommendations = self.get_recommendations()

        ids = [
            item["event"].id
            for item in recommendations
        ]

        self.assertNotIn(self.cancelled_id, ids)

    def test_003_excludes_past_events(self):
        recommendations = self.get_recommendations()

        ids = [
            item["event"].id
            for item in recommendations
        ]

        self.assertNotIn(self.past_id, ids)

    def test_004_related_event_ranks_above_unrelated(self):
        recommendations = self.get_recommendations()

        scores = {
            item["event"].id: item["score"]
            for item in recommendations
        }

        self.assertGreater(
            scores[self.related_id],
            scores[self.unrelated_id],
        )

    def test_005_recommendations_include_explanations(self):
        recommendations = self.get_recommendations()

        related = next(
            item
            for item in recommendations
            if item["event"].id == self.related_id
        )

        self.assertTrue(related["reasons"])

        self.assertIn(
            "Both are Night Markets events",
            related["reasons"],
        )

    def test_006_recommendations_include_ai_scores(self):
        recommendations = self.get_recommendations()

        for item in recommendations:
            self.assertIn("semantic_score", item)
            self.assertIn("attribute_score", item)
            self.assertIn("score", item)

    def test_007_maximum_four_recommendations(self):
        recommendations = self.get_recommendations()

        self.assertLessEqual(
            len(recommendations),
            4,
        )


if __name__ == "__main__":
    unittest.main()


import unittest
from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from nightbite.ai_search import (
    cosine_similarity,
    hybrid_search,
)


class FakeEvent:
    def __init__(
        self,
        event_id,
        title,
        description,
        cuisine,
        category,
        venue,
        suburb,
        ticket_price,
    ):
        self.id = event_id
        self.title = title
        self.description = description
        self.cuisine = cuisine
        self.category = SimpleNamespace(name=category)

        self.venue = venue
        self.street_address = "100 Test Street"
        self.suburb = suburb
        self.state = "QLD"

        self.start_datetime = datetime.now() + timedelta(days=10)
        self.end_datetime = self.start_datetime + timedelta(hours=4)

        self.ticket_price = Decimal(str(ticket_price))
        self.ticket_capacity = 100

        self.vegetarian = False
        self.vegan = False
        self.gluten_free = False
        self.halal = False

        self.accessibility = "Wheelchair accessible"

        self.is_cancelled = False
        self.acknowledgement_type = "none"
        self.acknowledgement_text = ""
        self.traditional_custodians = ""
        self.acknowledgement_source = ""


class AISearchTests(unittest.TestCase):

    def setUp(self):
        self.market = FakeEvent(
            event_id=1,
            title="Riverside Night Market",
            description="Asian street food stalls and outdoor dining",
            cuisine="Asian",
            category="Night Markets",
            venue="Riverside Precinct",
            suburb="South Brisbane",
            ticket_price=12.00,
        )

        self.dessert = FakeEvent(
            event_id=2,
            title="Midnight Dessert Club",
            description="Sweet treats, cakes and pastries",
            cuisine="Dessert",
            category="Dessert",
            venue="Dessert Hall",
            suburb="West End",
            ticket_price=15.00,
        )

        self.tacos = FakeEvent(
            event_id=3,
            title="Valley Taco Trucks",
            description="Mexican tacos and food trucks",
            cuisine="Mexican",
            category="Food Trucks",
            venue="Valley Precinct",
            suburb="Fortitude Valley",
            ticket_price=20.00,
        )

        self.events = [
            self.market,
            self.dessert,
            self.tacos,
        ]

        self.embeddings = {
            self.market: np.array(
                [1.0, 0.0, 0.0],
                dtype=np.float32,
            ),
            self.dessert: np.array(
                [0.0, 1.0, 0.0],
                dtype=np.float32,
            ),
            self.tacos: np.array(
                [0.2, 0.8, 0.0],
                dtype=np.float32,
            ),
        }

    def test_001_identical_vectors_have_high_similarity(self):
        vector = np.array(
            [1.0, 0.0, 0.0],
            dtype=np.float32,
        )

        score = cosine_similarity(vector, vector)

        self.assertAlmostEqual(score, 1.0, places=5)

    def test_002_orthogonal_vectors_have_zero_similarity(self):
        first = np.array(
            [1.0, 0.0, 0.0],
            dtype=np.float32,
        )

        second = np.array(
            [0.0, 1.0, 0.0],
            dtype=np.float32,
        )

        score = cosine_similarity(first, second)

        self.assertAlmostEqual(score, 0.0, places=5)

    @patch("nightbite.ai_search.get_event_embedding")
    @patch("nightbite.ai_search.get_model")
    def test_003_semantic_search_ranks_relevant_event_first(
        self,
        mock_model,
        mock_event_embedding,
    ):
        mock_model.return_value.encode.return_value = np.array(
            [1.0, 0.0, 0.0],
            dtype=np.float32,
        )

        mock_event_embedding.side_effect = (
            lambda event: self.embeddings[event]
        )

        results = hybrid_search(
            "outdoor Asian food experience",
            self.events,
        )

        self.assertTrue(results)
        self.assertEqual(results[0], self.market)

        mock_model.return_value.encode.assert_called_once()
        self.assertEqual(mock_event_embedding.call_count, 3)

    @patch("nightbite.ai_search.get_event_embedding")
    @patch("nightbite.ai_search.get_model")
    def test_004_hybrid_search_returns_ranked_events(
        self,
        mock_model,
        mock_event_embedding,
    ):
        mock_model.return_value.encode.return_value = np.array(
            [1.0, 0.0, 0.0],
            dtype=np.float32,
        )

        mock_event_embedding.side_effect = (
            lambda event: self.embeddings[event]
        )

        results = hybrid_search(
            "Asian street food",
            self.events,
        )

        self.assertIsInstance(results, list)
        self.assertTrue(results)
        self.assertEqual(results[0], self.market)

    def test_005_empty_event_list_returns_empty_results(self):
        results = hybrid_search(
            "night markets",
            [],
        )

        self.assertEqual(results, [])

    def test_006_empty_query_returns_all_events(self):
        results = hybrid_search(
            "",
            self.events,
        )

        self.assertEqual(results, self.events)

    @patch("nightbite.ai_search.get_model")
    def test_007_keyword_fallback_when_ai_unavailable(
        self,
        mock_model,
    ):
        mock_model.side_effect = RuntimeError(
            "AI model unavailable"
        )

        results = hybrid_search(
            "tacos",
            self.events,
        )

        self.assertTrue(results)
        self.assertEqual(results[0], self.tacos)

    @patch("nightbite.ai_search.get_event_embedding")
    @patch("nightbite.ai_search.get_model")
    def test_008_semantic_similarity_affects_ranking(
        self,
        mock_model,
        mock_event_embedding,
    ):
        mock_model.return_value.encode.return_value = np.array(
            [1.0, 0.0, 0.0],
            dtype=np.float32,
        )

        mock_event_embedding.side_effect = (
            lambda event: self.embeddings[event]
        )

        results = hybrid_search(
            "outdoor dining experience",
            self.events,
        )

        self.assertTrue(results)
        self.assertEqual(results[0], self.market)

    @patch("nightbite.ai_search.get_model")
    def test_009_no_keyword_match_in_fallback(
        self,
        mock_model,
    ):
        mock_model.side_effect = RuntimeError(
            "AI unavailable"
        )

        results = hybrid_search(
            "xyznonexistentfoodexperience",
            self.events,
        )

        self.assertEqual(results, [])


if __name__ == "__main__":
    unittest.main()

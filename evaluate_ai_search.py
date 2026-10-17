
from contextlib import redirect_stdout
from datetime import datetime, timedelta
from decimal import Decimal
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from nightbite.ai_search import (
    SEMANTIC_WEIGHT,
    KEYWORD_WEIGHT,
    MIN_RELEVANCE_SCORE,
    event_text,
    get_model,
    hybrid_search,
    keyword_score,
)


class EvaluationEvent:
    def __init__(
        self,
        event_id,
        title,
        description,
        category,
        cuisine,
        suburb,
        venue,
        price=15,
        vegan=False,
        vegetarian=False,
        gluten_free=False,
        halal=False,
    ):
        self.id = event_id
        self.title = title
        self.description = description
        self.category = SimpleNamespace(name=category)
        self.cuisine = cuisine
        self.suburb = suburb
        self.venue = venue
        self.accessibility = "Wheelchair accessible"
        self.ticket_price = Decimal(str(price))

        self.vegan = vegan
        self.vegetarian = vegetarian
        self.gluten_free = gluten_free
        self.halal = halal

        self.start_datetime = datetime.now() + timedelta(days=10)
        self.end_datetime = self.start_datetime + timedelta(hours=4)


EVENTS = [
    EvaluationEvent(
        1,
        "Riverside Night Market",
        "Asian street food stalls, open-air dining and evening entertainment",
        "Night Markets",
        "Asian",
        "South Brisbane",
        "Riverside Precinct",
    ),
    EvaluationEvent(
        2,
        "Midnight Dessert Club",
        "Late-night cakes, pastries, chocolate and sweet treats",
        "Dessert",
        "Dessert",
        "West End",
        "Dessert Hall",
    ),
    EvaluationEvent(
        3,
        "Valley Taco Trucks",
        "Mexican tacos, burritos and casual meals served from food trucks",
        "Food Trucks",
        "Mexican",
        "Fortitude Valley",
        "Valley Precinct",
    ),
    EvaluationEvent(
        4,
        "Plant-Based Food Festival",
        "Vegan meals, plant-based cooking and meat-free dishes",
        "Cultural Food",
        "Vegan",
        "Brisbane",
        "Festival Grounds",
        vegan=True,
        vegetarian=True,
    ),
    EvaluationEvent(
        5,
        "Brisbane Pizza Pop-Up",
        "Wood-fired pizzas, Italian dishes and fresh ingredients",
        "Pop-Ups",
        "Italian",
        "New Farm",
        "Pizza Courtyard",
    ),
    EvaluationEvent(
        6,
        "Global Street Food Festival",
        "International dishes, multicultural flavours and food stalls",
        "Street Food",
        "International",
        "South Bank",
        "Cultural Plaza",
    ),
]


QUERIES = [
    (
        "somewhere to eat outdoors at night",
        {1},
    ),
    (
        "something sweet after dinner",
        {2},
    ),
    (
        "casual Mexican food from mobile vendors",
        {3},
    ),
    (
        "meals without animal products",
        {4},
    ),
    (
        "fresh Italian food cooked in a traditional oven",
        {5},
    ),
    (
        "try dishes from different countries",
        {6},
    ),
]


def keyword_search(query, events):
    scored = [
        (event, keyword_score(query, event))
        for event in events
    ]

    scored.sort(
        key=lambda item: (
            -item[1],
            item[0].start_datetime,
            item[0].id,
        )
    )

    return [
        event
        for event, score in scored
        if score > 0
    ]


def evaluate():
    print("Loading Sentence Transformers model...")

    model = get_model()

    print("Generating event embeddings...")

    embeddings = {
        event.id: np.asarray(
            model.encode(
                event_text(event),
                normalize_embeddings=True,
                convert_to_numpy=True,
            ),
            dtype=np.float32,
        )
        for event in EVENTS
    }

    keyword_hits = 0
    hybrid_hits = 0

    print("\nNIGHTBITE AI SEARCH EVALUATION")
    print("=" * 75)

    print(
        f"Semantic weight: {SEMANTIC_WEIGHT} | "
        f"Keyword weight: {KEYWORD_WEIGHT}"
    )
    print(f"Minimum hybrid relevance: {MIN_RELEVANCE_SCORE}")

    for number, (query, expected_ids) in enumerate(QUERIES, 1):

        keyword_results = keyword_search(query, EVENTS)

        with patch(
            "nightbite.ai_search.get_event_embedding",
            side_effect=lambda event: embeddings[event.id],
        ):
            with redirect_stdout(StringIO()):
                hybrid_results = hybrid_search(query, EVENTS)

        keyword_top = (
            keyword_results[0]
            if keyword_results
            else None
        )

        hybrid_top = (
            hybrid_results[0]
            if hybrid_results
            else None
        )

        keyword_success = (
            keyword_top is not None
            and keyword_top.id in expected_ids
        )

        hybrid_success = (
            hybrid_top is not None
            and hybrid_top.id in expected_ids
        )

        keyword_hits += int(keyword_success)
        hybrid_hits += int(hybrid_success)

        print(f"\nQuery {number}: {query}")

        print(
            "Expected: "
            + ", ".join(
                event.title
                for event in EVENTS
                if event.id in expected_ids
            )
        )

        print(
            "Keyword top result: "
            + (
                keyword_top.title
                if keyword_top
                else "No matching event"
            )
        )

        print(
            "Hybrid top result: "
            + (
                hybrid_top.title
                if hybrid_top
                else "No matching event"
            )
        )

        print(
            f"Keyword Hit@1: {'PASS' if keyword_success else 'FAIL'}"
        )

        print(
            f"Hybrid Hit@1: {'PASS' if hybrid_success else 'FAIL'}"
        )

    total = len(QUERIES)

    keyword_accuracy = keyword_hits / total * 100
    hybrid_accuracy = hybrid_hits / total * 100

    print("\n" + "=" * 75)
    print("FINAL RESULTS")
    print("=" * 75)

    print(
        f"Keyword-only Hit@1: "
        f"{keyword_hits}/{total} ({keyword_accuracy:.1f}%)"
    )

    print(
        f"Hybrid AI Hit@1: "
        f"{hybrid_hits}/{total} ({hybrid_accuracy:.1f}%)"
    )

    print(
        f"Difference: "
        f"{hybrid_accuracy - keyword_accuracy:+.1f} percentage points"
    )

    print("=" * 75)


if __name__ == "__main__":
    evaluate()

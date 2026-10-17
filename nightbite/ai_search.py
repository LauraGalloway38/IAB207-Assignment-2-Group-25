
from decimal import Decimal, InvalidOperation
from functools import lru_cache
import hashlib
import logging
import re

import numpy as np
from sentence_transformers import SentenceTransformer

from . import db
from .models import EventEmbedding


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

SEMANTIC_WEIGHT = 0.70
KEYWORD_WEIGHT = 0.30
MIN_RELEVANCE_SCORE = 0.30

logger = logging.getLogger(__name__)

_embedding_cache = {}

STOP_WORDS = {
    "a", "an", "and", "at", "for", "in", "is",
    "of", "on", "or", "the", "to", "with",
    "some", "find", "me", "i", "want",
}


@lru_cache(maxsize=1)
def get_model():
    return SentenceTransformer(MODEL_NAME)


def event_text(event):
    dietary = [
        name
        for name, enabled in (
            ("vegetarian", event.vegetarian),
            ("vegan plant-based", event.vegan),
            ("gluten-free", event.gluten_free),
            ("halal", event.halal),
        )
        if enabled
    ]

    category = (
        event.category.name
        if event.category is not None
        else ""
    )

    fields = [
        event.title,
        event.description,
        category,
        event.cuisine,
        event.venue,
        event.suburb,
        event.accessibility,
        " ".join(dietary),
    ]

    return " ".join(
        str(value).strip()
        for value in fields
        if value
    )


def text_fingerprint(text):
    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()




def get_event_embedding(event):
    text = event_text(event)
    fingerprint = text_fingerprint(text)
    key = (event.id, MODEL_NAME, fingerprint)

    if key in _embedding_cache:
        return _embedding_cache[key]

    stored = db.session.scalar(
        db.select(EventEmbedding).where(
            EventEmbedding.event_id == event.id
        )
    )

    if (
        stored is not None
        and stored.model_name == MODEL_NAME
        and stored.content_hash == fingerprint
    ):
        embedding = np.frombuffer(
            stored.embedding,
            dtype=np.float32,
        ).copy()

        if embedding.shape == (384,):
            _embedding_cache[key] = embedding
            return embedding

    embedding = np.asarray(
        get_model().encode(
            text,
            normalize_embeddings=True,
            convert_to_numpy=True,
        ),
        dtype=np.float32,
    )

    return embedding


def index_event_embedding(event):
    db.session.flush()

    text = event_text(event)
    fingerprint = text_fingerprint(text)

    stored = db.session.scalar(
        db.select(EventEmbedding).where(
            EventEmbedding.event_id == event.id
        )
    )

    if (
        stored is not None
        and stored.model_name == MODEL_NAME
        and stored.content_hash == fingerprint
        and len(stored.embedding) == 384 * 4
    ):
        return False

    embedding = np.asarray(
        get_model().encode(
            text,
            normalize_embeddings=True,
            convert_to_numpy=True,
        ),
        dtype=np.float32,
    )

    if stored is None:
        stored = EventEmbedding(
            event_id=event.id,
            model_name=MODEL_NAME,
            content_hash=fingerprint,
            embedding=embedding.tobytes(),
        )
        db.session.add(stored)
    else:
        stored.model_name = MODEL_NAME
        stored.content_hash = fingerprint
        stored.embedding = embedding.tobytes()

    db.session.flush()

    return True


def clear_embedding_cache():
    _embedding_cache.clear()


def cosine_similarity(first, second):
    first = np.asarray(first, dtype=float)
    second = np.asarray(second, dtype=float)

    denominator = (
        np.linalg.norm(first)
        * np.linalg.norm(second)
    )

    if denominator == 0:
        return 0.0

    return float(
        np.dot(first, second) / denominator
    )


def tokenize(text):
    return set(
        word
        for word in re.findall(
            r"\b\w+\b",
            text.casefold(),
        )
        if word not in STOP_WORDS
    )


def keyword_score(query, event):
    query = query.casefold().strip()

    if not query:
        return 0.0

    category = (
        event.category.name
        if event.category is not None
        else ""
    )

    fields = [
        (event.title or "").casefold(),
        (event.description or "").casefold(),
        (event.cuisine or "").casefold(),
        (event.venue or "").casefold(),
        (event.suburb or "").casefold(),
        category.casefold(),
    ]

    if any(query in field for field in fields):
        return 1.0

    query_words = tokenize(query)

    if not query_words:
        return 0.0

    searchable_words = tokenize(
        " ".join(fields)
    )

    matched = query_words.intersection(
        searchable_words
    )

    return len(matched) / len(query_words)


def interpret_query(query):
    text = query.casefold().strip()

    constraints = {
        "vegan": False,
        "vegetarian": False,
        "gluten_free": False,
        "halal": False,
        "max_price": None,
        "free_only": False,
    }

    dietary_patterns = {
        "vegan": (
            r"\b(?:vegan|plant[\s-]*based)\b"
        ),
        "vegetarian": r"\bvegetarian\b",
        "gluten_free": (
            r"\b(?:gluten[\s-]*free|"
            r"coeliac|celiac)\b"
        ),
        "halal": r"\bhalal\b",
    }

    for field, pattern in dietary_patterns.items():
        for match in re.finditer(pattern, text):
            prefix = text[
                max(0, match.start() - 25):
                match.start()
            ]

            negated = re.search(
                r"\b(?:not|non|no|without)\s*$",
                prefix,
            )

            if not negated:
                constraints[field] = True

    price_match = re.search(
        r"\b(?:under|below|less than|"
        r"up to|maximum|max)\s*"
        r"\$?\s*(\d+(?:\.\d{1,2})?)\b",
        text,
    )

    if not price_match:
        price_match = re.search(
            r"\$\s*(\d+(?:\.\d{1,2})?)"
            r"\s*(?:or less|or under|maximum|max)\b",
            text,
        )

    if price_match:
        try:
            constraints["max_price"] = Decimal(
                price_match.group(1)
            )
        except InvalidOperation:
            pass

    if re.search(
        r"\b(?:free entry|free admission|"
        r"free events?|no entry fee)\b",
        text,
    ):
        constraints["free_only"] = True

    return constraints


def matches_constraints(event, constraints):
    for field in (
        "vegan",
        "vegetarian",
        "gluten_free",
        "halal",
    ):
        if (
            constraints[field]
            and not getattr(event, field, False)
        ):
            return False

    try:
        price = Decimal(
            str(event.ticket_price)
        )
    except (InvalidOperation, TypeError):
        return False

    if (
        constraints["free_only"]
        and price != Decimal("0")
    ):
        return False

    maximum = constraints["max_price"]

    if maximum is not None and price > maximum:
        return False

    return True


def hybrid_search(
    query,
    events,
    min_score=MIN_RELEVANCE_SCORE,
):
    events = list(events)

    if not query or not query.strip():
        return events

    if not events:
        return []

    constraints = interpret_query(query)

    eligible_events = [
        event
        for event in events
        if matches_constraints(event, constraints)
    ]

    logger.info(
        "AI search: %s | Eligible: %s/%s",
        query,
        len(eligible_events),
        len(events),
    )

    if not eligible_events:
        return []

    try:
        query_embedding = get_model().encode(
            query.strip(),
            normalize_embeddings=True,
            convert_to_numpy=True,
        )

        ranked = []

        for event in eligible_events:
            semantic = cosine_similarity(
                query_embedding,
                get_event_embedding(event),
            )

            keyword = keyword_score(
                query,
                event,
            )

            score = (
                SEMANTIC_WEIGHT
                * max(0.0, semantic)
                + KEYWORD_WEIGHT
                * keyword
            )

            ranked.append({
                "event": event,
                "semantic": semantic,
                "keyword": keyword,
                "score": score,
            })

    except Exception:
        logger.exception(
            "Semantic search failed; "
            "using keyword fallback."
        )

        ranked = []

        for event in eligible_events:
            keyword = keyword_score(
                query,
                event,
            )

            ranked.append({
                "event": event,
                "semantic": 0.0,
                "keyword": keyword,
                "score": keyword,
            })

    ranked.sort(
        key=lambda result: (
            -result["score"],
            result["event"].start_datetime,
            result["event"].id,
        )
    )

    print(f"\nAI SEARCH: {query}")
    print(f"Constraints: {constraints}")
    print("-" * 75)
    print(
        f'{"Event":30} '
        f'{"Semantic":>10} '
        f'{"Keyword":>10} '
        f'{"Hybrid":>10}'
    )
    print("-" * 75)

    for result in ranked:
        print(
            f'{result["event"].title[:30]:30} '
            f'{result["semantic"]:>10.3f} '
            f'{result["keyword"]:>10.3f} '
            f'{result["score"]:>10.3f}'
        )

    relevant = [
        result["event"]
        for result in ranked
        if result["score"] >= min_score
    ]

    print("-" * 75)
    print(
        f"Relevant results: "
        f"{len(relevant)} / "
        f"{len(eligible_events)}"
    )
    print(
        f"Minimum relevance score: "
        f"{min_score:.2f}"
    )
    print("-" * 75)

    return relevant

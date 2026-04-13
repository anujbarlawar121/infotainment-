import math
import re
from collections import defaultdict
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .services import get_content_collections


MOOD_HINTS = {
    "happy": "uplifting feel-good comedy pop bright inspiring celebration",
    "sad": "comfort gentle emotional reflective warm hopeful healing",
    "excited": "trending action fast vibrant energetic intense viral",
    "relaxed": "calm chill mellow acoustic scenic focus peaceful",
    "curious": "insightful documentary innovation world discovery analysis",
}

MOOD_CATEGORY_BIAS = {
    "happy": {"songs": 1.0, "memes": 0.8, "videos": 0.5},
    "sad": {"songs": 0.7, "movies": 0.5, "news": -0.15},
    "excited": {"videos": 0.9, "movies": 0.75, "news": 0.4},
    "relaxed": {"songs": 0.9, "movies": 0.45, "news": 0.1},
    "curious": {"news": 1.0, "videos": 0.5, "movies": 0.2},
}

INTEREST_CATEGORY_HINTS = {
    "ai": "news",
    "tech": "news",
    "technology": "news",
    "startup": "news",
    "politics": "news",
    "economy": "news",
    "movie": "movies",
    "cinema": "movies",
    "film": "movies",
    "trailer": "movies",
    "music": "songs",
    "song": "songs",
    "album": "songs",
    "dance": "songs",
    "video": "videos",
    "youtube": "videos",
    "creator": "videos",
    "gaming": "videos",
    "sports": "videos",
    "football": "videos",
    "cricket": "videos",
    "basketball": "videos",
    "soccer": "videos",
    "nba": "videos",
    "nfl": "videos",
    "meme": "memes",
    "funny": "memes",
    "humor": "memes",
}

TRUSTED_DOMAINS = (
    "bbc",
    "reuters",
    "nytimes",
    "theverge",
    "arstechnica",
    "engadget",
    "youtube",
    "spotify",
    "apple",
    "deezer",
    "tmdb",
    "imgflip",
    "reddit",
)


def _normalize_text(value):
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def _tokenize(value):
    return [token for token in re.findall(r"[a-z0-9]+", (value or "").lower()) if len(token) > 1]


def _parse_date(raw_value):
    if not raw_value:
        return None
    value = raw_value.strip()
    if not value:
        return None
    try:
        if value.endswith("Z"):
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        else:
            parsed = datetime.fromisoformat(value)
    except ValueError:
        try:
            parsed = parsedate_to_datetime(value)
        except Exception:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _freshness_score(item):
    parsed = _parse_date(item.get("published_at", ""))
    if not parsed:
        return 0.35
    age_days = max((datetime.now(timezone.utc) - parsed).days, 0)
    if age_days <= 1:
        return 1.0
    if age_days <= 3:
        return 0.85
    if age_days <= 7:
        return 0.7
    if age_days <= 30:
        return 0.5
    return 0.3


def _source_quality(item):
    provider = _normalize_text(item.get("provider", ""))
    domain = _normalize_text(item.get("domain", "")) or _normalize_text(urlparse(item.get("url", "")).netloc)
    source_text = f"{provider} {domain}"
    if any(pattern in source_text for pattern in TRUSTED_DOMAINS):
        return 1.0
    if source_text:
        return 0.6
    return 0.45


def _infer_categories(interests):
    inferred = set()
    for token in _tokenize(interests):
        mapped = INTEREST_CATEGORY_HINTS.get(token)
        if mapped:
            inferred.add(mapped)
    return inferred


def _keyword_overlap(item, interest_tokens):
    if not interest_tokens:
        return 0.0
    haystack_tokens = set(
        _tokenize(
            _normalize_text(
                f"{item.get('title', '')} {item.get('description', '')} {item.get('provider', '')} {item.get('category', '')}"
            )
        )
    )
    matches = sum(1 for token in interest_tokens if token in haystack_tokens)
    return min(matches / max(len(interest_tokens), 1), 1.0)


def _matched_interest_tokens(item, interest_tokens):
    haystack_tokens = set(
        _tokenize(
            _normalize_text(
                f"{item.get('title', '')} {item.get('description', '')} {item.get('provider', '')} {item.get('category', '')}"
            )
        )
    )
    return [token for token in interest_tokens if token in haystack_tokens]


def _match_explanation(item, overlap, category_score, freshness, source_score, interest_tokens):
    reasons = []
    if overlap >= 0.35 and interest_tokens:
        matched = _matched_interest_tokens(item, interest_tokens)
        if matched:
            reasons.append(f"Matches interests: {', '.join(sorted(set(matched[:3])))}")
        else:
            reasons.append("Strong keyword match to your interests")
    if category_score >= 0.85:
        reasons.append(f"Aligned with {item.get('category', 'your preferred')} content")
    if freshness >= 0.85:
        reasons.append("Recently published")
    if source_score >= 0.95:
        reasons.append("From a high-confidence source")
    return " | ".join(reasons[:3]) or "Relevant based on mood + semantic similarity"


def _category_alignment(item, mood, inferred_categories):
    category_slug = (item.get("category", "") or "").strip().lower()
    mood_bias = MOOD_CATEGORY_BIAS.get(mood, {}).get(category_slug, 0.0)
    inferred_bias = 0.85 if category_slug in inferred_categories else 0.0
    return min(max(0.25 + mood_bias + inferred_bias, 0.0), 1.0)


def _build_profile(mood, interests, inferred_categories):
    category_words = " ".join(sorted(inferred_categories))
    mood_hint = MOOD_HINTS.get(mood, mood)
    return f"{interests} {mood_hint} {category_words}".strip()


def build_catalog():
    items = []
    for collection in get_content_collections(limit=18).values():
        items.extend(collection)
    return items


def _semantic_similarity(catalog, profile):
    corpus = [
        _normalize_text(
            f"{item.get('title', '')} {item.get('description', '')} {item.get('category', '')} {item.get('provider', '')}"
        )
        for item in catalog
    ]

    word_vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), min_df=1, sublinear_tf=True)
    word_matrix = word_vectorizer.fit_transform(corpus + [profile])
    word_scores = cosine_similarity(word_matrix[-1], word_matrix[:-1]).flatten()

    char_vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=1, sublinear_tf=True)
    char_matrix = char_vectorizer.fit_transform(corpus + [profile])
    char_scores = cosine_similarity(char_matrix[-1], char_matrix[:-1]).flatten()
    return (0.72 * word_scores) + (0.28 * char_scores)


def _normalize_confidence(raw_score, max_score):
    if max_score <= 0:
        return 35.0
    scaled = raw_score / max_score
    return round(min(99.0, max(35.0, 38 + (scaled * 61))), 1)


def get_recommendations(mood, interests, limit=8, catalog=None):
    catalog = catalog if catalog is not None else build_catalog()
    if not catalog:
        return []

    clean_mood = (mood or "curious").strip().lower()
    clean_interests = (interests or "").strip().lower()
    interest_tokens = _tokenize(clean_interests)
    inferred_categories = _infer_categories(clean_interests)
    profile = _build_profile(clean_mood, clean_interests, inferred_categories)

    semantic_scores = _semantic_similarity(catalog, profile)
    ranked = []
    for item, semantic in zip(catalog, semantic_scores):
        overlap = _keyword_overlap(item, interest_tokens)
        category_score = _category_alignment(item, clean_mood, inferred_categories)
        freshness = _freshness_score(item)
        source_score = _source_quality(item)

        semantic_weight = 0.46 if interest_tokens else 0.60
        overlap_weight = 0.30 if interest_tokens else 0.10
        category_weight = 0.14
        freshness_weight = 0.06
        source_weight = 0.04

        total = (
            (semantic * semantic_weight)
            + (overlap * overlap_weight)
            + (category_score * category_weight)
            + (freshness * freshness_weight)
            + (source_score * source_weight)
        )
        if interest_tokens and overlap == 0:
            total *= 0.8
        elif interest_tokens and overlap >= 0.4:
            total += 0.08

        category_slug = (item.get("category", "") or "").strip().lower()
        if inferred_categories:
            if category_slug in inferred_categories:
                total += 0.12
            elif overlap == 0:
                total *= 0.55

        ranked.append(
            {
                **item,
                "raw_score": float(total),
                "match_explanation": _match_explanation(
                    item,
                    overlap,
                    category_score,
                    freshness,
                    source_score,
                    interest_tokens,
                ),
            }
        )

    ranked.sort(key=lambda record: record["raw_score"], reverse=True)

    # Keep category diversity so recommendations reflect multiple interests.
    target_categories = set(inferred_categories)
    target_categories.update(
        category for category, bias in MOOD_CATEGORY_BIAS.get(clean_mood, {}).items() if bias > 0.2
    )
    if len(target_categories) == 1:
        max_per_category = max(4, math.ceil(limit * 0.75))
    elif len(target_categories) >= 3:
        max_per_category = max(2, math.ceil(limit / max(len(target_categories), 1)))
    else:
        max_per_category = max(2, math.ceil(limit / 2))

    buckets = defaultdict(list)
    for item in ranked:
        buckets[(item.get("category", "") or "").lower()].append(item)
    ordered_categories = sorted(
        buckets.keys(),
        key=lambda category: (
            0 if category in target_categories else 1,
            -buckets[category][0]["raw_score"],
        ),
    )

    category_counts = defaultdict(int)
    category_indexes = defaultdict(int)
    diversified = []

    while len(diversified) < limit:
        added_any = False
        for category_key in ordered_categories:
            if category_counts[category_key] >= max_per_category:
                continue
            idx = category_indexes[category_key]
            if idx >= len(buckets[category_key]):
                continue
            diversified.append(buckets[category_key][idx])
            category_indexes[category_key] += 1
            category_counts[category_key] += 1
            added_any = True
            if len(diversified) >= limit:
                break
        if not added_any:
            break

    if len(diversified) < limit:
        chosen_urls = {entry.get("url", "") for entry in diversified}
        for item in ranked:
            if item.get("url", "") in chosen_urls:
                continue
            diversified.append(item)
            chosen_urls.add(item.get("url", ""))
            if len(diversified) >= limit:
                break

    diversified.sort(key=lambda item: item["raw_score"], reverse=True)
    max_score = max((item["raw_score"] for item in diversified), default=0.0)
    for item in diversified:
        item["score"] = _normalize_confidence(item["raw_score"], max_score)
        item.pop("raw_score", None)
    return diversified

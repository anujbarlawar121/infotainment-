import re
from functools import lru_cache

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression


NEGATIONS = {
    "not",
    "no",
    "never",
    "none",
    "nobody",
    "nothing",
    "neither",
    "hardly",
    "barely",
    "rarely",
    "without",
    "dont",
    "don't",
    "didnt",
    "didn't",
    "cant",
    "can't",
    "couldnt",
    "couldn't",
    "wont",
    "won't",
    "isnt",
    "isn't",
    "wasnt",
    "wasn't",
}
CONTRAST_WORDS = {"but", "however", "though", "yet", "although"}
INTENSIFIERS = {
    "very": 1.25,
    "really": 1.25,
    "so": 1.2,
    "too": 1.15,
    "extremely": 1.45,
    "super": 1.3,
    "absolutely": 1.4,
    "totally": 1.3,
    "deeply": 1.3,
    "incredibly": 1.45,
}
DAMPENERS = {
    "slightly": 0.75,
    "somewhat": 0.8,
    "kind": 0.85,
    "kinda": 0.85,
    "little": 0.8,
    "bit": 0.85,
}
TYPO_NORMALIZATIONS = {
    "loose": "lose",
    "loosing": "losing",
    "looses": "loses",
    "dont": "don't",
    "didnt": "didn't",
    "cant": "can't",
    "wont": "won't",
}
WORD_SENTIMENT = {
    "love": 2.8,
    "loved": 2.8,
    "like": 1.4,
    "liked": 1.5,
    "awesome": 2.6,
    "amazing": 2.8,
    "great": 2.3,
    "good": 1.8,
    "nice": 1.5,
    "fun": 1.8,
    "enjoy": 2.1,
    "enjoyed": 2.2,
    "enjoying": 2.1,
    "happy": 2.3,
    "hopeful": 2.2,
    "excited": 2.2,
    "relaxed": 1.8,
    "calm": 1.4,
    "peaceful": 1.8,
    "smile": 1.5,
    "smiled": 1.6,
    "smiling": 1.5,
    "beautiful": 2.1,
    "brilliant": 2.3,
    "fantastic": 2.7,
    "perfect": 2.7,
    "helpful": 1.9,
    "useful": 1.7,
    "care": 1.2,
    "cared": 1.4,
    "win": 2.0,
    "won": 2.3,
    "winning": 2.2,
    "best": 2.2,
    "better": 1.5,
    "glad": 1.8,
    "positive": 1.7,
    "recommend": 1.6,
    "hate": -3.2,
    "hated": -3.2,
    "bad": -2.0,
    "worse": -2.5,
    "worst": -3.0,
    "awful": -3.0,
    "terrible": -3.1,
    "sad": -2.3,
    "angry": -2.7,
    "hurt": -2.3,
    "hurting": -2.4,
    "upset": -2.4,
    "frustrated": -2.7,
    "frustrating": -2.5,
    "annoyed": -2.2,
    "stressful": -2.4,
    "stressed": -2.3,
    "tired": -1.5,
    "bored": -1.9,
    "boring": -1.8,
    "disappointing": -2.6,
    "disappointed": -2.6,
    "dislike": -2.4,
    "cry": -2.5,
    "cried": -2.8,
    "tears": -2.7,
    "tearful": -2.6,
    "alone": -2.2,
    "lonely": -2.5,
    "empty": -1.9,
    "grief": -2.9,
    "heartbroken": -3.1,
    "broken": -2.3,
    "pain": -2.1,
    "lose": -2.4,
    "losing": -2.5,
    "lost": -2.7,
    "defeat": -2.5,
    "defeated": -2.9,
    "failure": -2.7,
    "problem": -1.9,
    "problems": -2.0,
    "issue": -1.8,
    "issues": -1.9,
    "bug": -1.7,
    "hard": -1.1,
    "difficult": -1.4,
    "unhappy": -2.4,
    "negative": -1.7,
    "anti": -0.9,
    "antigovernment": -2.1,
    "corrupt": -2.6,
    "corruption": -2.7,
    "oppression": -2.8,
    "hostile": -2.0,
    "violence": -2.4,
    "hatefilled": -2.8,
    "propaganda": -1.9,
    "threat": -2.2,
    "dangerous": -2.1,
    "never": -0.8,
}
PHRASE_SENTIMENT = {
    "feel good": 2.4,
    "works well": 2.2,
    "pretty good": 1.9,
    "very good": 2.4,
    "good times": 1.4,
    "so happy": 2.8,
    "not bad": 1.6,
    "not good": -2.2,
    "not happy": -2.4,
    "not great": -1.8,
    "i am bored": -2.2,
    "im bored": -2.1,
    "i'm bored": -2.2,
    "anti government": -2.6,
    "anti-government": -2.6,
    "anti government sentiment": -2.8,
    "anti-government sentiment": -2.8,
    "hate speech": -3.0,
    "violent rhetoric": -2.8,
    "incites violence": -3.2,
    "deeply corrupt": -3.0,
    "gross corruption": -3.0,
    "fed up": -2.8,
    "let down": -2.4,
    "all the time": -0.7,
    "every time": -0.9,
    "lose all the time": -3.2,
    "lost all the time": -3.2,
    "defeated me every time": -3.6,
    "keep losing": -3.0,
    "so frustrating": -3.0,
    "really frustrating": -3.0,
    "filled with tears": -3.2,
    "eyes filled with tears": -3.4,
    "never come back": -3.1,
    "would never come back": -3.3,
    "no one cared": -3.1,
    "no one else seemed to care": -3.4,
    "walked away": -1.8,
    "without saying a word": -2.1,
}


def _normalize_text(text):
    normalized = text.lower().strip()
    for wrong, right in TYPO_NORMALIZATIONS.items():
        normalized = re.sub(rf"\b{re.escape(wrong)}\b", right, normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def _tokenize(text):
    return re.findall(r"[a-z']+", text.lower())


def _split_clauses(text):
    parts = re.split(r"(\bbut\b|\bhowever\b|\bthough\b|\byet\b|\balthough\b|[.!?;]+)", text)
    clauses = []
    contrast_next = False

    for part in parts:
        if not part:
            continue
        stripped = part.strip(" ,")
        if not stripped:
            continue

        lowered = stripped.lower()
        if lowered in CONTRAST_WORDS:
            contrast_next = True
            continue
        if re.fullmatch(r"[.!?;]+", stripped):
            contrast_next = False
            continue

        clauses.append(
            {
                "text": stripped,
                "weight": 1.35 if contrast_next else 1.0,
                "contrast": contrast_next,
            }
        )
        contrast_next = False

    return clauses or [{"text": text, "weight": 1.0, "contrast": False}]


def _modifier_from_window(window):
    modifier = 1.0
    for token in window:
        modifier *= INTENSIFIERS.get(token, 1.0)
        modifier *= DAMPENERS.get(token, 1.0)
    return modifier


def _is_negated(window):
    return any(token in NEGATIONS for token in window)


def _score_clause(clause):
    tokens = _tokenize(clause["text"])
    score = 0.0
    hits = []
    occupied = set()

    for phrase, base_weight in sorted(PHRASE_SENTIMENT.items(), key=lambda item: len(item[0].split()), reverse=True):
        phrase_tokens = phrase.split()
        length = len(phrase_tokens)
        if len(tokens) < length:
            continue
        for index in range(len(tokens) - length + 1):
            if tuple(tokens[index : index + length]) != tuple(phrase_tokens):
                continue
            weight = base_weight * clause["weight"]
            score += weight
            hits.append({"term": phrase, "weight": round(weight, 2)})
            occupied.update(range(index, index + length))

    for index, token in enumerate(tokens):
        if token not in WORD_SENTIMENT or index in occupied:
            continue

        window = tokens[max(0, index - 3) : index]
        weight = WORD_SENTIMENT[token]
        weight *= _modifier_from_window(window)

        display_term = token
        if _is_negated(window):
            weight *= -0.9
            display_term = f"not {token}"

        weight *= clause["weight"]
        score += weight
        hits.append({"term": display_term, "weight": round(weight, 2)})

    return score, hits


def _unique_hits(hits):
    strongest_by_term = {}
    for hit in sorted(hits, key=lambda item: abs(item["weight"]), reverse=True):
        strongest_by_term.setdefault(hit["term"], hit)
    return list(strongest_by_term.values())


def _calculate_probabilities(positive_strength, negative_strength):
    if positive_strength == 0 and negative_strength == 0:
        return {"Negative": 10.0, "Neutral": 80.0, "Positive": 10.0}, "Neutral", 80.0

    neutral_component = max(0.8, 1.6 - min(positive_strength + negative_strength, 8.0) * 0.12)
    positive_component = positive_strength
    negative_component = negative_strength
    total = positive_component + negative_component + neutral_component

    scores = {
        "Negative": round((negative_component / total) * 100, 2),
        "Neutral": round((neutral_component / total) * 100, 2),
        "Positive": round((positive_component / total) * 100, 2),
    }

    dominant = max(positive_strength, negative_strength)
    weaker = min(positive_strength, negative_strength)
    if weaker >= 2.2 and dominant <= weaker * 1.4:
        label = "Mixed"
        confidence = round(min(92.0, 52.0 + weaker * 8.0), 2)
        return scores, label, confidence

    label = "Positive" if positive_strength > negative_strength else "Negative"
    confidence = scores[label]
    if abs(positive_strength - negative_strength) < 0.8:
        label = "Neutral"
        confidence = max(scores["Neutral"], 45.0)
    return scores, label, round(confidence, 2)


def _build_summary(label, unique_hits):
    if not unique_hits:
        return "No strong positive or negative language was detected, so the text looks mostly neutral."

    strongest = unique_hits[:4]
    cues = ", ".join(f"{hit['term']} ({hit['weight']:+.2f})" for hit in strongest)
    if label == "Mixed":
        return f"The text contains strong signals in both directions. Main cues: {cues}."
    return f"The result is driven mainly by these cues: {cues}."


ML_REFERENCE_DATA = [
    ("I love this product and it works perfectly", "positive"),
    ("The experience was amazing and I enjoyed every minute", "positive"),
    ("Great support team, very helpful and kind", "positive"),
    ("This update is fantastic and much better", "positive"),
    ("I am excited and happy with the results", "positive"),
    ("What a brilliant and beautiful performance", "positive"),
    ("The music is uplifting and makes me smile", "positive"),
    ("Everything went smoothly and the service was excellent", "positive"),
    ("I recommend this movie, it was awesome", "positive"),
    ("This app is useful, reliable, and fast", "positive"),
    ("The team delivered great quality work", "positive"),
    ("I feel hopeful and confident after this", "positive"),
    ("This is a terrible experience and I hate it", "negative"),
    ("The service was awful, slow, and frustrating", "negative"),
    ("I am disappointed and upset about the result", "negative"),
    ("This product is bad and full of problems", "negative"),
    ("I feel defeated and tired all the time", "negative"),
    ("I am bored and not enjoying this", "negative"),
    ("I'm bored with this content", "negative"),
    ("The response was rude and hostile", "negative"),
    ("This report describes anti-government sentiments in the speech", "negative"),
    ("There was violent rhetoric and hate speech", "negative"),
    ("The app keeps crashing and it is very annoying", "negative"),
    ("I regret using this and would not recommend it", "negative"),
    ("The corruption scandal is deeply troubling", "negative"),
    ("He made dangerous and threatening remarks", "negative"),
    ("The meeting happened at 4 PM in the main hall", "neutral"),
    ("She shared an update about the project timeline", "neutral"),
    ("This article summarizes market trends for this week", "neutral"),
    ("The event includes music, news, and video sessions", "neutral"),
    ("He expressed anti-government sentiments in his speech", "neutral"),
    ("The weather was cloudy in the afternoon", "neutral"),
    ("We reviewed the dashboard and export logs", "neutral"),
    ("The platform has new recommendations and analytics", "neutral"),
    ("They discussed policy topics during the interview", "neutral"),
    ("The user submitted feedback through the contact form", "neutral"),
    ("This is an informational statement without emotion", "neutral"),
    ("A news anchor described the situation on air", "neutral"),
]


@lru_cache(maxsize=1)
def _ml_sentiment_model():
    texts = [text for text, _label in ML_REFERENCE_DATA]
    labels = [label for _text, label in ML_REFERENCE_DATA]
    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), min_df=1, sublinear_tf=True)
    matrix = vectorizer.fit_transform(texts)
    classifier = LogisticRegression(max_iter=600, class_weight="balanced", random_state=42)
    classifier.fit(matrix, labels)
    return vectorizer, classifier


def _ml_probabilities(text):
    vectorizer, classifier = _ml_sentiment_model()
    matrix = vectorizer.transform([text])
    probabilities = classifier.predict_proba(matrix)[0]
    classes = list(classifier.classes_)
    return {
        "Negative": round(float(probabilities[classes.index("negative")]) * 100, 2),
        "Neutral": round(float(probabilities[classes.index("neutral")]) * 100, 2),
        "Positive": round(float(probabilities[classes.index("positive")]) * 100, 2),
    }


def _normalize_scores(scores):
    bounded = {label: max(value, 0.01) for label, value in scores.items()}
    total = sum(bounded.values())
    return {label: round((value / total) * 100, 2) for label, value in bounded.items()}


def _blend_scores(lexical_scores, ml_scores, normalized_text):
    blended = {
        "Negative": (lexical_scores["Negative"] * 0.42) + (ml_scores["Negative"] * 0.58),
        "Neutral": (lexical_scores["Neutral"] * 0.42) + (ml_scores["Neutral"] * 0.58),
        "Positive": (lexical_scores["Positive"] * 0.42) + (ml_scores["Positive"] * 0.58),
    }

    # Domain-specific override for explicit hostility and anti-government cues.
    if re.search(r"\banti[- ]government\b|\bcorrupt(ion)?\b|\bhate speech\b|\bviolent rhetoric\b", normalized_text):
        blended["Negative"] += 8.0
        blended["Neutral"] -= 4.0
        blended["Positive"] -= 2.0

    if re.search(r"\bsummary\b|\breport(ed|s|ing)?\b|\bdescribed?\b", normalized_text):
        blended["Neutral"] += 3.0

    return _normalize_scores(blended)


def _pick_label(scores):
    positive = scores["Positive"]
    negative = scores["Negative"]
    neutral = scores["Neutral"]
    if positive >= 33 and negative >= 33 and abs(positive - negative) <= 8:
        return "Mixed", round(min(95.0, ((positive + negative) / 2) + 8), 2)

    label = max(scores, key=scores.get)
    confidence = round(scores[label], 2)
    if label == "Neutral" and confidence < 48 and abs(positive - negative) > 10:
        label = "Positive" if positive > negative else "Negative"
        confidence = round(max(positive, negative), 2)
    return label, confidence


def analyze_sentiment(text):
    normalized = _normalize_text(text)
    clauses = _split_clauses(normalized)

    total_score = 0.0
    hits = []
    for clause in clauses:
        clause_score, clause_hits = _score_clause(clause)
        total_score += clause_score
        hits.extend(clause_hits)

    unique_hits = _unique_hits(hits)
    positive_strength = round(sum(hit["weight"] for hit in unique_hits if hit["weight"] > 0), 2)
    negative_strength = round(abs(sum(hit["weight"] for hit in unique_hits if hit["weight"] < 0)), 2)
    lexical_scores, _lexical_label, _lexical_confidence = _calculate_probabilities(positive_strength, negative_strength)
    ml_scores = _ml_probabilities(normalized)
    scores = _blend_scores(lexical_scores, ml_scores, normalized)
    label, confidence = _pick_label(scores)

    return {
        "label": label,
        "confidence": confidence,
        "scores": scores,
        "compound": round(total_score, 2),
        "summary": _build_summary(label, unique_hits),
        "positive_cues": [hit["term"] for hit in unique_hits if hit["weight"] > 0][:4],
        "negative_cues": [hit["term"] for hit in unique_hits if hit["weight"] < 0][:4],
        "method": "Hybrid lexical + ML sentiment engine",
    }

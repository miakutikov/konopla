"""
relevance.py — Relevance scoring for news candidates.

Scores each candidate 0.0–1.0 based on:
- Hemp keyword presence in title/content
- Source trust level
- Content quality signals
- Absence of drug-related soft stop words
"""

from config import HEMP_KEYWORDS, SOFT_STOP_WORDS, ALLOW_CONTEXT, CATEGORY_IMAGE_QUERIES

# Category detection keywords (Ukrainian + English)
CATEGORY_KEYWORDS = {
    "текстиль": ["textile", "fabric", "fiber", "fibre", "clothing", "fashion", "текстиль", "волокно", "тканин", "одяг"],
    "будівництво": ["hempcrete", "construction", "building", "insulation", "будівн", "бетон", "ізоляц"],
    "агро": ["farm", "cultivation", "crop", "seed", "harvest", "agriculture", "агро", "вирощ", "урожай", "насінн", "посів"],
    "біопластик": ["bioplastic", "plastic", "composite", "packaging", "пластик", "композит", "упаков"],
    "автопром": ["automotive", "car", "vehicle", "auto", "авто", "машин"],
    "харчова": ["food", "nutrition", "protein", "seed oil", "харч", "їж", "протеїн", "олія"],
    "енергетика": ["energy", "battery", "biofuel", "supercapacitor", "енерг", "батаре", "паливо"],
    "косметика": ["cosmetic", "skincare", "beauty", "cream", "косметик", "крем", "догляд"],
    "законодавство": ["law", "regulation", "legislation", "policy", "legal", "bill", "закон", "регулюв", "легаліз", "політик"],
    "наука": ["research", "study", "university", "laboratory", "science", "наук", "дослідж", "університет", "лаборатор"],
    "екологія": ["ecology", "environment", "sustainable", "green", "carbon", "еколог", "довкілл", "сталий", "вуглец"],
    "бізнес": ["business", "company", "market", "invest", "startup", "revenue", "бізнес", "компан", "ринок", "інвест"],
}


def compute_relevance(title, content, source_name, sources):
    """Score a candidate article for relevance.

    Args:
        title: Article title (original language)
        content: Article content/preview text
        source_name: Name of the RSS source
        sources: List of full source objects (from load_sources(full=True))

    Returns:
        (score: float, reasons: list[str]) — score 0.0–1.0 and list of reasons
    """
    score = 0.0
    reasons = []
    text_lower = f"{title} {content}".lower()
    title_lower = title.lower()

    # Base: passed hemp keyword filter (article wouldn't be here otherwise)
    score += 0.3
    reasons.append("passed hemp filter")

    # Trusted source
    source_trusted = is_source_trusted(source_name, sources)
    if source_trusted:
        score += 0.2
        reasons.append("trusted source")

    # Hemp keyword in title (stronger signal than just in content)
    title_has_hemp = any(kw in title_lower for kw in HEMP_KEYWORDS)
    if title_has_hemp:
        score += 0.2
        reasons.append("hemp keyword in title")

    # Multiple hemp keywords (covers topic deeply)
    hemp_count = sum(1 for kw in HEMP_KEYWORDS if kw in text_lower)
    if hemp_count >= 2:
        score += 0.1
        reasons.append(f"{hemp_count} hemp keywords")

    # Content length (substantive article)
    if len(content) > 200:
        score += 0.1
        reasons.append("substantive content")

    # Soft stop words penalty
    has_allow = any(w.lower() in text_lower for w in ALLOW_CONTEXT)
    if not has_allow:
        has_soft = any(w.lower() in text_lower for w in SOFT_STOP_WORDS)
        if has_soft:
            score -= 0.3
            reasons.append("soft stop words without context")

    score = max(0.0, min(1.0, round(score, 2)))
    return score, reasons


def is_source_trusted(source_name, sources):
    """Check if a source is marked as trusted in sources.json."""
    if not sources:
        return False
    for s in sources:
        if s.get("name", "") == source_name:
            return s.get("trusted", False)
    return False


def guess_category(title, content):
    """Guess article category based on keyword matching.

    Returns the best-matching category or 'інше' if no match.
    """
    text_lower = f"{title} {content}".lower()
    best_cat = "інше"
    best_count = 0

    for category, keywords in CATEGORY_KEYWORDS.items():
        count = sum(1 for kw in keywords if kw in text_lower)
        if count > best_count:
            best_count = count
            best_cat = category

    return best_cat

"""
Recommendation engine.

TF-IDF over enriched listing documents + cosine similarity against the student's
skill vector. A +0.1 bonus is applied when the listing's domain matches the
student's preferred domain.

    match = cosine_sim(student_vector, listing_tfidf)   -> scaled 0..1
    if listing.domain == student.preferred_domain: match += 0.10
    match_pct = round(min(match, 1.0) * 100)
"""
from __future__ import annotations

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from services.skills_taxonomy import DOMAIN_SIGNALS

DOMAIN_PREFERENCE_BONUS = 0.10

# Corpus calibration: raw cosine values for resume-vs-listing TF-IDF vectors are
# small (this corpus tops out around 0.23). We blend a set-relative normalisation
# with an absolute, corpus-calibrated one so the displayed match % is meaningful
# in both ranked and filtered/browse views.
COSINE_CEILING = 0.28          # observed practical maximum
RELATIVE_WEIGHT = 0.45         # share of the score driven by "best in this candidate set"
ABSOLUTE_WEIGHT = 0.55         # share driven by absolute content similarity
SCORE_HEADROOM = 0.90          # keeps the +0.10 domain bonus from saturating instantly

_vectorizer: TfidfVectorizer | None = None
_matrix = None
_cache_key: tuple | None = None


def _get(obj, key, default=None):
    """Field accessor that works for both ORM rows and plain dicts."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def listing_document(listing) -> str:
    """Weighted bag-of-words document for a listing (skills repeated for emphasis)."""
    skills = _get(listing, "skills_required") or []
    domain = _get(listing, "domain")
    title = _get(listing, "title")
    description = _get(listing, "description")

    parts = [
        str(title or ""), str(title or ""),                 # title weighted x2
        " ".join(skills) * 3,                               # skills weighted x3
        str(domain or "") * 2,
        str(description or ""),
    ]
    # inject domain signal vocabulary so domain inference works even on thin JDs
    for signal in DOMAIN_SIGNALS.get(domain, []) if domain else []:
        parts.append(signal * 2)
    return " ".join(parts).lower()


def student_document(profile) -> str:
    """Student document mirrors the listing document structure."""
    vector = profile.skill_vector or {}
    skills = profile.skills or []
    weights = vector or {s: 1.0 for s in skills}
    tokens: list[str] = []
    for skill, weight in sorted(weights.items(), key=lambda kv: -kv[1]):
        repeats = 3 if weight >= 0.08 else 2 if weight >= 0.04 else 1
        tokens.extend([skill.replace(" ", "_")] * repeats)
    domain = (profile.preferred_domain or "").lower().replace(" ", "_")
    if domain:
        tokens.extend([domain] * 2)
    return " ".join(tokens)


def build_index(listings: list) -> None:
    """Fit the TF-IDF vectorizer over all listings (cached until listings change)."""
    global _vectorizer, _matrix, _cache_key
    if not listings:
        _vectorizer, _matrix, _cache_key = None, None, None
        return
    key = (len(listings), max(l.id for l in listings), sum(l.trust_score or 0 for l in listings))
    if _cache_key == key:
        return
    docs = [listing_document(l) for l in listings]
    _vectorizer = TfidfVectorizer(max_features=9000, ngram_range=(1, 2),
                                  sublinear_tf=True, min_df=1, token_pattern=r"[a-zA-Z][a-zA-Z0-9_+#\.\-]*")
    _matrix = _vectorizer.fit_transform(docs)
    _cache_key = key


def invalidate_index() -> None:
    global _cache_key
    _cache_key = None


def _skill_overlap(profile, listing) -> list[dict]:
    student_skills = set(profile.skills or [])
    required = set(listing.skills_required or [])
    matched = sorted(student_skills & required)
    missing = sorted(required - student_skills)
    return [
        {"skill": s, "weight": (profile.skill_vector or {}).get(s, 0.1)}
        for s in sorted(matched, key=lambda s: -(profile.skill_vector or {}).get(s, 0.1))
    ], missing


def recommend(profile, listings: list, top_k: int = 20, include_flagged: bool = True,
              min_trust: int = 0, domain_filter: str | None = None,
              work_mode: str | None = None) -> list[dict]:
    """Rank listings for a student. Returns enriched recommendation dicts."""
    candidates = [l for l in listings if (include_flagged or not l.fraud_flag)]
    if min_trust:
        candidates = [l for l in candidates if (l.trust_score or 0) >= min_trust]
    if domain_filter:
        candidates = [l for l in candidates if (l.domain or "") == domain_filter]
    if work_mode and work_mode != "any":
        candidates = [l for l in candidates if (l.work_mode or "") == work_mode]

    if not candidates:
        return []

    build_index(listings)
    if _vectorizer is None or _matrix is None:
        return []

    student_doc = student_document(profile)
    if not student_doc.strip():
        student_doc = " ".join(profile.skills or []) or "general"

    student_vec = _vectorizer.transform([student_doc])
    # Similarity is computed against the whole corpus so the relative component is
    # anchored to the global best fit — narrowing the filters can't inflate scores.
    all_sims = cosine_similarity(student_vec, _matrix)[0]
    index_of = {id(l): i for i, l in enumerate(listings)}
    rows = [index_of[id(l)] for l in candidates]
    sims = all_sims[rows]
    global_max = float(all_sims.max()) if all_sims.size else 0.0

    preferred = (profile.preferred_domain or "").strip()
    results = []
    for idx, listing in enumerate(candidates):
        raw = float(sims[idx])
        domain_match = bool(preferred) and listing.domain == preferred
        bonus = DOMAIN_PREFERENCE_BONUS if domain_match else 0.0

        relative = (raw / global_max) if global_max > 0 else 0.0    # vs best fit in whole corpus
        absolute = min(raw / COSINE_CEILING, 1.0)                 # corpus-calibrated similarity
        normalised = RELATIVE_WEIGHT * relative + ABSOLUTE_WEIGHT * absolute
        match = min(normalised * SCORE_HEADROOM + bonus, 1.0)
        match_pct = int(round(match * 100))
        matched_skills, missing_skills = _skill_overlap(profile, listing)

        results.append({
            "internship": listing.to_dict(),
            "match_pct": match_pct,
            "cosine_similarity": round(raw, 4),
            "relative_similarity": round(relative, 4),
            "normalised_similarity": round(normalised, 4),
            "domain_bonus_applied": domain_match,
            "domain_bonus": bonus,
            "matched_skills": matched_skills,
            "missing_skills": missing_skills[:6],
            "skill_coverage": int(round(100 * len(matched_skills) / max(len(listing.skills_required or []), 1))),
            "explanation": _explain(match_pct, domain_match, matched_skills, listing),
            "rank": 0,
        })

    # rank: trust score acts as a tiebreaker/weight so scam listings don't top the list
    results.sort(key=lambda r: (-(r["match_pct"] * 0.85 + (r["internship"]["trust_score"] or 0) * 0.15),
                                -r["internship"]["trust_score"]))
    for i, item in enumerate(results[:top_k], start=1):
        item["rank"] = i
    return results[:top_k]


def _explain(match_pct: int, domain_match: bool, matched: list[dict], listing) -> str:
    bits = []
    if matched:
        names = ", ".join(m["skill"] for m in matched[:4])
        bits.append(f"matches your {names}")
    if domain_match:
        bits.append(f"your preferred domain ({listing.domain}) +10% boost")
    if not bits:
        bits.append("content similarity to your resume vector")
    return f"{match_pct}% match — " + "; ".join(bits) + "."


def explain_scoring() -> dict:
    return {
        "algorithm": "TF-IDF (1-2 gram, sublinear TF) + cosine similarity",
        "domain_bonus": DOMAIN_PREFERENCE_BONUS,
        "formula": "match_pct = round(min(0.90 x (0.45 x relative + 0.55 x absolute) + domain_bonus, 1) x 100)",
        "ranking_tiebreak": "0.85 x match_pct + 0.15 x trust_score",
        "constants": {"cosine_ceiling": COSINE_CEILING, "relative_weight": RELATIVE_WEIGHT,
                      "absolute_weight": ABSOLUTE_WEIGHT, "score_headroom": SCORE_HEADROOM},
        "notes": [
            "Listing documents weight skills x3 and title x2 to sharpen similarity.",
            "relative = raw_cosine / best_cosine_in_candidate_set (0..1).",
            "absolute = raw_cosine / 0.28 (corpus-calibrated ceiling).",
            "+0.10 is added when listing.domain equals the student's preferred domain.",
            "Trust score contributes 15% of the final rank so flagged listings sink.",
        ],
    }

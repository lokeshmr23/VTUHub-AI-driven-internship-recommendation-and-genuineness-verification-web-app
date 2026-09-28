"""
ML fraud classifier.

Trains a scikit-learn pipeline (TF-IDF over a token-pattern analyser + a
scaled numeric/domain feature block, combined with FeatureUnion into a
LogisticRegression) on labelled seed listings, persists it to
ml/artifacts/fraud_model.joblib, and exposes fraud_probability(listing).
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import numpy as np

from services.trust_rules_seed import FRAUD_SEED_TEXT, GENUINE_SEED_TEXT

ARTIFACT_DIR = Path(__file__).resolve().parent.parent / "ml" / "artifacts"
MODEL_PATH = ARTIFACT_DIR / "fraud_model.joblib"

_model = None

TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9+#\.\-]{1,}")


def _tokens(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_RE.findall(text or "")]


def numeric_features(listing: dict) -> list[float]:
    """Hand-crafted risk features the classifier learns to weight."""
    desc = (listing.get("description") or "")
    words = len(desc.split())
    blob = f"{listing.get('title','')} {desc} {listing.get('apply_url','')}".lower()
    email = (listing.get("contact_email") or "").lower()
    domain = email.split("@")[-1] if "@" in email else ""
    stipend = float(listing.get("stipend") or 0)
    age = float(listing.get("domain_age_days") or 0)
    skills = listing.get("skills_required") or []

    return [
        1.0 if listing.get("is_free_provider") else 0.0,
        1.0 if listing.get("is_blacklisted") else 0.0,
        1.0 if not listing.get("contact_email") else 0.0,
        min(age, 4000) / 4000.0,
        1.0 if age and age < 180 else 0.0,
        min(words, 400) / 400.0,
        len(skills) / 8.0,
        1.0 if stipend == 0 else 0.0,
        min(stipend, 60000) / 60000.0,
        1.0 if any(k in blob for k in ("fee", "deposit", "registration charge", "pay rs")) else 0.0,
        1.0 if "whatsapp" in blob or "telegram" in blob else 0.0,
        1.0 if "guarantee" in blob else 0.0,
        1.0 if re.search(r"(₹|rs\.?|inr)\s?\d", blob) else 0.0,
        1.0 if domain.endswith((".xyz", ".top", ".click", ".online", ".club", ".work")) else 0.0,
        1.0 if listing.get("deadline") else 0.0,
        float(listing.get("rule_score") or 0.0),
    ]


def select_text(rows) -> list[str]:
    """FeatureUnion helper — module level so joblib can pickle the pipeline."""
    return [r.get("text", "") for r in rows]


def select_numeric(rows):
    """FeatureUnion helper — engineered risk feature matrix."""
    if not rows:
        return np.zeros((0, 16))
    return np.array([numeric_features(r) for r in rows])


def _build_pipeline():
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline, FeatureUnion
    from sklearn.preprocessing import FunctionTransformer, MaxAbsScaler

    text_block = Pipeline([
        ("select", FunctionTransformer(select_text, validate=False)),
        ("tfidf", TfidfVectorizer(
            tokenizer=_tokens, token_pattern=None, lowercase=False,
            ngram_range=(1, 2), min_df=1, sublinear_tf=True, max_features=6000,
        )),
    ])
    num_block = Pipeline([
        ("select", FunctionTransformer(select_numeric, validate=False)),
        ("scale", MaxAbsScaler()),
    ])
    return Pipeline([
        ("features", FeatureUnion([("text", text_block), ("num", num_block)])),
        ("clf", LogisticRegression(C=2.5, max_iter=1200, class_weight="balanced",
                                   solver="liblinear")),
    ])


def _training_rows() -> list[dict]:
    """Synthetic labelled corpus: fraud patterns vs genuine internship copy."""
    rows: list[dict] = []
    fraud_domains = ["internshippay.in", "joboffer-verify.xyz", "careers-placement.top",
                     "stipend-fast.net", "hirequickly.work", "freeintern.xyz"]
    for i, text in enumerate(FRAUD_SEED_TEXT):
        dom = fraud_domains[i % len(fraud_domains)]
        rows.append({
            "text": f"{text} {dom}",
            "label": 1,
            "contact_email": f"hr{i}@{dom}",
            "is_blacklisted": dom in {"internshippay.in", "joboffer-verify.xyz"},
            "is_free_provider": False,
            "domain_age_days": 12 + (i * 7) % 80,
            "stipend": [0, 5000, 25000][i % 3],
            "skills_required": [],
            "rule_score": round(0.05 + 0.15 * ((i % 4) / 3), 3),
            "apply_url": f"https://{dom}/apply",
        })
    genuine_domains = ["flipkart.com", "swiggy.in", "razorpay.com", "freshworks.com",
                       "zoho.com", "tcs.com", "infosys.com", "sarvam.ai", "postman.com"]
    for i, text in enumerate(GENUINE_SEED_TEXT):
        dom = genuine_domains[i % len(genuine_domains)]
        rows.append({
            "text": f"{text} {dom}",
            "label": 0,
            "contact_email": f"talent{i}@{dom}",
            "is_blacklisted": False,
            "is_free_provider": False,
            "domain_age_days": 1400 + (i * 90) % 4000,
            "stipend": 15000 + (i % 6) * 5000,
            "skills_required": ["python", "sql", "communication skills"][: 1 + i % 3],
            "rule_score": round(0.78 + 0.18 * ((i % 5) / 4), 3),
            "apply_url": f"https://{dom}/careers",
        })
    # borderline: free-mail recruiters with decent copy still riskier
    for i, text in enumerate(GENUINE_SEED_TEXT[:8]):
        rows.append({
            "text": f"{text} gmail.com",
            "label": 1 if i % 3 == 0 else 0,
            "contact_email": f"hr.team{i}@gmail.com",
            "is_blacklisted": False,
            "is_free_provider": True,
            "domain_age_days": 6000,
            "stipend": 8000 + i * 1000,
            "skills_required": ["excel", "communication skills"],
            "rule_score": 0.45 + 0.05 * (i % 4),
            "apply_url": "https://forms.gle/demo",
        })
    return rows


def train_model(save: bool = True, verbose: bool = False) -> dict:
    global _model
    from sklearn.metrics import accuracy_score, f1_score, roc_auc_score

    rows = _training_rows()
    X = rows
    y = np.array([r["label"] for r in rows])
    pipeline = _build_pipeline()
    pipeline.fit(X, y)

    proba = pipeline.predict_proba(X)[:, 1]
    pred = (proba >= 0.5).astype(int)
    metrics = {
        "samples": len(rows),
        "fraud_samples": int(y.sum()),
        "genuine_samples": int((y == 0).sum()),
        "train_accuracy": round(float(accuracy_score(y, pred)), 4),
        "f1": round(float(f1_score(y, pred)), 4),
        "roc_auc": round(float(roc_auc_score(y, proba)), 4),
        "features": "TF-IDF(1-2gram) + 16 engineered risk features -> LogisticRegression",
    }
    _model = pipeline
    if save:
        import joblib

        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        joblib.dump({"pipeline": pipeline, "metrics": metrics}, MODEL_PATH)
    if verbose:
        print(metrics)
    return metrics


def load_model():
    global _model
    if _model is not None:
        return _model
    if MODEL_PATH.exists():
        try:
            import joblib

            payload = joblib.load(MODEL_PATH)
            _model = payload["pipeline"] if isinstance(payload, dict) else payload
            return _model
        except Exception:
            _model = None
    train_model(save=True)
    return _model


def model_metrics() -> dict:
    metrics = None
    if MODEL_PATH.exists():
        try:
            import joblib

            payload = joblib.load(MODEL_PATH)
            if isinstance(payload, dict):
                metrics = payload.get("metrics")
        except Exception:
            metrics = None
    if metrics is None:
        metrics = train_model(save=True)
    return metrics


def fraud_probability(listing: dict) -> float:
    """P(fraud) in [0,1] for a single listing dict."""
    model = load_model()
    row = dict(listing)
    row.setdefault("text", " ".join(filter(None, [
        row.get("title"), row.get("description"),
        row.get("location"), " ".join(row.get("skills_required") or []),
        (row.get("contact_email") or "").split("@")[-1], row.get("apply_url"),
    ])))
    try:
        proba = float(model.predict_proba([row])[0][1])
    except Exception:
        # graceful degradation: rule-driven fallback
        rs = float(row.get("rule_score") or 0.5)
        proba = max(0.02, min(0.98, 1.0 - rs))
    return round(proba, 4)


def fraud_probability_bulk(listings: list[dict]) -> list[float]:
    model = load_model()
    rows = []
    for listing in listings:
        row = dict(listing)
        row.setdefault("text", " ".join(filter(None, [
            row.get("title"), row.get("description"),
            row.get("location"), " ".join(row.get("skills_required") or []),
            (row.get("contact_email") or "").split("@")[-1], row.get("apply_url"),
        ])))
        rows.append(row)
    try:
        return [round(float(p), 4) for p in model.predict_proba(rows)[:, 1]]
    except Exception:
        return [fraud_probability(r) for r in rows]

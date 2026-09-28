"""
Internship Trust Score engine.

    TrustScore = round( (0.5 * RuleScore + 0.5 * (1 - MLFraudProbability)) * 100 )

RuleScore (0..1) blends three independent sub-scores:
    * email/domain validation  40%   free-provider, disposable, blacklist, age, MX
    * red-flag phrase analysis 35%   fee demands, urgency, payment rails, vagueness
    * listing completeness     25%   required fields, JD depth, stipend, deadline

FraudFlag is raised when the final score < 45 OR a domain hard-check fails.
Badges: Green >= 75, Amber 50-74, Red < 50 (or flagged).
"""
from __future__ import annotations

import re
from datetime import date, datetime

from flask import current_app

from models import Internship
from services.domain_intel import domain_from_email, domain_from_url, lookup_domain
from services.ml_fraud import fraud_probability

# ---------------------------------------------------------------- red flags
RED_FLAG_RULES: list[dict] = [
    {
        "id": "registration_fee",
        "pattern": r"\b(registration|onboarding|joining|processing|security|training|"
                   r"application|enrol+l?ment|kit)\s*(fee|charge|amount|deposit|payment)\b",
        "label": "Asks for a registration / onboarding fee",
        "weight": 0.34,
        "severity": "high",
    },
    {
        "id": "pay_to_work",
        "pattern": r"\b(pay|payment|deposit|remit|transfer)\b[^.\n]{0,28}\b(₹|rs\.?|inr|\$)\s?\d"
                   r"|\b(₹|rs\.?|inr|\$)\s?\d[\d,]*\b[^.\n]{0,28}\b(fee|deposit|registration|refundable)\b",
        "label": "Money demanded from the intern",
        "weight": 0.36,
        "severity": "high",
    },
    {
        "id": "upi_payment",
        "pattern": r"\b(upi|gpay|google pay|phonepe|paytm|paypal|western union|bank transfer|"
                   r"neft|imps|account number|ifsc)\b",
        "label": "Payment via UPI / bank transfer / wallet",
        "weight": 0.30,
        "severity": "high",
    },
    {
        "id": "guaranteed",
        "pattern": r"\b(100%\s*(job|placement|guarantee)|guaranteed\s+(job|placement|internship|stipend)|"
                   r"assured\s+(job|placement|stipend)|job\s+guarantee)\b",
        "label": "Guaranteed job / placement claims",
        "weight": 0.28,
        "severity": "high",
    },
    {
        "id": "unrealistic_stipend",
        "pattern": r"\b(earn|salary|stipend|income)\b[^.\n]{0,40}\b(1|2|3)?[,]?\d{5,}\b\s*(?:/\s*(?:month|mo))?"
                   r"|\b\d{2,3}[,]?\d{3}\s*(?:per|/)\s*(?:month|week|day)\b",
        "label": "Unrealistic pay promise for an internship",
        "weight": 0.22,
        "severity": "medium",
    },
    {
        "id": "urgency",
        "pattern": r"\b(immediate(ly)?\s+(joining|start|hiring)|limited\s+seats?|"
                   r"only\s+\d+\s+(seats?|slots?|vacancies)|hurry|last\s+date\s+today|apply\s+fast|"
                   r"urgent(ly)?\s+(required|hiring))\b",
        "label": "Pressure tactics / artificial urgency",
        "weight": 0.16,
        "severity": "medium",
    },
    {
        "id": "no_interview",
        "pattern": r"\b(no\s+interview|direct\s+(joining|selection)|without\s+interview|"
                   r"instant\s+(offer|joining|approval)|selected\s+directly)\b",
        "label": "No interview / instant selection promised",
        "weight": 0.26,
        "severity": "high",
    },
    {
        "id": "whatsapp_only",
        "pattern": r"\b(whatsapp|telegram)\b[^.\n]{0,30}\b(only|for\s+(details|apply|updates|contact))\b"
                   r"|\bcontact\s+(on\s+)?(whatsapp|telegram)\b",
        "label": "Hiring driven through WhatsApp / Telegram",
        "weight": 0.24,
        "severity": "high",
    },
    {
        "id": "vague",
        "pattern": r"\b(work\s+from\s+home|simple\s+(typing|data\s+entry|copy\s+paste)|"
                   r"part\s*time\s+typing|easy\s+money|no\s+experience\s+needed|"
                   r"any\s+graduate\s+can\s+apply)\b",
        "label": "Vague, low-skill 'easy money' work described",
        "weight": 0.20,
        "severity": "medium",
    },
    {
        "id": "personal_docs",
        "pattern": r"\b(aadhaar|aadhar|pan\s+card|passport|original\s+certificates?|"
                   r"bank\s+details?|otp)\b[^.\n]{0,25}\b(required|must|before|submit|share)\b",
        "label": "Sensitive documents demanded up-front",
        "weight": 0.30,
        "severity": "high",
    },
    {
        "id": "commission",
        "pattern": r"\b(commission|incentive)\s+(based|per\s+(sale|task|referral))|"
                   r"\breferral\s+(income|bonus)\b|\bunlimited\s+earning\b",
        "label": "Commission/MLM-style earning model",
        "weight": 0.24,
        "severity": "high",
    },
    {
        "id": "link_shortener",
        "pattern": r"\b(bit\.ly|tinyurl|t\.me|rb\.gy|cutt\.ly|linktr\.ee|forms\.gle)\b",
        "label": "Application link goes through a shortener / third-party form",
        "weight": 0.15,
        "severity": "medium",
    },
]

COMPILED_FLAGS = [(r, re.compile(r["pattern"], re.I)) for r in RED_FLAG_RULES]

FREE_MAIL_PENALTY = 0.15
DISPOSABLE_MAIL_PENALTY = 0.06
BLACKLIST_PENALTY = 0.02


# ---------------------------------------------------------------- rule scoring
def score_domain(domain_info: dict) -> tuple[float, list[dict], bool]:
    """(sub_score 0..1, findings, hard_check_failed)"""
    findings: list[dict] = []
    hard_fail = False

    if not domain_info.get("domain"):
        findings.append({"check": "email_missing", "level": "danger",
                         "label": "No recruiter contact email on the listing", "penalty": 0.4})
        return 0.30, findings, True

    if not domain_info.get("valid_syntax"):
        findings.append({"check": "email_syntax", "level": "danger",
                         "label": "Malformed recruiter email domain", "penalty": 0.5})
        hard_fail = True

    score = 1.0

    if domain_info.get("is_blacklisted"):
        findings.append({"check": "blacklist", "level": "danger",
                         "label": f"{domain_info['domain']} is on the fraud blacklist",
                         "penalty": 0.95})
        return 0.05, findings, True

    if domain_info.get("is_disposable"):
        findings.append({"check": "disposable", "level": "danger",
                         "label": "Disposable / burner email provider", "penalty": 0.85})
        hard_fail = True
        score *= DISPOSABLE_MAIL_PENALTY

    if domain_info.get("is_free_provider"):
        findings.append({"check": "free_provider", "level": "warning",
                         "label": "Recruiter writes from a free email provider "
                                  "(gmail/yahoo/outlook) instead of a corporate domain",
                         "penalty": 0.85})
        score *= FREE_MAIL_PENALTY

    age = domain_info.get("age_days") or 0
    if age < 90:
        findings.append({"check": "domain_age", "level": "danger",
                         "label": f"Domain registered only {age} days ago", "penalty": 0.55})
        score *= 0.18
    elif age < 180:
        findings.append({"check": "domain_age", "level": "warning",
                         "label": f"Domain is {age} days old (< 6 months)", "penalty": 0.3})
        score *= 0.5
    elif age < 365:
        findings.append({"check": "domain_age", "level": "warning",
                         "label": f"Domain is under a year old ({age} days)", "penalty": 0.15})
        score *= 0.78
    else:
        findings.append({"check": "domain_age", "level": "success",
                         "label": f"Domain age {round(age / 365.25, 1)} years", "penalty": 0.0})

    if not domain_info.get("mx_valid"):
        findings.append({"check": "mx", "level": "danger",
                         "label": "Domain has no reachable mail exchanger (MX)", "penalty": 0.6})
        score *= 0.25
        hard_fail = True

    return max(0.0, min(score, 1.0)), findings, hard_fail


def score_red_flags(text_blob: str, apply_url: str | None) -> tuple[float, list[dict]]:
    haystack = (text_blob or "") + "\n" + (apply_url or "")
    hits: list[dict] = []
    penalty = 0.0
    if not haystack.strip():
        return 1.0, hits
    for rule, rx in COMPILED_FLAGS:
        m = rx.search(haystack)
        if m:
            # keep a little surrounding context so the UI can show *why* it matched
            start = max(0, m.start() - 46)
            end = min(len(haystack), m.end() + 46)
            snippet = " ".join(haystack[start:end].split())
            if start > 0:
                snippet = "…" + snippet
            if end < len(haystack):
                snippet = snippet + "…"
            hits.append({
                "id": rule["id"], "label": rule["label"], "severity": rule["severity"],
                "weight": rule["weight"], "match": m.group(0).strip()[:80],
                "evidence": snippet[:180],
            })
            penalty += rule["weight"]

    hits.sort(key=lambda h: -h["weight"])
    # Hyperbolic decay instead of a hard linear cut: many small flags still hurt,
    # but one or two flags don't collapse the score to zero — the queue stays
    # informative instead of every scam listing landing on the same number.
    #   1 flag (0.34) -> 0.62   2 flags (0.70) -> 0.44   4 flags (1.4) -> 0.28
    sub = 1.0 / (1.0 + 1.8 * penalty)
    return max(0.0, min(sub, 1.0)), hits


REQUIRED_FIELDS = ["title", "company", "location", "domain", "description",
                   "contact_email", "apply_url"]


def score_completeness(listing: dict) -> tuple[float, list[dict]]:
    findings: list[dict] = []
    present = 0
    for field in REQUIRED_FIELDS:
        val = listing.get(field)
        ok = bool(val) and (len(str(val).strip()) > 2)
        present += 1 if ok else 0
        if not ok:
            findings.append({"check": f"missing_{field}", "level": "warning",
                             "label": f"Missing field: {field.replace('_', ' ')}"})
    field_ratio = present / len(REQUIRED_FIELDS)

    desc = (listing.get("description") or "").strip()
    words = len(desc.split())
    if words >= 120:
        depth = 1.0
    elif words >= 60:
        depth = 0.8
    elif words >= 25:
        depth = 0.55
    else:
        depth = 0.25
        findings.append({"check": "thin_description", "level": "warning",
                         "label": f"Job description is only {words} words — very thin"})

    skills = listing.get("skills_required") or []
    skill_ratio = min(len(skills), 5) / 5

    stipend = listing.get("stipend") or 0
    stipend_ratio = 1.0 if stipend >= 8000 else 0.75 if stipend > 0 else 0.35
    if stipend == 0:
        findings.append({"check": "no_stipend", "level": "warning",
                         "label": "Stipend not disclosed"})

    deadline = listing.get("deadline")
    deadline_ratio = 0.0
    if deadline:
        deadline_ratio = 1.0
        if isinstance(deadline, (date, datetime)) and deadline.date() < date.today() \
                if isinstance(deadline, datetime) else isinstance(deadline, date) and deadline < date.today():
            findings.append({"check": "expired", "level": "warning",
                             "label": "Application deadline has already passed"})
            deadline_ratio = 0.4
    else:
        findings.append({"check": "no_deadline", "level": "info",
                         "label": "No application deadline provided"})

    sub = (0.40 * field_ratio + 0.24 * depth + 0.18 * skill_ratio
           + 0.10 * stipend_ratio + 0.08 * deadline_ratio)
    return max(0.0, min(sub, 1.0)), findings


def compute_rule_score(domain_sub: float, flag_sub: float, complete_sub: float) -> float:
    return round(0.40 * domain_sub + 0.35 * flag_sub + 0.25 * complete_sub, 4)


def badge_for(score: int, flagged: bool) -> str:
    cfg = current_app.config if current_app else {}
    if flagged or score < cfg.get("BADGE_AMBER", 50):
        return "Red"
    if score >= cfg.get("BADGE_GREEN", 75):
        return "Green"
    return "Amber"


def evaluate_listing(listing: dict | Internship, persist: bool = True) -> dict:
    """Run the complete trust pipeline for one listing (dict or ORM object)."""
    if isinstance(listing, Internship):
        data = listing.to_dict(detailed=True)
    else:
        data = dict(listing)

    email = data.get("contact_email") or ""
    domain = data.get("company_domain") or domain_from_email(email) or domain_from_url(data.get("apply_url"))
    domain_info = lookup_domain(domain)

    domain_sub, domain_findings, hard_fail = score_domain(domain_info)

    blob = " ".join(filter(None, [
        data.get("title"), data.get("company"), data.get("description"),
        data.get("location"), " ".join(data.get("skills_required") or []),
        data.get("apply_url"),
    ]))
    flag_sub, flag_hits = score_red_flags(blob, data.get("apply_url"))
    complete_sub, complete_findings = score_completeness(data)

    # hard domain checks that force the flag even if the blend looks healthy
    if domain_info.get("is_blacklisted") or domain_info.get("is_disposable"):
        hard_fail = True
    if (domain_info.get("age_days") or 0) < 30:
        hard_fail = True
    if any(h["id"] in {"registration_fee", "pay_to_work", "upi_payment"} for h in flag_hits):
        hard_fail = True

    rule_score = compute_rule_score(domain_sub, flag_sub, complete_sub)

    ml_prob = fraud_probability({
        "title": data.get("title") or "",
        "company": data.get("company") or "",
        "description": data.get("description") or "",
        "location": data.get("location") or "",
        "skills_required": data.get("skills_required") or [],
        "apply_url": data.get("apply_url") or "",
        "contact_email": email,
        "stipend": data.get("stipend") or 0,
        "duration_months": data.get("duration_months") or 3,
        "openings": data.get("openings") or 1,
        "posted_date": data.get("posted_date"),
        "deadline": data.get("deadline"),
        "rule_score": rule_score,
        "domain_age_days": domain_info.get("age_days") or 0,
        "is_free_provider": domain_info.get("is_free_provider", False),
        "is_blacklisted": domain_info.get("is_blacklisted", False),
    })

    cfg = current_app.config if current_app else {}
    w_rule = cfg.get("TRUST_WEIGHT_RULE", 0.5)
    w_ml = cfg.get("TRUST_WEIGHT_ML", 0.5)
    composite = w_rule * rule_score + w_ml * (1.0 - ml_prob)
    trust_score = int(round(composite * 100))
    trust_score = max(0, min(trust_score, 100))

    flagged = trust_score < (cfg.get("FRAUD_FLAG_THRESHOLD", 45)) or hard_fail
    badge = badge_for(trust_score, flagged)

    breakdown = {
        "domain": {"score": round(domain_sub * 100), "weight": 40,
                   "label": "Email & domain validation", "findings": domain_findings},
        "red_flags": {"score": round(flag_sub * 100), "weight": 35,
                      "label": "Red-flag phrase analysis", "hits": flag_hits},
        "completeness": {"score": round(complete_sub * 100), "weight": 25,
                         "label": "Listing completeness", "findings": complete_findings},
        "ml": {"fraud_probability": round(ml_prob, 4), "weight": 50,
               "label": "ML fraud classifier"},
        "formula": {
            "rule_score": round(rule_score, 4),
            "weight_rule": w_rule,
            "weight_ml": w_ml,
            "expression": "round((0.5 x RuleScore + 0.5 x (1 - MLFraudProbability)) x 100)",
            "computed": trust_score,
        },
    }

    result = {
        "trust_score": trust_score,
        "rule_score": round(rule_score, 4),
        "ml_fraud_prob": round(ml_prob, 4),
        "fraud_flag": flagged,
        "badge": badge,
        "hard_check_failed": hard_fail,
        "trust_breakdown": breakdown,
        "red_flags": flag_hits,
        "domain_info": domain_info,
        "checked_at": datetime.utcnow().isoformat(),
    }

    if persist and isinstance(listing, Internship):
        listing.trust_score = trust_score
        listing.rule_score = round(rule_score, 4)
        listing.ml_fraud_prob = round(ml_prob, 4)
        listing.fraud_flag = flagged
        listing.badge = badge
        listing.hard_check_failed = hard_fail
        listing.trust_breakdown = breakdown
        listing.red_flags = flag_hits
        listing.company_domain = domain_info.get("domain") or listing.company_domain
        listing.trust_checked_at = datetime.utcnow()

    return result

"""
Recruiter-domain intelligence.

Checks performed per domain:
  1. free-provider detection (gmail/yahoo/outlook/... used for "corporate" hiring)
  2. disposable-provider detection
  3. domain age via WHOIS (live) or a deterministic synthetic registry (offline)
  4. blacklist membership (maintained list + admin-curated table)
  5. MX record presence (live only)

Live WHOIS/DNS is OFF by default (offline-safe demo). Flip
ENABLE_LIVE_DOMAIN_CHECKS=1 in .env to query the real registrar data.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone

from flask import current_app

from extensions import db
from models import DomainIntel

FREE_PROVIDERS = {
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.in", "yahoo.in",
    "outlook.com", "hotmail.com", "live.com", "msn.com", "rediffmail.com",
    "aol.com", "protonmail.com", "proton.me", "icloud.com", "mail.com",
    "gmx.com", "zoho.com", "yandex.com", "yopmail.com",
}
DISPOSABLE_PROVIDERS = {
    "mailinator.com", "guerrillamail.com", "10minutemail.com", "tempmail.com",
    "trashmail.com", "sharklasers.com", "throwawaymail.com", "dispostable.com",
    "getnada.com", "tempmailo.com", "fakeinbox.com",
}
DOMAIN_BLACKLIST = {
    "internshippay.in", "joboffer-verify.xyz", "careers-placement.top",
    "stipend-fast.net", "hirequickly.work", "freeintern.xyz", "trainee-pay.club",
    "workfromhome-easy.online", "intern-registration.site", "verify-jobs.click",
}
# Domains we treat as verified/corporate recruiters in the demo registry.
VERIFIED_CORPORATE_DOMAINS = {
    "flipkart.com", "swiggy.in", "zomato.com", "phonepe.com", "razorpay.com",
    "freshworks.com", "zoho.com", "tcs.com", "infosys.com", "wipro.com",
    "techmahindra.com", "hcltech.com", "ltts.com", "mphasis.com", "persistent.com",
    "thoughtworks.com", "postman.com", "browserstack.com", "hasura.io",
    "cred.club", "groww.in", "zerodha.com", "meesho.io", "nykaa.com",
    "ola.cabs", "olacabs.com", "dunzo.in", "delhivery.com", "bigbasket.com",
    "myntra.com", "paytm.com", "bharatpe.com", "sliceit.com", "jupiter.money",
    "cleartax.in", "sarvam.ai", "krutrim.ai", "glance.com", "inmobi.com",
    "sharechat.com", "dailyhunt.in", "dream11.com", "mpl.live", "games24x7.com",
    "tataelxsi.com", "tatamotors.com", "mahindra.com", "bosch.in", "siemens.co.in",
    "ge.com", "qualcomm.com", "nvidia.com", "samsung.com", "bosch.com",
    "larsentoubro.com", "reliancejio.com", "jio.com", "airtel.in", "vi.in",
    "godrej.com", "cummins.com", "honeywell.com", "abb.com", "schneider-electric.com",
    "drdo.gov.in", "isro.gov.in", "bhel.com", "ongcindia.com", "ntpc.co.in",
    "iisc.ac.in", "iitb.ac.in", "iiit.ac.in", "vit.ac.in", "manipal.edu",
    "amazon.in", "microsoft.com", "google.com", "adobe.com", "salesforce.com",
    "oracle.com", "sap.com", "dell.com", "hp.com", "cisco.com", "intel.com",
    "accenture.com", "capgemini.com", "cognizant.com", "deloitte.com",
    "ey.com", "kpmg.com", "pwc.com", "mckinsey.com", "goldmansachs.com",
}

SUSPICIOUS_TLDS = {
    "xyz", "top", "click", "online", "club", "work", "site", "icu", "live",
    "shop", "rest", "buzz", "monster", "loan", "cam", "quest", "cfd",
}
# Legacy/typo-squat style patterns typical of fake internship ops
SQUAT_PATTERNS = [
    r"internship[s]?[-_]?(pay|fee|offer|form|portal|register|verify)",
    r"(pay|fee)[-_]?(internship|stipend|registration)",
    r"(naukri|job)[-_]?(verify|offer|fast|quick|easy)",
    r"(tcs|infosys|wipro|amazon|google|flipkart)[-_.](careers|hiring|jobs)[-_.]",
    r"(secure|easy|fast)[-_]?(stipend|offer|hire|job)",
]

DOMAIN_RE = re.compile(r"^[a-z0-9]([a-z0-9\-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9\-]{0,61}[a-z0-9])?)+$")


def domain_from_email(email: str | None) -> str | None:
    if not email or "@" not in email:
        return None
    domain = email.split("@")[-1].strip().lower().strip(">")
    return domain or None


def domain_from_url(url: str | None) -> str | None:
    if not url:
        return None
    url = url.strip().lower()
    url = re.sub(r"^https?://", "", url)
    url = re.sub(r"^www\.", "", url)
    domain = url.split("/")[0].split(":")[0]
    return domain or None


FREE_PROVIDER_AGE_DAYS = {  # well-known consumer mail domains are decades old
    "gmail.com": 7900, "googlemail.com": 7200, "yahoo.com": 10200, "yahoo.co.in": 8600,
    "yahoo.in": 8600, "outlook.com": 9200, "hotmail.com": 10500, "live.com": 9000,
    "msn.com": 10500, "rediffmail.com": 10400, "aol.com": 11300, "protonmail.com": 4200,
    "proton.me": 1800, "icloud.com": 7000, "mail.com": 9500, "zoho.com": 8800,
    "yandex.com": 9000,
}


def _synthetic_age_days(domain: str) -> int:
    """Deterministic pseudo-WHOIS age for the offline demo registry."""
    if domain in FREE_PROVIDER_AGE_DAYS:
        return FREE_PROVIDER_AGE_DAYS[domain]
    if domain in VERIFIED_CORPORATE_DOMAINS:
        h = int(hashlib.sha256(domain.encode()).hexdigest()[:8], 16)
        return 900 + (h % 9000)                     # ~2.5 - 27 years
    h = int(hashlib.sha256(("age:" + domain).encode()).hexdigest()[:8], 16)
    if any(re.search(p, domain) for p in SQUAT_PATTERNS):
        return 3 + (h % 60)                          # weeks old -> burner
    tld = domain.rsplit(".", 1)[-1]
    if tld in SUSPICIOUS_TLDS:
        return 20 + (h % 300)                        # under a year
    return 60 + (h % 2400)


def _live_whois_age_days(domain: str) -> int | None:
    try:
        import whois  # python-whois

        record = whois.whois(domain)
        created = record.creation_date
        if isinstance(created, list):
            created = created[0]
        if isinstance(created, datetime):
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            return max(0, (datetime.now(timezone.utc) - created).days)
    except Exception:
        return None
    return None


def _live_mx_ok(domain: str) -> bool | None:
    try:
        import dns.resolver  # dnspython (optional)

        answers = dns.resolver.resolve(domain, "MX", lifetime=3)
        return len(answers) > 0
    except Exception:
        return None


def lookup_domain(domain: str | None, use_cache: bool = True) -> dict:
    """Return domain intelligence; cached in the domain_intel table."""
    if not domain:
        return {
            "domain": None, "valid_syntax": False, "age_days": 0, "age_years": 0,
            "is_free_provider": False, "is_disposable": False, "is_blacklisted": False,
            "mx_valid": False, "source": "missing", "tld": None,
        }

    domain = domain.lower().strip()
    if use_cache:
        cached = DomainIntel.query.filter_by(domain=domain).first()
        if cached:
            data = cached.to_dict()
            data.update({"valid_syntax": bool(DOMAIN_RE.match(domain)),
                         "tld": domain.rsplit(".", 1)[-1],
                         "reputation": _reputation(data)})
            return data

    valid_syntax = bool(DOMAIN_RE.match(domain)) and "." in domain
    is_free = domain in FREE_PROVIDERS
    is_disposable = domain in DISPOSABLE_PROVIDERS
    is_blacklisted = domain in DOMAIN_BLACKLIST
    tld = domain.rsplit(".", 1)[-1]

    live = current_app.config.get("ENABLE_LIVE_DOMAIN_CHECKS") if current_app else False
    age_days, mx_valid, source = None, None, "heuristic"

    if live and valid_syntax:
        age_days = _live_whois_age_days(domain)
        mx_valid = _live_mx_ok(domain)
        if age_days is not None:
            source = "whois"

    if age_days is None:
        age_days = _synthetic_age_days(domain)
    if mx_valid is None:
        mx_valid = not (not valid_syntax or is_disposable)

    record = DomainIntel.query.filter_by(domain=domain).first()
    if record is None:
        record = DomainIntel(domain=domain)
        db.session.add(record)
    record.age_days = age_days
    record.is_free_provider = is_free
    record.is_disposable = is_disposable
    record.is_blacklisted = is_blacklisted
    record.mx_valid = mx_valid
    record.source = source
    record.last_checked = datetime.utcnow()
    db.session.commit()

    return {
        "domain": domain,
        "valid_syntax": valid_syntax,
        "age_days": age_days,
        "age_years": round(age_days / 365.25, 2),
        "is_free_provider": is_free,
        "is_disposable": is_disposable,
        "is_blacklisted": is_blacklisted,
        "mx_valid": mx_valid,
        "tld": tld,
        "source": source,
        "reputation": _reputation({"age_days": age_days, "is_free_provider": is_free,
                                   "is_disposable": is_disposable,
                                   "is_blacklisted": is_blacklisted,
                                   "mx_valid": mx_valid, "domain": domain}),
    }


def _reputation(info: dict) -> dict:
    """Human-readable verdict for the domain (drives the fraud-detail UI)."""
    if not info.get("domain"):
        return {"label": "Missing recruiter email", "level": "danger", "points": 40}
    if info.get("is_blacklisted"):
        return {"label": "Blacklisted recruiter domain", "level": "danger", "points": 0}
    if info.get("is_disposable"):
        return {"label": "Disposable / burner email domain", "level": "danger", "points": 10}
    if info.get("is_free_provider"):
        return {"label": "Free email provider used for hiring", "level": "warning", "points": 55}
    verified = info["domain"] in VERIFIED_CORPORATE_DOMAINS
    age = info.get("age_days") or 0
    if verified and age >= 365:
        return {"label": "Verified corporate domain", "level": "success", "points": 100}
    if age >= 730:
        return {"label": "Established domain (>2 yrs)", "level": "success", "points": 92}
    if age >= 365:
        return {"label": "Domain older than 1 year", "level": "success", "points": 82}
    if age >= 180:
        return {"label": "Domain registered < 1 year ago", "level": "warning", "points": 62}
    if age >= 90:
        return {"label": "Recently registered domain", "level": "warning", "points": 45}
    return {"label": "Brand-new domain (high risk)", "level": "danger", "points": 18}

"""
NLP resume engine.

Pipeline:  raw file (PDF/DOCX) -> text -> NLTK normalisation -> skill/entity
extraction -> weighted skill vector -> ATS score & profile insights.
"""
from __future__ import annotations

import io
import re
from collections import Counter
from datetime import date

import nltk
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from nltk.tokenize import sent_tokenize, word_tokenize

from .skills_taxonomy import ALIAS_INDEX, DOMAIN_SIGNALS, MAX_ALIAS_TOKENS, SKILL_TAXONOMY

# ---------------------------------------------------------------- NLTK setup
_NLTK_PACKAGES = ["punkt", "punkt_tab", "stopwords", "wordnet", "omw-1.4"]
_ready = False


def ensure_nltk_data() -> None:
    global _ready
    if _ready:
        return
    for pkg in _NLTK_PACKAGES:
        try:
            nltk.data.find(f"corpora/{pkg}" if pkg in ("stopwords", "wordnet", "omw-1.4")
                           else f"tokenizers/{pkg}")
        except LookupError:
            nltk.download(pkg, quiet=True)
    _ready = True


ensure_nltk_data()

LEMMATIZER = WordNetLemmatizer()
STOPWORDS = set(stopwords.words("english"))

SECTION_HEADS = {
    "skills": ["skill", "technical skill", "technologies", "tech stack", "core competenc",
               "tools", "software", "programming languages"],
    "experience": ["experience", "internship", "work history", "employment", "professional"],
    "projects": ["project", "academic project", "personal project", "capstone"],
    "education": ["education", "academic", "qualification", "degree", "university", "college"],
    "certifications": ["certification", "certificate", "course", "training", "workshop"],
    "achievements": ["achievement", "award", "accomplishment", "honour", "honor", "publication"],
}

DEGREE_PATTERNS = [
    (r"b\.?\s?tech|bachelor of technology", "B.Tech"),
    (r"b\.?\s?e\.?\b|bachelor of engineering", "B.E."),
    (r"m\.?\s?tech|master of technology", "M.Tech"),
    (r"m\.?\s?c\.?a|master of computer applications", "MCA"),
    (r"b\.?\s?c\.?a|bachelor of computer applications", "BCA"),
    (r"b\.?\s?sc|bachelor of science", "B.Sc"),
    (r"m\.?\s?b\.?\s?a|mba", "MBA"),
    (r"diploma", "Diploma"),
]

BRANCH_PATTERNS = [
    (r"computer science|computers?\b|cse\b|information technology|it\b|ise\b", "Computer Science"),
    (r"electronics|electrical|eee|ece\b", "Electronics & Electrical"),
    (r"mechanical|mech\b", "Mechanical"),
    (r"civil", "Civil"),
    (r"chemical", "Chemical"),
    (r"artificial intelligence|ai & ml|machine learning", "AI & ML"),
    (r"data science", "Data Science"),
    (r"biotech|biomedical", "Biotechnology"),
    (r"instrumentation", "Instrumentation"),
]

DATE_RANGE_RE = re.compile(
    r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s*,?\s*(19|20)\d{2}"
    r"\s*(?:-|–|to|till|until)\s*"
    r"((jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s*,?\s*(19|20)\d{2}|present|current|till date|ongoing)",
    re.I,
)
CGPA_RE = re.compile(r"(?:cgpa|gpa|sgpa)\s*[:\-]?\s*(\d{1,2}(?:\.\d{1,2})?)\s*(?:/\s*10)?", re.I)
PERCENT_RE = re.compile(r"(\d{2,3}(?:\.\d{1,2})?)\s*%")
YEAR_RE = re.compile(r"\b(20[0-3]\d)\b")
EMAIL_RE = re.compile(r"[\w.\-+]+@[\w\-]+\.[\w.\-]+")
PHONE_RE = re.compile(r"(?:\+91[\-\s]?)?[6-9]\d{9}\b")
URL_RE = re.compile(r"https?://[^\s)]+|www\.[^\s)]+", re.I)


# ---------------------------------------------------------------- text loader
def extract_text_from_pdf(data: bytes) -> str:
    """Try pypdf first (fast), fall back to pdfminer.six (more tolerant)."""
    text_parts: list[str] = []
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        for page in reader.pages[:15]:
            text_parts.append(page.extract_text() or "")
        text = "\n".join(text_parts).strip()
        if len(text) > 80:
            return text
    except Exception:
        pass

    try:
        from pdfminer.high_level import extract_text as pdfminer_extract

        return (pdfminer_extract(io.BytesIO(data)) or "").strip()
    except Exception as exc:  # pragma: no cover
        raise ValueError(f"Could not read PDF content: {exc}") from exc


def extract_text_from_docx(data: bytes) -> str:
    try:
        import docx

        document = docx.Document(io.BytesIO(data))
    except Exception as exc:
        raise ValueError(f"Could not read DOCX content: {exc}") from exc

    blocks = [p.text for p in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            blocks.append(" | ".join(cell.text for cell in row.cells))
    return "\n".join(b for b in blocks if b and b.strip()).strip()


def extract_text(filename: str, data: bytes) -> str:
    lowered = filename.lower()
    if lowered.endswith(".pdf"):
        return extract_text_from_pdf(data)
    if lowered.endswith(".docx"):
        return extract_text_from_docx(data)
    if lowered.endswith(".txt"):
        return data.decode("utf-8", errors="ignore")
    raise ValueError("Unsupported file type. Upload a PDF or DOCX resume.")


# ---------------------------------------------------------------- normalisation
def normalise_text(text: str) -> str:
    text = text.replace("\u2013", "-").replace("\u2014", "-").replace("\u2019", "'")
    text = re.sub(r"[\u2022\u25cf\u25aa\u00b7]", " ", text)      # bullets
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def tokenize(text: str) -> list[str]:
    try:
        return word_tokenize(text)
    except LookupError:  # pragma: no cover
        ensure_nltk_data()
        return word_tokenize(text)


def lemmatize(tokens: list[str]) -> list[str]:
    out = []
    for tok in tokens:
        low = tok.lower()
        if low.isalpha() and len(low) > 2 and low not in STOPWORDS:
            out.append(LEMMATIZER.lemmatize(low))
    return out


def detect_sections(text: str) -> dict[str, str]:
    """Split resume into sections using heading heuristics (line-based)."""
    lines = text.split("\n")
    sections: dict[str, list[str]] = {"header": []}
    current = "header"
    for line in lines:
        stripped = line.strip()
        low = stripped.lower().strip(":-•* ")
        if 2 <= len(low) <= 48 and stripped:
            for section, heads in SECTION_HEADS.items():
                if any(low == h or low.startswith(h) for h in heads) and not low.endswith("."):
                    current = section
                    sections.setdefault(current, [])
                    break
            else:
                sections.setdefault(current, []).append(line)
        elif stripped:
            sections.setdefault(current, []).append(line)
    return {k: "\n".join(v) for k, v in sections.items() if v}


# ---------------------------------------------------------------- skill mining
def _alias_ngrams(tokens_lower: list[str]) -> Counter:
    """Count taxonomy alias hits as 1..4-grams, longest match wins per position."""
    counts: Counter = Counter()
    i = 0
    n = len(tokens_lower)
    while i < n:
        matched = 0
        for size in range(MAX_ALIAS_TOKENS, 0, -1):
            if i + size > n:
                continue
            gram = " ".join(tokens_lower[i:i + size])
            if gram in ALIAS_INDEX:
                counts[ALIAS_INDEX[gram]] += 1
                matched = size
                break
        i += matched if matched else 1
    return counts


SECTION_WEIGHT = {
    "skills": 1.6, "experience": 1.45, "projects": 1.3,
    "certifications": 1.15, "achievements": 1.1, "header": 1.0, "education": 1.05,
}


def extract_skills(text: str) -> list[dict]:
    """Return [{skill, category, weight, evidence, mentions}] sorted by weight."""
    sections = detect_sections(text) or {"header": text}
    scores: dict[str, float] = {}
    evidence: dict[str, set] = {}

    for section, body in sections.items():
        sec_w = SECTION_WEIGHT.get(section, 1.0)
        tokens_lower = [t.lower() for t in tokenize(body)]
        counts = _alias_ngrams(tokens_lower)
        for skill, count in counts.items():
            scores[skill] = scores.get(skill, 0.0) + sec_w * (1 + min(count, 4) * 0.25)
            evidence.setdefault(skill, set()).add(section)

    # company/tool context boost: skill appearing near "internship"/"built"/"developed"
    bonus_ctx = re.compile(
        r"(?:developed|built|designed|implemented|deployed|intern|worked on|project)[^.\n]{0,80}",
        re.I,
    )
    for ctx in bonus_ctx.findall(text):
        for skill in _alias_ngrams([t.lower() for t in tokenize(ctx)]):
            scores[skill] = scores.get(skill, 0.0) + 0.4

    if not scores:
        return []

    max_score = max(scores.values())
    details = []
    for skill, raw in scores.items():
        meta = SKILL_TAXONOMY.get(skill, {"category": "Other", "aliases": []})
        details.append({
            "skill": skill,
            "category": meta["category"],
            "weight": round(min(raw / max_score, 1.0), 3),
            "raw_score": round(raw, 3),
            "mentions": int(round(raw)),
            "found_in": sorted(evidence.get(skill, [])),
        })
    details.sort(key=lambda d: (-d["raw_score"], d["skill"]))
    return details


def build_skill_vector(skill_details: list[dict]) -> dict[str, float]:
    """Normalised {skill: weight} vector used by the TF-IDF style matcher."""
    if not skill_details:
        return {}
    total = sum(d["weight"] for d in skill_details) or 1.0
    return {d["skill"]: round(d["weight"] / total, 5) for d in skill_details}


def infer_domains(skill_vector: dict[str, float]) -> list[dict]:
    """Score every internship domain against the student's skill vector."""
    ranked = []
    for domain, signals in DOMAIN_SIGNALS.items():
        score = sum(skill_vector.get(s, 0.0) for s in signals)
        hits = [s for s in signals if s in skill_vector]
        if score > 0:
            ranked.append({
                "domain": domain,
                "score": round(score, 4),
                "matched_skills": sorted(hits, key=lambda s: -skill_vector[s])[:6],
                "confidence": 0,
            })
    ranked.sort(key=lambda d: -d["score"])
    if ranked:
        top = ranked[0]["score"] or 1.0
        for r in ranked:
            r["confidence"] = round(min(r["score"] / top, 1.0) * 100)
    return ranked


def parse_meta(text: str) -> dict:
    """Pull structured entities: degree, branch, CGPA, experience, links, counts."""
    sections = detect_sections(text)
    lowered = text.lower()

    degree = next((label for pat, label in DEGREE_PATTERNS if re.search(pat, lowered)), None)
    branch = next((label for pat, label in BRANCH_PATTERNS if re.search(pat, lowered)), None)

    cgpa = None
    m = CGPA_RE.search(text)
    if m:
        try:
            val = float(m.group(1))
            cgpa = val if 0 < val <= 10 else round(val / 10, 2)
        except ValueError:
            cgpa = None
    if cgpa is None:
        pct = PERCENT_RE.search(text)
        if pct:
            try:
                p = float(pct.group(1))
                if 35 <= p <= 100:
                    cgpa = round(p / 9.5, 2)
            except ValueError:
                pass

    grad_year = None
    years = [int(y) for y in YEAR_RE.findall(text)]
    future = [y for y in years if y >= 2025]
    if future:
        grad_year = min(future)
    elif years:
        grad_year = max(years)

    # experience estimate from "Mon YYYY - Mon YYYY|Present" ranges
    exp_months = 0
    month_names = ["jan", "feb", "mar", "apr", "may", "jun",
                   "jul", "aug", "sep", "oct", "nov", "dec"]
    today = date.today()
    for match in DATE_RANGE_RE.finditer(text):
        raw = match.group(0)
        years_in_match = [int(y) for y in re.findall(r"(19|20)\d{2}", raw)]
        if not years_in_match:
            continue
        start_y = years_in_match[0]
        start_m = month_names.index(match.group(1)[:3].lower()) \
            if match.group(1)[:3].lower() in month_names else 0

        end_token = (match.group(3) or "").strip().lower()
        if end_token.startswith(("present", "current", "till", "ongoing")):
            end_m, end_y = today.month - 1, today.year
        else:
            end_m = month_names.index(match.group(4)[:3].lower()) \
                if match.group(4) and match.group(4)[:3].lower() in month_names else 11
            end_y = years_in_match[-1]

        exp_months += max(0, (end_y - start_y) * 12 + (end_m - start_m))
    exp_months = min(exp_months, 60)

    project_count = len(re.findall(r"(?:^|\n)\s*(?:project|capstone)\b", text, re.I))
    if project_count == 0 and "projects" in sections:
        project_count = max(1, len(re.findall(r"[•\-]\s", sections["projects"])))

    cert_count = len(re.findall(r"(?:certificat|coursera|udemy|nptel|edx|aws certified|google cloud)", text, re.I))

    return {
        "degree": degree,
        "branch": branch,
        "cgpa": cgpa,
        "graduation_year": grad_year,
        "experience_months": exp_months,
        "project_count": project_count,
        "certification_count": cert_count,
        "emails": list(dict.fromkeys(EMAIL_RE.findall(text)))[:3],
        "phones": list(dict.fromkeys(PHONE_RE.findall(text)))[:3],
        "links": list(dict.fromkeys(URL_RE.findall(text)))[:6],
        "word_count": len(tokenize(text)),
        "sections_found": sorted(sections.keys()),
    }


def compute_ats_score(text: str, skills: list[dict], meta: dict) -> int:
    """Heuristic 0-100 resume-quality score (ATS friendliness + signal density)."""
    score = 0.0
    words = meta.get("word_count", 0)
    score += 18 if 250 <= words <= 900 else 12 if words > 900 else 6
    score += min(len(skills), 18) / 18 * 22
    score += 12 if meta.get("degree") else 0
    score += 8 if meta.get("cgpa") else 0
    score += 10 if meta.get("graduation_year") else 0
    score += 8 if meta.get("emails") else 0
    score += 6 if meta.get("phones") else 0
    score += 8 if meta.get("links") else 0
    score += min(meta.get("project_count", 0), 3) / 3 * 10
    sections = set(meta.get("sections_found", []))
    score += min(len(sections & {"skills", "projects", "experience", "education"}), 4) / 4 * 8
    return int(round(min(score, 100)))


def analyse_resume(text: str) -> dict:
    """Full resume analysis used by POST /api/upload-resume."""
    text = normalise_text(text)
    if len(text) < 60:
        raise ValueError(
            "The extracted text is too short — the resume may be a scanned image "
            "or password protected. Please upload a text-based PDF/DOCX."
        )

    skill_details = extract_skills(text)
    skill_vector = build_skill_vector(skill_details)
    meta = parse_meta(text)
    domains = infer_domains(skill_vector)
    ats = compute_ats_score(text, skill_details, meta)

    tokens = lemmatize(tokenize(text))
    keyword_freq = Counter(
        t for t in tokens
        if len(t) > 3 and t not in STOPWORDS and not t.isdigit()
    )

    return {
        "text": text,
        "skills": [d["skill"] for d in skill_details],
        "skill_details": skill_details,
        "skill_vector": skill_vector,
        "meta": meta,
        "domain_matches": domains,
        "top_domain": domains[0]["domain"] if domains else None,
        "domain_confidence": domains[0]["confidence"] if domains else 0,
        "ats_score": ats,
        "keywords": keyword_freq.most_common(25),
        "skill_categories": _category_rollup(skill_details),
        "insights": _insights(skill_details, meta, ats, domains),
        "sentences": len(sent_tokenize(text)),
    }


def _category_rollup(skill_details: list[dict]) -> list[dict]:
    buckets: dict[str, list[dict]] = {}
    for d in skill_details:
        buckets.setdefault(d["category"], []).append(d)
    rollup = [
        {"category": cat, "count": len(items),
         "skills": [i["skill"] for i in items],
         "strength": round(sum(i["weight"] for i in items) / len(items), 3)}
        for cat, items in buckets.items()
    ]
    rollup.sort(key=lambda r: (-r["count"], r["category"]))
    return rollup


def _insights(skills: list[dict], meta: dict, ats: int, domains: list[dict]) -> list[dict]:
    out = []
    if not meta.get("links"):
        out.append({"level": "warning", "text": "No GitHub / portfolio link detected — "
                                                "recruiters filter on this. Add one."})
    if meta.get("experience_months", 0) == 0:
        out.append({"level": "info", "text": "No dated internship experience found. "
                                             "Add month-year ranges (e.g. Jun 2025 - Aug 2025)."})
    if len(skills) < 8:
        out.append({"level": "warning", "text": f"Only {len(skills)} recognisable skills "
                                                "extracted. Expand your Skills section."})
    else:
        out.append({"level": "success", "text": f"{len(skills)} skills recognised across "
                                                f"{len({s['category'] for s in skills})} categories."})
    if not meta.get("cgpa"):
        out.append({"level": "info", "text": "CGPA not detected — many listings gate on a 7.0+ CGPA."})
    if ats >= 75:
        out.append({"level": "success", "text": f"Strong ATS score ({ats}/100) — parses cleanly."})
    elif ats < 50:
        out.append({"level": "warning", "text": f"Low ATS score ({ats}/100). Use standard headings "
                                                "(Skills, Projects, Education) and avoid tables/columns."})
    if domains:
        out.append({"level": "success",
                    "text": f"Best-fit domain: {domains[0]['domain']} "
                            f"({domains[0]['confidence']}% confidence)."})
    return out

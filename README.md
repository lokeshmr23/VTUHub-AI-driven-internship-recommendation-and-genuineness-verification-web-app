# InternMatch AI

**AI-driven internship recommendation + genuineness verification platform for undergraduate engineering students and college placement cells.**

Students upload a resume → NLP extracts skills → a TF-IDF/cosine engine ranks internships by real fit → every listing carries a **0–100 Trust Score** built from recruiter-domain intelligence, red-flag phrase analysis and an ML fraud classifier. Admins get full listing CRUD, CSV bulk import, a fraud review queue, audited trust-score overrides and Chart.js analytics.

```
                       ┌──────────────────────────── Trust engine ────────────────────────────┐
resume (PDF/DOCX) ──▶  │  NLTK pipeline ▶ skill vector ▶ TF-IDF + cosine similarity (+0.10)   │ ──▶ ranked matches
                       │  RuleScore (domain · red flags · completeness) + ML fraud probability │ ──▶ trust badge
                       └──────────────────────────────────────────────────────────────────────┘
```

---

## 1. Quick start

```bash
cd internmatch
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -c "import nltk;[nltk.download(p,quiet=True) for p in ['punkt','punkt_tab','stopwords','wordnet','omw-1.4']]"

flask --app app init-db        # create tables
flask --app app train-ml       # train + persist the fraud classifier
flask --app app seed           # 500 listings, 50 students, applications, feedback (≈40 s)
flask --app app gen-samples    # sample resume PDFs + bulk-upload CSV
python app.py                  # → http://localhost:8000
```

Or one shot: `./run.sh` (creates the venv, installs, seeds and serves).

### Demo logins

| Role | Email | Password |
|------|-------|----------|
| Student | `student1@internmatch.ai` | `Student@123` |
| Admin (placement cell) | `admin@internmatch.ai` | `Admin@123` |

Seeded inventory: **500 listings** (~30 % scam-tier, ~20 % caution band, ~50 % verified), **50 student profiles** with skill vectors, **~330 applications**, feedback reports, 100+ cached recruiter domains and precomputed trust scores for every listing. Login page has one-click "Fill demo" buttons.

---

## 2. Database — MySQL (primary) with SQLite fallback

The app targets **MySQL** through SQLAlchemy. Configure `.env` (copy of `.env.example`):

```ini
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=secret
MYSQL_DATABASE=internmatch
# or a full URI, which takes priority:
# DATABASE_URL=mysql+pymysql://root:secret@localhost:3306/internmatch?charset=utf8mb4
```

Create the schema and import the seeded dataset:

```bash
mysql -u root -p -e "CREATE DATABASE internmatch CHARACTER SET utf8mb4;"
mysql -u root -p internmatch < sql/schema_mysql.sql     # 8 tables, InnoDB, utf8mb4, JSON columns
mysql -u root -p internmatch < sql/seed_data.sql        # generated 500-listing demo dataset
```

With no MySQL settings present the app auto-falls back to SQLite (`instance/internmatch.db`) so the demo runs anywhere — the schema is identical (`db.create_all()` derives it from the models, including `JSON` columns which SQLAlchemy maps to MySQL `JSON` / SQLite `JSON`).

**Tables:** `users`, `student_profiles`, `resume_uploads`, `domain_intel`, `internships`, `applications`, `feedback`, `trust_audit_log`.

---

## 3. Trust Score engine

### Formula (exactly as implemented in `services/trust_engine.py`)

```
TrustScore = round( (0.5 × RuleScore + 0.5 × (1 − MLFraudProbability)) × 100 )

RuleScore  = 0.40 × domain_score      # 40 %  email/domain validation
           + 0.35 × redflag_score     # 35 %  red-flag phrase analysis
           + 0.25 × completeness      # 25 %  listing completeness
```

### Domain validation (40 %)

| Check | Effect |
|-------|--------|
| Syntax valid | malformed domain → hard check fail |
| Blacklist membership | score → 0.05, **hard fail** |
| Disposable/burner provider | × 0.06, **hard fail** |
| Free provider (gmail/yahoo/outlook) | × 0.15 plus a warning finding |
| Domain age via WHOIS | < 90 d × 0.18 (**hard fail < 30 d**), < 180 d × 0.5, < 1 y × 0.78 |
| MX records | missing → × 0.25, **hard fail** |

Set `ENABLE_LIVE_DOMAIN_CHECKS=1` to query real WHOIS + DNS (python-whois, dnspython). By default the app uses a deterministic synthetic registry (verified-corporate list, squat-pattern detection, suspicious-TLD risk model) so demos are offline-safe and reproducible. Results are cached in `domain_intel`.

### Red-flag phrases (35 %)

12 weighted pattern families over title + description + apply URL, each with captured evidence:

registration/onboarding fee · money demanded · UPI/GPay/Paytm/bank transfer rails · guaranteed placement · unrealistic pay · artificial urgency · "no interview, direct joining" · WhatsApp/Telegram-only hiring · vague "easy money" work · Aadhaar/PAN/OTP demanded up-front · commission/MLM model · link shorteners & third-party forms.

A fee/UPI/payment hit is treated as a **hard fail** — the listing is flagged no matter how healthy the rest of the blend looks.

### Listing completeness (25 %)

Required-field coverage (title, company, location, domain, description, contact email, apply URL) + JD depth (word count bands) + skills density + stipend disclosure + deadline presence/validity.

### ML fraud classifier

`scikit-learn` pipeline: `FeatureUnion[ TF-IDF(1–2 grams, sublinear) over listing text , MaxAbsScaler(16 engineered risk features) ] → LogisticRegression`, trained on a labelled genuine/fraud corpus (`services/trust_rules_seed.py`, 38 rows) and persisted to `ml/artifacts/fraud_model.joblib`. Retrain from the admin UI (`POST /api/admin/ml/retrain`) — it rescoring the whole catalogue afterwards.

### Badges & flagging

```
Green : score ≥ 75                      (safe to apply)
Amber : 50 ≤ score < 75                 (apply with caution)
Red   : score < 50  OR  fraud_flag      (do not pay anything)
FraudFlag = trust_score < 45  OR  a domain hard check failed
```

---

## 4. Recommendation engine

```
document(listing)  = title ×2 + skills ×3 + domain ×2 + description + domain-signal vocabulary
document(student)  = weighted skill vector (repeat factor by weight) + preferred domain
raw_similarity     = cosine_similarity(TF-IDF(student), TF-IDF(listing))   # computed against the whole corpus
relative           = raw_similarity / best_similarity_in_corpus            # 0..1, set-relative
absolute           = min(raw_similarity / 0.28, 1.0)                       # corpus-calibrated ceiling
normalised         = 0.45 × relative + 0.55 × absolute
match              = min(normalised × 0.90 + (0.10 if listing.domain == student.preferred_domain else 0), 1.0)
match_pct          = round(match × 100)
final_rank         = 0.85 × match_pct + 0.15 × trust_score                 # keeps scams out of the top slots
```

Similarity is always computed against the **full corpus**, so narrowing the filters can't inflate a weak match:
a Data-Science student gets ~81 % for a matching ML/backend role and ~32 % when the domain filter is forced to
Cybersecurity. The `+0.10` domain bonus applies on top of that normalised score.

Each recommendation returns matched skills, missing skills, skill coverage, the cosine value, whether the +0.10 domain bonus applied, and a plain-English explanation string. Filters: domain, work mode, minimum trust, include/exclude flagged, search, sort (best match / trust / stipend / recent) plus a **browse mode** with server-side pagination over all 500+ listings.

---

## 5. API reference

JWT bearer auth (`Authorization: Bearer <token>`); an httpOnly cookie is set as well so the app survives sandboxed iframes. Roles: `student`, `admin`.

### Auth — `/api/auth`
| Method | Endpoint | Notes |
|---|---|---|
| POST | `/register` | role-aware; admins need `ADMIN_INVITE_CODE` |
| POST | `/login` · `/logout` · `/refresh` | issues/rotates the JWT |
| GET | `/me` | current user + profile |
| POST | `/change-password` | self-service |

### Student
| Method | Endpoint | Notes |
|---|---|---|
| POST | `/api/upload-resume` | **PDF/DOCX** → text, skills, vectors, ATS score, insights |
| GET | `/api/student/profile/<student_id>` | profile, skill cloud, domain fit, uploads |
| PUT | `/api/student/profile/<student_id>` | edit profile / preferred domain |
| GET | `/api/recommendations/<student_id>` | ranked matches (`limit, domain, work_mode, min_trust, include_flagged, q`) |
| GET | `/api/student/dashboard/<student_id>` | KPIs, funnel, trust exposure, top recs |
| GET | `/api/internships` · `/api/internships/<id>` | browse + filtered pagination, detail + similar |
| GET | `/api/trustscore/<internship_id>` | full breakdown (`?refresh=true` re-runs checks) |
| POST/PATCH/DELETE | `/api/applications` · `/api/applications/<id>` | apply, update status, withdraw |
| POST | `/api/feedback` | Verified/Suspicious verdict + 1–5 rating + comment |

### Admin
| Method | Endpoint | Notes |
|---|---|---|
| GET/POST | `/api/admin/internships` · `/api/admin/add-internship` | list + create (auto-scored) |
| PUT/DELETE | `/api/admin/internships/<id>` | edit (re-scores) · delete |
| POST | `/api/admin/internships/<id>/recompute` | re-run the trust pipeline |
| POST | `/api/admin/bulk-upload` (+ `/template`) | CSV import with duplicate detection & per-row verdicts |
| GET | `/api/admin/flagged` · `/flagged/<id>/resolve` | fraud review queue + clear-a-flag (audited) |
| POST | `/api/admin/trustscore-override` | manual score with **mandatory justification**, writes audit row |
| POST | `/api/admin/trustscore/recompute-all` | bulk re-score |
| GET | `/api/admin/analytics` | KPIs, badge/band distributions, domain risk, flag frequency, 8-week trend, ML metrics |
| GET | `/api/admin/students` · `/applications` · `/feedback` · `/audit-log` · `/domains` | management views |
| GET | `/api/admin/export/flagged.csv` | CSV export |
| POST | `/api/admin/ml/retrain` | retrain classifier + re-score catalogue |

Plus `GET /healthz` for liveness and a `/api/auth/branches` reference endpoint.

---

## 6. UI

Server-rendered Jinja shells with a static-JS dashboard layer (Bootstrap 5 + Chart.js vendored locally — no CDN needed).

**Student:** sidebar dashboard (KPIs, application funnel, trust exposure doughnut, skill tag cloud with weighted bubble sizes, top-match cards, recent applications) · recommendation feed with filter bar, match-percentage cards, trust badges, matched/missing skill chips · resume & skills page (drag-drop upload with progress state, extraction results, domain-fit bars, category chart, keyword cloud, entity list, ATS insights, upload history) · applications tracker (status dropdown with optimistic update + rollback, withdraw with confirm modal) · feedback page · listing detail with the complete trust report (component bars, matched phrase evidence, domain intelligence, score history timeline) · **apply → external site → feedback popup → thank-you state**.

**Admin:** placement dashboard (score bands, badge split, top fraud signals, ML card, posting trend, lowest-trust watchlist, re-score-all) · listings CRUD (modal form with live validation, trust preview, re-score, override, delete with optimistic removal) · fraud review queue (severity filters, red-flag evidence, mark-safe / override / delete, CSV export) · bulk CSV upload (drag-drop, per-row results table, flagged rows pushed straight to the queue) · analytics (6 charts + recruiter leaderboard + model card) · students directory with skill-cloud drawer · feedback stream · audit log with domain intelligence panel.

Empty states, loading skeletons, spinner states, toast notifications and optimistic updates are used throughout.

---

## 7. Project layout

```
internmatch/
├── app.py                     # app factory, page routes, CLI (init-db/seed/train-ml/gen-samples/export-sql/rescoring/stats),
│                              #   self-healing first boot: create tables + seed inside a cross-process lock
├── config.py                  # MySQL-first config with SQLite fallback + MySQL TLS options
├── models.py                  # 8 SQLAlchemy models
├── security.py                # JWT issue/verify, role decorators
├── extensions.py
├── routes/
│   ├── auth_routes.py         # register/login/me/refresh/logout/password
│   ├── student_routes.py      # resume upload, profile, recommendations, applications, feedback, dashboard
│   ├── admin_routes.py        # CRUD, CSV, fraud queue, override, analytics, audit, ML retrain
│   └── helpers.py             # JSON envelopes, pagination, error wrapper
├── services/
│   ├── nlp_engine.py          # PDF/DOCX → text → sections → skills → vector → entities → ATS
│   ├── skills_taxonomy.py     # 180+ skills, 15 categories, domain signal map
│   ├── recommender.py         # TF-IDF + cosine + 0.10 domain bonus
│   ├── trust_engine.py        # RuleScore + ML blend, badges, hard checks, breakdowns
│   ├── ml_fraud.py            # sklearn pipeline, training corpus, persisted artifact
│   ├── domain_intel.py        # WHOIS/DNS checks, free/disposable/blacklist, caching
│   ├── seeder.py              # 500 listings + 50 students + interactions
│   ├── resume_builder.py      # seeded + downloadable sample resumes (reportlab)
│   ├── sample_factory.py      # sample PDFs and bulk-upload CSV
│   └── sql_export.py          # MySQL INSERT dump generator
├── templates/                 # 16 pages (student/, admin/, partials/)
├── static/css/app.css         # design system (sidebar shell, badges, rings, skeletons)
├── static/js/{api,ui,student,admin}.js
├── static/vendor/             # bootstrap 5.3, bootstrap-icons, chart.js 4.4 (vendored)
├── sql/schema_mysql.sql       # MySQL DDL
├── sql/seed_data.sql          # generated demo dataset (INSERTs)
├── samples/                   # 5 uploadable resume PDFs + bulk-upload CSV
├── build.sh                   # deploy build: deps + NLTK corpora + ML warm-up
├── render.yaml / Procfile     # Render Blueprint and portable start command
├── DEPLOY.md                  # git + GitHub + Render walkthrough
├── tests/test_api.py          # 83-assertion end-to-end API suite
├── tests/test_smoke.py        # 26 read-only assertions vs a fresh seed
└── ml/artifacts/fraud_model.joblib
```

## 8. Testing

```bash
python app.py &               # start the server (or: make serve)
python tests/test_api.py      # 83 assertions, mutates data (or: make test)
python tests/test_smoke.py    # 26 read-only assertions against a fresh seed
```

Both suites accept a target URL, so they also work against a deployed instance:

```bash
SMOKE_BASE=https://your-app.onrender.com python tests/test_smoke.py   # read-only, safe on prod
BASE_URL=http://127.0.0.1:8090 python tests/test_api.py               # e.g. against MySQL locally
```

`test_api.py` covers auth & role boundaries, PDF **and** DOCX extraction, recommendation ranking + domain bonus +
filters, the trust formula identity (`0.5·rule + 0.5·(1−p) == trust_score`), application/feedback validation,
admin CRUD, auto-flagging of a scam listing, override guardrails (note + range), CSV import/duplicate
detection/template validation, analytics payloads and every HTML page route. `test_smoke.py` verifies a pristine
seed (500 listings / 50 students, badge mix, formula identity on a flagged listing, all 16 page routes) without
changing any data — run it after `flask --app app seed` to confirm an install is healthy.

The UI layer was additionally verified in headless Chromium across 16 flows (login, resume upload, ranking,
fraud detail, apply → feedback popup → thank-you, admin CRUD, CSV import, charts, mobile viewport) with **zero
console errors**.

## 9. Deployment (Render + free MySQL)

`DEPLOY.md` is the full walkthrough: git → GitHub → external MySQL (Aiven free tier, since **Render
hosts no MySQL**) → Render Blueprint or manual service → verification → free-tier caveats.

tl;dr — the repo already contains everything the host needs:

| File | Purpose |
| --- | --- |
| `build.sh` | `pip install -r requirements.txt`, pre-downloads NLTK corpora, warms the ML model |
| `render.yaml` | Render Blueprint: build/start commands, health check, env vars |
| `Procfile` | same start command for other PaaS hosts |

First boot against an empty database **creates the schema and seeds the 500 listings + 50 students by
itself** (inside a cross-process lock, so it is safe with multiple gunicorn workers) — required because
free Render services have no shell or one-off jobs to run `flask seed` in. Verified end-to-end against a
real MySQL server: identical trust scores to the SQLite demo, 26/26 smoke and 83/83 API assertions, and
TLS connections to a TLS-only server.

## 10. Notes & production hardening

* The dev server is single-process SQLite-friendly; for production use the `gunicorn` command from `render.yaml`, MySQL, `FLASK_CONFIG=prod`, HTTPS-only cookies (`secure=True`) and a rotated `JWT_SECRET`.
* The recommender caches its TF-IDF index and invalidates it whenever listings change (seed, CRUD, CSV import, cleanup) — first call after a change re-fits in ~1 s for 500 documents.
* Sample data is deterministic (`random.Random(20250928)`), so scores and rankings are reproducible across machines.
* Live WHOIS/DNS is opt-in; the synthetic registry keeps the demo fast and offline.

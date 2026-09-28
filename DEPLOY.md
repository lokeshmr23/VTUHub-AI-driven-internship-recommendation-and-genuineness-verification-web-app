# Deploy InternMatch AI — GitHub + Render

Everything needed to get this project into git and live on a public URL.
Written for **Render's free tier**, which has three quirks that shape the steps:

| Render free-tier constraint | Consequence for this project |
| --- | --- |
| **No managed MySQL** (only Postgres, which also expires after 30 days) | Point `MYSQL_*` at a free external MySQL (Aiven is used below) |
| **No shell, no one-off jobs** on free services | You cannot run `flask seed` after deploy — so the app **seeds itself** on the first boot against an empty database. Already wired up and tested. |
| **Ephemeral disk**, 512 MB RAM, sleeps after 15 min idle | Your database lives at the provider (persists); `uploads/` and any local SQLite file do not. Cold start ≈ 1 min. |

---

## 0. Pre-flight (optional but recommended)

```bash
cd internmatch
pip install -r requirements.txt
flask --app app init-db && flask --app app train-ml && flask --app app seed
python app.py                    # http://localhost:8000
python tests/test_smoke.py       # 26 read-only checks against a fresh seed
```

Everything green? Then the same image will come up on Render.

---

## 1. Put the project in git

`.gitignore` is already set up, so `.env`, `instance/`, `uploads/*.pdf|docx`,
`ml/artifacts/*.joblib` and `nltk_data/` stay out of the repo (they are local
state or get regenerated at build time).

```bash
cd internmatch

git init -b main
git add .
git status          # ← check: no .env, no instance/, no nltk_data/ in the list
git commit -m "InternMatch AI — Flask + MySQL internship recommender with trust scoring"
```

### Create the GitHub repo and push

```bash
# Option A — GitHub CLI (creates the repo and pushes in one step)
gh auth login
gh repo create internmatch-ai --private --source=. --remote=origin --push

# Option B — create an empty repo at github.com/new (no README), then:
git remote add origin https://github.com/<your-username>/internmatch-ai.git
git push -u origin main
```

Afterwards each change is just:

```bash
git add -A && git commit -m "what changed" && git push
```

---

## 2. Get a MySQL database (Render doesn't provide one)

The stack mandates MySQL, so the database is hosted externally. Both options
below are free and need no credit card. **TLS is handled for you** — the pinned
PyMySQL driver negotiates an encrypted connection by default (verified against a
TLS-only server; see §7).

### Option A — Aiven for MySQL (real MySQL, free forever) ← recommended

1. Sign up at <https://aiven.io> (free services need no card).
2. **Create service → MySQL → plan `Free`** (1 GB storage, free indefinitely).
   Pick the region closest to your users (e.g. `ap-south-1 Mumbai` /
   `ap-southeast-1 Singapore`). Keep the service name handy.
3. Wait until the service shows **Running**, then copy from its *Overview*:

   | Aiven field | Render env var |
   | --- | --- |
   | Host | `MYSQL_HOST` |
   | Port | `MYSQL_PORT` |
   | User | `MYSQL_USER` |
   | Password | `MYSQL_PASSWORD` |
   | Database (usually `defaultdb`) | `MYSQL_DATABASE` |

4. That's it — no schema import needed. Leave the database empty: the first boot
   creates all 8 tables and seeds 500 listings + 50 students by itself.

> Aiven's free tier may power a service off after long inactivity; just restart
> it from the Aiven console if the app starts returning database errors.

### Option B — TiDB Cloud Serverless (MySQL-compatible, 5 GiB free)

Free forever within quota at <https://tidbcloud.com> (no card). Create a
Serverless cluster, then in the SQL editor run `CREATE DATABASE internmatch;`
and use the connection details it shows (port **4000**, user like
`2Uk3f4...root`). TLS is mandatory there and works out of the box.

Other names you may see recommended (PlanetScale, Railway, freesqldatabase) have
changed their free tiers repeatedly — Aiven is the stable choice for a college
demo.

---

## 3. Deploy on Render

### Route 1 — Blueprint (uses the included `render.yaml`)

1. Push to GitHub (step 1).
2. Render Dashboard → **New + → Blueprint** → connect your GitHub account →
   select the `internmatch-ai` repo → **Apply**.
3. Render reads `render.yaml` and prompts for the values marked `sync: false`:
   `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE`
   — paste the Aiven/TiDB details. `SECRET_KEY` and `JWT_SECRET` are generated
   for you.
4. **Create / Apply**. Done — Render builds and deploys automatically.

### Route 2 — Manual web service (equivalent to the Blueprint)

Render Dashboard → **New + → Web Service** → pick the repo, then:

| Setting | Value |
| --- | --- |
| Language / Runtime | `Python` |
| Branch | `main` |
| Region | Singapore (or nearest) |
| Instance type | `Free` |
| **Build Command** | `bash build.sh` |
| **Start Command** | `gunicorn -w 2 -k gthread --threads 4 --timeout 120 -b 0.0.0.0:$PORT app:app` |
| Health Check Path | `/healthz` |

Environment variables (Render → your service → *Environment*):

| Key | Value |
| --- | --- |
| `PYTHON_VERSION` | `3.13.0` (any 3.13.x works) |
| `FLASK_CONFIG` | `prod` |
| `SECRET_KEY` | a long random string (Render can generate it) |
| `JWT_SECRET` | another long random string |
| `NLTK_DATA` | `/opt/render/project/src/nltk_data` |
| `MYSQL_HOST` / `MYSQL_PORT` / `MYSQL_USER` / `MYSQL_PASSWORD` / `MYSQL_DATABASE` | from step 2 |

Optional: `ADMIN_INVITE_CODE`, `JWT_EXPIRES_HOURS`, `ENABLE_LIVE_DOMAIN_CHECKS=1`
(real WHOIS/MX lookups — slower, needs outbound DNS), `MYSQL_SSL_MODE` /
`MYSQL_SSL_CA` (§ Troubleshooting).

### What happens on that first boot

```
[INFO] Bootstrapped demo data: {'listings': 500, 'flagged': 156, 'students': 50,
       'applications': 325, 'feedback': 44, 'avg_trust': 70.1,
       'green': 280, 'amber': 64, 'red': 156}
```

Tables are created and demo data is seeded **once**, inside a cross-process lock,
so it is safe with multiple gunicorn workers and several instances sharing one
database. Expect the very first boot to take ~30–60 s; later boots are instant.

---

## 4. Verify the deployment

```bash
curl https://<your-app>.onrender.com/healthz
```

```json
{"status":"ok","database":"mysql+pymysql","listings":500,"students":50,...}
```

`"database":"mysql+pymysql"` confirms it is really talking to MySQL.

Then open the site and log in:

| Role | Email | Password |
| --- | --- | --- |
| Placement admin | `admin@internmatch.ai` | `Admin@123` |
| Student demo | `student1@internmatch.ai` | `Student@123` |

Worth clicking through once: **Student → Recommendations** (ranked matches,
trust badges, breakdown chart), a **Red** listing's detail page (red-flag
evidence), **Student → upload a resume** (the `samples/` folder has 5 PDFs and a
bulk-upload CSV for the admin side).

The read-only suite can be pointed at production:

```bash
SMOKE_BASE=https://<your-app>.onrender.com python tests/test_smoke.py
```

> It asserts a *pristine* 500/50 seed, so run it before editing data in the app.

---

## 5. Living with the free tier

* **Sleeps after 15 min idle** → the next visit takes ~1 min to wake. Hit
  `/healthz` a minute before a demo/viva. (A free uptime-pinger works too.)
* **Ephemeral disk** → uploaded resumes vanish on redeploy/restart. The
  `uploads/` folder is demo-only; nothing else depends on disk (MySQL is
  external, and the ML model is retrained automatically if its file is missing).
* **512 MB RAM** → ~162 MB per worker here (measured), so the two workers in the
  start command use ~350 MB. If Render logs show OOM kills, switch to
  `gunicorn -w 1 -k gthread --threads 4 --timeout 120 -b 0.0.0.0:$PORT app:app`.
* **No shell / no one-off jobs** → to force a reseed you either deploy with a
  fresh empty database or run `flask --app app seed` from your own machine with
  the same `MYSQL_*` values exported (it will rebuild the schema and the 500/50
  dataset remotely).
* **Single instance** — no autoscaling; fine for a demo.

---

## 6. Day-2 operations

| Task | How |
| --- | --- |
| Ship a change | `git push` → Render auto-deploys (build → health check → swap) |
| Roll back | Render → service → *Events* → pick a previous deploy → **Redeploy** |
| Change an env var | Render → *Environment* → edit → save (triggers a restart) |
| Reseed the demo data | Locally with prod `MYSQL_*` exported: `flask --app app seed` |
| Re-run migrations | none — `db.create_all()` runs on every boot and is idempotent |
| Rotate secrets | change `SECRET_KEY`/`JWT_SECRET` in Render → existing sessions are invalidated |

---

## 7. Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| First request hangs ~1 min | Render free spin-down — expected, not a bug |
| `Worker failed to boot` / `Table '…' already exists` at boot | Multi-worker bootstrap race. Fixed via the advisory/file lock in `app.py`; make sure the deployed commit includes it |
| `Can't connect to MySQL server` | Wrong `MYSQL_*` values, or the free DB provider powered the service off — check its console |
| `3159 Connections using insecure transport are prohibited` | The server demands TLS and it was disabled. Leave `MYSQL_SSL_MODE` unset (default negotiates TLS), or set `verify-ca` + `MYSQL_SSL_CA` |
| `NLTK LookupError` | `NLTK_DATA` points somewhere empty; the app will re-download at runtime (slower first boot). `build.sh` normally prevents this |
| Uploads disappear after a redeploy | Expected on the ephemeral free disk |
| Login works but dashboards 500 | Check `MYSQL_*` again — the API returns `{"success": false, "error": …}` in the response body |
| Build fails at `pip install` | Python version mismatch — set `PYTHON_VERSION=3.13.0` |

---

## 8. What was verified before writing this guide

All of it on a throwaway MySQL 11.4 server with the app running under gunicorn,
i.e. the same shape as Render:

| Check | Result |
| --- | --- |
| Empty MySQL database + first boot | Tables created, 500 listings / 50 students / 325 applications / 44 feedback seeded automatically |
| Cross-engine determinism | Trust scores byte-identical to the SQLite demo (Green 280 / Amber 64 / Red 156, avg 70.1) |
| `gunicorn -w 2` on a fresh database | Exactly one bootstrap, both workers stay up (race fixed) |
| TLS-only MySQL (`require_secure_transport=ON`) | Connects over TLS 1.3; `verify-ca` / `verify-identity` also pass; `disabled` is correctly refused |
| Read-only suite vs MySQL (`SMOKE_BASE=…`) | 26 / 26 |
| Full API suite vs MySQL (`BASE_URL=…`) | 83 / 83 |
| `build.sh` NLTK step | All 5 corpora download non-interactively (`NLTK_DATA` must be exported first — done in the script) |
| ML artifact | Regenerated on demand if absent, so it stays out of git |

Two genuine deploy-blockers were found and fixed during that work:
a MySQL metadata-lock deadlock on first boot, and a multi-worker DDL/seed race —
both are in the current code (`app.py`, `services/seeder.py`).

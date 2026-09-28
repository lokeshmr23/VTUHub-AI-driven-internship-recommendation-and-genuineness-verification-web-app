#!/usr/bin/env bash
# =====================================================================
# InternMatch AI — one-command local bootstrap
#   ./run.sh          -> set up venv, install deps, seed demo data, serve
#   ./run.sh mysql    -> same, but using MySQL (reads .env)
# =====================================================================
set -euo pipefail
cd "$(dirname "$0")"

PY=${PYTHON:-python3}
VENV=.venv

if [ ! -d "$VENV" ]; then
  echo "▶ Creating virtualenv…"
  "$PY" -m venv "$VENV"
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"

echo "▶ Installing dependencies…"
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

echo "▶ Fetching NLTK corpora (punkt, stopwords, wordnet)…"
python - <<'PY'
import nltk
for pkg in ["punkt", "punkt_tab", "stopwords", "wordnet", "omw-1.4"]:
    nltk.download(pkg, quiet=True)
print("   corpora ready")
PY

if [ ! -f .env ] && [ "${1:-}" = "mysql" ]; then
  echo "▶ No .env found — copying the MySQL template"
  cp .env.example .env
  echo "   edit .env with your MySQL credentials, then re-run ./run.sh mysql"
  exit 1
fi

echo "▶ Creating tables + training the fraud model + seeding demo data…"
flask --app app init-db
flask --app app train-ml
flask --app app seed --listings 500 --students 50
flask --app app gen-samples
flask --app app export-sql

PORT=${PORT:-8000}
echo ""
echo "======================================================================"
echo " InternMatch AI is starting on http://localhost:${PORT}"
echo "   student demo : student1@internmatch.ai / Student@123"
echo "   admin demo   : admin@internmatch.ai   / Admin@123"
echo "======================================================================"
echo ""
exec python app.py

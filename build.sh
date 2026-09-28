#!/usr/bin/env bash
# =====================================================================
# InternMatch AI — build step (Render / Railway / any PaaS)
#
#   bash build.sh
#
# Installs dependencies, pre-downloads the NLTK corpora the NLP engine
# needs, and trains the ML fraud classifier so the first request is fast.
# Idempotent: safe to re-run on every deploy.
# =====================================================================
set -euo pipefail
cd "$(dirname "$0")"

PY=${PYTHON:-python3}

echo "▶ Installing Python dependencies…"
"$PY" -m pip install --upgrade pip
"$PY" -m pip install -r requirements.txt

# NLTK >= 3.10 sandboxes downloads to the locations in nltk.data.path plus
# $NLTK_DATA, so the target directory has to be declared *before* downloading
# (otherwise every package fails with "Security Violation: Unauthorized path"
# and, in a non-interactive build, kills the deploy). The same directory is set
# as NLTK_DATA at run time — see render.yaml.
export NLTK_DATA="$(pwd)/nltk_data"

echo "▶ Downloading NLTK corpora into $NLTK_DATA …"
"$PY" - <<'PY'
import os
import nltk

target = os.environ["NLTK_DATA"]
for pkg in ("punkt", "punkt_tab", "stopwords", "wordnet", "omw-1.4"):
    ok = nltk.download(pkg, download_dir=target, quiet=True)
    print(f"   {pkg:<10} {'ok' if ok else 'FAILED — nlp_engine retries at runtime'}")

import nltk.data
from nltk.corpus import stopwords
nltk.data.path.insert(0, target)
print(f"   stopwords loaded: {len(stopwords.words('english'))}")
PY

# Trains from a curated in-repo seed corpus — no database needed, deterministic
# (accuracy/f1/roc_auc = 1.0 on those 38 samples). The app retrains on demand if
# the artifact is missing, so this step is a warm-up, not a hard requirement.
echo "▶ Training the ML fraud classifier…"
"$PY" -c "from services.ml_fraud import train_model; print('  ', train_model(save=True))"

echo "✔ Build complete."

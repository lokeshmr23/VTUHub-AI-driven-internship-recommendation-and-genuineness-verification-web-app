# InternMatch AI — common tasks
PY ?= python3
FLASK = $(PY) -m flask --app app

.PHONY: help install nltk db seed samples sql ml score serve test clean reset mysql-schema

help:
	@echo "InternMatch AI — make targets"
	@echo "  install   install python dependencies"
	@echo "  nltk      download required NLTK corpora"
	@echo "  db        create tables (MySQL if .env is set, else SQLite)"
	@echo "  seed      generate 500 listings + 50 students + trust scores"
	@echo "  samples   write sample resume PDFs + bulk-upload CSV"
	@echo "  sql       export sql/seed_data.sql (MySQL INSERTs)"
	@echo "  ml        train the ML fraud classifier"
	@echo "  score     re-run the trust engine over every listing"
	@echo "  serve     run the dev server on :8000"
	@echo "  test      run the API end-to-end test suite"
	@echo "  reset     drop + rebuild + reseed everything"

install:
	$(PY) -m pip install -r requirements.txt

nltk:
	$(PY) -c "import nltk; [nltk.download(p, quiet=True) for p in ['punkt','punkt_tab','stopwords','wordnet','omw-1.4']]"

db:
	$(FLASK) init-db

seed:
	$(FLASK) seed --listings 500 --students 50

samples:
	$(FLASK) gen-samples

sql:
	$(FLASK) export-sql

ml:
	$(FLASK) train-ml

score:
	$(FLASK) rescoring

serve:
	$(PY) app.py

test:
	$(PY) tests/test_api.py

mysql-schema:
	mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS internmatch CHARACTER SET utf8mb4;"
	mysql -u root -p internmatch < sql/schema_mysql.sql

reset: db ml seed samples sql
	@echo "✔ database rebuilt and reseeded"

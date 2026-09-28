# Procfile — used by Render, Railway, Heroku-style platforms.
# Prefer render.yaml if you deploy with a Render Blueprint; it carries the same
# start command plus the environment variables.
web: gunicorn -w ${WEB_CONCURRENCY:-2} -k gthread --threads 4 --timeout 120 -b 0.0.0.0:$PORT app:app

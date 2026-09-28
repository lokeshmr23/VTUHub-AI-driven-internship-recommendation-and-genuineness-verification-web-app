"""
InternMatch AI — application entry point.

    python app.py                        # dev server on 0.0.0.0:8000
    flask --app app seed --listings 500  # (re)seed demo data
    flask --app app init-db              # create tables only

Database: MySQL via MYSQL_* env vars / DATABASE_URL, SQLite fallback otherwise.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import click
from flask import Flask, jsonify, redirect, render_template, request, session, url_for

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from config import CONFIG_MAP                       # noqa: E402
from extensions import cors, db                     # noqa: E402
from models import Internship, StudentProfile, User  # noqa: E402
from routes.admin_routes import admin_bp            # noqa: E402
from routes.auth_routes import auth_bp              # noqa: E402
from routes.student_routes import student_bp        # noqa: E402
from security import AuthError, decode_token        # noqa: E402


def create_app(config_name: str | None = None) -> Flask:
    config_name = config_name or os.getenv("FLASK_CONFIG", "default")
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(CONFIG_MAP.get(config_name, CONFIG_MAP["default"]))
    app.config.setdefault("ADMIN_INVITE_CODE", os.getenv("ADMIN_INVITE_CODE", "INTERNMATCH-ADMIN"))

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    Path(app.config["ML_ARTIFACT_DIR"]).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": "*"}},
                  supports_credentials=True,
                  allow_headers=["Content-Type", "Authorization"])

    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(admin_bp)

    _register_pages(app)
    _register_errors(app)
    _register_cli(app)
    register_jinja(app)

    @app.after_request
    def _no_store_api(resp):
        if request.path.startswith("/api/"):
            resp.headers["Cache-Control"] = "no-store"
        return resp

    with app.app_context():
        _init_database(app)

    return app


def _bootstrap_lock(app: Flask):
    """Serialise first-boot DDL + seeding across processes.

    Gunicorn boots every worker by importing this module, so with ``-w N`` all N
    workers would race through ``create_all()`` and seeding on a fresh database
    (``Table 'x' already exists`` / clashing ``DROP TABLE`` → "Worker failed to
    boot"). MySQL sessions make this worse: an open read transaction holds a
    metadata lock that blocks the seeder's DDL.

    MySQL/MariaDB gets a server-wide advisory lock, which also covers several
    instances sharing one database. Everything else (SQLite) uses an flock file.
    """
    import contextlib

    uri = app.config["SQLALCHEMY_DATABASE_URI"]

    @contextlib.contextmanager
    def _locked():
        if uri.startswith("mysql"):
            from sqlalchemy import text

            conn = db.engine.connect()
            try:
                try:
                    got = conn.execute(
                        text("SELECT GET_LOCK('internmatch_bootstrap', 120)")
                    ).scalar()
                    if not got:
                        app.logger.warning("Bootstrap lock not acquired — continuing.")
                except Exception:                      # pragma: no cover - server quirk
                    app.logger.warning("Bootstrap lock unavailable — continuing.")
                yield
            finally:
                try:
                    conn.execute(text("SELECT RELEASE_LOCK('internmatch_bootstrap')"))
                except Exception:                      # pragma: no cover
                    pass
                conn.close()
        else:
            import fcntl

            lock_path = Path(app.config["UPLOAD_FOLDER"]).parent / "instance" / ".bootstrap.lock"
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            handle = open(lock_path, "w")
            try:
                try:
                    fcntl.flock(handle, fcntl.LOCK_EX)
                except Exception:                      # pragma: no cover - non-POSIX
                    pass
                yield
            finally:
                try:
                    fcntl.flock(handle, fcntl.LOCK_UN)
                except Exception:                      # pragma: no cover
                    pass
                handle.close()

    return _locked()


def _init_database(app: Flask) -> None:
    """Create tables, then seed demo data if the database is empty."""
    with _bootstrap_lock(app):
        db.create_all()
        _ensure_bootstrap_data(app)


# --------------------------------------------------------------------- pages
def _register_pages(app: Flask) -> None:
    @app.get("/")
    def landing():
        return render_template("landing.html", page="landing")

    @app.get("/login")
    def login_page():
        return render_template("login.html", page="login")

    @app.get("/register")
    def register_page():
        return render_template("register.html", page="register")

    @app.get("/student/dashboard")
    def student_dashboard_page():
        return render_template("student/dashboard.html", page="student-dashboard")

    @app.get("/student/recommendations")
    def student_recommendations_page():
        return render_template("student/recommendations.html", page="recommendations")

    @app.get("/student/profile")
    def student_profile_page():
        return render_template("student/profile.html", page="profile")

    @app.get("/student/applications")
    def student_applications_page():
        return render_template("student/applications.html", page="applications")

    @app.get("/student/feedback")
    def student_feedback_page():
        return render_template("student/feedback.html", page="feedback")

    @app.get("/student/internship/<int:internship_id>")
    def internship_detail_page(internship_id: int):
        return render_template("student/internship_detail.html", page="internship-detail",
                               internship_id=internship_id)

    @app.get("/admin/dashboard")
    def admin_dashboard_page():
        return render_template("admin/dashboard.html", page="admin-dashboard")

    @app.get("/admin/listings")
    def admin_listings_page():
        return render_template("admin/listings.html", page="admin-listings")

    @app.get("/admin/flagged")
    def admin_flagged_page():
        return render_template("admin/flagged.html", page="admin-flagged")

    @app.get("/admin/bulk-upload")
    def admin_bulk_page():
        return render_template("admin/bulk_upload.html", page="admin-bulk")

    @app.get("/admin/analytics")
    def admin_analytics_page():
        return render_template("admin/analytics.html", page="admin-analytics")

    @app.get("/admin/students")
    def admin_students_page():
        return render_template("admin/students.html", page="admin-students")

    @app.get("/admin/feedback")
    def admin_feedback_page():
        return render_template("admin/feedback.html", page="admin-feedback")

    @app.get("/admin/audit")
    def admin_audit_page():
        return render_template("admin/audit.html", page="admin-audit")

    @app.get("/healthz")
    def healthz():
        return jsonify({
            "status": "ok",
            "database": db.engine.url.drivername,
            "listings": Internship.query.count(),
            "students": StudentProfile.query.count(),
            "demo_accounts": {"student": "student1@internmatch.ai / Student@123",
                              "admin": "admin@internmatch.ai / Admin@123"},
        })


def register_jinja(app: Flask) -> None:
    @app.context_processor
    def inject_globals():
        return {
            "app_name": "InternMatch AI",
            "demo_student": {"email": "student1@internmatch.ai", "password": "Student@123"},
            "demo_admin": {"email": "admin@internmatch.ai", "password": "Admin@123"},
        }

    @app.template_filter("inr")
    def inr(value):
        try:
            return f"₹{int(value):,}"
        except (TypeError, ValueError):
            return "—"


# -------------------------------------------------------------------- errors
def _register_errors(app: Flask) -> None:
    @app.errorhandler(AuthError)
    def _auth_error(exc):
        return jsonify({"success": False, "error": exc.message}), exc.status

    @app.errorhandler(413)
    def _too_large(_exc):
        return jsonify({"success": False, "error": "File exceeds the 8 MB upload limit."}), 413

    @app.errorhandler(404)
    def _not_found(_exc):
        if request.path.startswith("/api/"):
            return jsonify({"success": False, "error": "Endpoint not found."}), 404
        return render_template("error.html", code=404,
                               message="We couldn't find that page."), 404

    @app.errorhandler(500)
    def _server_error(exc):  # pragma: no cover
        if request.path.startswith("/api/"):
            return jsonify({"success": False, "error": "Internal server error."}), 500
        return render_template("error.html", code=500,
                               message="Something broke on our side."), 500


# ----------------------------------------------------------------------- CLI
def _register_cli(app: Flask) -> None:
    @app.cli.command("init-db")
    def init_db():
        """Create all tables."""
        db.create_all()
        click.echo(f"✔ Tables created on {db.engine.url.drivername}")

    @app.cli.command("seed")
    @click.option("--listings", default=500, help="Number of internship listings to generate.")
    @click.option("--students", default=50, help="Number of student profiles to generate.")
    def seed(listings: int, students: int):
        """Rebuild the database with realistic demo data."""
        from services.seeder import seed_all

        stats = seed_all(listings=listings, students=students)
        click.echo("✔ Demo data seeded:")
        for key, value in stats.items():
            click.echo(f"   {key:<14} {value}")
        click.echo("\n   student login : student1@internmatch.ai / Student@123")
        click.echo("   admin login   : admin@internmatch.ai / Admin@123")

    @app.cli.command("train-ml")
    def train_ml():
        """(Re)train the ML fraud classifier and print metrics."""
        from services.ml_fraud import train_model

        click.echo("✔ Model trained:")
        for key, value in train_model(save=True).items():
            click.echo(f"   {key:<18} {value}")

    @app.cli.command("rescoring")
    def rescoring():
        """Recompute trust scores for every listing."""
        from services.trust_engine import evaluate_listing

        changed = 0
        for listing in Internship.query.all():
            before = listing.trust_score
            evaluate_listing(listing)
            changed += listing.trust_score != before
        db.session.commit()
        click.echo(f"✔ Re-scored {Internship.query.count()} listings ({changed} changed)")

    @app.cli.command("gen-samples")
    def gen_samples():
        """Generate uploadable sample resumes (PDF) and a CSV bulk-upload file."""
        from services.sample_factory import generate_samples

        paths = generate_samples(app)
        click.echo("✔ Sample assets written:")
        for path in paths:
            click.echo(f"   {path}")

    @app.cli.command("export-sql")
    @click.option("--out", default="sql/seed_data.sql")
    def export_sql(out: str):
        """Export the current listings/users as MySQL INSERT statements."""
        from services.sql_export import export_seed_sql

        path = export_seed_sql(Path(out))
        click.echo(f"✔ SQL export written to {path}")

    @app.cli.command("stats")
    def stats():
        """Print a quick DB summary."""
        from services.ml_fraud import model_metrics

        total = Internship.query.count()
        flagged = Internship.query.filter(Internship.fraud_flag.is_(True)).count()
        click.echo(f"listings={total} flagged={flagged} students={StudentProfile.query.count()}")
        click.echo(f"users={User.query.count()} ml={model_metrics()}")


def _ensure_bootstrap_data(app: Flask) -> None:
    """On a fresh database, create demo accounts + a small listing set.

    The emptiness check opens a read transaction. On MySQL (REPEATABLE READ) that
    transaction keeps a metadata lock on `users` until it is released, which
    deadlocks the seeder's ``DROP TABLE users`` when it rebuilds the schema on a
    first boot. So the session is torn down *before* seeding — a no-op on SQLite.
    """
    with app.app_context():
        fresh = User.query.count() == 0
        db.session.remove()                     # release read txn / MySQL metadata locks
        if not fresh:
            return

        from services.seeder import seed_all

        stats = seed_all(listings=500, students=50)
        db.session.remove()
        app.logger.info("Bootstrapped demo data: %s", stats)


app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    app.run(host="0.0.0.0", port=port, debug=os.getenv("FLASK_DEBUG", "0") == "1",
            use_reloader=False)

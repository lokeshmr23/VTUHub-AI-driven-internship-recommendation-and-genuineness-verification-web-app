"""
Configuration for InternMatch AI.

MySQL is the primary target database (see README + sql/schema_mysql.sql).
A zero-config SQLite fallback is used when no MySQL connection details are
present, so the demo runs anywhere.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _build_database_uri() -> str:
    """Priority: DATABASE_URL  >  MYSQL_* env vars  >  SQLite fallback."""
    explicit = os.getenv("DATABASE_URL")
    if explicit:
        return explicit

    host = os.getenv("MYSQL_HOST")
    if host:
        user = os.getenv("MYSQL_USER", "root")
        pwd = os.getenv("MYSQL_PASSWORD", "")
        port = os.getenv("MYSQL_PORT", "3306")
        name = os.getenv("MYSQL_DATABASE", "internmatch")
        return (
            f"mysql+pymysql://{user}:{pwd}@{host}:{port}/{name}"
            "?charset=utf8mb4"
        )

    (BASE_DIR / "instance").mkdir(exist_ok=True)
    return f"sqlite:///{BASE_DIR / 'instance' / 'internmatch.db'}"


def _mysql_connect_args() -> dict:
    """TLS options for managed MySQL.

    Render has no managed MySQL, so production usually points at a provider such
    as Aiven or TiDB Cloud, both of which *require* an encrypted connection.
    Pinned PyMySQL 2.x already attempts TLS by default ("preferred mode") and only
    falls back to plaintext when the server offers no TLS, so the common case
    needs no configuration.

    MYSQL_SSL_MODE tunes that behaviour:

        preferred (default)  try TLS, fall back to plaintext
        verify-ca            require TLS and verify the server certificate
                             (needs MYSQL_SSL_CA=/path/to/ca.pem)
        verify-identity      as above, plus host-name verification
        disabled             never use TLS (local socket / trusted VPN only)
    """
    mode = os.getenv("MYSQL_SSL_MODE", "preferred").strip().lower()
    if mode in ("", "preferred", "default"):
        return {}
    if mode == "disabled":
        return {"ssl_disabled": True}

    ca = os.getenv("MYSQL_SSL_CA")
    if not ca:
        raise RuntimeError(f"MYSQL_SSL_MODE={mode} requires MYSQL_SSL_CA=<path to ca.pem>")
    args = {"ssl_ca": ca, "ssl_verify_cert": True}
    if mode == "verify-identity":
        args["ssl_verify_identity"] = True
    return args


def _engine_options() -> dict:
    """Pool defaults, plus MySQL TLS args when a MySQL URI is in play."""
    opts = {"pool_pre_ping": True, "pool_recycle": 280}
    if _DATABASE_URI.startswith("mysql"):
        opts["connect_args"] = _mysql_connect_args()
    return opts


_DATABASE_URI = _build_database_uri()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "internmatch-dev-secret-change-me")
    JWT_SECRET = os.getenv("JWT_SECRET", SECRET_KEY)
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRES_HOURS = int(os.getenv("JWT_EXPIRES_HOURS", "12"))

    SQLALCHEMY_DATABASE_URI = _DATABASE_URI
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = _engine_options()

    UPLOAD_FOLDER = str(BASE_DIR / "uploads")
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024          # 8 MB resume cap
    ALLOWED_EXTENSIONS = {"pdf", "docx"}

    ML_ARTIFACT_DIR = str(BASE_DIR / "ml" / "artifacts")
    SAMPLES_DIR = str(BASE_DIR / "samples")

    # Live WHOIS / DNS lookups are disabled by default (offline-safe demo).
    # Set ENABLE_LIVE_DOMAIN_CHECKS=1 in .env to query real WHOIS + MX records.
    ENABLE_LIVE_DOMAIN_CHECKS = os.getenv("ENABLE_LIVE_DOMAIN_CHECKS", "0") == "1"

    TRUST_WEIGHT_RULE = 0.5
    TRUST_WEIGHT_ML = 0.5
    FRAUD_FLAG_THRESHOLD = 45
    BADGE_GREEN = 75
    BADGE_AMBER = 50

    JSON_SORT_KEYS = False


class DevConfig(Config):
    DEBUG = True


class ProdConfig(Config):
    DEBUG = False


CONFIG_MAP = {"dev": DevConfig, "prod": ProdConfig, "default": DevConfig}

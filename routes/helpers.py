"""Shared helpers for API routes."""
from __future__ import annotations

from functools import wraps

from flask import jsonify, request

from extensions import db


def ok(payload: dict | None = None, status: int = 200, **extra):
    body = {"success": True}
    if payload:
        body.update(payload)
    if extra:
        body.update(extra)
    return jsonify(body), status


def fail(message: str, status: int = 400, **extra):
    body = {"success": False, "error": message}
    if extra:
        body.update(extra)
    return jsonify(body), status


def paginate(query, default_per_page: int = 12, max_per_page: int = 100) -> dict:
    page = max(int(request.args.get("page", 1) or 1), 1)
    per_page = min(max(int(request.args.get("per_page", default_per_page) or default_per_page), 1),
                   max_per_page)
    total = query.count()
    items = query.limit(per_page).offset((page - 1) * per_page).all()
    return {
        "items": items,
        "meta": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": max((total + per_page - 1) // per_page, 1),
            "has_next": page * per_page < total,
            "has_prev": page > 1,
        },
    }


def api_error_handler(fn):
    """Wrap a route so service-level ValueErrors return clean 400s."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except ValueError as exc:
            db.session.rollback()
            return fail(str(exc), 400)
        except Exception as exc:  # pragma: no cover
            db.session.rollback()
            from flask import current_app

            current_app.logger.exception("API error in %s", fn.__name__)
            return fail(f"Unexpected server error: {exc}", 500)

    return wrapper

"""JWT auth: issue/verify tokens, role-aware route decorators."""
from datetime import datetime, timedelta
from functools import wraps

import jwt
from flask import current_app, g, jsonify, request

from extensions import db
from models import StudentProfile, User


class AuthError(Exception):
    def __init__(self, message: str, status: int = 401):
        super().__init__(message)
        self.message = message
        self.status = status


def issue_token(user: User) -> dict:
    now = datetime.utcnow()
    exp = now + timedelta(hours=current_app.config["JWT_EXPIRES_HOURS"])
    payload = {
        "sub": str(user.id),
        "uid": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "student_id": user.student.id if user.student else None,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "iss": "internmatch-ai",
    }
    token = jwt.encode(
        payload, current_app.config["JWT_SECRET"], algorithm=current_app.config["JWT_ALGORITHM"]
    )
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    return {"access_token": token, "token_type": "Bearer", "expires_at": exp.isoformat()}


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            current_app.config["JWT_SECRET"],
            algorithms=[current_app.config["JWT_ALGORITHM"]],
            issuer="internmatch-ai",
        )
    except jwt.ExpiredSignatureError:
        raise AuthError("Session expired — please log in again.", 401)
    except jwt.InvalidTokenError:
        raise AuthError("Invalid authentication token.", 401)


def _extract_token() -> str | None:
    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return request.cookies.get("access_token")


def jwt_required(*roles: str):
    """Decorator: requires a valid JWT, optionally restricted to given roles."""

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            token = _extract_token()
            if not token:
                return jsonify({"success": False, "error": "Authentication required."}), 401
            try:
                claims = decode_token(token)
            except AuthError as exc:
                return jsonify({"success": False, "error": exc.message}), exc.status

            user = db.session.get(User, claims.get("uid"))
            if not user or not user.is_active:
                return jsonify({"success": False, "error": "Account not found or disabled."}), 401
            if roles and user.role not in roles:
                return jsonify(
                    {"success": False, "error": f"Requires role: {' / '.join(roles)}."}
                ), 403

            g.current_user = user
            g.jwt_claims = claims
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def current_student() -> StudentProfile | None:
    user = getattr(g, "current_user", None)
    if not user:
        return None
    return user.student


def require_self_or_admin(student_id: int):
    """Students may only read their own records; admins may read any."""
    user = getattr(g, "current_user", None)
    if user is None:
        return jsonify({"success": False, "error": "Authentication required."}), 401
    if user.role == "admin":
        return None
    if not user.student or user.student.id != int(student_id):
        return jsonify({"success": False, "error": "You can only access your own data."}), 403
    return None

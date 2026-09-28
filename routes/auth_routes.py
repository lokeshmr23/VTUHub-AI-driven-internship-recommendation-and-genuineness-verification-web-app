"""Auth API — register / login / me / refresh / change-password (JWT)."""
from datetime import datetime

from flask import Blueprint, current_app, g, jsonify, request

from extensions import db
from models import StudentProfile, User
from routes.helpers import api_error_handler, fail, ok
from security import issue_token, jwt_required

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

def _attach_cookie(response, token: dict):
    """Also set the JWT as an httpOnly cookie so the app still authenticates
    inside sandboxed preview iframes where localStorage is unavailable."""
    response.set_cookie(
        "access_token", token["access_token"],
        max_age=current_app.config["JWT_EXPIRES_HOURS"] * 3600,
        httponly=True, samesite="Lax", secure=False, path="/")
    return response


VALID_BRANCHES = [
    "Computer Science", "Information Science", "Information Technology",
    "Electronics & Communication", "Electrical & Electronics", "Mechanical Engineering",
    "Civil Engineering", "AI & ML", "Chemical Engineering", "Biotechnology",
]


@auth_bp.post("/register")
@api_error_handler
def register():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    role = (data.get("role") or "student").lower()

    if not name or len(name) < 3:
        return fail("Please enter your full name (min 3 characters).")
    if "@" not in email or "." not in email.split("@")[-1]:
        return fail("Please enter a valid email address.")
    if len(password) < 6:
        return fail("Password must be at least 6 characters.")
    if role not in {"student", "admin"}:
        return fail("Role must be either 'student' or 'admin'.")
    if User.query.filter_by(email=email).first():
        return fail("An account with this email already exists.", 409)

    # Admin self-registration needs the invite code
    if role == "admin":
        from flask import current_app

        expected = current_app.config.get("ADMIN_INVITE_CODE", "INTERNMATCH-ADMIN")
        if (data.get("admin_code") or "").strip() != expected:
            return fail("Invalid admin invite code.", 403)

    user = User(name=name, email=email, role=role,
                phone=(data.get("phone") or "").strip() or None)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()

    if role == "student":
        profile = StudentProfile(
            user_id=user.id,
            roll_number=(data.get("roll_number") or "").strip() or None,
            college=(data.get("college") or "").strip() or None,
            branch=(data.get("branch") or "").strip() or None,
            graduation_year=int(data["graduation_year"]) if data.get("graduation_year") else None,
            cgpa=float(data["cgpa"]) if data.get("cgpa") else None,
            preferred_domain=(data.get("preferred_domain") or "").strip() or None,
            preferred_location=(data.get("preferred_location") or "").strip() or None,
            phone=user.phone,
            skills=[], skill_details=[], skill_vector={},
        )
        db.session.add(profile)

    db.session.commit()
    token = issue_token(user)
    resp, status = ok({"message": f"Welcome, {user.name}!",
                       "user": user.to_dict(with_profile=True), **token}, 201)
    return _attach_cookie(resp, token), status


@auth_bp.post("/login")
@api_error_handler
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    if not email or not password:
        return fail("Email and password are required.")

    user = User.query.filter_by(email=email).first()
    if not user or not user.verify_password(password):
        return fail("Invalid email or password.", 401)
    if not user.is_active:
        return fail("This account has been disabled. Contact the placement cell.", 403)

    user.last_login = datetime.utcnow()
    db.session.commit()
    token = issue_token(user)
    resp, status = ok({"message": f"Logged in as {user.role}.",
                       "user": user.to_dict(with_profile=True), **token})
    return _attach_cookie(resp, token), status


@auth_bp.get("/me")
@jwt_required()
@api_error_handler
def me():
    return ok({"user": g.current_user.to_dict(with_profile=True)})


@auth_bp.post("/refresh")
@jwt_required()
@api_error_handler
def refresh():
    token = issue_token(g.current_user)
    resp, status = ok({"message": "Token refreshed.", **token})
    return _attach_cookie(resp, token), status


@auth_bp.post("/logout")
def logout():
    resp, status = ok({"message": "Signed out."})
    resp.delete_cookie("access_token", path="/")
    return resp, status


@auth_bp.post("/change-password")
@jwt_required()
@api_error_handler
def change_password():
    data = request.get_json(silent=True) or {}
    current = data.get("current_password") or ""
    new = data.get("new_password") or ""
    if not g.current_user.verify_password(current):
        return fail("Current password is incorrect.", 403)
    if len(new) < 6:
        return fail("New password must be at least 6 characters.")
    g.current_user.set_password(new)
    db.session.commit()
    return ok({"message": "Password updated successfully."})


@auth_bp.get("/branches")
def branches():
    return ok({"branches": VALID_BRANCHES, "roles": ["student", "admin"]})

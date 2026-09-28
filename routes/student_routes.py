"""Student-facing API: resume upload, profile, recommendations, applications, feedback."""
from __future__ import annotations

import os
import uuid
from datetime import datetime

from flask import Blueprint, current_app, g, request
from sqlalchemy import or_

from extensions import db
from models import (Application, Feedback, Internship, ResumeUpload,
                    StudentProfile, TrustAuditLog)
from routes.helpers import api_error_handler, fail, ok, paginate
from security import current_student, jwt_required, require_self_or_admin
from services.domain_intel import lookup_domain
from services.nlp_engine import analyse_resume, extract_text
from services.recommender import (DOMAIN_PREFERENCE_BONUS, explain_scoring,
                                   invalidate_index, recommend)
from services.skills_taxonomy import DOMAINS, DOMAIN_SIGNALS
from services.trust_engine import evaluate_listing

student_bp = Blueprint("student", __name__, url_prefix="/api")


def _allowed(filename: str) -> bool:
    return "." in filename and \
        filename.rsplit(".", 1)[1].lower() in current_app.config["ALLOWED_EXTENSIONS"]


# --------------------------------------------------------------------- resume
@student_bp.post("/upload-resume")
@jwt_required("student", "admin")
@api_error_handler
def upload_resume():
    student = current_student()
    if student is None:
        student_id = request.form.get("student_id") or (request.get_json(silent=True) or {}).get("student_id")
        if not student_id:
            return fail("No student profile linked to this account. Pass student_id explicitly "
                        "when uploading as an admin.", 400)
        student = db.session.get(StudentProfile, int(student_id))
        if not student:
            return fail("Student profile not found.", 404)

    if "resume" not in request.files and "file" not in request.files:
        return fail("No file part named 'resume' found in the request.")
    file = request.files.get("resume") or request.files.get("file")
    if not file or not file.filename:
        return fail("Please choose a PDF or DOCX file to upload.")
    if not _allowed(file.filename):
        return fail("Only .pdf and .docx resumes are supported.")

    raw = file.read()
    if not raw:
        return fail("The uploaded file is empty.")
    if len(raw) > current_app.config["MAX_CONTENT_LENGTH"]:
        return fail("File is larger than 8 MB.")

    text = extract_text(file.filename, raw)
    analysis = analyse_resume(text)          # raises ValueError -> 400

    upload_dir = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_dir, exist_ok=True)
    safe_name = f"{student.id}_{uuid.uuid4().hex[:8]}_{file.filename.rsplit('/', 1)[-1]}"
    safe_name = safe_name.replace(" ", "_")
    stored_path = os.path.join(upload_dir, safe_name)
    with open(stored_path, "wb") as fh:
        fh.write(raw)

    student.resume_filename = file.filename
    student.resume_text = analysis["text"]
    student.resume_uploaded_at = datetime.utcnow()
    student.skills = analysis["skills"]
    student.skill_details = analysis["skill_details"]
    student.skill_vector = analysis["skill_vector"]
    student.ats_score = analysis["ats_score"]

    meta = analysis["meta"]
    parsed = dict(student.parsed_meta or {})
    parsed.update({k: v for k, v in meta.items() if v not in (None, [], "")})
    if meta.get("cgpa") and not student.cgpa:
        student.cgpa = meta["cgpa"]
    if meta.get("graduation_year") and not student.graduation_year:
        student.graduation_year = meta["graduation_year"]
    if meta.get("branch") and not student.branch:
        student.branch = meta["branch"]
    student.parsed_meta = parsed
    if not student.preferred_domain and analysis["top_domain"]:
        student.preferred_domain = analysis["top_domain"]

    upload = ResumeUpload(
        student_id=student.id, filename=file.filename,
        file_type=file.filename.rsplit(".", 1)[1].lower(), size_bytes=len(raw),
        skills_found=len(analysis["skills"]), ats_score=analysis["ats_score"],
        text_chars=len(analysis["text"]),
    )
    db.session.add(upload)
    db.session.commit()
    invalidate_index()

    return ok({
        "message": f"Resume parsed — {len(analysis['skills'])} skills extracted "
                   f"across {len(analysis['skill_categories'])} categories.",
        "upload": upload.to_dict(),
        "profile": student.to_dict(),
        "extraction": {
            "skills": analysis["skills"],
            "skill_details": analysis["skill_details"],
            "skill_categories": analysis["skill_categories"],
            "domains": analysis["domain_matches"],
            "top_domain": analysis["top_domain"],
            "domain_confidence": analysis["domain_confidence"],
            "keywords": analysis["keywords"],
            "meta": analysis["meta"],
            "ats_score": analysis["ats_score"],
            "insights": analysis["insights"],
            "sentences": analysis["sentences"],
        },
    }, 201)


# -------------------------------------------------------------------- profile
@student_bp.get("/student/profile/<int:student_id>")
@jwt_required("student", "admin")
@api_error_handler
def get_profile(student_id: int):
    denied = require_self_or_admin(student_id)
    if denied:
        return denied
    profile = db.session.get(StudentProfile, student_id)
    if not profile:
        return fail("Student profile not found.", 404)

    applications = Application.query.filter_by(student_id=student_id).count()
    feedback_count = Feedback.query.filter_by(student_id=student_id).count()
    return ok({
        "profile": profile.to_dict(),
        "skill_cloud": _skill_cloud(profile),
        "domain_matches": _domain_matches(profile),
        "stats": {
            "total_skills": len(profile.skills or []),
            "categories": len({d.get("category") for d in (profile.skill_details or [])}),
            "ats_score": profile.ats_score or 0,
            "completeness": profile.completeness,
            "applications": applications,
            "feedback_given": feedback_count,
        },
        "uploads": [u.to_dict() for u in
                    ResumeUpload.query.filter_by(student_id=student_id)
                    .order_by(ResumeUpload.created_at.desc()).limit(8)],
        "recommendation_config": explain_scoring(),
    })


@student_bp.put("/student/profile/<int:student_id>")
@jwt_required("student", "admin")
@api_error_handler
def update_profile(student_id: int):
    denied = require_self_or_admin(student_id)
    if denied:
        return denied
    profile = db.session.get(StudentProfile, student_id)
    if not profile:
        return fail("Student profile not found.", 404)

    data = request.get_json(silent=True) or {}
    editable = ["roll_number", "college", "branch", "graduation_year", "cgpa",
                "preferred_domain", "preferred_location", "work_mode_pref", "phone"]
    for field in editable:
        if field in data:
            value = data[field]
            if field in ("cgpa",):
                value = float(value) if value not in (None, "") else None
            if field in ("graduation_year",):
                value = int(value) if value not in (None, "") else None
            setattr(profile, field, value)
    if data.get("name") or data.get("phone"):
        if data.get("name"):
            profile.user.name = data["name"].strip()
        if data.get("phone"):
            profile.user.phone = data["phone"]
    db.session.commit()
    invalidate_index()
    return ok({"message": "Profile updated.", "profile": profile.to_dict()})


# ------------------------------------------------------------ recommendations
@student_bp.get("/recommendations/<int:student_id>")
@jwt_required("student", "admin")
@api_error_handler
def get_recommendations(student_id: int):
    denied = require_self_or_admin(student_id)
    if denied:
        return denied
    profile = db.session.get(StudentProfile, student_id)
    if not profile:
        return fail("Student profile not found.", 404)

    top_k = min(int(request.args.get("limit", 12) or 12), 50)
    include_flagged = request.args.get("include_flagged", "true").lower() != "false"
    min_trust = int(request.args.get("min_trust", 0) or 0)
    domain_filter = request.args.get("domain") or None
    work_mode = request.args.get("work_mode") or None
    search = (request.args.get("q") or "").strip().lower()

    listings = Internship.query.all()
    if search:
        listings = [l for l in listings
                    if search in l.title.lower() or search in (l.company or "").lower()]
    if not listings:
        return ok({"student_id": student_id, "profile": profile.to_dict(),
                   "recommendations": [], "empty_state": {
                       "title": "No listings available",
                       "message": "Ask the placement cell to publish internship listings."},
                   "config": explain_scoring()})

    if not profile.skills:
        fallback = sorted(
            Internship.query.all(),
            key=lambda l: (-(l.trust_score or 0), l.posted_date or l.created_at))[:top_k]
        return ok({
            "student_id": student_id,
            "profile": profile.to_dict(),
            "recommendations": [],
            "needs_resume": True,
            "fallback_listings": [l.to_dict() for l in fallback],
            "empty_state": {
                "title": "Upload your resume to unlock ranked matches",
                "message": "We couldn't find a skill vector for you yet. Upload a PDF/DOCX "
                           "resume and the NLP engine will build one in a few seconds.",
                "cta": {"label": "Upload resume", "href": "/student/profile"},
            },
            "config": explain_scoring(),
        })

    recs = recommend(profile, listings, top_k=top_k, include_flagged=include_flagged,
                     min_trust=min_trust, domain_filter=domain_filter, work_mode=work_mode)

    return ok({
        "student_id": student_id,
        "profile": profile.to_dict(),
        "count": len(recs),
        "recommendations": recs,
        "filters": {"domain": domain_filter, "work_mode": work_mode, "min_trust": min_trust,
                    "include_flagged": include_flagged, "q": search or None},
        "config": explain_scoring(),
        "empty_state": None if recs else {
            "title": "No matches for these filters",
            "message": "Try widening the domain filter or lowering the minimum trust score.",
        },
    })


# -------------------------------------------------------- browse & trust score
@student_bp.get("/internships")
@jwt_required("student", "admin")
@api_error_handler
def list_internships():
    q = Internship.query
    domain = request.args.get("domain")
    badge = request.args.get("badge")
    location = request.args.get("location")
    work_mode = request.args.get("work_mode")
    flagged = request.args.get("flagged")
    min_trust = request.args.get("min_trust")
    search = (request.args.get("q") or "").strip()

    if domain:
        q = q.filter(Internship.domain == domain)
    if badge:
        q = q.filter(Internship.badge == badge)
    if location:
        q = q.filter(Internship.location.ilike(f"%{location}%"))
    if work_mode and work_mode != "any":
        q = q.filter(Internship.work_mode == work_mode)
    if flagged is not None and flagged != "":
        q = q.filter(Internship.fraud_flag == (flagged.lower() == "true"))
    if min_trust:
        q = q.filter(Internship.trust_score >= int(min_trust))
    if search:
        q = q.filter(or_(Internship.title.ilike(f"%{search}%"),
                         Internship.company.ilike(f"%{search}%"),
                         Internship.description.ilike(f"%{search}%")))

    sort = request.args.get("sort", "recent")
    sorters = {
        "recent": Internship.posted_date.desc(),
        "trust": Internship.trust_score.desc(),
        "trust_asc": Internship.trust_score.asc(),
        "stipend": Internship.stipend.desc(),
        "stipend_asc": Internship.stipend.asc(),
    }
    q = q.order_by(sorters.get(sort, Internship.posted_date.desc()))

    page = paginate(q, default_per_page=12, max_per_page=48)
    return ok({
        "internships": [i.to_dict() for i in page["items"]],
        "meta": page["meta"],
        "domains": DOMAINS,
    })


@student_bp.get("/internships/<int:internship_id>")
@jwt_required("student", "admin")
@api_error_handler
def get_internship(internship_id: int):
    listing = db.session.get(Internship, internship_id)
    if not listing:
        return fail("Listing not found.", 404)
    history = [h.to_dict() for h in TrustAuditLog.query
               .filter_by(internship_id=listing.id)
               .order_by(TrustAuditLog.created_at.desc()).limit(10)]
    return ok({"internship": listing.to_dict(detailed=True),
               "trust": _trust_payload(listing),
               "history": history,
               "similar": [l.to_dict() for l in Internship.query
                           .filter(Internship.domain == listing.domain,
                                   Internship.id != listing.id)
                           .order_by(Internship.trust_score.desc()).limit(3)]})


@student_bp.get("/trustscore/<int:internship_id>")
@jwt_required("student", "admin")
@api_error_handler
def get_trust_score(internship_id: int):
    listing = db.session.get(Internship, internship_id)
    if not listing:
        return fail("Listing not found.", 404)
    refresh = request.args.get("refresh", "false").lower() == "true"
    if refresh:
        before = listing.trust_score
        evaluate_listing(listing)
        db.session.add(TrustAuditLog(
            internship_id=listing.id, actor=(g.current_user.email if g.current_user else "system"),
            action="recompute", old_score=before, new_score=listing.trust_score,
            new_badge=listing.badge, note="Manual recompute via API"))
        db.session.commit()
    return ok({"internship_id": listing.id,
               "title": listing.title,
               "company": listing.company,
               "trust": _trust_payload(listing),
               "history": [h.to_dict() for h in TrustAuditLog.query
                           .filter_by(internship_id=listing.id)
                           .order_by(TrustAuditLog.created_at.desc()).limit(10)]})


def _trust_payload(listing: Internship) -> dict:
    breakdown = listing.trust_breakdown or {}
    domain_info = lookup_domain(listing.company_domain or listing.contact_email)
    return {
        "trust_score": listing.trust_score,
        "badge": listing.badge,
        "fraud_flag": listing.fraud_flag,
        "hard_check_failed": listing.hard_check_failed,
        "rule_score": listing.rule_score,
        "ml_fraud_prob": listing.ml_fraud_prob,
        "breakdown": breakdown,
        "red_flags": listing.red_flags or [],
        "domain": domain_info,
        "override_by_admin": listing.override_by_admin,
        "override_note": listing.override_note,
        "checked_at": listing.trust_checked_at.isoformat() if listing.trust_checked_at else None,
        "badge_legend": {"Green": ">= 75 — safe to apply",
                         "Amber": "50-74 — apply with caution",
                         "Red": "< 50 or flagged — do not pay anything"},
    }


# ----------------------------------------------------------------- dashboard
@student_bp.get("/student/dashboard/<int:student_id>")
@jwt_required("student", "admin")
@api_error_handler
def student_dashboard(student_id: int):
    denied = require_self_or_admin(student_id)
    if denied:
        return denied
    profile = db.session.get(StudentProfile, student_id)
    if not profile:
        return fail("Student profile not found.", 404)

    apps = (Application.query.filter_by(student_id=student_id)
            .order_by(Application.applied_at.desc()).all())
    recs = []
    if profile.skills:
        recs = recommend(profile, Internship.query.all(), top_k=6)

    return ok({
        "profile": profile.to_dict(),
        "stats": {
            "applications": len(apps),
            "shortlisted": sum(1 for a in apps if a.status in ("shortlisted", "interview", "selected")),
            "selected": sum(1 for a in apps if a.status == "selected"),
            "avg_match": round(sum(a.match_score or 0 for a in apps) / len(apps) * 100, 1)
            if apps else 0,
            "skills": len(profile.skills or []),
            "ats_score": profile.ats_score or 0,
            "feedback_given": Feedback.query.filter_by(student_id=student_id).count(),
        },
        "recent_applications": [a.to_dict() for a in apps[:6]],
        "top_recommendations": recs,
        "skill_cloud": _skill_cloud(profile),
        "domain_matches": _domain_matches(profile),
        "status_breakdown": _status_breakdown(student_id),
        "trust_exposure": _trust_exposure(apps),
    })


# -------------------------------------------------------------- applications
@student_bp.post("/applications")
@jwt_required("student")
@api_error_handler
def create_application():
    data = request.get_json(silent=True) or {}
    student = current_student()
    student_id = data.get("student_id") or (student.id if student else None)
    internship_id = data.get("internship_id")
    if not student_id or not internship_id:
        return fail("student_id and internship_id are required.")

    denied = require_self_or_admin(int(student_id))
    if denied:
        return denied

    listing = db.session.get(Internship, int(internship_id))
    if not listing:
        return fail("Listing not found.", 404)

    existing = Application.query.filter_by(student_id=int(student_id),
                                           internship_id=listing.id).first()
    if existing:
        return ok({"message": "You have already applied to this listing.",
                   "application": existing.to_dict()}, 200)

    profile = db.session.get(StudentProfile, int(student_id))
    match = 0.0
    if profile and profile.skills:
        recs = recommend(profile, Internship.query.all(), top_k=500)
        match = next((r["match_pct"] / 100 for r in recs
                      if r["internship"]["id"] == listing.id), 0.0)

    status = (data.get("status") or "applied").lower()
    if status not in {"applied", "under_review", "shortlisted", "interview", "selected", "rejected"}:
        return fail("Invalid application status.")

    app_row = Application(student_id=int(student_id), internship_id=listing.id,
                          status=status, match_score=round(match, 4),
                          notes=(data.get("notes") or "").strip() or None)
    db.session.add(app_row)
    db.session.commit()
    return ok({"message": f"Application recorded for {listing.title} at {listing.company}.",
               "application": app_row.to_dict(),
               "trust_warning": listing.fraud_flag}, 201)


@student_bp.get("/student/applications/<int:student_id>")
@jwt_required("student", "admin")
@api_error_handler
def list_applications(student_id: int):
    denied = require_self_or_admin(student_id)
    if denied:
        return denied
    q = Application.query.filter_by(student_id=student_id)
    status = request.args.get("status")
    if status:
        q = q.filter(Application.status == status)
    q = q.order_by(Application.applied_at.desc())
    page = paginate(q, default_per_page=10)
    return ok({"applications": [a.to_dict() for a in page["items"]], "meta": page["meta"],
               "status_breakdown": _status_breakdown(student_id)})


@student_bp.patch("/applications/<int:application_id>")
@jwt_required("student", "admin")
@api_error_handler
def update_application(application_id: int):
    app_row = db.session.get(Application, application_id)
    if not app_row:
        return fail("Application not found.", 404)
    denied = require_self_or_admin(app_row.student_id)
    if denied:
        return denied

    data = request.get_json(silent=True) or {}
    if "status" in data:
        status = data["status"].lower()
        if status not in {"applied", "under_review", "shortlisted", "interview", "selected", "rejected"}:
            return fail("Invalid application status.")
        app_row.status = status
    if "notes" in data:
        app_row.notes = (data["notes"] or "").strip() or None
    db.session.commit()
    return ok({"message": "Application updated.", "application": app_row.to_dict()})


@student_bp.delete("/applications/<int:application_id>")
@jwt_required("student", "admin")
@api_error_handler
def delete_application(application_id: int):
    app_row = db.session.get(Application, application_id)
    if not app_row:
        return fail("Application not found.", 404)
    denied = require_self_or_admin(app_row.student_id)
    if denied:
        return denied
    db.session.delete(app_row)
    db.session.commit()
    return ok({"message": "Application withdrawn."})


# ------------------------------------------------------------------- feedback
@student_bp.post("/feedback")
@jwt_required("student")
@api_error_handler
def submit_feedback():
    data = request.get_json(silent=True) or {}
    student = current_student()
    student_id = data.get("student_id") or (student.id if student else None)
    if not student_id:
        return fail("student_id is required.")
    denied = require_self_or_admin(int(student_id))
    if denied:
        return denied

    internship_id = data.get("internship_id")
    rating = data.get("rating")
    verdict = (data.get("verdict") or "").strip().title()
    if not internship_id:
        return fail("internship_id is required.")
    if verdict not in {"Verified", "Suspicious"}:
        return fail("verdict must be 'Verified' or 'Suspicious'.")
    try:
        rating = int(rating)
    except (TypeError, ValueError):
        return fail("rating must be an integer between 1 and 5.")
    if not 1 <= rating <= 5:
        return fail("rating must be between 1 and 5.")

    listing = db.session.get(Internship, int(internship_id))
    if not listing:
        return fail("Listing not found.", 404)

    row = Feedback(student_id=int(student_id), internship_id=listing.id,
                   rating=rating, verdict=verdict,
                   comment=(data.get("comment") or "").strip()[:500] or None)
    db.session.add(row)
    db.session.commit()

    agg = db.session.query(db.func.avg(Feedback.rating), db.func.count(Feedback.id)) \
        .filter(Feedback.internship_id == listing.id).first()
    return ok({"message": "Thanks for the feedback — it helps other students stay safe.",
               "feedback": row.to_dict(),
               "internship_rating": {"average": round(agg[0] or 0, 2), "count": agg[1]}}, 201)


@student_bp.get("/student/feedback/<int:student_id>")
@jwt_required("student", "admin")
@api_error_handler
def list_feedback(student_id: int):
    denied = require_self_or_admin(student_id)
    if denied:
        return denied
    rows = (Feedback.query.filter_by(student_id=student_id)
            .order_by(Feedback.created_at.desc()).limit(50).all())
    return ok({"feedback": [r.to_dict() for r in rows], "count": len(rows)})


# ------------------------------------------------------------------- helpers
def _skill_cloud(profile: StudentProfile) -> list[dict]:
    details = profile.skill_details or []
    if details:
        mx = max((d.get("weight") or 0) for d in details) or 1
        return [{
            "skill": d["skill"],
            "category": d.get("category", "Other"),
            "weight": round((d.get("weight") or 0) / mx, 3),
            "mentions": d.get("mentions", 1),
            "size": 14 + int(22 * ((d.get("weight") or 0) / mx)),
        } for d in sorted(details, key=lambda x: -(x.get("weight") or 0))]
    vector = profile.skill_vector or {}
    mx = max(vector.values()) if vector else 1
    return [{"skill": s, "category": "Other", "weight": round(w / mx, 3), "mentions": 1,
             "size": 14 + int(22 * (w / mx))}
            for s, w in sorted(vector.items(), key=lambda kv: -kv[1])]


def _domain_matches(profile: StudentProfile) -> list[dict]:
    vector = profile.skill_vector or {}
    out = []
    for domain, signals in DOMAIN_SIGNALS.items():
        score = sum(vector.get(s, 0) for s in signals)
        if score:
            out.append({
                "domain": domain, "score": round(score, 4),
                "matched_skills": sorted([s for s in signals if s in vector],
                                         key=lambda s: -vector[s])[:6],
                "is_preferred": domain == profile.preferred_domain,
            })
    out.sort(key=lambda d: -d["score"])
    top = out[0]["score"] if out else 1
    for row in out:
        row["confidence"] = round(row["score"] / top * 100)
    return out[:8]


def _status_breakdown(student_id: int) -> list[dict]:
    rows = (db.session.query(Application.status, db.func.count(Application.id))
            .filter(Application.student_id == student_id)
            .group_by(Application.status).all())
    return [{"status": s, "count": c} for s, c in rows]


def _trust_exposure(apps: list[Application]) -> dict:
    buckets = {"Green": 0, "Amber": 0, "Red": 0}
    for app_row in apps:
        if app_row.internship:
            buckets[app_row.internship.badge or "Amber"] += 1
    return buckets

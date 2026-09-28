"""Admin API: listing CRUD, CSV bulk upload, fraud queue, trust override, analytics."""
from __future__ import annotations

import csv
import io
from datetime import date, datetime, timedelta

from flask import Blueprint, current_app, g, request
from sqlalchemy import func, or_

from extensions import db
from models import (Application, Feedback, Internship, StudentProfile,
                    TrustAuditLog, User)
from routes.helpers import api_error_handler, fail, ok, paginate
from security import jwt_required
from services.domain_intel import DOMAIN_BLACKLIST, DomainIntel, lookup_domain
from services.ml_fraud import model_metrics, train_model
from services.recommender import invalidate_index
from services.skills_taxonomy import DOMAINS
from services.trust_engine import badge_for, evaluate_listing

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")

CSV_COLUMNS = ["title", "company", "contact_email", "location", "work_mode", "domain",
               "description", "skills_required", "stipend", "duration_months", "openings",
               "apply_url", "deadline", "posted_date", "source"]


def _parse_date(value):
    if not value:
        return None
    if isinstance(value, date):
        return value
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%b %d, %Y"):
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            continue
    return None


def _clean_payload(data: dict, partial: bool = False) -> tuple[dict, list[str]]:
    errors: list[str] = []
    payload: dict = {}

    text_fields = ["title", "company", "contact_email", "location", "work_mode", "domain",
                   "description", "apply_url", "source"]
    for field in text_fields:
        if field in data:
            value = data[field]
            payload[field] = str(value).strip() if value is not None else None

    if not partial:
        for required in ("title", "company", "description", "contact_email"):
            if not payload.get(required):
                errors.append(f"'{required}' is required.")

    skills = data.get("skills_required")
    if skills is not None:
        if isinstance(skills, str):
            skills = [s.strip().lower() for s in skills.replace(";", ",").split(",") if s.strip()]
        payload["skills_required"] = [str(s).strip().lower() for s in skills if str(s).strip()]

    for num_field, caster in (("stipend", int), ("duration_months", int), ("openings", int)):
        if num_field in data and data[num_field] not in (None, ""):
            try:
                payload[num_field] = max(caster(float(data[num_field])), 0)
            except (TypeError, ValueError):
                errors.append(f"'{num_field}' must be a number.")

    for date_field in ("posted_date", "deadline"):
        if date_field in data:
            parsed = _parse_date(data[date_field])
            if data[date_field] and not parsed:
                errors.append(f"'{date_field}' must be a valid date (YYYY-MM-DD).")
            payload[date_field] = parsed

    if payload.get("work_mode") and payload["work_mode"] not in {"remote", "onsite", "hybrid"}:
        errors.append("'work_mode' must be remote, onsite or hybrid.")
    if payload.get("domain") and payload["domain"] not in DOMAINS:
        # allow unknown domains but flag them (we still store the value)
        pass
    if payload.get("contact_email") and "@" not in payload["contact_email"]:
        errors.append("'contact_email' must be a valid email address.")

    return payload, errors


# ------------------------------------------------------------------ list CRUD
@admin_bp.get("/internships")
@jwt_required("admin")
@api_error_handler
def admin_list_internships():
    q = Internship.query
    search = (request.args.get("q") or "").strip()
    badge = request.args.get("badge")
    flagged = request.args.get("flagged")
    domain = request.args.get("domain")
    if search:
        q = q.filter(or_(Internship.title.ilike(f"%{search}%"),
                         Internship.company.ilike(f"%{search}%"),
                         Internship.contact_email.ilike(f"%{search}%")))
    if badge:
        q = q.filter(Internship.badge == badge)
    if flagged in ("true", "false"):
        q = q.filter(Internship.fraud_flag == (flagged == "true"))
    if domain:
        q = q.filter(Internship.domain == domain)

    sort = request.args.get("sort", "recent")
    sorters = {"recent": Internship.posted_date.desc(),
               "trust": Internship.trust_score.desc(),
               "trust_asc": Internship.trust_score.asc(),
               "company": Internship.company.asc(),
               "applications": Internship.id.desc()}
    q = q.order_by(sorters.get(sort, Internship.posted_date.desc()))
    page = paginate(q, default_per_page=10, max_per_page=100)
    return ok({"internships": [i.to_dict() for i in page["items"]],
               "meta": page["meta"], "domains": DOMAINS})


@admin_bp.post("/add-internship")
@jwt_required("admin")
@api_error_handler
def add_internship():
    data = request.get_json(silent=True) or {}
    payload, errors = _clean_payload(data)
    if errors:
        return fail("Please fix the highlighted fields.", 400, field_errors=errors)

    listing = Internship(**payload)
    if not listing.posted_date:
        listing.posted_date = date.today()
    if not listing.deadline:
        listing.deadline = listing.posted_date + timedelta(days=30)
    listing.source = payload.get("source") or "admin"
    db.session.add(listing)
    db.session.flush()

    result = evaluate_listing(listing)
    db.session.add(TrustAuditLog(
        internship_id=listing.id, actor=g.current_user.email, action="create",
        new_score=result["trust_score"], new_badge=result["badge"],
        note="Listing created by admin"))
    db.session.commit()
    invalidate_index()

    return ok({
        "message": f"Listing created — trust score {result['trust_score']}/100 "
                   f"({result['badge']} badge).",
        "internship": listing.to_dict(detailed=True),
        "trust": {"trust_score": result["trust_score"], "badge": result["badge"],
                  "fraud_flag": result["fraud_flag"], "rule_score": result["rule_score"],
                  "ml_fraud_prob": result["ml_fraud_prob"],
                  "red_flags": result["red_flags"]},
    }, 201)


@admin_bp.put("/internships/<int:internship_id>")
@jwt_required("admin")
@api_error_handler
def update_internship(internship_id: int):
    listing = db.session.get(Internship, internship_id)
    if not listing:
        return fail("Listing not found.", 404)

    data = request.get_json(silent=True) or {}
    payload, errors = _clean_payload(data, partial=True)
    if errors:
        return fail("Please fix the highlighted fields.", 400, field_errors=errors)

    for key, value in payload.items():
        setattr(listing, key, value)
    listing.updated_at = datetime.utcnow()

    before = listing.trust_score
    result = evaluate_listing(listing)
    db.session.add(TrustAuditLog(
        internship_id=listing.id, actor=g.current_user.email, action="recompute",
        old_score=before, new_score=result["trust_score"], old_badge=None,
        new_badge=result["badge"], note="Re-scored after admin edit"))
    db.session.commit()
    invalidate_index()
    return ok({"message": "Listing updated and re-scored.",
               "internship": listing.to_dict(detailed=True),
               "trust": {"trust_score": result["trust_score"], "badge": result["badge"],
                         "fraud_flag": result["fraud_flag"]}})


@admin_bp.delete("/internships/<int:internship_id>")
@jwt_required("admin")
@api_error_handler
def delete_internship(internship_id: int):
    listing = db.session.get(Internship, internship_id)
    if not listing:
        return fail("Listing not found.", 404)
    title = listing.title
    db.session.delete(listing)
    db.session.commit()
    invalidate_index()
    return ok({"message": f"Deleted listing '{title}'."})


@admin_bp.post("/internships/<int:internship_id>/recompute")
@jwt_required("admin")
@api_error_handler
def recompute_trust(internship_id: int):
    listing = db.session.get(Internship, internship_id)
    if not listing:
        return fail("Listing not found.", 404)
    before, before_badge = listing.trust_score, listing.badge
    result = evaluate_listing(listing)
    db.session.add(TrustAuditLog(
        internship_id=listing.id, actor=g.current_user.email, action="recompute",
        old_score=before, new_score=result["trust_score"], old_badge=before_badge,
        new_badge=result["badge"], note="Manual recompute"))
    db.session.commit()
    return ok({"message": "Trust score recomputed.", "trust_score": result["trust_score"],
               "badge": result["badge"], "fraud_flag": result["fraud_flag"],
               "breakdown": result["trust_breakdown"]})


# ------------------------------------------------------------- CSV bulk upload
@admin_bp.post("/bulk-upload")
@jwt_required("admin")
@api_error_handler
def bulk_upload():
    if "file" not in request.files:
        return fail("Attach a CSV file under the 'file' field.")
    file = request.files["file"]
    if not file.filename:
        return fail("No file selected.")
    if not file.filename.lower().endswith(".csv"):
        return fail("Bulk upload expects a .csv file. Download the template from this page.")

    raw = file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1", errors="ignore")

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return fail("The CSV appears to be empty.")
    missing_cols = [c for c in ("title", "company", "contact_email", "description")
                    if c not in [h.strip() for h in reader.fieldnames]]
    if missing_cols:
        return fail(f"CSV is missing required column(s): {', '.join(missing_cols)}. "
                    "Download the template for the expected header row.")

    created, skipped, errors = 0, 0, []
    new_listings: list[Internship] = []

    for idx, row in enumerate(reader, start=2):
        row = {(k or "").strip(): (v or "").strip() for k, v in row.items()}
        if not any(row.values()):
            continue
        payload, row_errors = _clean_payload(row)
        if row_errors:
            skipped += 1
            errors.append({"row": idx, "company": row.get("company"), "errors": row_errors})
            continue

        # de-duplicate on company + title
        exists = Internship.query.filter(
            func.lower(Internship.title) == payload["title"].lower(),
            func.lower(Internship.company) == payload["company"].lower()).first()
        if exists:
            skipped += 1
            errors.append({"row": idx, "company": payload["company"],
                           "errors": ["Duplicate of an existing listing — skipped."]})
            continue

        listing = Internship(**payload)
        listing.posted_date = listing.posted_date or date.today()
        listing.deadline = listing.deadline or listing.posted_date + timedelta(days=30)
        listing.source = "csv"
        db.session.add(listing)
        new_listings.append(listing)
        created += 1

    db.session.flush()
    results = []
    for listing in new_listings:
        result = evaluate_listing(listing)
        db.session.add(TrustAuditLog(
            internship_id=listing.id, actor=g.current_user.email, action="csv_upload",
            new_score=result["trust_score"], new_badge=result["badge"],
            note=f"Bulk CSV import ({file.filename})"))
        results.append({"id": listing.id, "title": listing.title, "company": listing.company,
                        "trust_score": result["trust_score"], "badge": result["badge"],
                        "fraud_flag": result["fraud_flag"]})
    db.session.commit()
    invalidate_index()

    flagged = sum(1 for r in results if r["fraud_flag"])
    return ok({
        "message": f"{created} listing(s) imported, {skipped} skipped, "
                   f"{flagged} flagged for review.",
        "created": created, "skipped": skipped, "flagged": flagged,
        "results": results[:100], "errors": errors[:50],
        "columns_expected": CSV_COLUMNS,
    }, 201 if created else 200)


@admin_bp.get("/bulk-upload/template")
@jwt_required("admin")
def csv_template():
    from flask import Response

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(CSV_COLUMNS)
    writer.writerow([
        "Backend Engineer Intern", "Acme Analytics", "careers@acmeanalytics.in",
        "Bengaluru, KA", "hybrid", "Backend Engineering",
        "Work with the platform team on Python/Flask microservices, write tests and "
        "ship features. Mentorship and certificate provided.",
        "python, flask, mysql, docker", "25000", "3", "2",
        "https://acmeanalytics.in/careers/backend-intern", "2026-11-30", "2026-09-20", "admin",
    ])
    return Response(buf.getvalue(), mimetype="text/csv", headers={
        "Content-Disposition": "attachment; filename=internship_bulk_template.csv"})


# ------------------------------------------------------------- fraud review
@admin_bp.get("/flagged")
@jwt_required("admin")
@api_error_handler
def flagged_queue():
    q = Internship.query.filter(Internship.fraud_flag.is_(True))
    severity = request.args.get("severity")
    if severity == "critical":
        q = q.filter(Internship.trust_score < 30)
    elif severity == "high":
        q = q.filter(Internship.trust_score >= 30, Internship.trust_score < 45)
    search = (request.args.get("q") or "").strip()
    if search:
        q = q.filter(or_(Internship.company.ilike(f"%{search}%"),
                         Internship.title.ilike(f"%{search}%")))
    q = q.order_by(Internship.trust_score.asc())
    page = paginate(q, default_per_page=10, max_per_page=100)

    items = []
    for listing in page["items"]:
        data = listing.to_dict()
        data["top_flags"] = (listing.red_flags or [])[:3]
        items.append(data)

    total_flagged = Internship.query.filter(Internship.fraud_flag.is_(True)).count()
    recent_cut = datetime.utcnow() - timedelta(days=7)
    new_flags = Internship.query.filter(Internship.fraud_flag.is_(True),
                                        Internship.trust_checked_at >= recent_cut).count()
    return ok({
        "queue": items,
        "meta": page["meta"],
        "summary": {
            "total_flagged": total_flagged,
            "new_this_week": new_flags,
            "critical": Internship.query.filter(Internship.trust_score < 30).count(),
            "avg_flagged_score": round(
                db.session.query(func.avg(Internship.trust_score))
                .filter(Internship.fraud_flag.is_(True)).scalar() or 0, 1),
        },
    })


@admin_bp.post("/flagged/<int:internship_id>/resolve")
@jwt_required("admin")
@api_error_handler
def resolve_flag(internship_id: int):
    """Clear a flag (mark as reviewed-safe) but keep the trust audit trail."""
    listing = db.session.get(Internship, internship_id)
    if not listing:
        return fail("Listing not found.", 404)
    data = request.get_json(silent=True) or {}
    note = (data.get("note") or "Reviewed by placement cell — cleared as safe.").strip()

    before, before_badge = listing.trust_score, listing.badge
    listing.fraud_flag = False
    listing.badge = badge_for(listing.trust_score or 0, False)
    listing.override_by_admin = True
    listing.override_note = note
    db.session.add(TrustAuditLog(
        internship_id=listing.id, actor=g.current_user.email, action="override",
        old_score=before, new_score=listing.trust_score, old_badge=before_badge,
        new_badge=listing.badge, note=note))
    db.session.commit()
    invalidate_index()
    return ok({"message": "Flag cleared. Badge updated to "
                          f"{listing.badge}.",
               "internship": listing.to_dict()})


# ------------------------------------------------------------ trust override
@admin_bp.post("/trustscore-override")
@jwt_required("admin")
@api_error_handler
def trust_override():
    data = request.get_json(silent=True) or {}
    internship_id = data.get("internship_id")
    new_score = data.get("trust_score")
    note = (data.get("note") or "").strip()

    if not internship_id:
        return fail("internship_id is required.")
    if new_score is None:
        return fail("trust_score is required.")
    try:
        new_score = int(new_score)
    except (TypeError, ValueError):
        return fail("trust_score must be an integer 0-100.")
    if not 0 <= new_score <= 100:
        return fail("trust_score must be between 0 and 100.")
    if len(note) < 5:
        return fail("A justification note (min 5 chars) is required for an override — "
                    "overrides are audited.")

    listing = db.session.get(Internship, internship_id)
    if not listing:
        return fail("Listing not found.", 404)

    before, before_badge = listing.trust_score, listing.badge
    m = float(data.get("mark_fraud", -1))
    flagged = listing.fraud_flag if m == -1 else bool(m)

    listing.trust_score = new_score
    listing.fraud_flag = flagged
    listing.badge = badge_for(new_score, flagged)
    listing.override_by_admin = True
    listing.override_note = note
    listing.trust_checked_at = datetime.utcnow()
    breakdown = dict(listing.trust_breakdown or {})
    breakdown["override"] = {"by": g.current_user.email, "note": note,
                             "from": before, "to": new_score,
                             "at": datetime.utcnow().isoformat()}
    if flagged and not breakdown.get("red_flags"):
        breakdown["red_flags"] = {"score": breakdown.get("red_flags", {}).get("score", 50),
                                  "weight": 35, "label": "Red-flag phrase analysis",
                                  "hits": listing.red_flags or []}
    listing.trust_breakdown = breakdown

    db.session.add(TrustAuditLog(
        internship_id=listing.id, actor=g.current_user.email, action="override",
        old_score=before, new_score=new_score, old_badge=before_badge,
        new_badge=listing.badge, note=f"Manual override: {note}"))
    db.session.commit()
    invalidate_index()
    return ok({"message": f"Trust score overridden {before} → {new_score} "
                          f"(badge {listing.badge}).",
               "internship": listing.to_dict(detailed=True)})


@admin_bp.post("/trustscore/recompute-all")
@jwt_required("admin")
@api_error_handler
def recompute_all():
    listings = Internship.query.all()
    changed = []
    for listing in listings:
        before = listing.trust_score
        evaluate_listing(listing)
        if listing.trust_score != before:
            changed.append({"id": listing.id, "from": before, "to": listing.trust_score})
    db.session.add(TrustAuditLog(
        actor=g.current_user.email, action="recompute", note=f"Bulk recompute of "
        f"{len(listings)} listings ({len(changed)} changed)"))
    db.session.commit()
    invalidate_index()
    return ok({"message": f"Recomputed {len(listings)} listings — {len(changed)} scores changed.",
               "total": len(listings), "changed": len(changed), "sample": changed[:25]})


# ---------------------------------------------------------------- analytics
@admin_bp.get("/analytics")
@jwt_required("admin")
@api_error_handler
def analytics():
    total = Internship.query.count()
    flagged = Internship.query.filter(Internship.fraud_flag.is_(True)).count()
    buckets = dict(db.session.query(Internship.badge, func.count(Internship.id))
                   .group_by(Internship.badge).all())
    avg_trust = db.session.query(func.avg(Internship.trust_score)).scalar() or 0

    domain_rows = (db.session.query(
        Internship.domain, func.count(Internship.id),
        func.avg(Internship.trust_score),
        func.sum(db.case((Internship.fraud_flag.is_(True), 1), else_=0)))
        .group_by(Internship.domain)
        .order_by(func.count(Internship.id).desc()).all())

    score_bands = {"0-24": 0, "25-44": 0, "45-59": 0, "60-74": 0, "75-89": 0, "90-100": 0}
    for (score,) in db.session.query(Internship.trust_score).all():
        s = score or 0
        if s < 25:
            score_bands["0-24"] += 1
        elif s < 45:
            score_bands["25-44"] += 1
        elif s < 60:
            score_bands["45-59"] += 1
        elif s < 75:
            score_bands["60-74"] += 1
        elif s < 90:
            score_bands["75-89"] += 1
        else:
            score_bands["90-100"] += 1

    flag_counter: dict[str, int] = {}
    for listing in Internship.query.filter(Internship.fraud_flag.is_(True)).all():
        for hit in (listing.red_flags or []):
            flag_counter[hit["label"]] = flag_counter.get(hit["label"], 0) + 1
    top_flags = sorted(flag_counter.items(), key=lambda kv: -kv[1])[:8]

    posted_rows = []
    today = date.today()
    for week in range(7, -1, -1):
        start = today - timedelta(days=(week + 1) * 7)
        end = today - timedelta(days=week * 7)
        count = Internship.query.filter(Internship.posted_date > start,
                                        Internship.posted_date <= end).count()
        flagged_week = Internship.query.filter(Internship.posted_date > start,
                                              Internship.posted_date <= end,
                                              Internship.fraud_flag.is_(True)).count()
        posted_rows.append({"label": end.strftime("%d %b"), "posted": count,
                            "flagged": flagged_week})

    status_rows = dict(db.session.query(Application.status, func.count(Application.id))
                       .group_by(Application.status).all())

    feedback_rows = (db.session.query(Feedback.verdict, func.count(Feedback.id),
                                      func.avg(Feedback.rating))
                     .group_by(Feedback.verdict).all())

    top_companies = (db.session.query(Internship.company, func.count(Internship.id))
                     .group_by(Internship.company)
                     .order_by(func.count(Internship.id).desc()).limit(8).all())

    return ok({
        "kpis": {
            "total_listings": total,
            "flagged_listings": flagged,
            "flag_rate": round(flagged / total * 100, 1) if total else 0,
            "avg_trust_score": round(float(avg_trust), 1),
            "students": StudentProfile.query.count(),
            "applications": Application.query.count(),
            "feedback": Feedback.query.count(),
            "avg_student_ats": round(float(db.session.query(func.avg(StudentProfile.ats_score))
                                           .scalar() or 0), 1),
        },
        "badge_distribution": {b: buckets.get(b, 0) for b in ("Green", "Amber", "Red")},
        "score_bands": score_bands,
        "domain_stats": [{"domain": d or "Unspecified", "listings": c,
                          "avg_trust": round(float(a or 0), 1), "flagged": int(f or 0)}
                         for d, c, a, f in domain_rows],
        "top_flags": [{"label": label, "count": count} for label, count in top_flags],
        "posting_trend": posted_rows,
        "application_status": [{"status": s, "count": c} for s, c in status_rows.items()],
        "feedback_split": [{"verdict": v, "count": c, "avg_rating": round(float(a or 0), 2)}
                           for v, c, a in feedback_rows],
        "top_companies": [{"company": c, "listings": n} for c, n in top_companies],
        "ml_model": model_metrics(),
        "trust_thresholds": {"green": 75, "amber": 50, "flag": 45},
    })


@admin_bp.post("/ml/retrain")
@jwt_required("admin")
@api_error_handler
def retrain_model():
    metrics = train_model(save=True, verbose=False)
    changed = 0
    for listing in Internship.query.all():
        before = listing.trust_score
        evaluate_listing(listing)
        changed += 1 if listing.trust_score != before else 0
    db.session.commit()
    invalidate_index()
    return ok({"message": f"Model retrained ({metrics['train_accuracy'] * 100:.1f}% train accuracy) "
                          f"and {changed} listing scores updated.",
               "metrics": metrics, "rescored": changed})


# ------------------------------------------------------------------- people
@admin_bp.get("/students")
@jwt_required("admin")
@api_error_handler
def list_students():
    q = StudentProfile.query.join(User)
    search = (request.args.get("q") or "").strip()
    if search:
        q = q.filter(or_(User.name.ilike(f"%{search}%"), User.email.ilike(f"%{search}%"),
                         StudentProfile.college.ilike(f"%{search}%")))
    branch = request.args.get("branch")
    if branch:
        q = q.filter(StudentProfile.branch == branch)
    q = q.order_by(StudentProfile.ats_score.desc())
    page = paginate(q, default_per_page=10, max_per_page=100)

    items = []
    for profile in page["items"]:
        data = profile.to_dict()
        data["applications"] = Application.query.filter_by(student_id=profile.id).count()
        data["shortlisted"] = Application.query.filter(
            Application.student_id == profile.id,
            Application.status.in_(["shortlisted", "interview", "selected"])).count()
        items.append(data)

    return ok({"students": items, "meta": page["meta"]})


@admin_bp.get("/applications")
@jwt_required("admin")
@api_error_handler
def list_all_applications():
    q = Application.query
    status = request.args.get("status")
    if status:
        q = q.filter(Application.status == status)
    flagged_only = request.args.get("flagged")
    if flagged_only == "true":
        q = q.join(Internship).filter(Internship.fraud_flag.is_(True))
    q = q.order_by(Application.applied_at.desc())
    page = paginate(q, default_per_page=15, max_per_page=100)
    return ok({"applications": [a.to_dict() for a in page["items"]], "meta": page["meta"]})


@admin_bp.patch("/applications/<int:application_id>")
@jwt_required("admin")
@api_error_handler
def admin_update_application(application_id: int):
    row = db.session.get(Application, application_id)
    if not row:
        return fail("Application not found.", 404)
    data = request.get_json(silent=True) or {}
    if "status" in data:
        status = (data["status"] or "").lower()
        if status not in {"applied", "under_review", "shortlisted", "interview", "selected", "rejected"}:
            return fail("Invalid application status.")
        row.status = status
    if "notes" in data:
        row.notes = (data["notes"] or "").strip() or None
    db.session.commit()
    return ok({"message": "Application updated.", "application": row.to_dict()})


@admin_bp.delete("/applications/<int:application_id>")
@jwt_required("admin")
@api_error_handler
def admin_delete_application(application_id: int):
    row = db.session.get(Application, application_id)
    if not row:
        return fail("Application not found.", 404)
    db.session.delete(row)
    db.session.commit()
    return ok({"message": "Application deleted."})


@admin_bp.get("/feedback")
@jwt_required("admin")
@api_error_handler
def list_all_feedback():
    q = Feedback.query
    verdict = request.args.get("verdict")
    if verdict:
        q = q.filter(Feedback.verdict == verdict)
    q = q.order_by(Feedback.created_at.desc())
    page = paginate(q, default_per_page=15, max_per_page=100)
    rows = []
    for fb in page["items"]:
        data = fb.to_dict()
        data["trust_score"] = fb.internship.trust_score if fb.internship else None
        data["student_name"] = fb.student.user.name if fb.student else None
        rows.append(data)
    agg = db.session.query(func.avg(Feedback.rating), func.count(Feedback.id)).first()
    return ok({"feedback": rows, "meta": page["meta"],
               "summary": {"average_rating": round(float(agg[0] or 0), 2), "count": agg[1]}})


@admin_bp.get("/audit-log")
@jwt_required("admin")
@api_error_handler
def audit_log():
    q = TrustAuditLog.query.order_by(TrustAuditLog.created_at.desc())
    action = request.args.get("action")
    if action:
        q = q.filter(TrustAuditLog.action == action)
    page = paginate(q, default_per_page=20, max_per_page=100)
    return ok({"logs": [row.to_dict() for row in page["items"]], "meta": page["meta"]})


@admin_bp.get("/domains")
@jwt_required("admin")
@api_error_handler
def list_domains():
    rows = DomainIntel.query.order_by(DomainIntel.is_blacklisted.desc(),
                                      DomainIntel.age_days.asc()).limit(400).all()
    return ok({"domains": [r.to_dict() for r in rows],
               "blacklist": sorted(DOMAIN_BLACKLIST)})


@admin_bp.get("/export/flagged.csv")
@jwt_required("admin")
def export_flagged():
    from flask import Response

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "title", "company", "contact_email", "domain", "trust_score",
                     "badge", "ml_fraud_prob", "rule_score", "red_flags", "posted_date"])
    for listing in Internship.query.filter(Internship.fraud_flag.is_(True)) \
            .order_by(Internship.trust_score.asc()).all():
        writer.writerow([
            listing.id, listing.title, listing.company, listing.contact_email,
            listing.company_domain, listing.trust_score, listing.badge,
            listing.ml_fraud_prob, listing.rule_score,
            " | ".join(h["label"] for h in (listing.red_flags or [])),
            listing.posted_date,
        ])
    return Response(buf.getvalue(), mimetype="text/csv", headers={
        "Content-Disposition": "attachment; filename=flagged_listings.csv"})

"""Export the seeded dataset as MySQL INSERT statements (sql/seed_data.sql)."""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from models import Application, Feedback, Internship, StudentProfile, User


def _q(value) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, datetime):
        return "'" + value.strftime("%Y-%m-%d %H:%M:%S") + "'"
    if isinstance(value, date):
        return "'" + value.isoformat() + "'"
    if isinstance(value, (dict, list)):
        import json

        text = json.dumps(value, ensure_ascii=False).replace("\\", "\\\\").replace("'", "''")
        return f"'{text}'"
    return "'" + str(value).replace("\\", "\\\\").replace("'", "''") + "'"


def _inserts(table: str, rows: list[dict], batch: int = 50) -> list[str]:
    if not rows:
        return []
    cols = list(rows[0].keys())
    col_sql = ", ".join(f"`{c}`" for c in cols)
    out = [f"-- {len(rows)} row(s) -> {table}"]
    for i in range(0, len(rows), batch):
        chunk = rows[i:i + batch]
        values = ",\n  ".join("(" + ", ".join(_q(r[c]) for c in cols) + ")" for r in chunk)
        out.append(f"INSERT INTO `{table}` ({col_sql}) VALUES\n  {values};")
    return out


def export_seed_sql(out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    users = [{
        "id": u.id, "name": u.name, "email": u.email, "password_hash": u.password_hash,
        "role": u.role, "phone": u.phone, "is_active": True,
        "created_at": u.created_at, "last_login": u.last_login,
    } for u in User.query.order_by(User.id).all()]

    profiles = [{
        "id": p.id, "user_id": p.user_id, "roll_number": p.roll_number, "college": p.college,
        "branch": p.branch, "graduation_year": p.graduation_year, "cgpa": p.cgpa,
        "preferred_domain": p.preferred_domain, "preferred_location": p.preferred_location,
        "work_mode_pref": p.work_mode_pref, "phone": p.phone,
        "resume_filename": p.resume_filename, "resume_uploaded_at": p.resume_uploaded_at,
        "skills": p.skills, "skill_vector": p.skill_vector, "parsed_meta": p.parsed_meta,
        "ats_score": p.ats_score,
    } for p in StudentProfile.query.order_by(StudentProfile.id).all()]

    listings = [{
        "id": l.id, "title": l.title, "company": l.company, "company_domain": l.company_domain,
        "contact_email": l.contact_email, "location": l.location, "work_mode": l.work_mode,
        "domain": l.domain, "description": l.description, "skills_required": l.skills_required,
        "stipend": l.stipend, "duration_months": l.duration_months, "openings": l.openings,
        "apply_url": l.apply_url, "posted_date": l.posted_date, "deadline": l.deadline,
        "source": l.source, "trust_score": l.trust_score, "rule_score": l.rule_score,
        "ml_fraud_prob": l.ml_fraud_prob, "fraud_flag": l.fraud_flag, "badge": l.badge,
        "hard_check_failed": l.hard_check_failed, "trust_breakdown": l.trust_breakdown,
        "red_flags": l.red_flags, "override_by_admin": l.override_by_admin,
        "override_note": l.override_note, "trust_checked_at": l.trust_checked_at,
    } for l in Internship.query.order_by(Internship.id).all()]

    applications = [{
        "id": a.id, "student_id": a.student_id, "internship_id": a.internship_id,
        "status": a.status, "match_score": a.match_score, "notes": a.notes,
        "applied_at": a.applied_at,
    } for a in Application.query.order_by(Application.id).all()]

    feedbacks = [{
        "id": f.id, "student_id": f.student_id, "internship_id": f.internship_id,
        "rating": f.rating, "verdict": f.verdict, "comment": f.comment,
        "created_at": f.created_at,
    } for f in Feedback.query.order_by(Feedback.id).all()]

    lines = [
        "-- =====================================================================",
        "-- InternMatch AI — seeded demo dataset (generated export)",
        "-- Import AFTER schema_mysql.sql:  mysql -u root -p internmatch < seed_data.sql",
        "-- Passwords are werkzeug hashes of 'Student@123' / 'Admin@123'.",
        "-- =====================================================================",
        "SET NAMES utf8mb4;",
        "SET FOREIGN_KEY_CHECKS = 0;",
        "",
    ]
    for table, rows in (("users", users), ("student_profiles", profiles),
                        ("internships", listings), ("applications", applications),
                        ("feedback", feedbacks)):
        lines += _inserts(table, rows) + [""]
    lines += ["SET FOREIGN_KEY_CHECKS = 1;", ""]

    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path

"""SQLAlchemy models — fully MySQL-compatible (utf8mb4, JSON columns, InnoDB)."""
from datetime import datetime, date

from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db


def utcnow() -> datetime:
    return datetime.utcnow()


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(190), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="student")  # student | admin
    phone = db.Column(db.String(20))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    last_login = db.Column(db.DateTime)

    student = db.relationship(
        "StudentProfile", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )

    def set_password(self, raw: str) -> None:
        self.password_hash = generate_password_hash(raw)

    def verify_password(self, raw: str) -> bool:
        return check_password_hash(self.password_hash, raw)

    def to_dict(self, with_profile: bool = False) -> dict:
        data = {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "role": self.role,
            "phone": self.phone,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if with_profile and self.student:
            data["profile"] = self.student.to_dict()
        return data


class StudentProfile(db.Model):
    __tablename__ = "student_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    roll_number = db.Column(db.String(40), index=True)
    college = db.Column(db.String(190))
    branch = db.Column(db.String(90))
    graduation_year = db.Column(db.Integer)
    cgpa = db.Column(db.Float)
    preferred_domain = db.Column(db.String(60), index=True)
    preferred_location = db.Column(db.String(90))
    work_mode_pref = db.Column(db.String(20), default="any")
    phone = db.Column(db.String(20))

    # resume + NLP artefacts
    resume_filename = db.Column(db.String(255))
    resume_text = db.Column(db.Text)
    resume_uploaded_at = db.Column(db.DateTime)
    skills = db.Column(db.JSON, default=list)            # ["python","react", ...]
    skill_details = db.Column(db.JSON, default=list)      # [{skill, category, weight, evidence}]
    skill_vector = db.Column(db.JSON, default=dict)       # {skill: weight} -> TF-IDF style profile
    parsed_meta = db.Column(db.JSON, default=dict)        # cgpa / degree / experience / projects
    ats_score = db.Column(db.Integer, default=0)

    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    user = db.relationship("User", back_populates="student")
    applications = db.relationship(
        "Application", back_populates="student", cascade="all, delete-orphan"
    )
    resumes = db.relationship(
        "ResumeUpload", back_populates="student", cascade="all, delete-orphan"
    )

    @property
    def completeness(self) -> int:
        checks = [
            bool(self.roll_number), bool(self.college), bool(self.branch),
            bool(self.graduation_year), bool(self.cgpa), bool(self.preferred_domain),
            bool(self.resume_filename), bool(self.skills),
        ]
        return round(100 * sum(checks) / len(checks))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.user.name if self.user else None,
            "email": self.user.email if self.user else None,
            "roll_number": self.roll_number,
            "college": self.college,
            "branch": self.branch,
            "graduation_year": self.graduation_year,
            "cgpa": self.cgpa,
            "preferred_domain": self.preferred_domain,
            "preferred_location": self.preferred_location,
            "work_mode_pref": self.work_mode_pref,
            "resume_filename": self.resume_filename,
            "resume_uploaded_at": self.resume_uploaded_at.isoformat()
            if self.resume_uploaded_at else None,
            "skills": self.skills or [],
            "skill_details": self.skill_details or [],
            "skill_vector": self.skill_vector or {},
            "parsed_meta": self.parsed_meta or {},
            "ats_score": self.ats_score,
            "completeness": self.completeness,
        }


class ResumeUpload(db.Model):
    __tablename__ = "resume_uploads"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.Integer, db.ForeignKey("student_profiles.id", ondelete="CASCADE"), index=True
    )
    filename = db.Column(db.String(255))
    file_type = db.Column(db.String(10))
    size_bytes = db.Column(db.Integer)
    skills_found = db.Column(db.Integer, default=0)
    ats_score = db.Column(db.Integer, default=0)
    text_chars = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=utcnow)

    student = db.relationship("StudentProfile", back_populates="resumes")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "filename": self.filename,
            "file_type": self.file_type,
            "size_kb": round((self.size_bytes or 0) / 1024, 1),
            "skills_found": self.skills_found,
            "ats_score": self.ats_score,
            "text_chars": self.text_chars,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class DomainIntel(db.Model):
    """Cached recruiter-email domain intelligence (age, provider type, blacklist)."""

    __tablename__ = "domain_intel"

    id = db.Column(db.Integer, primary_key=True)
    domain = db.Column(db.String(190), unique=True, nullable=False, index=True)
    age_days = db.Column(db.Integer, default=0)
    is_free_provider = db.Column(db.Boolean, default=False)
    is_disposable = db.Column(db.Boolean, default=False)
    is_blacklisted = db.Column(db.Boolean, default=False)
    mx_valid = db.Column(db.Boolean, default=True)
    source = db.Column(db.String(40), default="heuristic")
    last_checked = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    def to_dict(self) -> dict:
        return {
            "domain": self.domain,
            "age_days": self.age_days,
            "age_years": round((self.age_days or 0) / 365.25, 2),
            "is_free_provider": self.is_free_provider,
            "is_disposable": self.is_disposable,
            "is_blacklisted": self.is_blacklisted,
            "mx_valid": self.mx_valid,
            "source": self.source,
        }


class Internship(db.Model):
    __tablename__ = "internships"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(190), nullable=False)
    company = db.Column(db.String(190), nullable=False, index=True)
    company_domain = db.Column(db.String(190), index=True)
    contact_email = db.Column(db.String(190))
    location = db.Column(db.String(120), index=True)
    work_mode = db.Column(db.String(20), default="onsite")   # remote | onsite | hybrid
    domain = db.Column(db.String(60), index=True)
    description = db.Column(db.Text)
    skills_required = db.Column(db.JSON, default=list)
    stipend = db.Column(db.Integer, default=0)               # INR / month
    duration_months = db.Column(db.Integer, default=3)
    openings = db.Column(db.Integer, default=1)
    apply_url = db.Column(db.String(400))
    posted_date = db.Column(db.Date, default=date.today, index=True)
    deadline = db.Column(db.Date)
    source = db.Column(db.String(40), default="partner")     # partner | scraped | admin | csv

    # ---- Trust engine outputs (precomputed & persisted) ----
    trust_score = db.Column(db.Integer, default=0, index=True)
    rule_score = db.Column(db.Float, default=0.0)
    ml_fraud_prob = db.Column(db.Float, default=0.0)
    fraud_flag = db.Column(db.Boolean, default=False, index=True)
    badge = db.Column(db.String(10), default="Amber")        # Green | Amber | Red
    hard_check_failed = db.Column(db.Boolean, default=False)
    trust_breakdown = db.Column(db.JSON, default=dict)
    red_flags = db.Column(db.JSON, default=list)
    override_by_admin = db.Column(db.Boolean, default=False)
    override_note = db.Column(db.String(400))
    trust_checked_at = db.Column(db.DateTime, default=utcnow)

    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    applications = db.relationship(
        "Application", back_populates="internship", cascade="all, delete-orphan"
    )
    feedbacks = db.relationship(
        "Feedback", back_populates="internship", cascade="all, delete-orphan"
    )

    @property
    def skills_list(self):
        return self.skills_required or []

    @property
    def applicant_count(self) -> int:
        return len(self.applications) if self.applications is not None else 0

    def to_dict(self, detailed: bool = False) -> dict:
        data = {
            "id": self.id,
            "title": self.title,
            "company": self.company,
            "company_domain": self.company_domain,
            "contact_email": self.contact_email,
            "location": self.location,
            "work_mode": self.work_mode,
            "domain": self.domain,
            "skills_required": self.skills_list,
            "stipend": self.stipend,
            "stipend_display": f"₹{self.stipend:,}/mo" if self.stipend else "Unpaid / TBD",
            "duration_months": self.duration_months,
            "openings": self.openings,
            "apply_url": self.apply_url,
            "posted_date": self.posted_date.isoformat() if self.posted_date else None,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "source": self.source,
            "trust_score": self.trust_score,
            "rule_score": self.rule_score,
            "ml_fraud_prob": self.ml_fraud_prob,
            "fraud_flag": self.fraud_flag,
            "badge": self.badge,
            "hard_check_failed": self.hard_check_failed,
            "trust_breakdown": self.trust_breakdown or {},
            "red_flags": self.red_flags or [],
            "override_by_admin": self.override_by_admin,
            "override_note": self.override_note,
            "trust_checked_at": self.trust_checked_at.isoformat()
            if self.trust_checked_at else None,
            "applicant_count": self.applicant_count,
        }
        if detailed:
            data["description"] = self.description
        else:
            data["description_excerpt"] = (self.description or "")[:180]
        return data


class Application(db.Model):
    __tablename__ = "applications"
    __table_args__ = (db.UniqueConstraint("student_id", "internship_id", name="uq_student_listing"),)

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.Integer, db.ForeignKey("student_profiles.id", ondelete="CASCADE"), index=True
    )
    internship_id = db.Column(
        db.Integer, db.ForeignKey("internships.id", ondelete="CASCADE"), index=True
    )
    status = db.Column(db.String(24), default="applied")
    match_score = db.Column(db.Float, default=0.0)
    notes = db.Column(db.String(400))
    applied_at = db.Column(db.DateTime, default=utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    student = db.relationship("StudentProfile", back_populates="applications")
    internship = db.relationship("Internship", back_populates="applications")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "student_id": self.student_id,
            "internship_id": self.internship_id,
            "status": self.status,
            "match_score": self.match_score,
            "notes": self.notes,
            "applied_at": self.applied_at.isoformat() if self.applied_at else None,
            "internship": self.internship.to_dict() if self.internship else None,
        }


class Feedback(db.Model):
    __tablename__ = "feedback"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.Integer, db.ForeignKey("student_profiles.id", ondelete="CASCADE"), index=True
    )
    internship_id = db.Column(
        db.Integer, db.ForeignKey("internships.id", ondelete="CASCADE"), index=True
    )
    rating = db.Column(db.Integer, nullable=False)                # 1..5
    verdict = db.Column(db.String(20), nullable=False)            # Verified | Suspicious
    comment = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=utcnow, index=True)

    internship = db.relationship("Internship", back_populates="feedbacks")
    student = db.relationship("StudentProfile", backref="feedbacks")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "student_id": self.student_id,
            "internship_id": self.internship_id,
            "internship_title": self.internship.title if self.internship else None,
            "company": self.internship.company if self.internship else None,
            "student_name": self.student.user.name if (self.student and self.student.user) else None,
            "rating": self.rating,
            "verdict": self.verdict,
            "comment": self.comment,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class TrustAuditLog(db.Model):
    """Every trust-score write (recompute, override, bulk upload) is auditable."""

    __tablename__ = "trust_audit_log"

    id = db.Column(db.Integer, primary_key=True)
    internship_id = db.Column(
        db.Integer, db.ForeignKey("internships.id", ondelete="CASCADE"), index=True
    )
    actor = db.Column(db.String(120), default="system")
    action = db.Column(db.String(60))                 # recompute | override | create | csv_upload
    old_score = db.Column(db.Integer)
    new_score = db.Column(db.Integer)
    old_badge = db.Column(db.String(10))
    new_badge = db.Column(db.String(10))
    note = db.Column(db.String(400))
    created_at = db.Column(db.DateTime, default=utcnow)

    internship = db.relationship("Internship")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "internship_id": self.internship_id,
            "internship_title": self.internship.title if self.internship else None,
            "actor": self.actor,
            "action": self.action,
            "old_score": self.old_score,
            "new_score": self.new_score,
            "old_badge": self.old_badge,
            "new_badge": self.new_badge,
            "note": self.note,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

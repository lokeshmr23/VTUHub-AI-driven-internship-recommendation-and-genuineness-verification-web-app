"""Generates downloadable sample assets: resume PDFs + a bulk-upload CSV."""
from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path

from services.resume_builder import build_resume_pdf

SAMPLE_RESUMES = [
    {
        "name": "Ananya Sharma", "branch": "Computer Science", "college": "NIT Surathkal",
        "cgpa": 8.9, "grad_year": 2027,
        "skills": ["python", "flask", "mysql", "docker", "git", "rest api", "sql",
                   "javascript", "react", "testing", "linux", "communication skills"],
        "projects": ["Campus Ride Sharing Web App", "REST API Rate Limiter"],
    },
    {
        "name": "Rohan Iyer", "branch": "AI & ML", "college": "IIIT Hyderabad",
        "cgpa": 9.2, "grad_year": 2027,
        "skills": ["python", "machine learning", "deep learning", "pytorch", "nlp", "pandas",
                   "numpy", "scikit-learn", "statistics", "llm engineering",
                   "data visualization", "problem solving"],
        "projects": ["Document QA with Transformers", "Churn Prediction Pipeline"],
    },
    {
        "name": "Sneha Reddy", "branch": "Electronics & Communication",
        "college": "PSG College of Technology", "cgpa": 8.2, "grad_year": 2027,
        "skills": ["embedded c", "iot", "c", "matlab", "robotics", "cad modeling",
                   "networking", "linux", "problem solving", "teamwork"],
        "projects": ["Smart Energy Meter with ESP32", "Gesture Controlled Robot"],
    },
    {
        "name": "Karan Gupta", "branch": "Mechanical Engineering",
        "college": "College of Engineering Pune", "cgpa": 7.8, "grad_year": 2027,
        "skills": ["autocad", "cad modeling", "thermodynamics", "manufacturing",
                   "excel", "supply chain", "problem solving", "teamwork"],
        "projects": ["Formula Student Chassis Design", "Assembly Line Waste Study"],
    },
    {
        "name": "Divya Menon", "branch": "Information Technology",
        "college": "VIT Vellore", "cgpa": 8.4, "grad_year": 2028,
        "skills": ["aws", "docker", "kubernetes", "linux", "ci/cd", "bash", "terraform",
                   "monitoring", "python", "git", "networking", "communication skills"],
        "projects": ["Multi-tenant CI/CD Pipeline", "Kubernetes Cost Optimiser"],
    },
]

SAMPLE_CSV_ROWS = [
    ["Backend Engineer Intern", "Nimbus Payments", "careers@nimbuspayments.in",
     "Bengaluru, KA", "hybrid", "Backend Engineering",
     "Work with the payments platform team on API design, writing production Python "
     "services, database migrations and observability. You will ship code in your first "
     "two weeks with mentorship from senior engineers. Interviews include one DSA round "
     "and one system design discussion.",
     "python, flask, postgresql, docker, rest api", "28000", "6", "2",
     "https://nimbuspayments.in/careers/backend-intern", "2026-12-15", "2026-09-25", "admin"],
    ["Machine Learning Intern", "Kavach Cyber", "talent@kavachcyber.in",
     "Hyderabad, TS", "onsite", "Data Science & ML",
     "Build anomaly detection models over network telemetry. Requirements: Python, "
     "scikit-learn, pandas and a solid grasp of statistics. You will prepare datasets, "
     "train models, evaluate them and document findings for the security team.",
     "python, machine learning, scikit-learn, pandas, statistics", "35000", "6", "1",
     "https://kavachcyber.in/careers/ml-intern", "2026-11-30", "2026-09-22", "admin"],
    ["Paid Internship with Certificate", "Easy Internship India",
     "hr12@easyinternshipindia.top", "Work From Home", "remote", "Business & Analytics",
     "Earn 45000 per month from home doing simple data entry. Registration fee Rs 499 is "
     "mandatory to confirm your seat. No interview required, direct joining letter. Pay the "
     "fee to our UPI id and share the screenshot on WhatsApp. Limited seats, apply fast.",
     "excel", "0", "2", "25", "https://bit.ly/intern-apply-7777", "2026-10-10", "2026-09-26",
     "csv"],
    ["Flutter App Intern", "Suvidha EdTech", "interns@suvidhaedtech.com",
     "Pune, MH", "remote", "Mobile App Development",
     "Develop features for our learning app in Flutter, integrate REST APIs, improve "
     "performance and help with Play Store releases. You will collaborate with designers "
     "and get detailed code reviews on every pull request. Certificate and LOR provided.",
     "flutter, rest api, git, ui/ux design", "18000", "4", "2",
     "https://suvidhaedtech.com/jobs/flutter-intern", "2026-11-20", "2026-09-24", "admin"],
    ["Quality Assurance Intern", "Bluewave Systems", "hr@bluewavesystems.in",
     "Chennai, TN", "onsite", "QA & Testing",
     "Write and execute test cases for our logistics platform, automate regression suites "
     "with Selenium and pytest, and log defects in Jira. Exposure to SQL and API testing "
     "with Postman is expected. You will work with the QA lead on release sign-off.",
     "testing, selenium, sql, manual testing", "15000", "3", "1",
     "https://bluewavesystems.in/careers/qa-intern", "2026-10-30", "2026-09-20", "csv"],
    ["Marketing Intern", "Placement Assured Cell", "team@placementassured.co",
     "Delhi NCR", "remote", "Business & Analytics",
     "100% placement guarantee internship with certificate. Processing fee Rs 750 to issue "
     "your intern id. Transfer the amount to the given account number and share the IFSC "
     "receipt. Only 5 slots left, contact HR on WhatsApp only.",
     "digital marketing, content writing", "5000", "1", "20",
     "https://forms.gle/demo-7781", "2026-10-05", "2026-09-27", "csv"],
]


def generate_samples(app) -> list[str]:
    """Write sample PDFs + CSV into the configured samples dir; return paths."""
    samples_dir = Path(app.config["SAMPLES_DIR"])
    resumes_dir = samples_dir / "resumes"
    resumes_dir.mkdir(parents=True, exist_ok=True)

    written: list[str] = []
    for idx, spec in enumerate(SAMPLE_RESUMES, start=1):
        path = resumes_dir / f"{idx}_{spec['name'].lower().replace(' ', '_')}_resume.pdf"
        build_resume_pdf(
            name=spec["name"], skills=spec["skills"], cgpa=spec["cgpa"],
            college=spec["college"], branch=spec["branch"], grad_year=spec["grad_year"],
            out_path=path, projects=spec["projects"],
            experience=("Intern, Tantra Analytics — Jun 2026 - Aug 2026"
                        if idx % 2 == 1 else ""),
        )
        written.append(str(path.relative_to(samples_dir.parent)))

    csv_path = samples_dir / "internships_bulk_upload.csv"
    header = ["title", "company", "contact_email", "location", "work_mode", "domain",
              "description", "skills_required", "stipend", "duration_months", "openings",
              "apply_url", "deadline", "posted_date", "source"]
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(SAMPLE_CSV_ROWS)
    written.append(str(csv_path.relative_to(samples_dir.parent)))

    return written

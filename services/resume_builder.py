"""
Resume text/PDF builder.

Used for (a) seeding demo resume text, (b) generating downloadable sample
resumes that students/admins can test the upload pipeline with.
"""
from __future__ import annotations

from pathlib import Path

DEFAULT_PROJECTS = ["Campus Placement Analytics Dashboard",
                    "AI Internship Recommender"]
BULLETS = ["Built REST APIs with Flask and MySQL serving 10k+ requests/day",
           "Trained classification models reaching 0.91 F1 on held-out data",
           "Automated reporting pipelines that cut manual effort by 6 hours/week",
           "Containerised services with Docker and deployed on AWS EC2"]


def build_resume_text(name: str, skills: list[str], cgpa: float, college: str,
                      branch: str, grad_year: int, projects: list[str] | None = None,
                      experience: str = "", email: str | None = None,
                      phone: str = "+91 98800 12345") -> str:
    projects = projects or DEFAULT_PROJECTS
    email = email or f"{name.lower().replace(' ', '.')}@student.internmatch.ai"
    cats: dict[str, list[str]] = {}
    from services.skills_taxonomy import SKILL_TAXONOMY

    for s in skills:
        cat = SKILL_TAXONOMY.get(s, {"category": "Tools"})["category"]
        cats.setdefault(cat, []).append(s)

    lines = [
        name.upper(),
        f"{branch} Undergraduate | {college}",
        f"Email: {email} | Phone: {phone} | GitHub: github.com/{name.split()[0].lower()}-dev",
        "",
        "EDUCATION",
        f"B.Tech in {branch}, {college} ({2023} - {grad_year})",
        f"CGPA: {cgpa}/10 | Relevant coursework: Data Structures, Algorithms, DBMS, Machine Learning",
        "Class XII (CBSE): 91.4%",
        "",
        "TECHNICAL SKILLS",
    ]
    for cat, items in cats.items():
        lines.append(f"{cat}: {', '.join(items)}")
    lines += ["", "EXPERIENCE"]
    if experience:
        lines.append(experience)
        for b in BULLETS[:2]:
            lines.append(f"- {b}")
    else:
        lines.append("Open Source Contributor - GitHub (2025)")
        lines.append(f"- {BULLETS[3]}")
    lines += ["", "PROJECTS"]
    for i, proj in enumerate(projects):
        lines.append(proj)
        lines.append(f"- {BULLETS[i % len(BULLETS)]}")
    lines += [
        "",
        "CERTIFICATIONS & ACHIEVEMENTS",
        "NPTEL Certification - Machine Learning (Elite, 2025)",
        "Winner, Inter-College Hackathon 2025; Runner-up, Coding Contest (CodeChef Chapter)",
        "",
        "POSITIONS OF RESPONSIBILITY",
        "Technical Lead, Coding Club - conducted 6 workshops for 200+ students (leadership, teamwork)",
    ]
    return "\n".join(lines)


def build_resume_pdf(name: str, skills: list[str], cgpa: float, college: str, branch: str,
                     grad_year: int, out_path: str | Path, experience: str = "",
                     projects: list[str] | None = None) -> str:
    """Render a real, uploadable PDF resume (reportlab)."""
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (ListFlowable, ListItem, Paragraph,
                                    SimpleDocTemplate, Spacer)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = build_resume_text(name, skills, cgpa, college, branch, grad_year,
                             projects=projects, experience=experience)

    styles = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=9.4, leading=13,
                          alignment=TA_LEFT, spaceAfter=2)
    head = ParagraphStyle("head", parent=styles["Heading2"], fontSize=11, leading=14,
                          spaceBefore=8, spaceAfter=3, textColor="#12335c")
    title = ParagraphStyle("title", parent=styles["Title"], fontSize=17, leading=20,
                           spaceAfter=2)

    doc = SimpleDocTemplate(str(out_path), pagesize=A4,
                            leftMargin=16 * mm, rightMargin=16 * mm,
                            topMargin=14 * mm, bottomMargin=14 * mm,
                            title=f"{name} - Resume", author=name)
    story = [Paragraph(name, title)]
    for line in text.split("\n")[1:]:
        line = line.strip()
        if not line:
            story.append(Spacer(1, 3))
            continue
        if line.isupper() or (len(line) < 40 and line.endswith(("S", "S:", "G")) ):
            story.append(Paragraph(line, head))
        elif line.startswith("- "):
            story.append(ListFlowable(
                [ListItem(Paragraph(line[2:], body), leftIndent=10)], bulletType="bullet",
                start="•", bulletFontSize=7, leftIndent=10))
        else:
            story.append(Paragraph(line.replace("&", "&amp;"), body))
    doc.build(story)
    return str(out_path)

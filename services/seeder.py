"""
Realistic demo-data seeder.

Generates ~500 internship listings (genuine + suspicious mix), 50 student
profiles with skill vectors, applications, feedback, domain intelligence and
precomputed trust scores. Deterministic (seeded RNG) so results are stable.

    flask --app app seed --listings 500 --students 50
"""
from __future__ import annotations

import random
from datetime import date, datetime, timedelta

from extensions import db
from models import (Application, DomainIntel, Feedback, Internship,
                    ResumeUpload, StudentProfile, TrustAuditLog, User)
from services.nlp_engine import (build_skill_vector, compute_ats_score,
                                 extract_skills, infer_domains, parse_meta)
from services.recommender import invalidate_index
from services.skills_taxonomy import DOMAINS, DOMAIN_SIGNALS, SKILL_TAXONOMY
from services.resume_builder import build_resume_text

RNG = random.Random(20250928)

LOCATIONS = ["Bengaluru, KA", "Hyderabad, TS", "Pune, MH", "Chennai, TN", "Mumbai, MH",
             "Delhi NCR", "Noida, UP", "Gurugram, HR", "Ahmedabad, GJ", "Kolkata, WB",
             "Coimbatore, TN", "Jaipur, RJ", "Indore, MP", "Kochi, KL", "Remote (India)"]

GENUINE_COMPANIES = [
    ("Flipkart", "flipkart.com"), ("Swiggy", "swiggy.in"), ("Zomato", "zomato.com"),
    ("PhonePe", "phonepe.com"), ("Razorpay", "razorpay.com"), ("Freshworks", "freshworks.com"),
    ("Zoho", "zoho.com"), ("Postman", "postman.com"), ("BrowserStack", "browserstack.com"),
    ("Hasura", "hasura.io"), ("CRED", "cred.club"), ("Groww", "groww.in"),
    ("Zerodha", "zerodha.com"), ("Meesho", "meesho.io"), ("Nykaa", "nykaa.com"),
    ("Delhivery", "delhivery.com"), ("BigBasket", "bigbasket.com"), ("Myntra", "myntra.com"),
    ("Paytm", "paytm.com"), ("BharatPe", "bharatpe.com"), ("Jupiter Money", "jupiter.money"),
    ("ClearTax", "cleartax.in"), ("Sarvam AI", "sarvam.ai"), ("InMobi", "inmobi.com"),
    ("ShareChat", "sharechat.com"), ("Dream11", "dream11.com"), ("Games24x7", "games24x7.com"),
    ("Tata Elxsi", "tataelxsi.com"), ("Tata Motors", "tatamotors.com"),
    ("Mahindra & Mahindra", "mahindra.com"), ("Bosch India", "bosch.in"),
    ("Siemens India", "siemens.co.in"), ("L&T Technology Services", "ltts.com"),
    ("Persistent Systems", "persistent.com"), ("ThoughtWorks", "thoughtworks.com"),
    ("Mphasis", "mphasis.com"), ("Qualcomm India", "qualcomm.com"),
    ("NVIDIA India", "nvidia.com"), ("Samsung R&D", "samsung.com"),
    ("Honeywell India", "honeywell.com"), ("ABB India", "abb.com"),
    ("Schneider Electric", "schneider-electric.com"), ("Cummins India", "cummins.com"),
    ("BHEL", "bhel.com"), ("NTPC", "ntpc.co.in"), ("Reliance Jio", "jio.com"),
    ("Airtel Digital", "airtel.in"), ("Godrej & Boyce", "godrej.com"),
    ("Infosys", "infosys.com"), ("TCS Research", "tcs.com"), ("Wipro Digital", "wipro.com"),
    ("HCLTech", "hcltech.com"), ("Tech Mahindra", "techmahindra.com"),
    ("Accenture", "accenture.com"), ("Capgemini", "capgemini.com"),
    ("Cognizant", "cognizant.com"), ("Deloitte India", "deloitte.com"),
    ("EY GDS", "ey.com"), ("Amazon India", "amazon.in"), ("Microsoft India", "microsoft.com"),
]
MID_COMPANIES = [
    ("Nexora Labs", "nexoralabs.in"), ("Tantra Analytics", "tantraanalytics.com"),
    ("Bluewave Systems", "bluewavesystems.in"), ("Pi Robotics", "pirobotics.co.in"),
    ("Quantel Devices", "quanteldevices.com"), ("Meridian Infra", "meridianinfra.co.in"),
    ("Vistara Components", "vistaracomponents.in"), ("Helios Energy", "heliosenergy.in"),
    ("Cogent Semiconductors", "cogentsemi.com"), ("Aster Healthcare Tech", "asterht.in"),
    ("Zenith Autoparts", "zenithautoparts.in"), ("Orbit Fintech", "orbitfintech.in"),
    ("Kavach Cyber", "kavachcyber.in"), ("Pragati Logistics", "pragatilogistics.in"),
    ("Suvidha EdTech", "suvidhaedtech.com"), ("Aarogya Health AI", "aarogyahealth.ai"),
]
FAKE_COMPANIES = [
    ("Internship Pay Portal", "internshippay.in"), ("Job Offer Verification Cell", "joboffer-verify.xyz"),
    ("Career Placement Hub", "careers-placement.top"), ("FastStipend Services", "stipend-fast.net"),
    ("HireQuickly Consultancy", "hirequickly.work"), ("Free Intern Program", "freeintern.xyz"),
    ("Trainee Pay Club", "trainee-pay.club"), ("Work From Home Easy", "workfromhome-easy.online"),
    ("Intern Registration Desk", "intern-registration.site"), ("Verify Jobs Cell", "verify-jobs.click"),
    ("Global Internship Solutions", "globalintern-solutions.site"), ("Stipend Now Services", "stipendnow.online"),
    ("National Internship Cell", "nationalinternship.club"), ("Earn While Learn India", "earnwhilelearn.top"),
    ("Certificate Verify Pro", "certverifypro.xyz"), ("Internship Form Center", "internshipform.center"),
    ("Quick Placement Services", "quickplacement.online"), ("Online Internship Desk", "onlineintern.work"),
    ("Job Guarantee India", "jobguaranteeindia.top"), ("Student Earning Portal", "studentearning.site"),
    ("Placement Assured Cell", "placementassured.co"),
    ("Easy Internship India", "easyinternshipindia.top"),
    ("Remote Task Hub", "remotetaskhub.xyz"),
    ("Data Entry Interns India", "dataentryinterns.online"),
    ("Premium Intern Offers", "premiuminternoffers.store"),
]

GENUINE_DOMAINS_COMPANIES = GENUINE_COMPANIES + MID_COMPANIES

GENUINE_JD: dict[str, list[tuple[str, list[str]]]] = {
    "Web Development": [
        ("Frontend Developer Intern",
         ["html", "css", "javascript", "react", "rest api", "git"]),
        ("Full Stack Web Intern",
         ["javascript", "node.js", "react", "mysql", "rest api", "git"]),
        ("React Developer Intern",
         ["react", "redux", "typescript", "html", "css", "rest api"]),
    ],
    "Backend Engineering": [
        ("Backend Engineer Intern (Python)",
         ["python", "flask", "mysql", "rest api", "docker", "git"]),
        ("Java Backend Intern",
         ["java", "spring boot", "sql", "microservices", "git"]),
        ("API Platform Intern",
         ["python", "fastapi", "postgresql", "redis", "docker"]),
    ],
    "Data Science & ML": [
        ("Data Science Intern",
         ["python", "pandas", "scikit-learn", "statistics", "data visualization", "sql"]),
        ("Machine Learning Intern",
         ["python", "machine learning", "deep learning", "tensorflow", "numpy"]),
        ("NLP Research Intern",
         ["python", "nlp", "pytorch", "llm engineering", "machine learning"]),
        ("Analytics Intern",
         ["sql", "excel", "data analysis", "data visualization", "statistics"]),
    ],
    "Mobile App Development": [
        ("Android Developer Intern",
         ["android", "kotlin", "rest api", "git", "sqlite"]),
        ("Flutter App Intern",
         ["flutter", "rest api", "git", "ui/ux design"]),
        ("iOS Developer Intern", ["ios", "swift", "rest api", "git"]),
    ],
    "Cloud & DevOps": [
        ("Cloud Engineering Intern",
         ["aws", "linux", "docker", "ci/cd", "bash"]),
        ("DevOps Intern",
         ["docker", "kubernetes", "terraform", "ci/cd", "linux", "monitoring"]),
        ("Site Reliability Intern",
         ["linux", "aws", "nginx", "monitoring", "bash"]),
    ],
    "Cybersecurity": [
        ("Security Analyst Intern",
         ["cybersecurity", "siem", "networking", "linux", "appsec"]),
        ("Penetration Testing Intern",
         ["penetration testing", "appsec", "networking", "linux"]),
        ("Application Security Intern",
         ["appsec", "cryptography", "javascript", "python", "networking"]),
    ],
    "Embedded & IoT": [
        ("Embedded Firmware Intern",
         ["embedded c", "iot", "c", "robotics"]),
        ("IoT Solutions Intern",
         ["iot", "python", "embedded c", "networking"]),
        ("VLSI Design Intern", ["vlsi", "c", "matlab"]),
    ],
    "Mechanical Engineering": [
        ("Mechanical Design Intern",
         ["autocad", "cad modeling", "manufacturing"]),
        ("Manufacturing Excellence Intern",
         ["manufacturing", "supply chain", "excel"]),
        ("Robotics Engineering Intern",
         ["robotics", "cad modeling", "embedded c", "iot"]),
    ],
    "Civil Engineering": [
        ("Structural Design Intern",
         ["structural analysis", "autocad", "gis"]),
        ("Site Engineering Intern",
         ["autocad", "structural analysis", "excel", "supply chain"]),
    ],
    "Electrical Engineering": [
        ("Power Systems Intern",
         ["power systems", "matlab", "embedded c"]),
        ("Electrical Design Intern",
         ["power systems", "autocad", "matlab"]),
    ],
    "QA & Testing": [
        ("QA Automation Intern",
         ["testing", "selenium", "python", "sql"]),
        ("Manual QA Intern", ["manual testing", "testing", "sql"]),
        ("Performance Testing Intern",
         ["performance testing", "testing", "python", "linux"]),
    ],
    "UI/UX Design": [
        ("UI/UX Design Intern",
         ["ui/ux design", "graphic design", "html", "css"]),
        ("Product Design Intern",
         ["ui/ux design", "product management", "communication skills"]),
    ],
    "Business & Analytics": [
        ("Business Analyst Intern",
         ["business analysis", "excel", "sql", "communication skills", "product management"]),
        ("Product Management Intern",
         ["product management", "data analysis", "communication skills", "excel"]),
        ("Digital Marketing Intern",
         ["digital marketing", "content writing", "excel", "communication skills"]),
        ("Finance Intern",
         ["finance", "excel", "data analysis", "communication skills"]),
    ],
    "Blockchain & Web3": [
        ("Blockchain Developer Intern",
         ["blockchain", "solidity", "javascript", "cryptography"]),
        ("Smart Contract Intern",
         ["solidity", "blockchain", "testing", "python"]),
    ],
}

TEAM_SUFFIXES = [
    "— Payments Platform", "— Growth Engineering", "— Data Platform", "— Core Infrastructure",
    "— Merchant Experience", "— Developer Tools", "— Supply Chain Tech", "— Risk & Trust",
    "— Customer Platform", "— Applied Research", "— Quality Engineering", "— Design Systems",
]

GENUINE_JD_BODY = [
    ("You will own a scoped project end to end under the guidance of a senior engineer, "
     "participate in daily standups, code reviews and sprint planning. We expect strong "
     "fundamentals, curiosity and the ability to read unfamiliar code. Deliverables are "
     "reviewed weekly and you will present your work to the team at the end of the internship. "
     "Mentorship, learning budget and a certificate of completion are provided. "
     "Selection process: online assessment, technical interview and a short manager conversation."),
    ("This internship sits inside our product engineering pod. You will write production code, "
     "write tests, fix real defects reported by users and contribute to documentation. "
     "Our stack is modern and our code review culture is strong — expect detailed feedback on "
     "every pull request. Work mode is hybrid with two days in office for collaboration. "
     "Top performers receive a pre-placement offer at the end of the term."),
    ("We are looking for curious students who want to see how real products are built. "
     "Day to day you will collaborate with designers and engineers, break down problems, "
     "and ship incremental improvements. Requirements: solid coursework in your discipline, "
     "good communication, willingness to learn fast. Interviews are technical + behavioural. "
     "Stipend is paid monthly and travel reimbursement is available for on-site days."),
]

STIPEND_BY_DOMAIN = {
    "Data Science & ML": (20000, 55000), "Web Development": (12000, 35000),
    "Backend Engineering": (18000, 45000), "Mobile App Development": (15000, 35000),
    "Cloud & DevOps": (18000, 42000), "Cybersecurity": (15000, 38000),
    "Embedded & IoT": (12000, 30000), "Mechanical Engineering": (8000, 22000),
    "Civil Engineering": (7000, 18000), "Electrical Engineering": (9000, 24000),
    "QA & Testing": (10000, 25000), "UI/UX Design": (10000, 28000),
    "Business & Analytics": (10000, 30000), "Blockchain & Web3": (18000, 40000),
}

FRAUD_JD_TEMPLATES = [
    ("*  *  *  Need interns urgently. Registration fee Rs {fee} is mandatory before joining. "
     "No interview required, direct joining letter in 24 hours. Pay the fee to our UPI id and "
     "send the screenshot on WhatsApp to confirm your seat. Limited seats available, hurry up."),
    ("Work from home internship. Earn Rs {salary} per month. Simple typing and copy paste data entry work. "
     "No experience needed, any graduate can apply. Refundable security deposit of Rs {fee} required "
     "for onboarding. Contact only on WhatsApp for payment details."),
    ("100% placement guarantee internship with certificate. Guaranteed job in MNC after completion. "
     "Processing fee Rs {fee} to issue your intern id card and certificate. Transfer the amount to the "
     "given account number and share the IFSC receipt. Immediate joining available."),
    ("Congratulations, you are shortlisted. To activate your internship slot, pay the training charge "
     "of Rs {fee} through GPay or PhonePe. Send your Aadhaar card and PAN card copy with bank details "
     "for verification. Only {seats} slots left, apply fast, last date today."),
    ("Hiring interns for our new startup. Onboarding fee Rs {fee} covers laptop and kit charges. "
     "100 percent assured stipend of Rs {salary} per month. No interview, direct selection. "
     "Share the OTP received on your phone to our Telegram id for verification."),
    ("Easy money internship. Earn up to Rs {salary} per month working from home on promotion tasks. "
     "Commission based per sale payment plus referral income. Registration charge Rs {fee} to generate "
     "your employee ID. No interview, work from home, apply fast limited slots."),
    ("Get internship certificate without doing any internship. Fee Rs {fee} for a verified certificate "
     "with QR code. Instant certificate, no project work needed. Send Aadhaar card and passport photo "
     "for registration. Payment via UPI or Google Pay only."),
    ("Urgent requirement for online interns. Stipend Rs {salary} monthly. Selection is direct, "
     "no interview and no technical round. Registration fee Rs {fee} non refundable. "
     "Contact HR on WhatsApp only. Join our Telegram channel for daily updates and tasks."),
]

FAKE_APPLY_URLS = [
    "https://bit.ly/intern-apply-{n}", "https://forms.gle/demo-{n}",
    "https://{dom}/register", "https://t.me/internship_offers_india",
]

BRANCHES = [
    ("Computer Science", "Computer Science", ["python", "java", "javascript", "sql", "git",
                                              "testing", "docker", "rest api"]),
    ("Information Science", "Computer Science", ["python", "javascript", "mysql", "git",
                                                  "rest api", "testing"]),
    ("Electronics & Communication", "Electronics & Electrical", ["embedded c", "iot", "c",
                                                                 "matlab", "networking", "vlsi"]),
    ("Electrical & Electronics", "Electronics & Electrical", ["power systems", "matlab",
                                                             "embedded c", "autocad"]),
    ("Mechanical Engineering", "Mechanical", ["autocad", "cad modeling", "thermodynamics",
                                              "manufacturing", "excel"]),
    ("Civil Engineering", "Civil", ["autocad", "structural analysis", "gis", "excel"]),
    ("AI & Machine Learning", "AI & ML", ["python", "machine learning", "deep learning", "nlp",
                                          "scikit-learn", "pandas"]),
    ("Chemical Engineering", "Chemical", ["process engineering", "excel", "data analysis"]),
    ("Biotechnology", "Biotechnology", ["data analysis", "content writing", "excel"]),
    ("Information Technology", "Computer Science", ["python", "flask", "sql", "javascript",
                                                    "docker", "git", "linux"]),
]

COLLEGES = [
    "NIT Surathkal", "RV College of Engineering", "BMS College of Engineering",
    "PES University", "Manipal Institute of Technology", "VIT Vellore",
    "IIIT Hyderabad", "College of Engineering Pune", "PSG College of Technology",
    "SRM Institute of Science & Technology", "Thapar Institute", "Amrita Vishwa Vidyapeetham",
    "KLE Technological University", "Dayananda Sagar College of Engineering",
    "Siddaganga Institute of Technology", "MS Ramaiah Institute of Technology",
]

FIRST_NAMES = ["Aarav", "Aditi", "Advait", "Aishwarya", "Akash", "Ananya", "Aniket", "Anjali",
               "Arjun", "Arya", "Bhavya", "Chaitanya", "Deepak", "Deepika", "Dhruv", "Divya",
               "Gaurav", "Gayatri", "Harsh", "Ishita", "Jahnavi", "Karan", "Kavya", "Kiran",
               "Lakshmi", "Madhav", "Meera", "Mohit", "Nandini", "Neha", "Nikhil", "Pallavi",
               "Pranav", "Priya", "Rahul", "Rakshita", "Ritika", "Rohan", "Sahana", "Sanjay",
               "Shreya", "Siddharth", "Sneha", "Sourabh", "Suhas", "Tanvi", "Tejas", "Vaishnavi",
               "Varun", "Yashas"]
LAST_NAMES = ["Sharma", "Reddy", "Nair", "Iyer", "Patel", "Rao", "Gupta", "Menon", "Kulkarni",
              "Desai", "Joshi", "Bhat", "Shetty", "Hegde", "Verma", "Chauhan", "Pillai",
              "Mishra", "Das", "Bose", "Kaur", "Singh", "Kumar", "Naidu", "Prabhu"]


# ----------------------------------------------------------------- listing gens
def _genuine_listing(i: int) -> dict:
    company, domain = RNG.choice(GENUINE_COMPANIES if RNG.random() < 0.72 else MID_COMPANIES)
    domain_key = RNG.choice(list(GENUINE_JD.keys()))
    title, skills = RNG.choice(GENUINE_JD[domain_key])
    if RNG.random() < 0.45:                      # vary titles so feeds look organic
        title = f"{title} {RNG.choice(TEAM_SUFFIXES)}"
    elif RNG.random() < 0.25:
        title = title.replace("Intern", RNG.choice(["Summer Intern", "Intern (6 months)",
                                                    "Intern, Full-time Track"]))
    body = RNG.choice(GENUINE_JD_BODY)
    lo, hi = STIPEND_BY_DOMAIN.get(domain_key, (10000, 30000))
    stipend = int(round(RNG.uniform(lo, hi), -2))
    posted = date.today() - timedelta(days=RNG.randint(1, 45))
    work_mode = RNG.choices(["onsite", "hybrid", "remote"], weights=[0.45, 0.33, 0.22])[0]
    desc = (f"About the role: {title} at {company}. {body}\n\n"
            f"Responsibilities: collaborate with the {domain_key.split()[0].lower()} team, "
            f"write code and documentation, take part in reviews and standups, and deliver a "
            f"presentable outcome at the end of {RNG.randint(2, 6)} months.\n\n"
            f"Requirements: {', '.join(skills)}. Strong fundamentals, good communication and "
            f"willingness to learn. Preferred graduation year {RNG.choice([2026, 2027, 2027, 2028])} "
            f"with CGPA above {RNG.choice(['6.5', '6.0', '7.0'])}.\n\n"
            f"Perks: mentorship, certificate, potential pre-placement offer. "
            f"Work mode: {work_mode}. Stipend Rs {stipend:,} per month.")
    slug = title.lower().replace(" (", "-").replace(")", "").replace(",", "").replace(" ", "-")
    return {
        "title": title,
        "company": company,
        "company_domain": domain,
        "contact_email": RNG.choice([f"careers@{domain}", f"talent@{domain}",
                                     f"internships@{domain}", f"campus.hiring@{domain}"]),
        "location": RNG.choice(LOCATIONS),
        "work_mode": work_mode,
        "domain": domain_key,
        "description": desc,
        "skills_required": skills,
        "stipend": stipend,
        "duration_months": RNG.choice([2, 3, 3, 4, 6]),
        "openings": RNG.choice([1, 1, 2, 2, 3, 5]),
        "apply_url": f"https://{domain}/careers/{slug}-{i:03d}",
        "posted_date": posted,
        "deadline": posted + timedelta(days=RNG.randint(20, 70)),
        "source": RNG.choices(["partner", "scraped", "admin", "csv"],
                              weights=[0.5, 0.3, 0.12, 0.08])[0],
    }


def _suspicious_listing(i: int, tier: str) -> dict:
    company, domain = RNG.choice(FAKE_COMPANIES)
    template = RNG.choice(FRAUD_JD_TEMPLATES)
    fee = RNG.choice([99, 149, 199, 249, 299, 399, 499, 599, 750, 999, 1200])
    salary = RNG.choice(["45,000", "60,000", "35,000", "80,000", "25,000"])
    seats = RNG.choice([3, 5, 7, 10])
    desc = template.format(fee=fee, salary=salary, seats=seats)

    if tier == "blacklisted":
        title = RNG.choice(["Paid Internship with Certificate", "Data Entry Intern",
                            "Online Internship Program", "Marketing Intern"])
        contact = f"hr{RNG.randint(1, 99)}@{domain}"
        apply_url = RNG.choice(FAKE_APPLY_URLS).format(n=i, dom=domain)
        posted = date.today() - timedelta(days=RNG.randint(0, 8))
        stipend = RNG.choice([0, 5000, 15000])
    elif tier == "newdomain":
        title = RNG.choice(["Work From Home Intern", "Content Writing Intern",
                            "Business Development Intern", "Social Media Intern"])
        contact = f"{RNG.choice(['hr', 'team', 'interns', 'contact'])}@{domain}"
        apply_url = f"https://{domain}/apply?id={i}"
        posted = date.today() - timedelta(days=RNG.randint(0, 20))
        stipend = RNG.choice([0, 8000, 12000, 20000])
    else:  # freemail — lower-risk shell listing that still trips the rule engine
        title = RNG.choice(["Junior Python Intern", "Web Developer Intern",
                            "Accounts Intern", "Research Intern"])
        contact = f"{RNG.choice(['internships', 'hr.team', 'talent'])}{RNG.randint(10, 99)}@gmail.com"
        apply_url = f"https://forms.gle/intern-form-{i}"
        posted = date.today() - timedelta(days=RNG.randint(0, 35))
        stipend = RNG.choice([5000, 10000, 12000, 15000])
        desc = (desc + " Good opportunity for freshers, dedicated mentorship and a certificate "
                       "will be provided after completion of the internship period.")

    return {
        "title": title,
        "company": company,
        "company_domain": domain if tier != "freemail" else "gmail.com",
        "contact_email": contact,
        "location": RNG.choice(["Remote (India)", "Work From Home", "Delhi NCR", "Mumbai, MH"]),
        "work_mode": "remote",
        "domain": RNG.choice(DOMAINS),
        "description": desc,
        "skills_required": RNG.choice([[], [], ["excel"], ["content writing"], ["communication skills"]]),
        "stipend": stipend,
        "duration_months": RNG.choice([1, 2, 3]),
        "openings": RNG.choice([10, 20, 25, 50]),
        "apply_url": apply_url,
        "posted_date": posted,
        "deadline": posted + timedelta(days=RNG.randint(5, 30)),
        "source": RNG.choice(["scraped", "partner", "csv"]),
    }


def _thin_listing(i: int) -> dict:
    """Genuine company but a weak listing: short JD, no deadline, no stipend.

    Lands in the Amber band — realistic for smaller recruiters.
    """
    company, domain = RNG.choice(MID_COMPANIES)
    domain_key = RNG.choice(list(GENUINE_JD.keys()))
    title, skills = RNG.choice(GENUINE_JD[domain_key])
    posted = date.today() - timedelta(days=RNG.randint(10, 90))
    desc = (f"We are hiring a {title} to support our {domain_key.split()[0].lower()} team. "
            f"Good learning opportunity for final-year students. Flexible timings, certificate "
            f"on completion.")
    return {
        "title": title, "company": company, "company_domain": domain,
        "contact_email": f"info@{domain}",
        "location": RNG.choice(LOCATIONS), "work_mode": RNG.choice(["onsite", "remote"]),
        "domain": domain_key, "description": desc,
        "skills_required": skills[:2],
        "stipend": 0 if RNG.random() < 0.4 else RNG.choice([5000, 6000, 8000, 10000]),
        "duration_months": RNG.choice([2, 3]),
        "openings": RNG.choice([1, 2]),
        "apply_url": f"https://{domain}/careers",
        "posted_date": posted, "deadline": None,
        "source": RNG.choice(["scraped", "partner"]),
    }


def _free_mail_listing(i: int) -> dict:
    """Small startup hiring from a gmail/yahoo address — no scam signals, but a
    free-provider recruiter domain. Lands in the Amber band with a warning."""
    domain_key = RNG.choice(list(GENUINE_JD.keys()))
    title, skills = RNG.choice(GENUINE_JD[domain_key])
    handle = RNG.choice(["hr.team", "internships", "talent", "careers", "hiring"])
    provider = RNG.choice(["gmail.com", "outlook.com", "yahoo.in"])
    company = RNG.choice([
        "Brightpath Solutions", "Nimbus Webworks", "Craftly Studio", "Datawise Consulting",
        "Skyline Robotics Lab", "Pixelforge Media", "Greenfield Analytics", "Codecraft Academy",
    ])
    posted = date.today() - timedelta(days=RNG.randint(2, 40))
    desc = (f"{company} is a small product team building tools for {domain_key.split()[0].lower()} "
            f"workflows. As a {title} you will work directly with the founders on live features, "
            f"write code, test it and see it ship to real users. Requirements: {', '.join(skills)}. "
            f"Mentorship, certificate and a letter of recommendation are provided. "
            f"Interviews are conversational plus a small practical task.")
    return {
        "title": title, "company": company,
        "company_domain": provider,
        "contact_email": f"{handle}{RNG.randint(1, 99)}@{provider}",
        "location": RNG.choice(LOCATIONS + ["Remote (India)"]),
        "work_mode": RNG.choice(["remote", "hybrid"]),
        "domain": domain_key, "description": desc,
        "skills_required": skills[: RNG.randint(2, 4)],
        "stipend": RNG.choice([6000, 8000, 10000, 12000, 15000]),
        "duration_months": RNG.choice([2, 3, 3, 4]),
        "openings": RNG.choice([1, 2]),
        "apply_url": f"https://{provider.split('.')[0]}.com/{company.split()[0].lower()}-careers",
        "posted_date": posted,
        "deadline": posted + timedelta(days=RNG.randint(15, 45)) if RNG.random() < 0.5 else None,
        "source": "scraped",
    }


def seed_listings(total: int = 500, suspicious_ratio: float = 0.30) -> list[Internship]:
    """Build a realistic corpus: solid genuine listings, a cautionary Amber band
    (thin listings + free-mail recruiters) and a Red band of scam listings."""
    risky_total = int(total * suspicious_ratio)          # ~30% scam-tier
    amber_total = int(total * 0.20)                      # ~20% Amber band
    genuine_total = total - risky_total - amber_total

    rows: list[Internship] = []
    for i in range(genuine_total):
        rows.append(Internship(**_genuine_listing(i)))

    # Amber band: weak-but-honest listings and free-mail recruiters
    thin = int(amber_total * 0.4)
    for i in range(thin):
        rows.append(Internship(**_thin_listing(i)))
    for i in range(amber_total - thin):
        rows.append(Internship(**_free_mail_listing(i)))

    # Red band: blacklisted / brand-new-domain / free-mail scam shells
    tiers = (["blacklisted"] * int(risky_total * 0.40)
             + ["newdomain"] * int(risky_total * 0.38)
             + ["freemail"] * int(risky_total * 0.22))
    while len(tiers) < risky_total:
        tiers.append("newdomain")
    RNG.shuffle(tiers)
    for i, tier in enumerate(tiers):
        rows.append(Internship(**_suspicious_listing(1000 + i, tier)))

    RNG.shuffle(rows)
    db.session.add_all(rows)
    db.session.commit()
    return rows


# ----------------------------------------------------------------- student gens
def _student_skills(branch_skills: list[str], n: int = 12) -> dict[str, float]:
    """Pick a plausible skill set and weight it into a normalised vector."""
    pool = list(branch_skills)
    # add adjacent skills from the same categories
    cats = {SKILL_TAXONOMY[s]["category"] for s in pool if s in SKILL_TAXONOMY}
    adjacent = [s for s, m in SKILL_TAXONOMY.items() if m["category"] in cats]
    pool = list(dict.fromkeys(pool + RNG.sample(adjacent, min(len(adjacent), 10))))
    soft = ["communication skills", "problem solving", "teamwork", "time management", "leadership"]
    raw: dict[str, float] = {}
    for skill in RNG.sample(pool, min(n, len(pool))):
        raw[skill] = round(RNG.uniform(0.35, 1.0), 3)
    for skill in RNG.sample(soft, RNG.randint(1, 3)):
        raw[skill] = round(RNG.uniform(0.3, 0.7), 3)
    total = sum(raw.values())
    return {k: round(v / total, 5) for k, v in sorted(raw.items(), key=lambda kv: -kv[1])}


def _skill_details_from_vector(vector: dict[str, float]) -> list[dict]:
    mx = max(vector.values()) if vector else 1.0
    details = []
    for skill, w in sorted(vector.items(), key=lambda kv: -kv[1]):
        meta = SKILL_TAXONOMY.get(skill, {"category": "Other"})
        details.append({
            "skill": skill, "category": meta["category"],
            "weight": round(w / mx, 3), "raw_score": round(w * 40, 3),
            "mentions": max(1, int(round(w * 20))),
            "found_in": RNG.sample(["skills", "experience", "projects", "certifications"],
                                   RNG.randint(1, 2)),
        })
    return details


def seed_students(count: int = 50) -> list[StudentProfile]:
    profiles: list[StudentProfile] = []
    used_emails: set[str] = set()

    for i in range(count):
        first = FIRST_NAMES[i % len(FIRST_NAMES)]
        last = LAST_NAMES[(i * 7) % len(LAST_NAMES)]
        name = f"{first} {last}"
        email = f"{first.lower()}.{last.lower()}{i}@student.internmatch.ai"
        if email in used_emails:
            email = f"{first.lower()}{i}@student.internmatch.ai"
        used_emails.add(email)

        branch, branch_group, branch_skills = RNG.choice(BRANCHES)
        domain_scores = {}
        for d, signals in DOMAIN_SIGNALS.items():
            overlap = len(set(signals) & set(branch_skills))
            if overlap:
                domain_scores[d] = overlap
        preferred = RNG.choices(
            list(domain_scores.keys()),
            weights=[v ** 2 for v in domain_scores.values()],
        )[0] if domain_scores else RNG.choice(DOMAINS)

        vector = _student_skills(branch_skills)
        details = _skill_details_from_vector(vector)
        skills = [d["skill"] for d in details]

        user = User(name=name, email=email, role="student",
                    phone=f"9{RNG.randint(100000000, 899999999)}")
        user.set_password("Student@123")
        db.session.add(user)
        db.session.flush()

        has_resume = RNG.random() < 0.62
        resume_text = None
        meta: dict = {}
        ats = 0
        if has_resume:
            resume_text = build_resume_text(
                name=name,
                skills=skills,
                cgpa=round(RNG.uniform(6.4, 9.6), 2),
                college=RNG.choice(COLLEGES),
                branch=branch,
                grad_year=RNG.choice([2026, 2027, 2027, 2028]),
                projects=RNG.sample(
    [
        f"{RNG.choice(['Smart', 'Real-time', 'AI-powered', 'Distributed', 'Automated'])} "
        + RNG.choice([
            'Attendance System',
            'Chatbot',
            'Recommendation Engine',
            'Dashboard',
            'Monitoring Platform',
            'Trading Bot',
            'Campus Portal',
            'Vision Model'
        ])
        for _ in range(3)
    ],
    2
),
                experience=RNG.choice([
                    f"Intern, {RNG.choice(GENUINE_COMPANIES)[0]} — Jun {2025} - Aug {2025}",
                    "", "",
                ]),
            )
            analysis = {
                "skills": skills, "skill_details": details,
                "meta": {"degree": "B.Tech", "cgpa": round(RNG.uniform(6.4, 9.6), 2),
                         "word_count": len(resume_text.split()), "emails": [email],
                         "phones": [], "links": ["https://github.com/demo"],
                         "project_count": 2, "sections_found": ["skills", "projects",
                                                                "education", "experience"]},
            }
            meta = analysis["meta"]
            ats = compute_ats_score(resume_text, details, meta)

        profile = StudentProfile(
            user_id=user.id,
            roll_number=f"{branch_group[:2].upper()}{RNG.randint(2019, 2023)}{RNG.randint(100, 999)}",
            college=RNG.choice(COLLEGES),
            branch=branch,
            graduation_year=RNG.choice([2026, 2027, 2027, 2028]),
            cgpa=round(RNG.uniform(6.2, 9.7), 2),
            preferred_domain=preferred,
            preferred_location=RNG.choice(LOCATIONS),
            work_mode_pref=RNG.choices(["any", "onsite", "hybrid", "remote"],
                                       weights=[0.4, 0.25, 0.2, 0.15])[0],
            phone=user.phone,
            resume_filename=f"{first.lower()}_{last.lower()}_resume.pdf" if has_resume else None,
            resume_text=resume_text,
            resume_uploaded_at=datetime.utcnow() - timedelta(days=RNG.randint(1, 60))
            if has_resume else None,
            skills=skills,
            skill_details=details,
            skill_vector=vector,
            parsed_meta=meta,
            ats_score=ats,
        )
        db.session.add(profile)
        db.session.flush()
        profiles.append(profile)

        if has_resume:
            db.session.add(ResumeUpload(
                student_id=profile.id,
                filename=profile.resume_filename,
                file_type="pdf", size_bytes=RNG.randint(90_000, 420_000),
                skills_found=len(skills), ats_score=ats,
                text_chars=len(resume_text or ""),
                created_at=profile.resume_uploaded_at,
            ))

    db.session.commit()
    return profiles


# ----------------------------------------------------------------- interactions
STATUS_WEIGHTS = [("applied", 0.34), ("under_review", 0.26), ("shortlisted", 0.16),
                  ("interview", 0.12), ("selected", 0.07), ("rejected", 0.05)]


def seed_applications(profiles: list[StudentProfile], internships: list[Internship]) -> None:
    if not internships:
        return
    statuses = [s for s, _ in STATUS_WEIGHTS]
    weights = [w for _, w in STATUS_WEIGHTS]
    rows = []

    for profile in profiles:
        picks = RNG.sample(internships, RNG.randint(4, 9))
        for listing in picks:
            overlap = len(set(profile.skills or []) & set(listing.skills_required or []))
            base = min(0.35 + overlap * 0.14, 0.96)
            if listing.domain == profile.preferred_domain:
                base = min(base + 0.10, 0.99)
            status = RNG.choices(statuses, weights=weights)[0]
            applied_at = datetime.utcnow() - timedelta(days=RNG.randint(1, 55))
            rows.append(Application(
                student_id=profile.id, internship_id=listing.id,
                status=status, match_score=round(base, 4), applied_at=applied_at,
                notes=RNG.choice([None, None, "Applied via company portal",
                                  "Referred by senior", "Followed up on email"]),
            ))

        # feedback from a subset of students (drives admin analytics)
        if RNG.random() < 0.45:
            for listing in RNG.sample(picks, min(2, len(picks))):
                flagged = listing.fraud_flag or (listing.trust_score or 0) < 50
                rows.append(Feedback(
                    student_id=profile.id, internship_id=listing.id,
                    rating=RNG.choice([1, 2, 2, 3]) if flagged else RNG.choice([2, 3, 4, 4, 5, 5]),
                    verdict="Suspicious" if flagged else "Verified",
                    comment=RNG.choice([
                        "Asked for a registration fee on WhatsApp — clearly a scam.",
                        "No fee requested, interview process was professional.",
                        "Recruiter was responsive and shared the offer letter.",
                        "Salary promise looked unrealistic for an intern role.",
                        "Listing details matched what HR told me on the call.",
                        "Domain looked new and the only contact was a form link.",
                        None,
                    ]),
                    created_at=datetime.utcnow() - timedelta(days=RNG.randint(0, 30)),
                ))
    db.session.add_all(rows)
    db.session.commit()


def seed_domain_intel(limit: int = 220) -> int:
    domains = {c[1] for c in GENUINE_COMPANIES} | {c[1] for c in MID_COMPANIES} | \
              {c[1] for c in FAKE_COMPANIES}
    from services.domain_intel import lookup_domain

    count = 0
    for domain in sorted(domains)[:limit]:
        lookup_domain(domain, use_cache=True)
        count += 1
    return count


def seed_all(listings: int = 500, students: int = 50) -> dict:
    """Wipe + reseed everything. Safe to run repeatedly."""
    reset_database()

    admin = User(name="Placement Admin", email="admin@internmatch.ai", role="admin",
                 phone="9880012345")
    admin.set_password("Admin@123")
    demo = User(name="Demo Student", email="student1@internmatch.ai", role="student",
                phone="9880054321")
    demo.set_password("Student@123")
    db.session.add_all([admin, demo])
    db.session.flush()

    demo_vector = {
        "python": 0.142, "machine learning": 0.121, "sql": 0.104, "pandas": 0.096,
        "flask": 0.083, "scikit-learn": 0.079, "nlp": 0.072, "data visualization": 0.061,
        "docker": 0.052, "git": 0.048, "rest api": 0.041, "communication skills": 0.036,
        "statistics": 0.033, "numpy": 0.032,
    }
    demo_details = _skill_details_from_vector(demo_vector)
    demo_resume = build_resume_text(
        name="Demo Student", skills=list(demo_vector.keys()), cgpa=8.6,
        college="NIT Surathkal", branch="Computer Science", grad_year=2027,
        projects=["AI-Powered Internship Recommender", "Campus Placement Analytics Dashboard"],
        experience="Data Science Intern, Tantra Analytics — Jun 2025 - Aug 2025",
    )
    demo_profile = StudentProfile(
        user_id=demo.id, roll_number="CS2021042", college="NIT Surathkal",
        branch="Computer Science", graduation_year=2027, cgpa=8.6,
        preferred_domain="Data Science & ML", preferred_location="Bengaluru, KA",
        work_mode_pref="hybrid", phone=demo.phone,
        resume_filename="demo_student_resume.pdf", resume_text=demo_resume,
        resume_uploaded_at=datetime.utcnow() - timedelta(days=3),
        skills=list(demo_vector.keys()), skill_details=demo_details,
        skill_vector=demo_vector,
        parsed_meta=parse_meta(demo_resume) | {"degree": "B.Tech"},
        ats_score=compute_ats_score(demo_resume, demo_details, parse_meta(demo_resume)),
    )
    db.session.add(demo_profile)
    db.session.flush()

    listing_rows = seed_listings(listings)
    student_rows = seed_students(max(students - 1, 0))
    all_profiles = [demo_profile] + student_rows

    # ---- trust scoring (precomputed and persisted for every listing) ----
    from services.trust_engine import evaluate_listing, badge_for

    for listing in listing_rows:
        result = evaluate_listing(listing)
        db.session.add(TrustAuditLog(
            internship_id=listing.id, actor="seed", action="create",
            new_score=result["trust_score"], new_badge=result["badge"],
            note="Initial scoring during demo seed"))
    db.session.commit()

    seed_applications(all_profiles, listing_rows)
    seed_domain_intel()
    invalidate_index()

    flagged = sum(1 for l in listing_rows if l.fraud_flag)
    stats = {
        "listings": len(listing_rows),
        "flagged": flagged,
        "students": len(all_profiles),
        "applications": Application.query.count(),
        "feedback": Feedback.query.count(),
        "avg_trust": round(sum(l.trust_score or 0 for l in listing_rows) / max(len(listing_rows), 1), 1),
        "green": sum(1 for l in listing_rows if l.badge == "Green"),
        "amber": sum(1 for l in listing_rows if l.badge == "Amber"),
        "red": sum(1 for l in listing_rows if l.badge == "Red"),
    }
    return stats


def reset_database() -> None:
    """Drop and recreate all tables (used by `flask seed`).

    ``db.session.remove()`` first is required on MySQL: any session that has read
    a table holds a metadata lock until its transaction ends, and DDL such as
    ``DROP TABLE`` blocks on that lock. SQLite is unaffected.
    """
    db.session.remove()
    db.drop_all()
    db.create_all()

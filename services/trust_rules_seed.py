"""
Labelled text corpus used to train the ML fraud classifier.

Fraud samples reflect real-world Indian fake-internship scam copy (fee demands,
UPI rails, urgency, guaranteed placement). Genuine samples reflect authentic
campus-hiring job descriptions.
"""

FRAUD_SEED_TEXT: list[str] = [
    "Urgent hiring interns work from home. Registration fee of Rs 499 is mandatory to confirm your seat. "
    "No interview required, selected candidates will get direct joining letter within 24 hours. "
    "Pay the registration amount to our UPI id and share the screenshot on WhatsApp for confirmation.",

    "Earn 35000 per month from home as a data entry intern. No experience needed, any graduate can apply. "
    "Limited seats available hurry up. Refundable security deposit of 999 rupees required before onboarding. "
    "Contact us on WhatsApp only for details and payment details.",

    "Guaranteed internship with placement guarantee 100 percent job guarantee certificate after completion. "
    "Processing fee 750. Transfer to the given account number and share IFSC receipt. Immediate joining, no skills required.",

    "Work from home part time typing job. Simple copy paste work earning unlimited income per task. "
    "Registration charge 250 rupees via gpay phonepe paytm. Selected directly without interview. "
    "Payment commission based per referral also available.",

    "Congratulations you are shortlisted for our internship program. To activate your intern id pay the "
    "training fee. Send your aadhaar card and pan card copy with bank details for verification. "
    "Only 5 slots left applies fast before deadline today.",

    "Hiring interns for our new startup. Onboarding fee of rs 1200 covers laptop and kit charges. "
    "100 percent assured stipend 45000 monthly. No interview direct selection. "
    "Share otp received on your phone to our telegram for verification.",

    "Registration charge for internship certificate is 599 only. Internship completion certificate with "
    "verified stamp within 7 days. Guaranteed job placement in mnc with assured salary package. "
    "Deposit the amount through neft and mail the receipt.",

    "Stipend now earning opportunity for students. Earn 20000 weekly simple survey filling work from home. "
    "No experience needed. Join telegram channel for tasks. Referral income and incentive payment per sale. "
    "Aadhaar required must submit before task allotment.",

    "Limited seats urgent requirement for internship in our company. Application fee 300 non refundable. "
    "Selected directly without interview. Direct joining letter. Payment accepted by upi only. "
    "Contact hr on whatsapp number given below. Hurry last date today.",

    "internship verification portal verify your internship certificate now. Pay verification fee 199. "
    "Our portal provides instant verified certificate for students. Registration charge applicable per certificate. "
    "Complete payment through bank transfer and get certificate in 1 hour.",

    "Placement guarantee program for final year students. 100 percent placement assurance after internship. "
    "Course fee 4500 payable in 2 installments. Guaranteed job in partnered mnc companies. "
    "Deposit the fee amount to account and mail us the transaction id.",

    "Easy money internship work from home. Simple typing data entry copy paste jobs. Earn unlimited salary "
    "50000 per month. No interview no experience needed. Processing charge 500 to generate your employee id. "
    "Pay using paytm gpay phonepe and share screenshot on whatsapp.",

    "Urgent hiring female and male interns for online promotion. Commission based per sale payment. "
    "Registration fee 350 refundable after 10 tasks. No interview, direct joining, work from home, "
    "no experience needed, apply fast limited slots, contact only on telegram.",

    "Get internship certificate without doing internship. Fee 899 for certificate with verification qr code. "
    "Instant certificate, no interview, no project work. Send aadhaar card and passport photo for registration. "
    "Payment via upi or google pay, certificate delivered in 24 hours guaranteed.",
]

GENUINE_SEED_TEXT: list[str] = [
    "Software Engineering Intern, Platform Team. You will build and ship production microservices in Python and "
    "Flask, write unit tests with pytest, participate in code reviews and design discussions. "
    "Strong fundamentals in data structures, algorithms and SQL required. Familiarity with Docker and Git "
    "is a plus. Interns work directly with senior engineers on live features and receive structured mentorship.",

    "Data Science Intern. Work with the analytics team on customer churn models, feature engineering and "
    "experiment design. Requirements: Python, pandas, scikit-learn, solid statistics, and the ability to "
    "communicate findings to business stakeholders. You will own a scoped summer project and present results.",

    "Frontend Developer Intern. Build responsive interfaces with React, TypeScript and Tailwind for our merchant "
    "dashboard. You should understand REST APIs, accessibility basics, and component testing with Jest. "
    "Portfolio or GitHub links appreciated. Hybrid schedule with 3 days in office.",

    "Marketing Analytics Intern. Assist with campaign attribution, funnel reporting and dashboarding in "
    "Power BI. Skills: advanced Excel, SQL, digital marketing fundamentals, strong written communication. "
    "You will work with the growth team on weekly performance reviews.",

    "Cybersecurity Intern, SOC rotation. Support the security operations team with log triage, SIEM alert "
    "tuning and vulnerability assessment using Burp Suite and Nessus. Coursework in networking, Linux and "
    "OWASP Top 10 expected. Certification stipend allowance provided on completion.",

    "Mechanical Design Intern. Support the chassis team with CAD modelling in SolidWorks, tolerance analysis "
    "and FEA validation using ANSYS. Final year BE/BTech students in Mechanical with coursework in strength "
    "of materials. On-site internship at our manufacturing plant with mentor supervision.",

    "Business Analyst Intern. Gather requirements, write user stories and maintain the sprint backlog in Jira. "
    "You will work with product managers on roadmap prioritisation and stakeholder interviews. "
    "Strong communication skills, Excel and an understanding of agile delivery required.",

    "Android Development Intern. Build features for our consumer app in Kotlin with Jetpack Compose, "
    "integrate REST APIs and improve app performance. Familiarity with MVVM architecture, Git and "
    "Play Store release process preferred. You will ship to a real user base.",

    "Cloud & DevOps Intern. Automate deployment pipelines with GitHub Actions, maintain Terraform modules and "
    "support Kubernetes workloads on AWS. Requirements: Linux fundamentals, bash scripting, Docker, "
    "CI/CD concepts. You will get hands-on production exposure with mentoring from SREs.",

    "Embedded Systems Intern. Develop firmware for IoT sensor nodes in embedded C on ARM Cortex-M "
    "microcontrollers, debug with oscilloscopes and integrate MQTT telemetry. Coursework in microcontrollers, "
    "RTOS concepts and circuit design required. Lab access provided at our hardware facility.",

    "UI/UX Design Intern. Conduct user research, create wireframes and high-fidelity prototypes in Figma for "
    "our B2B product. You will partner with engineers to ship design iterations and maintain the design system. "
    "Portfolio required. Design critique culture, weekly mentorship.",

    "Civil Engineering Intern. Assist the structural team with RCC design calculations, AutoCAD drawings and "
    "STAAD Pro analysis for commercial projects. Site visits to ongoing projects with safety induction. "
    "Third year Civil Engineering students preferred.",

    "Machine Learning Intern, NLP team. Build retrieval and ranking components for our document assistant "
    "using transformers, embeddings and vector search. Requirements: Python, PyTorch or TensorFlow, "
    "strong NLP coursework, experience with Hugging Face libraries. Publication encouraged but not required.",

    "Quality Assurance Intern. Write and execute test cases, automate regression suites with Selenium and "
    "pytest, and log defects in Jira. Exposure to API testing with Postman and basics of SQL expected. "
    "You will work alongside the QA lead on release sign-off.",

    "Finance Intern, Corporate Development. Support financial modelling, variance analysis and competitor "
    "research. Advanced Excel and accounting fundamentals required; CFA Level 1 candidates welcome. "
    "You will prepare monthly management review decks with the FP&A team.",

    "Product Management Intern. Own a small feature area end to end: user interviews, PRD writing, "
    "prioritisation and launch metrics. Need strong analytical skills, SQL comfort and clear communication. "
    "Weekly reviews with the product leadership team.",
]

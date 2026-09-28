"""
Skill taxonomy for engineering internships.

Each skill maps to a category and a list of surface aliases matched by the NLP
extractor (multi-word aliases are matched as n-grams).
"""

SKILL_TAXONOMY: dict[str, dict] = {
    # ---------------- Programming languages ----------------
    "python": {"category": "Programming", "aliases": ["python", "python3", "py"]},
    "java": {"category": "Programming", "aliases": ["java", "core java", "java 8", "java8"]},
    "javascript": {"category": "Programming", "aliases": ["javascript", "js", "es6", "ecmascript"]},
    "typescript": {"category": "Programming", "aliases": ["typescript", "ts"]},
    "c": {"category": "Programming", "aliases": ["c language", "c programming", "ansi c"]},
    "c++": {"category": "Programming", "aliases": ["c++", "cpp", "c plus plus", "stl"]},
    "c#": {"category": "Programming", "aliases": ["c#", "csharp", "dotnet c#"]},
    "go": {"category": "Programming", "aliases": ["golang", "go lang"]},
    "rust": {"category": "Programming", "aliases": ["rust", "rustlang"]},
    "php": {"category": "Programming", "aliases": ["php", "laravel php"]},
    "ruby": {"category": "Programming", "aliases": ["ruby", "ruby on rails"]},
    "kotlin": {"category": "Programming", "aliases": ["kotlin"]},
    "swift": {"category": "Programming", "aliases": ["swift", "swiftui"]},
    "scala": {"category": "Programming", "aliases": ["scala"]},
    "r": {"category": "Programming", "aliases": ["r programming", "r language", "rstudio"]},
    "matlab": {"category": "Programming", "aliases": ["matlab", "simulink"]},
    "sql": {"category": "Databases", "aliases": ["sql", "structured query language"]},
    "pl/sql": {"category": "Databases", "aliases": ["pl/sql", "plsql"]},
    "bash": {"category": "Programming", "aliases": ["bash", "shell scripting", "shell script"]},
    "solidity": {"category": "Blockchain", "aliases": ["solidity", "smart contract", "web3.js"]},

    # ---------------- Web / frontend ----------------
    "html": {"category": "Web", "aliases": ["html", "html5"]},
    "css": {"category": "Web", "aliases": ["css", "css3", "scss", "sass"]},
    "react": {"category": "Web", "aliases": ["react", "react.js", "reactjs", "react hooks"]},
    "next.js": {"category": "Web", "aliases": ["next.js", "nextjs", "next js"]},
    "angular": {"category": "Web", "aliases": ["angular", "angularjs", "angular 12"]},
    "vue": {"category": "Web", "aliases": ["vue", "vue.js", "vuejs"]},
    "bootstrap": {"category": "Web", "aliases": ["bootstrap", "bootstrap 5"]},
    "tailwind": {"category": "Web", "aliases": ["tailwind", "tailwindcss"]},
    "jquery": {"category": "Web", "aliases": ["jquery"]},
    "redux": {"category": "Web", "aliases": ["redux", "redux toolkit"]},
    "rest api": {"category": "Web", "aliases": ["rest api", "restful", "rest apis", "api development"]},
    "graphql": {"category": "Web", "aliases": ["graphql", "apollo graphql"]},
    "web accessibility": {"category": "Web", "aliases": ["wcag", "web accessibility", "a11y"]},

    # ---------------- Backend frameworks ----------------
    "flask": {"category": "Backend", "aliases": ["flask", "flask-restful"]},
    "django": {"category": "Backend", "aliases": ["django", "django rest framework", "drf"]},
    "fastapi": {"category": "Backend", "aliases": ["fastapi"]},
    "node.js": {"category": "Backend", "aliases": ["node.js", "nodejs", "node js", "express.js"]},
    "spring boot": {"category": "Backend", "aliases": ["spring boot", "springboot", "spring mvc"]},
    ".net": {"category": "Backend", "aliases": [".net", "asp.net", "dotnet", ".net core"]},
    "microservices": {"category": "Backend", "aliases": ["microservices", "microservice architecture"]},
    "graphql server": {"category": "Backend", "aliases": ["apollo server", "graphql federation"]},
    "webrtc": {"category": "Backend", "aliases": ["webrtc", "socket.io", "websockets"]},

    # ---------------- Data / ML ----------------
    "machine learning": {"category": "Data Science", "aliases": ["machine learning", "ml models", "supervised learning", "predictive modeling"]},
    "deep learning": {"category": "Data Science", "aliases": ["deep learning", "neural networks", "cnn", "rnn", "lstm"]},
    "nlp": {"category": "Data Science", "aliases": ["nlp", "natural language processing", "text mining", "nltk", "spacy", "transformers", "bert"]},
    "computer vision": {"category": "Data Science", "aliases": ["computer vision", "opencv", "image processing", "yolo"]},
    "scikit-learn": {"category": "Data Science", "aliases": ["scikit-learn", "sklearn", "scikit learn"]},
    "tensorflow": {"category": "Data Science", "aliases": ["tensorflow", "keras"]},
    "pytorch": {"category": "Data Science", "aliases": ["pytorch", "torch"]},
    "pandas": {"category": "Data Science", "aliases": ["pandas"]},
    "numpy": {"category": "Data Science", "aliases": ["numpy"]},
    "data analysis": {"category": "Data Science", "aliases": ["data analysis", "exploratory data analysis", "eda", "data wrangling"]},
    "data visualization": {"category": "Data Science", "aliases": ["data visualization", "matplotlib", "seaborn", "plotly", "tableau", "power bi", "looker studio"]},
    "statistics": {"category": "Data Science", "aliases": ["statistics", "statistical analysis", "hypothesis testing", "probability"]},
    "big data": {"category": "Data Science", "aliases": ["big data", "hadoop", "spark", "pyspark", "hive"]},
    "etl": {"category": "Data Science", "aliases": ["etl", "data pipeline", "airflow", "data warehousing"]},
    "llm engineering": {"category": "Data Science", "aliases": ["llm", "large language model", "langchain", "rag", "prompt engineering", "generative ai", "openai api"]},
    "mlops": {"category": "Data Science", "aliases": ["mlops", "model deployment", "mlflow", "feature store"]},
    "recommendation systems": {"category": "Data Science", "aliases": ["recommendation system", "recommender system", "collaborative filtering"]},

    # ---------------- Databases ----------------
    "mysql": {"category": "Databases", "aliases": ["mysql", "mariadb"]},
    "postgresql": {"category": "Databases", "aliases": ["postgresql", "postgres"]},
    "mongodb": {"category": "Databases", "aliases": ["mongodb", "mongo", "mongoose"]},
    "redis": {"category": "Databases", "aliases": ["redis", "caching layer"]},
    "sqlite": {"category": "Databases", "aliases": ["sqlite", "sqlite3"]},
    "database design": {"category": "Databases", "aliases": ["database design", "normalization", "erd", "schema design"]},
    "elasticsearch": {"category": "Databases", "aliases": ["elasticsearch", "opensearch", "kibana"]},

    # ---------------- DevOps / Cloud ----------------
    "docker": {"category": "DevOps", "aliases": ["docker", "containerization", "containers"]},
    "kubernetes": {"category": "DevOps", "aliases": ["kubernetes", "k8s", "helm"]},
    "aws": {"category": "Cloud", "aliases": ["aws", "amazon web services", "ec2", "s3", "lambda"]},
    "azure": {"category": "Cloud", "aliases": ["azure", "microsoft azure", "azure devops"]},
    "gcp": {"category": "Cloud", "aliases": ["gcp", "google cloud", "bigquery", "cloud run"]},
    "ci/cd": {"category": "DevOps", "aliases": ["ci/cd", "jenkins", "github actions", "gitlab ci", "continuous integration"]},
    "linux": {"category": "DevOps", "aliases": ["linux", "ubuntu", "unix", "centos", "bash shell"]},
    "terraform": {"category": "DevOps", "aliases": ["terraform", "infrastructure as code", "iac"]},
    "monitoring": {"category": "DevOps", "aliases": ["prometheus", "grafana", "observability", "datadog", "monitoring"]},
    "networking": {"category": "DevOps", "aliases": ["networking", "tcp/ip", "dns", "load balancer", "vpn"]},
    "git": {"category": "DevOps", "aliases": ["git", "github", "gitlab", "bitbucket", "version control"]},
    "nginx": {"category": "DevOps", "aliases": ["nginx", "apache server", "reverse proxy"]},

    # ---------------- Mobile ----------------
    "android": {"category": "Mobile", "aliases": ["android", "android studio", "jetpack compose"]},
    "ios": {"category": "Mobile", "aliases": ["ios", "xcode", "swift ios"]},
    "react native": {"category": "Mobile", "aliases": ["react native"]},
    "flutter": {"category": "Mobile", "aliases": ["flutter", "dart"]},

    # ---------------- Security ----------------
    "cybersecurity": {"category": "Security", "aliases": ["cybersecurity", "information security", "infosec"]},
    "penetration testing": {"category": "Security", "aliases": ["penetration testing", "pentest", "ethical hacking", "vapt", "burp suite"]},
    "siem": {"category": "Security", "aliases": ["siem", "splunk", "soc analysis", "threat hunting"]},
    "cryptography": {"category": "Security", "aliases": ["cryptography", "encryption", "tls", "pki"]},
    "appsec": {"category": "Security", "aliases": ["owasp", "secure coding", "appsec", "vulnerability assessment"]},

    # ---------------- QA ----------------
    "testing": {"category": "QA", "aliases": ["unit testing", "pytest", "junit", "test cases", "jest"]},
    "selenium": {"category": "QA", "aliases": ["selenium", "webdriver", "automation testing"]},
    "manual testing": {"category": "QA", "aliases": ["manual testing", "test plan", "regression testing"]},
    "performance testing": {"category": "QA", "aliases": ["jmeter", "load testing", "performance testing"]},

    # ---------------- Core engineering ----------------
    "autocad": {"category": "Core Engineering", "aliases": ["autocad", "autodesk", "catia", "solidworks"]},
    "cad modeling": {"category": "Core Engineering", "aliases": ["cad", "3d modeling", "finite element analysis", "ansys", "fea"]},
    "thermodynamics": {"category": "Core Engineering", "aliases": ["thermodynamics", "heat transfer", "hvac"]},
    "manufacturing": {"category": "Core Engineering", "aliases": ["manufacturing", "lean manufacturing", "six sigma", "cnc", "production planning"]},
    "robotics": {"category": "Core Engineering", "aliases": ["robotics", "ros", "automation systems", "plc"]},
    "embedded c": {"category": "Core Engineering", "aliases": ["embedded c", "microcontroller", "arduino", "rtos", "arm cortex"]},
    "iot": {"category": "Core Engineering", "aliases": ["iot", "internet of things", "esp32", "raspberry pi", "mqtt"]},
    "vlsi": {"category": "Core Engineering", "aliases": ["vlsi", "verilog", "vhdl", "fpga", "asic design"]},
    "power systems": {"category": "Core Engineering", "aliases": ["power systems", "electrical machines", "switchgear", "smart grid"]},
    "structural analysis": {"category": "Core Engineering", "aliases": ["structural analysis", "staad pro", "etabs", "rcc design", "surveying"]},
    "gis": {"category": "Core Engineering", "aliases": ["gis", "arcgis", "remote sensing", "qgis"]},
    "process engineering": {"category": "Core Engineering", "aliases": ["process engineering", "aspen plus", "chemical process", "distillation"]},
    "supply chain": {"category": "Core Engineering", "aliases": ["supply chain", "logistics", "inventory management", "procurement"]},

    # ---------------- Design / product / business ----------------
    "ui/ux design": {"category": "Design", "aliases": ["ui/ux", "ux design", "wireframing", "prototyping", "figma", "adobe xd", "user research"]},
    "graphic design": {"category": "Design", "aliases": ["graphic design", "photoshop", "illustrator", "canva"]},
    "product management": {"category": "Business", "aliases": ["product management", "roadmap", "product analytics", "jira", "agile", "scrum"]},
    "business analysis": {"category": "Business", "aliases": ["business analysis", "requirement gathering", "brd", "stakeholder management"]},
    "digital marketing": {"category": "Business", "aliases": ["digital marketing", "seo", "sem", "google analytics", "content marketing"]},
    "finance": {"category": "Business", "aliases": ["financial modeling", "accounting", "valuation", "tally", "excel modeling"]},
    "excel": {"category": "Business", "aliases": ["advanced excel", "ms excel", "vlookup", "pivot table"]},
    "content writing": {"category": "Business", "aliases": ["content writing", "technical writing", "copywriting", "documentation"]},
    "blockchain": {"category": "Blockchain", "aliases": ["blockchain", "ethereum", "hyperledger", "smart contracts"]},

    # ---------------- Soft skills ----------------
    "communication skills": {"category": "Soft Skills", "aliases": ["communication skills", "presentation skills", "client communication", "public speaking"]},
    "teamwork": {"category": "Soft Skills", "aliases": ["teamwork", "cross-functional collaboration", "team player"]},
    "problem solving": {"category": "Soft Skills", "aliases": ["problem solving", "analytical skills", "critical thinking", "dsa", "data structures", "algorithms"]},
    "leadership": {"category": "Soft Skills", "aliases": ["leadership", "team lead", "event coordinator", "club secretary"]},
    "time management": {"category": "Soft Skills", "aliases": ["time management", "multitasking", "deadline oriented"]},
}

# Invert taxonomy -> alias lookup (longest alias first so n-grams win)
ALIAS_INDEX: dict[str, str] = {}
for _skill, _meta in SKILL_TAXONOMY.items():
    for _alias in _meta["aliases"]:
        ALIAS_INDEX[_alias.lower()] = _skill

MAX_ALIAS_TOKENS = max(len(a.split()) for a in ALIAS_INDEX)

CATEGORY_ORDER = [
    "Programming", "Web", "Backend", "Data Science", "Databases", "Cloud",
    "DevOps", "Mobile", "Security", "QA", "Core Engineering", "Blockchain",
    "Design", "Business", "Soft Skills",
]

# Internship domains -> skills that signal that domain (used for the +0.1
# domain-preference bonus and for domain inference from a resume).
DOMAIN_SIGNALS: dict[str, list[str]] = {
    "Data Science & ML": ["machine learning", "deep learning", "nlp", "pandas", "numpy",
                          "scikit-learn", "tensorflow", "pytorch", "statistics",
                          "data analysis", "data visualization", "llm engineering",
                          "recommendation systems"],
    "Web Development": ["html", "css", "javascript", "react", "angular", "vue", "next.js",
                        "node.js", "rest api", "bootstrap", "typescript", "tailwind"],
    "Backend Engineering": ["flask", "django", "spring boot", "node.js", "fastapi", "microservices",
                            "rest api", "graphql", "redis", "postgresql", "mysql"],
    "Mobile App Development": ["android", "ios", "flutter", "react native", "kotlin", "swift"],
    "Cloud & DevOps": ["aws", "azure", "gcp", "docker", "kubernetes", "ci/cd", "terraform",
                       "linux", "monitoring", "nginx", "git"],
    "Cybersecurity": ["cybersecurity", "penetration testing", "siem", "cryptography", "appsec",
                      "networking", "linux"],
    "Embedded & IoT": ["embedded c", "iot", "robotics", "vlsi", "c"],
    "Mechanical Engineering": ["autocad", "cad modeling", "thermodynamics", "manufacturing", "robotics"],
    "Civil Engineering": ["structural analysis", "autocad", "gis"],
    "Electrical Engineering": ["power systems", "vlsi", "matlab", "embedded c"],
    "QA & Testing": ["testing", "selenium", "manual testing", "performance testing"],
    "UI/UX Design": ["ui/ux design", "graphic design"],
    "Business & Analytics": ["business analysis", "product management", "digital marketing",
                             "finance", "excel", "supply chain"],
    "Blockchain & Web3": ["blockchain", "solidity", "cryptography"],
}

DOMAINS = list(DOMAIN_SIGNALS.keys())

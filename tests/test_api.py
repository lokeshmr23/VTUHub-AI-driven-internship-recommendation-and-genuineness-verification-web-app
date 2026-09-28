"""InternMatch AI — end-to-end API test suite.

    python app.py &            # or: make serve
    python tests/test_api.py   # or: make test
"""
import csv, io, os, sys, time
import requests

B = os.environ.get("BASE_URL", "http://127.0.0.1:8000")
try:
    requests.get(f"{B}/healthz", timeout=4)
except Exception:
    sys.exit(f"Server not reachable at {B} — start it with `python app.py` first.")
ok=fail=0
def check(name, cond, extra=""):
    global ok, fail
    if cond: ok+=1; print(f"  PASS  {name} {extra}")
    else: fail+=1; print(f"  FAIL  {name} {extra}")

print("== health ==")
h=requests.get(f"{B}/healthz").json(); check("healthz", h["status"]=="ok", h.get("listings"))

print("== auth ==")
r=requests.post(f"{B}/api/auth/login", json={"email":"student1@internmatch.ai","password":"Student@123"})
check("student login", r.status_code==200 and r.json().get("access_token"))
stok=r.json()["access_token"]; s_hdr={"Authorization":f"Bearer {stok}"}
check("student profile id", r.json()["user"]["profile"]["id"]==1)

r=requests.post(f"{B}/api/auth/login", json={"email":"admin@internmatch.ai","password":"Admin@123"})
atok=r.json()["access_token"]; a_hdr={"Authorization":f"Bearer {atok}"}
check("admin login", r.status_code==200)
check("bad login rejected", requests.post(f"{B}/api/auth/login", json={"email":"x@y.com","password":"nope"}).status_code==401)
check("no-token blocked", requests.get(f"{B}/api/recommendations/1").status_code==401)
check("student blocked from admin", requests.get(f"{B}/api/admin/flagged", headers=s_hdr).status_code==403)
check("register validates", requests.post(f"{B}/api/auth/register", json={"name":"A","email":"bad","password":"123"}).status_code==400)

print("== resume upload (PDF + DOCX) ==")
with open("samples/resumes/2_rohan_iyer_resume.pdf","rb") as f:
    r=requests.post(f"{B}/api/upload-resume", headers=s_hdr, files={"resume":("rohan.pdf",f,"application/pdf")})
d=r.json(); check("PDF upload", r.status_code==201, f"{len(d.get('extraction',{}).get('skills',[]))} skills, ATS {d.get('extraction',{}).get('ats_score')}")
check("PDF skills extracted", {"python","machine learning","nlp"} <= set(d["extraction"]["skills"]))
check("domain inferred", d["extraction"]["top_domain"] is not None, d["extraction"]["top_domain"])
r=requests.get(f"{B}/api/student/profile/1", headers=s_hdr); pd=r.json()
check("profile after upload", r.status_code==200 and pd["stats"]["total_skills"]>10, f"{pd['stats']}")
check("student cannot read others", requests.get(f"{B}/api/student/profile/2", headers=s_hdr).status_code==403)
check("admin can read others", requests.get(f"{B}/api/student/profile/2", headers=a_hdr).status_code==200)

import docx
doc=docx.Document(); doc.add_paragraph("Test Student"); doc.add_paragraph("Skills: Python, Flask, MySQL, Docker, React")
doc.add_paragraph("Projects\nBuilt a REST API with Flask and MySQL. Deployed on AWS with Docker.")
doc.add_paragraph("Education\nB.Tech Computer Science, 2027. CGPA 8.4")
doc.save("/tmp/test.docx")
with open("/tmp/test.docx","rb") as f:
    r=requests.post(f"{B}/api/upload-resume", headers=s_hdr, files={"resume":("test.docx",f,"application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
check("DOCX upload", r.status_code==201, r.json().get("message","")[:60])
with open("/tmp/t.txt","w") as f: f.write("hello")
with open("/tmp/t.txt","rb") as f:
    check("bad filetype rejected", requests.post(f"{B}/api/upload-resume", headers=s_hdr, files={"resume":("t.txt",f)}).status_code==400)

print("== profile / recommendations ==")

r=requests.get(f"{B}/api/recommendations/1?limit=8", headers=s_hdr); d=r.json()
recs=d["recommendations"]
check("recommendations", r.status_code==200 and len(recs)==8, f"{len(recs)} recs")
check("ranked descending", all(recs[i]["match_pct"]>=recs[i+1]["match_pct"] for i in range(len(recs)-1)))
check("match_pct 0-100", all(0<=x["match_pct"]<=100 for x in recs))
check("has matched skills", any(x["matched_skills"] for x in recs))
rb=requests.get(f"{B}/api/recommendations/1?domain=Data%20Science%20%26%20ML&limit=6", headers=s_hdr).json()
check("domain bonus applied", all(x["domain_bonus_applied"] and x["domain_bonus"]==0.1 for x in rb["recommendations"]), f"{len(rb['recommendations'])} boosted")
rn=requests.get(f"{B}/api/recommendations/1?domain=Web%20Development&limit=6", headers=s_hdr).json()
check("no bonus off-domain", all(not x["domain_bonus_applied"] for x in rn["recommendations"]))
check("explanation string", bool(recs[0]["explanation"]))
r2=requests.get(f"{B}/api/recommendations/1?domain=Data%20Science%20%26%20ML&min_trust=60", headers=s_hdr).json()
check("filters apply", all(x["internship"]["domain"]=="Data Science & ML" and x["internship"]["trust_score"]>=60 for x in r2["recommendations"]))
r3=requests.get(f"{B}/api/recommendations/49?include_flagged=false", headers=a_hdr).json()
check("flagged excluded", all(not x["internship"]["fraud_flag"] for x in r3["recommendations"]))

print("== internships browse / trustscore ==")
d=requests.get(f"{B}/api/internships?per_page=5&sort=trust", headers=s_hdr).json()
check("listings paginated", len(d["internships"])==5 and d["meta"]["total"]>400, f"total={d['meta']['total']}")
fid=requests.get(f"{B}/api/internships?flagged=true&per_page=1", headers=s_hdr).json()["internships"][0]["id"]
r=requests.get(f"{B}/api/trustscore/{fid}", headers=s_hdr); t=r.json()["trust"]
check("trustscore endpoint", r.status_code==200 and 0<=t["trust_score"]<=100)
check("breakdown components", all(k in t["breakdown"] for k in ["domain","red_flags","completeness","ml","formula"]))
check("formula matches score", t["breakdown"]["formula"]["computed"]==t["trust_score"])
check("flagged listing has red flags", t["fraud_flag"] and len(t["red_flags"])>0, t["red_flags"][0]["label"][:44] if t["red_flags"] else "")
check("domain intel present", t["domain"]["domain"] and "reputation" in t["domain"])
calc = round((0.5*t["rule_score"] + 0.5*(1-t["ml_fraud_prob"]))*100)
check("score == formula", abs(calc - t["trust_score"])<=1, f"{calc} vs {t['trust_score']}")
r=requests.get(f"{B}/api/trustscore/{fid}?refresh=true", headers=a_hdr)
check("recompute works", r.status_code==200 and r.json()["trust"]["trust_score"] is not None)

print("== applications + feedback ==")
lid=recs[0]["internship"]["id"]
r=requests.post(f"{B}/api/applications", headers=s_hdr, json={"internship_id":lid,"student_id":1})
check("apply", r.status_code in (200,201), r.json().get("message","")[:52])
r=requests.get(f"{B}/api/student/applications/1?per_page=5", headers=s_hdr).json()
check("list applications", len(r["applications"])>0)
aid=r["applications"][0]["id"]
check("status update", requests.patch(f"{B}/api/applications/{aid}", headers=s_hdr, json={"status":"interview"}).status_code==200)
check("bad status rejected", requests.patch(f"{B}/api/applications/{aid}", headers=s_hdr, json={"status":"nonsense"}).status_code==400)
r=requests.post(f"{B}/api/feedback", headers=s_hdr, json={"internship_id":lid,"student_id":1,"verdict":"Verified","rating":5,"comment":"Interview process was professional."})
check("feedback", r.status_code==201, r.json().get("message","")[:44])
check("feedback validates verdict", requests.post(f"{B}/api/feedback", headers=s_hdr, json={"internship_id":lid,"student_id":1,"verdict":"Meh","rating":5}).status_code==400)
check("feedback validates rating", requests.post(f"{B}/api/feedback", headers=s_hdr, json={"internship_id":lid,"student_id":1,"verdict":"Verified","rating":9}).status_code==400)
r=requests.get(f"{B}/api/student/dashboard/1", headers=s_hdr).json()
check("dashboard payload", all(k in r for k in ["stats","top_recommendations","recent_applications","skill_cloud","trust_exposure"]))

print("== admin: CRUD + trust ==")
new={"title":"Platform Engineering Intern","company":"Testco Systems","contact_email":"careers@testco.in",
     "location":"Bengaluru, KA","work_mode":"hybrid","domain":"Backend Engineering",
     "description":"Work with the platform team on Python microservices, CI/CD and observability. You will write tested code, take part in reviews and own a scoped project for six months. Interviews are technical plus manager round.",
     "skills_required":"python, docker, ci/cd","stipend":25000,"duration_months":6,"openings":2,
     "apply_url":"https://testco.in/careers/platform-intern","deadline":"2026-12-31"}
r=requests.post(f"{B}/api/admin/add-internship", headers=a_hdr, json=new); d=r.json()
nid=d["internship"]["id"]; check("create listing", r.status_code==201, f"score {d['trust']['trust_score']} {d['trust']['badge']}")
check("auto-scored on create", d["trust"]["trust_score"]>0 and "formula" in d["internship"]["trust_breakdown"])
check("validation errors", requests.post(f"{B}/api/admin/add-internship", headers=a_hdr, json={"title":"x"}).status_code==400)
scam={**new,"title":"Urgent Paid Internship","company":"Fee Portal","contact_email":"hr@internshippay.in",
      "description":"Registration fee Rs 499 is mandatory. No interview required, direct joining. Pay to our UPI id and share screenshot on WhatsApp. Limited seats hurry.","apply_url":"https://bit.ly/x","stipend":0}
r=requests.post(f"{B}/api/admin/add-internship", headers=a_hdr, json=scam); sd=r.json()
check("scam auto-flagged", sd["trust"]["fraud_flag"] and sd["trust"]["badge"]=="Red", f"score {sd['trust']['trust_score']}, {len(sd['trust']['red_flags'])} flags")
r=requests.put(f"{B}/api/admin/internships/{nid}", headers=a_hdr, json={"stipend":30000})
check("update+rescore", r.status_code==200 and r.json()["trust"]["trust_score"]>0)
r=requests.post(f"{B}/api/admin/internships/{nid}/recompute", headers=a_hdr)
check("recompute endpoint", r.status_code==200)
r=requests.post(f"{B}/api/admin/trustscore-override", headers=a_hdr, json={"internship_id":sd["internship"]["id"],"trust_score":62,"mark_fraud":False,"note":"Called the company, domain is new but verified as legitimate."})
check("override", r.status_code==200 and r.json()["internship"]["override_by_admin"], r.json().get("message","")[:52])
check("override needs note", requests.post(f"{B}/api/admin/trustscore-override", headers=a_hdr, json={"internship_id":nid,"trust_score":80,"note":"x"}).status_code==400)
check("override range validated", requests.post(f"{B}/api/admin/trustscore-override", headers=a_hdr, json={"internship_id":nid,"trust_score":140,"note":"valid note here"}).status_code==400)

print("== admin: bulk CSV, queue, analytics ==")
base = open("samples/internships_bulk_upload.csv").read()
rows = list(csv.reader(io.StringIO(base)))
stamp = str(int(time.time()))[-6:]
uniq = io.StringIO()
w = csv.writer(uniq)
w.writerow(rows[0])
for row in rows[1:]:
    r2 = list(row)
    r2[0] = f"{r2[0]} · run {stamp}"      # avoid duplicate-title skips across runs
    w.writerow(r2)
r=requests.post(f"{B}/api/admin/bulk-upload", headers=a_hdr,
                files={"file":(f"bulk_{stamp}.csv", uniq.getvalue().encode(), "text/csv")})
d=r.json(); check("CSV bulk upload", r.status_code in (200,201) and d.get("created",0)>=5, d.get("message","")[:64])
check("CSV flags scams", d.get("flagged",0)>=1, f"flagged {d.get('flagged')}")
dup=requests.post(f"{B}/api/admin/bulk-upload", headers=a_hdr,
                  files={"file":("dup.csv", uniq.getvalue().encode(), "text/csv")})
check("CSV duplicate detection", dup.json().get("skipped",0)>=5, dup.json().get("message","")[:48])
r=requests.post(f"{B}/api/admin/bulk-upload", headers=a_hdr, files={"file":("bad.csv",b"foo,bar\n1,2\n","text/csv")})
check("CSV template validation", r.status_code==400)
check("template download", requests.get(f"{B}/api/admin/bulk-upload/template", headers=a_hdr).status_code==200)
d=requests.get(f"{B}/api/admin/flagged?per_page=5", headers=a_hdr).json()
check("flagged queue", len(d["queue"])==5 and d["summary"]["total_flagged"]>100, f"{d['summary']}")
check("queue has top flags", len(d["queue"][0]["top_flags"])>0)
check("export csv", requests.get(f"{B}/api/admin/export/flagged.csv", headers=a_hdr).text.startswith("id,title"))
d=requests.get(f"{B}/api/admin/analytics", headers=a_hdr).json()
need=["kpis","badge_distribution","score_bands","domain_stats","top_flags","posting_trend","application_status","feedback_split","top_companies","ml_model"]
check("analytics payload", all(k in d for k in need), f"kpis={d['kpis']}")
check("domain stats populated", len(d["domain_stats"])>=8)
d=requests.get(f"{B}/api/admin/students?per_page=5", headers=a_hdr).json()
check("students list", len(d["students"])==5 and d["students"][0]["skills"])
d=requests.get(f"{B}/api/admin/feedback?per_page=5", headers=a_hdr).json()
check("feedback list", len(d["feedback"])==5 and "average_rating" in d["summary"])
d=requests.get(f"{B}/api/admin/audit-log?per_page=5", headers=a_hdr).json()
check("audit log", len(d["logs"])==5)
d=requests.get(f"{B}/api/admin/domains", headers=a_hdr).json()
check("domain intel list", len(d["domains"])>50 and len(d["blacklist"])>=10)
r=requests.post(f"{B}/api/admin/ml/retrain", headers=a_hdr)
check("ml retrain", r.status_code==200, f"acc={r.json()['metrics']['train_accuracy']}")
d=requests.get(f"{B}/api/admin/internships?per_page=3&sort=trust_asc", headers=a_hdr).json()
check("admin listings CRUD read", len(d["internships"])==3)
check("delete listing", requests.delete(f"{B}/api/admin/internships/{nid}", headers=a_hdr).status_code==200)

print("== pages (HTML) ==")
for path in ["/","/login","/register","/student/dashboard","/student/recommendations","/student/profile",
             "/student/applications","/student/internship/5","/admin/dashboard","/admin/listings",
             "/admin/flagged","/admin/bulk-upload","/admin/analytics","/admin/students","/admin/audit","/student/feedback"]:
    rr=requests.get(B+path)
    check(f"page {path}", rr.status_code==200 and "<html" in rr.text.lower(), rr.status_code)

print(f"\n==== {ok} passed, {fail} failed ====")
sys.exit(1 if fail else 0)

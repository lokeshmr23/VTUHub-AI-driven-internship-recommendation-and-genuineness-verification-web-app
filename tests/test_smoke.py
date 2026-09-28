"""Read-only smoke test — verifies a freshly seeded instance without mutating it.

    python app.py &            # or: make serve
    python tests/test_smoke.py

Override the target with SMOKE_BASE (e.g. a MySQL-backed instance on another port):

    SMOKE_BASE=http://127.0.0.1:8090 python tests/test_smoke.py
"""
import os, requests, sys
B=os.getenv("SMOKE_BASE","http://127.0.0.1:8000"); ok=fail=0
def c(n,cond,x=""):
    global ok,fail
    ok += bool(cond); fail += (not cond)
    print(f"  {'PASS' if cond else 'FAIL'}  {n} {x}")

h=requests.get(f"{B}/healthz").json()
c("pristine inventory", h["listings"]==500 and h["students"]==50, f"{h['listings']} listings / {h['students']} students")
s=requests.post(f"{B}/api/auth/login",json={"email":"student1@internmatch.ai","password":"Student@123"}).json()
a=requests.post(f"{B}/api/auth/login",json={"email":"admin@internmatch.ai","password":"Admin@123"}).json()
sh={"Authorization":f"Bearer {s['access_token']}"}; ah={"Authorization":f"Bearer {a['access_token']}"}
c("demo logins", "access_token" in s and "access_token" in a)
r=requests.get(f"{B}/api/recommendations/1?limit=6",headers=sh).json()
c("ranked matches", len(r["recommendations"])==6, "top %d%%" % r["recommendations"][0]["match_pct"])
c("bonus flag", all("domain_bonus_applied" in x for x in r["recommendations"]))
fid=requests.get(f"{B}/api/internships?flagged=true&per_page=1",headers=sh).json()["internships"][0]["id"]
t=requests.get(f"{B}/api/trustscore/{fid}",headers=sh).json()["trust"]
calc=round((0.5*t["rule_score"]+0.5*(1-t["ml_fraud_prob"]))*100)
c("trust formula", abs(calc-t["trust_score"])<=1, f"{calc} vs {t['trust_score']} · badge {t['badge']} · flagged {t['fraud_flag']}")
c("fraud detail has flags", len(t["red_flags"])>0, t["red_flags"][0]["label"][:40])
p=requests.get(f"{B}/api/student/profile/1",headers=sh).json()
c("student profile", p["stats"]["total_skills"]>10, p["stats"])
dash=requests.get(f"{B}/api/student/dashboard/1",headers=sh).json()
c("dashboard", len(dash["top_recommendations"])>0 and dash["skill_cloud"])
an=requests.get(f"{B}/api/admin/analytics",headers=ah).json()
c("analytics", an["kpis"]["total_listings"]==500 and an["kpis"]["flagged_listings"]==156, f"{an['kpis']}")
q=requests.get(f"{B}/api/admin/flagged?per_page=40",headers=ah).json()
scores=sorted(x["trust_score"] for x in q["queue"])
c("queue score spread", len(set(scores))>=5, f"{scores[0]}..{scores[-1]} across {len(scores)}, distinct={len(set(scores))}")
for path in ["/","/login","/register","/student/dashboard","/student/recommendations","/student/profile",
             "/student/applications","/student/feedback","/admin/dashboard","/admin/listings",
             "/admin/flagged","/admin/bulk-upload","/admin/analytics","/admin/students","/admin/feedback","/admin/audit"]:
    rr=requests.get(B+path); c(f"page {path}", rr.status_code==200)
print(f"\n=== smoke: {ok} passed, {fail} failed ===")
sys.exit(1 if fail else 0)

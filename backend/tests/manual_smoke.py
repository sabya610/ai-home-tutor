"""Manual live smoke test against a running server (not collected by pytest).

Usage: python manual_smoke.py [base_url]
"""

import json
import sys
import time
import urllib.parse
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8123"


def wait_ready(timeout=20.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(BASE + "/api/health", timeout=2) as r:
                if r.status == 200:
                    return
        except Exception:
            time.sleep(0.5)
    raise SystemExit(f"server at {BASE} did not become ready")


def get(path):
    with urllib.request.urlopen(BASE + path) as r:
        return json.load(r)


def post_json(path, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        BASE + path, data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def post_form(path, fields):
    data = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(BASE + path, data=data)
    with urllib.request.urlopen(req) as r:
        return json.load(r)


wait_ready()
print("health   :", get("/api/health"))
s = post_json("/api/students", {"name": "Aria", "grade_level": 4})
print("student  :", s)
print("dict_new :", get("/api/dictation/new?level=2"))
d = post_form(
    "/api/dictation/check",
    {"expected": "the cat sat on the mat", "recognized_text": "the Cat on the mat", "student_id": s["id"]},
)
print(
    "dict_chk : overall=%s missing=%s caps=%s | %s"
    % (d["overall_score"], d["missing_words"], d["capitalization_errors"], d["feedback"])
)
h = post_form(
    "/api/homework/check",
    {"question": "What is 1/2 + 1/4?", "recognized_text": "2/6", "student_id": s["id"]},
)
print("hw_chk   : score=%s verdict=%s hint=%s" % (h["score"], h["verdict"], h["hint"]))
p = get("/api/students/%s/progress" % s["id"])
print("progress : attempts=%s rec=%s" % (p["total_attempts"], p["recommendation"]))
with urllib.request.urlopen(BASE + "/") as r:
    print("frontend : HTTP", r.status, "len", len(r.read()))
print("ALL OK")

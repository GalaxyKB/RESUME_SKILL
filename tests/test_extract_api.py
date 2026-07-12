"""Direct test of the extract API endpoint."""
import sys, pathlib, shutil, json, urllib.request, urllib.error, threading, time

sys.path.insert(0, "src")

# Clear ALL caches aggressively
for p in pathlib.Path("src").rglob("__pycache__"):
    shutil.rmtree(p, ignore_errors=True)
for p in pathlib.Path("src").rglob("*.pyc"):
    p.unlink(missing_ok=True)

print("=== Test 1: Direct PersonalInfoExtractor instantiation ===")
from resume_skill.extractor.extractor import PersonalInfoExtractor
e = PersonalInfoExtractor(personal_info_dir=r"E:\桌面\最新\RESUME_SKILL\personal_info")
print(f"OK: created {e}")

print("\n=== Test 2: Flask extract API endpoint ===")
from resume_skill.webui.app import app

def run():
    app.run(host="127.0.0.1", port=5003, debug=False)

t = threading.Thread(target=run, daemon=True)
t.start()
time.sleep(3)

# POST multipart with a dummy PDF
import io
data = (
    b'--bound\r\n'
    b'Content-Disposition: form-data; name="file"; filename="test.pdf"\r\n'
    b'Content-Type: application/pdf\r\n\r\n'
    b'%PDF-1.4 fake pdf\r\n'
    b'--bound--\r\n'
)

req = urllib.request.Request("http://127.0.0.1:5003/api/extract", data=data)
req.add_header("Content-Type", "multipart/form-data; boundary=bound")

try:
    r = urllib.request.urlopen(req, timeout=30)
    body = r.read().decode()
    print(f"HTTP {r.status}: {body[:300]}")
    if "llm_client" in body:
        print("BUG: llm_client error still present!")
    else:
        print("OK: llm_client bug not present")
except urllib.error.HTTPError as e:
    body = e.read().decode()
    print(f"HTTP {e.code}: {body[:300]}")
    if "llm_client" in body:
        print("BUG: llm_client error still present!")
    else:
        print("OK: different error (expected, test PDF may not parse)")
except Exception as exc:
    print(f"Exception: {exc}")

# Also test consolidate
print("\n=== Test 3: Flask consolidate API endpoint ===")
req2 = urllib.request.Request("http://127.0.0.1:5003/api/consolidate", method="POST")
try:
    r2 = urllib.request.urlopen(req2, timeout=30)
    body2 = r2.read().decode()
    print(f"HTTP {r2.status}: {body2[:300]}")
    if "llm_client" in body2:
        print("BUG: llm_client error!")
    else:
        print("OK: llm_client bug not present")
except urllib.error.HTTPError as e:
    body2 = e.read().decode()
    print(f"HTTP {e.code}: {body2[:300]}")
    if "llm_client" in body2:
        print("BUG: llm_client error!")

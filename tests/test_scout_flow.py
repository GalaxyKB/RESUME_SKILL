"""Test scout flow end-to-end"""
import sys, json, threading, time
sys.path.insert(0, "src")
from resume_skill.webui.app import app
import urllib.request, urllib.error


def run():
    app.run(host="127.0.0.1", port=5009, debug=False)


t = threading.Thread(target=run, daemon=True)
t.start()
time.sleep(3)

# ===== 1. Scout Login =====
print("--- 1. Scout Login ---")
companies = [{"name": "Test", "url": "https://example.com"}]
data = json.dumps({"companies": companies}).encode()
req = urllib.request.Request(
    "http://127.0.0.1:5009/api/scout/login",
    data=data,
    headers={"Content-Type": "application/json"},
)
try:
    r = urllib.request.urlopen(req, timeout=30)
    result = json.loads(r.read())
    print(f"OK: {result}")
except Exception as e:
    body = ""
    if hasattr(e, "read"):
        body = e.read().decode()
    print(f"FAILED: {body or str(e)}")
    import traceback
    traceback.print_exc()

# ===== 2. Scout Start =====
time.sleep(1)
print("\n--- 2. Scout Start ---")
req2 = urllib.request.Request(
    "http://127.0.0.1:5009/api/scout/start",
    method="POST",
)
try:
    r2 = urllib.request.urlopen(req2, timeout=10)
    result2 = json.loads(r2.read())
    print(f"OK: {result2}")
except Exception as e:
    body = ""
    if hasattr(e, "read"):
        body = e.read().decode()
    print(f"FAILED: {body or str(e)}")

# ===== 3. Poll Status =====
print("\n--- 3. Polling ---")
for i in range(15):
    time.sleep(1.5)
    r3 = urllib.request.urlopen("http://127.0.0.1:5009/api/scout/status")
    s = json.loads(r3.read())
    running = s.get("running")
    logs = len(s.get("log", []))
    results = len(s.get("results", []))
    last_log = ""
    if s.get("log"):
        last_log = s["log"][-1][:60]
    print(f"  [{i*1.5:.0f}s] running={running} logs={logs} results={results} | {last_log}")
    if not running:
        break

print("\nDone")

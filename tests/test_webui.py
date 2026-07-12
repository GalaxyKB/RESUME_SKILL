"""Quick test: start webui, check index + API."""
import sys, time, urllib.request, threading
sys.path.insert(0, "src")
from resume_skill.webui.app import app

def run_server():
    app.run(host="127.0.0.1", port=5000, debug=False)

t = threading.Thread(target=run_server, daemon=True)
t.start()
time.sleep(2)

# Test index page
r = urllib.request.urlopen("http://127.0.0.1:5000/")
html = r.read().decode()
assert "RESUME_SKILL" in html, "Index page should contain RESUME_SKILL"
print("[OK] Index page renders correctly")

# Test API
r = urllib.request.urlopen("http://127.0.0.1:5000/api/profile")
data = r.read().decode()
assert "exists" in data, "Profile API should return exists field"
print("[OK] Profile API works")

print("All tests passed!")

"""Test scout worker directly"""
import sys, json, threading, time
sys.path.insert(0, "src")
import resume_skill.webui.app as webapp
from resume_skill.agent.mcp.chrome_client import ChromeDevToolsClient

# Setup global chrome instance (simulating login step)
webapp._chrome_instance = ChromeDevToolsClient(headless=False)
webapp._chrome_instance.connect()
webapp._chrome_instance.call_tool("navigate_page", {"url": "https://example.com"})

_profile_text = "姓名：张三\n邮箱：zs@test.com\n教育：北京大学 本科"
_preferences = {
    "personal_info": {"base_city": "北京", "job_type": "校招"},
    "target_companies": [{"name": "Test", "url": "https://example.com"}],
}

# Start worker in thread
t = threading.Thread(target=webapp._scout_worker, args=(_profile_text, _preferences), daemon=True)
t.start()

# Wait and poll
poll_count = 0
while poll_count < 30:
    time.sleep(2)
    poll_count += 1
    running = webapp._scout_progress.get("running")
    logs = webapp._scout_progress.get("log", [])
    results = webapp._scout_progress.get("results", [])
    print(f"[{poll_count*2}s] running={running} logs={len(logs)} results={len(results)}")
    if logs:
        for l in logs[-3:]:
            print(f"  -> {l}")
    if not running:
        print("Worker finished")
        break
else:
    print("TIMEOUT - worker still running after 60s")

webapp._chrome_instance.close()

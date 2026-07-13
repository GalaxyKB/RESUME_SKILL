"""Find the scout step in the HTML"""
import re

with open("src/resume_skill/webui/templates/index.html", "r", encoding="utf-8") as f:
    html = f.read()

# Find scout sections
for m in re.finditer(r'(<!--.*?-->.*?|<div[^>]*v-if="step===4"[^>]*>.*?<div[^>]*class="card-header"[^>]*>.*?</div>)', html, re.DOTALL):
    text = m.group()
    if "勘探" in text or "scout" in text.lower() or "Scout" in text:
        print("FOUND SCOUT:")
        print(text[:500])

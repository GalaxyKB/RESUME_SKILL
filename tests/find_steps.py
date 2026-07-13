"""Find all step indicators in the HTML"""
import re

with open("src/resume_skill/webui/templates/index.html", "r", encoding="utf-8") as f:
    html = f.read()

pattern = r'<div[^>]*v-if="step===([0-9]+)"[^>]*>.*?class="card-header"[^>]*>(.*?)</div>'
for m in re.finditer(pattern, html, re.DOTALL):
    step_num = m.group(1)
    header = m.group(2)
    print(f"Step {step_num}: {header[:80]}")

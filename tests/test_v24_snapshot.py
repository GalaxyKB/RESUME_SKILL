"""v2.4 snapshot parse smoke test"""
import sys
sys.path.insert(0, "src")
from resume_skill.agent.mcp.agent import MCPAgent

agent = MCPAgent.__new__(MCPAgent)

snapshot_text = """textbox "name" uid=1_5
textbox "email" uid=1_6
combobox "degree" uid=1_7 options="high school,bachelor,master,phd"
button "submit" uid=1_8
button "next" uid=1_9"""

fields = agent._parse_snapshot(snapshot_text)
print(f"Fields parsed: {len(fields)}")
for f in fields:
    print(f"  {f}")

assert len(fields) == 3
assert fields[2]["type"] == "select"
assert fields[2]["options"] == ["high school", "bachelor", "master", "phd"]

submit_uid = agent._find_submit_uid(snapshot_text)
assert submit_uid == "1_8", f"Expected 1_8, got {submit_uid}"

next_uid = agent._find_next_uid(snapshot_text)
assert next_uid == "1_9", f"Expected 1_9, got {next_uid}"

print("\nAll snapshot parse tests passed!")

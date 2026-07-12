"""v2.4 端到端冒烟测试"""

import sys
sys.path.insert(0, "src")

from resume_skill.agent.mcp.chrome_client import ChromeDevToolsClient
from resume_skill.agent.mcp.agent import MCPAgent

# 模拟 snapshot 文本解析测试
agent = MCPAgent.__new__(MCPAgent)

snapshot_text = """
link "Home" uid=1_1
textbox "姓名" uid=1_2
textbox "邮箱" uid=1_3
combobox "学历" uid=1_4 options="高中,本科,硕士,博士"
button "提交" uid=1_5
button "下一步" uid=1_6
"""

fields = agent._parse_snapshot(snapshot_text)
print(f"解析结果: {len(fields)} 个字段")
for f in fields:
    print(f"  {f}")

assert len(fields) == 3  # textbox*2 + combobox
assert fields[2]["type"] == "select"
assert fields[2]["options"] == ["高中", "本科", "硕士", "博士"]

next_uid = agent._find_next_uid(snapshot_text)
assert next_uid == "1_6"

submit_uid = agent._find_submit_uid(snapshot_text)
assert submit_uid == "1_5"

print("\n✅ 所有解析测试通过")
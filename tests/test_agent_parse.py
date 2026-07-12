"""测试agent.py的_parse_snapshot方法"""

import sys
sys.path.insert(0, 'src')

from resume_skill.agent.mcp.agent import MCPAgent

agent = MCPAgent.__new__(MCPAgent)
test = 'textbox "姓名" uid=1_5\ntextbox "邮箱" uid=1_6\ncombobox "学历" uid=1_7 options="本科,硕士,博士"'
fields = agent._parse_snapshot(test)

print(f"解析结果: {len(fields)} 个字段")
for f in fields:
    print(f"  {f}")

assert len(fields) == 3
assert fields[0] == {'uid':'1_5','label':'姓名','type':'text','options':[]}
assert fields[2]['options'] == ['本科','硕士','博士']

print("\n✅ 所有断言通过")

"""临时测试：验证 ChromeDevToolsClient 连接与工具调用"""

import sys
sys.path.insert(0, "src")

from resume_skill.agent.mcp.chrome_client import ChromeDevToolsClient

c = ChromeDevToolsClient(headless=True)
c.connect()

# 测试1：导航到 example.com
r = c.call_tool("navigate_page", {"url": "https://example.com"})
print(f"navigate_page: {r}")

# 测试2：获取无障碍树快照
r = c.call_tool("take_snapshot", {})
text = str(r)
print(f"take_snapshot: {len(text)} chars")

# 检查快照中是否包含页面内容
assert "Example" in text or "example" in text.lower(), "快照中应包含页面内容"
print("快照内容验证通过")

# 测试3：截图
r = c.call_tool("take_screenshot", {})
print(f"take_screenshot: OK")

c.close()
print("所有测试通过")
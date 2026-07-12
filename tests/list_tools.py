"""List navigation tools from chrome-devtools-mcp"""
import sys
sys.path.insert(0, "src")
from resume_skill.agent.mcp.chrome_client import ChromeDevToolsClient

c = ChromeDevToolsClient(headless=True)
c.connect()
result = c.call_tool("list_tools", {})
print("Result type:", type(result))
print("Result (first 2000 chars):")
print(str(result)[:2000])
c.close()

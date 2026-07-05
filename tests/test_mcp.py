"""Smoke test for MCP Server + Client."""
import sys, time
sys.path.insert(0, r"src")
from resume_skill.agent.mcp.client import MCPClient

with MCPClient() as client:
    print("=== MCP Smoke Test ===")

    # 1. Start browser (headless)
    r = client.call_tool("browser_start", {
        "session_dir": ".session/test_mcp",
        "headless": True,
        "slow_motion": 100,
    })
    print(f"[OK] browser_start: {r['status']}")

    # 2. Navigate
    r = client.call_tool("browser_navigate", {"url": "https://example.com"})
    print(f"[OK] browser_navigate: {r['status']}")

    # 3. Get page text
    r = client.call_tool("get_page_text", {})
    print(f"[OK] get_page_text: {len(r.get('text', ''))} chars")

    # 4. Extract fields (example.com has no forms -> 0 fields)
    r = client.call_tool("extract_fields", {})
    print(f"[OK] extract_fields: {r.get('count', 0)} fields found")

    # 5. Close
    client.call_tool("browser_close", {})
    print("[OK] browser_close")
    print("=== All tests passed ===")

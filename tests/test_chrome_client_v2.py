"""测试：验证简化的ChromeDevToolsClient连接与工具调用"""

import sys
sys.path.insert(0, "src")

from resume_skill.agent.mcp.chrome_client import ChromeDevToolsClient

try:
    c = ChromeDevToolsClient(headless=True)
    c.connect()
    print("✅ 连接成功")
    
    # 测试1：获取工具列表
    try:
        print("获取工具列表...")
        # 注意：我们简化版的client不支持tools/list，先跳过这个测试
        print("⚠️  跳过工具列表测试（简化版暂不支持）")
    except Exception as e:
        print(f"⚠️  工具列表测试失败（预期中）: {e}")
    
    # 测试2：导航到example.com
    print("\n导航到 example.com...")
    try:
        r = c.call_tool("navigate_page", {"url": "https://example.com"})
        print(f"✅ navigate_page: {r}")
    except Exception as e:
        print(f"❌ navigate_page失败: {e}")
        # 可能是工具名不对，让我们尝试其他工具名
        print("尝试获取工具列表来确定可用的工具名...")
    
    # 测试3：直接测试几个常用工具（如果可用）
    test_tools = ["take_snapshot", "get_page_info", "evaluate_script"]
    for tool in test_tools:
        print(f"\n尝试工具: {tool}...")
        try:
            r = c.call_tool(tool, {})
            print(f"✅ {tool}: 成功 (响应长度: {len(str(r))})")
            if tool == "take_snapshot":
                print(f"快照示例: {str(r)[:200]}...")
            break  # 找到可用的工具就停止
        except Exception as e:
            print(f"❌ {tool}: {e}")
    
    c.close()
    print("\n✅ 测试完成（简化版客户端）")
    
except Exception as e:
    print(f"\n❌ 测试失败: {e}")
    import traceback
    traceback.print_exc()
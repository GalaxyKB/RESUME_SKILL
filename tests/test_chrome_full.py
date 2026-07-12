"""完整测试：验证chrome-devtools-mcp的所有核心功能"""

import sys
sys.path.insert(0, "src")

from resume_skill.agent.mcp.chrome_client import ChromeDevToolsClient

def main():
    print("=" * 60)
    print("chrome-devtools-mcp 完整功能测试")
    print("=" * 60)
    
    client = None
    try:
        # 1. 连接
        print("\n1. 连接到chrome-devtools-mcp...")
        client = ChromeDevToolsClient(headless=True)
        client.connect()
        print("✅ 连接成功")
        
        # 2. 列出页面
        print("\n2. 列出页面...")
        try:
            pages = client.call_tool("list_pages", {})
            print(f"✅ 页面列表: {pages}")
        except Exception as e:
            print(f"❌ 列出页面失败: {e}")
        
        # 3. 打开新页面并导航
        print("\n3. 导航到example.com...")
        try:
            # 使用navigate_page而不是new_page，因为可能已经有默认页面
            result = client.call_tool("navigate_page", {
                "type": "url",
                "url": "https://example.com"
            })
            print(f"✅ 导航结果: {result}")
        except Exception as e:
            print(f"❌ 导航失败: {e}")
            # 尝试new_page
            try:
                result = client.call_tool("new_page", {
                    "url": "https://example.com"
                })
                print(f"✅ 新页面结果: {result}")
            except Exception as e2:
                print(f"❌ 新页面也失败: {e2}")
        
        # 4. 等待页面加载
        print("\n4. 等待页面加载...")
        try:
            wait_result = client.call_tool("wait_for", {
                "text": ["Example", "example"]
            })
            print(f"✅ 等待结果: {wait_result}")
        except Exception as e:
            print(f"⚠️  等待失败（可能已加载）: {e}")
        
        # 5. 获取页面快照
        print("\n5. 获取页面快照...")
        try:
            snapshot = client.call_tool("take_snapshot", {})
            print(f"✅ 快照长度: {len(str(snapshot))} 字符")
            if isinstance(snapshot, dict) and "content" in snapshot:
                content = snapshot["content"][0]["text"]
                print(f"快照前500字符: {content[:500]}...")
                # 检查是否包含example.com的内容
                if "Example" in content or "example" in content:
                    print("✅ 快照包含页面内容")
        except Exception as e:
            print(f"❌ 获取快照失败: {e}")
        
        # 6. 截图
        print("\n6. 截图测试...")
        try:
            screenshot = client.call_tool("take_screenshot", {})
            print(f"✅ 截图结果: {screenshot}")
            if isinstance(screenshot, dict) and "content" in screenshot:
                print("✅ 截图成功（包含内容）")
        except Exception as e:
            print(f"❌ 截图失败: {e}")
        
        # 7. 执行JavaScript
        print("\n7. 执行JavaScript...")
        try:
            js_result = client.call_tool("evaluate_script", {
                "function": "() => document.title"
            })
            print(f"✅ JS执行结果: {js_result}")
        except Exception as e:
            print(f"❌ JS执行失败: {e}")
        
        print("\n" + "=" * 60)
        print("✅ 所有测试完成")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if client:
            print("\n关闭连接...")
            client.close()

if __name__ == "__main__":
    main()
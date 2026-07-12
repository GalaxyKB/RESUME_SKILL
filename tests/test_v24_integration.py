"""
v2.4 集成测试：验证完整表单填充流程
"""

import sys
sys.path.insert(0, "src")

from resume_skill.agent.mcp.agent import MCPAgent
from resume_skill.llm.factory import create_llm_client

def test_agent_initialization():
    """测试Agent初始化"""
    print("=" * 60)
    print("v2.4 MCP Agent 初始化测试")
    print("=" * 60)
    
    try:
        llm = create_llm_client()
        agent = MCPAgent(llm_client=llm)
        
        print(f"✅ MCPAgent初始化成功")
        print(f"  - LLM: {type(agent.llm).__name__}")
        print(f"  - Chrome Client: {type(agent.chrome).__name__}")
        print(f"  - Our Client: {type(agent.our_client).__name__}")
        print(f"  - Recorder: {type(agent.recorder).__name__}")
        
        return True
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_parse_snapshot():
    """测试快照解析功能"""
    print("\n" + "=" * 60)
    print("快照解析测试")
    print("=" * 60)
    
    try:
        llm = create_llm_client()
        agent = MCPAgent(llm_client=llm)
        
        # 模拟的take_snapshot返回文本
        snapshot_text = """
textbox "姓名" uid=1_5
textbox "邮箱" uid=1_6
combobox "学历" uid=1_7 options="本科,硕士,博士"
textarea "自我介绍" uid=1_8
button "提交" uid=1_9
button "下一步" uid=1_10
searchbox "搜索" uid=1_11
"""
        
        fields = agent._parse_snapshot(snapshot_text)
        print(f"✅ 解析出 {len(fields)} 个字段")
        
        for i, field in enumerate(fields, 1):
            print(f"  {i}. uid={field['uid']} label={field['label']} type={field['type']} options={field['options']}")
        
        # 验证解析结果
        expected_uids = ["1_5", "1_6", "1_7", "1_8", "1_11"]
        parsed_uids = [f["uid"] for f in fields]
        
        for uid in expected_uids:
            if uid in parsed_uids:
                print(f"✅ uid={uid} 正确解析")
            else:
                print(f"❌ uid={uid} 未找到")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ 快照解析失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_answer_fields():
    """测试LLM问答功能（使用模拟数据）"""
    print("\n" + "=" * 60)
    print("LLM问答功能测试")
    print("=" * 60)
    
    try:
        llm = create_llm_client()
        agent = MCPAgent(llm_client=llm)
        
        # 设置模拟profile
        agent.profile = {
            "姓名": "张三",
            "邮箱": "zhangsan@example.com",
            "学历": "硕士",
            "自我介绍": "拥有5年软件开发经验"
        }
        
        # 模拟字段
        fields = [
            {"uid": "1_5", "label": "姓名", "type": "text", "options": []},
            {"uid": "1_6", "label": "邮箱", "type": "text", "options": []},
            {"uid": "1_7", "label": "学历", "type": "select", "options": ["本科", "硕士", "博士"]},
            {"uid": "1_8", "label": "自我介绍", "type": "text", "options": []},
            {"uid": "1_9", "label": "身份证号", "type": "text", "options": []},  # 敏感字段
        ]
        
        print("模拟字段:")
        for field in fields:
            print(f"  - {field['label']} ({field['type']})")
        
        print("\n模拟Profile:")
        for key, value in agent.profile.items():
            print(f"  - {key}: {value}")
        
        print("\n正在调用LLM问答...")
        answers = agent._answer_fields(fields)
        
        print(f"\n✅ LLM返回 {len(answers)} 个答案")
        for ans in answers:
            print(f"  uid={ans.get('uid')}: answer={ans.get('answer')[:30]}... confidence={ans.get('confidence')} action={ans.get('action')}")
        
        return True
        
    except Exception as e:
        print(f"❌ LLM问答失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_find_buttons():
    """测试按钮查找功能"""
    print("\n" + "=" * 60)
    print("按钮查找功能测试")
    print("=" * 60)
    
    try:
        llm = create_llm_client()
        agent = MCPAgent(llm_client=llm)
        
        # 测试文本
        snapshot_text = """
textbox "姓名" uid=1_5
button "提交" uid=2_3
button "下一步" uid=2_4
button "Next" uid=2_5
button "continue" uid=2_6
"""
        
        submit_uid = agent._find_submit_uid(snapshot_text)
        print(f"提交按钮: uid={submit_uid or '未找到'}")
        
        next_uid = agent._find_next_uid(snapshot_text)
        print(f"下一步按钮: uid={next_uid or '未找到'}")
        
        if submit_uid == "2_3":
            print("✅ 提交按钮查找正确")
        else:
            print("❌ 提交按钮查找错误")
            return False
            
        if next_uid == "2_4":
            print("✅ 下一步按钮查找正确")
        else:
            print("❌ 下一步按钮查找错误")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ 按钮查找失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """运行所有测试"""
    print("v2.4 MCP Agent 集成测试")
    print("=" * 60)
    
    test_results = []
    
    # 运行测试
    test_results.append(("Agent初始化", test_agent_initialization()))
    test_results.append(("快照解析", test_parse_snapshot()))
    test_results.append(("LLM问答", test_answer_fields()))
    test_results.append(("按钮查找", test_find_buttons()))
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    passed = sum(1 for _, result in test_results if result)
    total = len(test_results)
    
    for name, result in test_results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{name}: {status}")
    
    print(f"\n总计: {passed}/{total} 项测试通过")
    print("=" * 60)
    
    if passed == total:
        print("🎉 所有测试通过！v2.4 MCP Agent 基础功能正常")
    else:
        print("⚠️  部分测试失败，请检查问题")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
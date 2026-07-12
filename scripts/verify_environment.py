#!/usr/bin/env python3
"""
v2.4 环境验证脚本
检查 Python、Node.js、npx、chrome-devtools-mcp 等依赖
"""

import subprocess
import sys
import platform

def run_command(cmd, shell=True, timeout=30):
    """运行命令并返回结果"""
    try:
        result = subprocess.run(
            cmd, 
            shell=shell, 
            capture_output=True, 
            text=True,
            timeout=timeout
        )
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "", f"命令超时: {cmd}"
    except Exception as e:
        return False, "", str(e)

def check_python_version():
    """检查 Python 版本"""
    print("🔍 检查 Python 版本...")
    
    # 检查 Python 可执行文件
    python_cmds = ["python", "python3"]
    python_path = None
    python_version = None
    
    for cmd in python_cmds:
        success, output, error = run_command(f"{cmd} --version")
        if success:
            python_path = cmd
            python_version = output
            break
    
    if not python_path:
        print("❌ 未找到 Python")
        return False
    
    print(f"✅ Python 路径: {python_path}")
    print(f"✅ Python 版本: {python_version}")
    
    # 检查是否为 Python 3.10+
    version_str = python_version.lower()
    if "python 3.10" in version_str or "python 3.11" in version_str or "python 3.12" in version_str:
        print("✅ Python 版本 3.10+ 符合要求")
        return True
    elif "python 3.9" in version_str:
        print("⚠️  Python 版本 3.9（无法使用 v2.4 MCP Agent）")
        return False
    else:
        print(f"❌ Python 版本不符合要求: {python_version}")
        return False

def check_nodejs():
    """检查 Node.js"""
    print("\n🔍 检查 Node.js...")
    
    success, output, error = run_command("node --version")
    if not success:
        print("❌ Node.js 未安装或不在 PATH 中")
        return False
    
    print(f"✅ Node.js 版本: {output}")
    
    # 检查是否为 v18+
    version_str = output.strip()
    if version_str.startswith("v"):
        version_num = int(version_str[1:].split(".")[0])
        if version_num >= 18:
            print("✅ Node.js 版本 v18+ 符合要求")
            return True
        else:
            print(f"❌ Node.js 版本过低: {version_str}，需要 v18+")
            return False
    return False

def check_npx():
    """检查 npx"""
    print("\n🔍 检查 npx...")
    
    success, output, error = run_command("npx --version")
    if not success:
        print("❌ npx 不可用")
        return False
    
    print(f"✅ npx 版本: {output}")
    return True

def check_chrome_devtools_mcp():
    """检查 chrome-devtools-mcp"""
    print("\n🔍 检查 chrome-devtools-mcp...")
    
    # 简单测试 npx 命令
    success, output, error = run_command("npx chrome-devtools-mcp@latest --help", timeout=60)
    if success:
        print("✅ chrome-devtools-mcp 可用")
        if "Options:" in output or "Usage:" in output:
            print("✅ 帮助文档正常显示")
            return True
        else:
            print("⚠️  帮助文档输出异常")
            return False
    else:
        print("❌ chrome-devtools-mcp 测试失败")
        print(f"错误: {error[:200]}")
        return False

def check_python_dependencies():
    """检查 Python 依赖"""
    print("\n🔍 检查 Python 依赖...")
    
    tests = [
        ("resume-skill", "resume-skill --version"),
        ("mcp", "python -c \"import mcp; print('✅ MCP SDK: ' + mcp.__version__)\""),
        ("playwright", "python -c \"from playwright.sync_api import sync_playwright; print('✅ Playwright 可用')\""),
    ]
    
    all_success = True
    for package, cmd in tests:
        success, output, error = run_command(cmd)
        if success:
            print(f"✅ {package}: 已安装")
        else:
            print(f"❌ {package}: 未安装或有问题")
            print(f"   错误: {error[:100]}")
            all_success = False
    
    return all_success

def main():
    """主验证函数"""
    print("=" * 60)
    print("RESUME_SKILL v2.4 环境验证")
    print("=" * 60)
    print(f"操作系统: {platform.system()} {platform.release()}")
    print(f"架构: {platform.machine()}")
    print()
    
    results = []
    
    # 运行所有检查
    results.append(("Python 3.10+", check_python_version()))
    results.append(("Node.js v18+", check_nodejs()))
    results.append(("npx", check_npx()))
    results.append(("chrome-devtools-mcp", check_chrome_devtools_mcp()))
    results.append(("Python 依赖", check_python_dependencies()))
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("验证结果汇总")
    print("=" * 60)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for check_name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{check_name}: {status}")
    
    print(f"\n总计: {passed}/{total} 项检查通过")
    print("=" * 60)
    
    if passed == total:
        print("🎉 环境配置完美！v2.4 MCP Agent 可以正常使用")
        print("\n下一步:")
        print("1. 运行测试: python tests/test_chrome_full.py")
        print("2. 验证功能: python tests/test_v24_integration.py")
        print("3. 使用: resume-skill apply --url \"URL\" --use-mcp")
    elif passed >= 3:
        print("⚠️  环境基本配置，部分功能可能受限")
        print("\n需要修复:")
        for check_name, success in results:
            if not success:
                print(f"  - {check_name}")
    else:
        print("❌ 环境配置不完整，v2.4 MCP Agent 无法使用")
        print("\n请参考 README.md 中的环境配置指南")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
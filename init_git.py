#!/usr/bin/env python
"""初始化Git仓库并创建首次提交"""
import subprocess
import os

os.chdir('E:\\桌面\\简历投递agent\\RESUME_SKILL')

print("\n" + "="*70)
print("  📦 准备上传到GitHub")
print("="*70 + "\n")

# 1. 初始化Git仓库
print("1️⃣  初始化Git仓库...")
try:
    subprocess.run(['git', 'init'], check=True, capture_output=True)
    print("   ✅ Git仓库已初始化\n")
except Exception as e:
    print(f"   ❌ 错误: {e}\n")

# 2. 配置Git用户
print("2️⃣  配置Git用户信息...")
try:
    subprocess.run(['git', 'config', 'user.email', 'noreply@github.com'], check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.name', 'RESUME_SKILL'], check=True, capture_output=True)
    print("   ✅ Git用户已配置\n")
except Exception as e:
    print(f"   ⚠️  警告: {e}\n")

# 3. 添加所有文件
print("3️⃣  添加所有文件到Git...")
try:
    subprocess.run(['git', 'add', '.'], check=True, capture_output=True)
    result = subprocess.run(['git', 'status', '--short'], capture_output=True, text=True)
    file_count = len([line for line in result.stdout.strip().split('\n') if line])
    print(f"   ✅ 已添加 {file_count} 个文件\n")
except Exception as e:
    print(f"   ❌ 错误: {e}\n")

# 4. 创建首次提交
print("4️⃣  创建首次提交...")
try:
    commit_msg = "Initial commit: RESUME_SKILL - AI-powered job application assistant"
    subprocess.run(['git', 'commit', '-m', commit_msg], check=True, capture_output=True)
    print("   ✅ 首次提交已创建\n")
except subprocess.CalledProcessError as e:
    print(f"   ⚠️  信息: 可能已有提交\n")

# 5. 显示Git状态
print("5️⃣  Git仓库状态:")
try:
    result = subprocess.run(['git', 'log', '--oneline', '-1'], capture_output=True, text=True)
    if result.stdout:
        print(f"   📌 最新提交: {result.stdout.strip()}\n")
except:
    pass

print("="*70)
print("  ✅ 本地Git仓库准备完毕！")
print("="*70 + "\n")

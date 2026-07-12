"""简单测试：验证chrome-devtools-mcp能在slim模式下工作"""

import subprocess
import json
import time
import sys

# 启动chrome-devtools-mcp进程
print("启动chrome-devtools-mcp...")
# Windows上需要使用shell=True
process = subprocess.Popen(
    "npx chrome-devtools-mcp@latest --headless --isolated --slim",
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    bufsize=1,
    shell=True
)

# 等待进程启动
time.sleep(3)

# 发送initialize请求
init_request = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {
            "name": "test-client",
            "version": "1.0.0"
        }
    }
}

print(f"发送初始化请求: {json.dumps(init_request)}")
try:
    process.stdin.write(json.dumps(init_request) + "\n")
    process.stdin.flush()
    
    # 等待响应
    time.sleep(2)
    
    # 尝试读取输出
    output = ""
    for _ in range(10):  # 尝试读取几行
        try:
            line = process.stdout.readline()
            if line:
                output += line
                print(f"收到输出: {line.strip()}")
        except Exception as e:
            print(f"读取错误: {e}")
            break
    
    print(f"\n最终输出: {output[:500]}...")
    
    # 尝试发送list_tools请求
    list_request = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {}
    }
    
    print(f"\n发送工具列表请求: {json.dumps(list_request)}")
    process.stdin.write(json.dumps(list_request) + "\n")
    process.stdin.flush()
    
    time.sleep(2)
    
    # 读取更多输出
    for _ in range(10):
        try:
            line = process.stdout.readline()
            if line:
                print(f"工具列表响应: {line.strip()}")
        except:
            break
    
except Exception as e:
    print(f"错误: {e}")
finally:
    # 终止进程
    print("\n终止进程...")
    process.terminate()
    process.wait()
    print("测试完成")
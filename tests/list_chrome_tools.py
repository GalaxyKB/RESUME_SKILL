"""列出chrome-devtools-mcp的所有可用工具"""

import subprocess
import json
import time
import threading

def list_chrome_tools():
    """启动chrome-devtools-mcp并列出所有可用工具"""
    
    # 启动进程
    cmd = "npx -y chrome-devtools-mcp@latest --headless --isolated"
    print(f"启动: {cmd}")
    
    process = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        shell=True
    )
    
    # 线程用于读取输出
    output_lines = []
    def read_output():
        while True:
            try:
                line = process.stdout.readline()
                if line:
                    output_lines.append(line.strip())
                    print(f"收到: {line.strip()}")
                else:
                    break
            except:
                break
    
    reader_thread = threading.Thread(target=read_output)
    reader_thread.daemon = True
    reader_thread.start()
    
    # 等待进程启动
    time.sleep(3)
    
    try:
        # 发送初始化请求
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "tool-lister", "version": "1.0"}
            }
        }
        
        print(f"发送初始化请求")
        process.stdin.write(json.dumps(init_request) + "\n")
        process.stdin.flush()
        
        time.sleep(2)
        
        # 发送工具列表请求
        list_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        
        print(f"发送工具列表请求")
        process.stdin.write(json.dumps(list_request) + "\n")
        process.stdin.flush()
        
        # 等待响应
        time.sleep(3)
        
        # 分析输出中的工具列表
        tools_found = []
        for line in output_lines:
            if "tools" in line.lower() or "name" in line.lower():
                try:
                    data = json.loads(line)
                    # 提取工具信息
                    if "result" in data and "tools" in data["result"]:
                        tools = data["result"]["tools"]
                        for tool in tools:
                            if isinstance(tool, dict) and "name" in tool:
                                tools_found.append({
                                    "name": tool["name"],
                                    "description": tool.get("description", ""),
                                    "inputSchema": tool.get("inputSchema", {})
                                })
                except json.JSONDecodeError:
                    continue
        
        return tools_found
        
    finally:
        # 清理
        process.terminate()
        process.wait()

if __name__ == "__main__":
    print("获取chrome-devtools-mcp工具列表...")
    tools = list_chrome_tools()
    
    print(f"\n找到 {len(tools)} 个工具:")
    for i, tool in enumerate(tools, 1):
        print(f"\n{i}. {tool['name']}")
        if tool['description']:
            print(f"   描述: {tool['description']}")
        if tool['inputSchema']:
            params = tool['inputSchema'].get('properties', {})
            if params:
                print(f"   参数: {list(params.keys())}")
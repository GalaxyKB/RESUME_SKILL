#!/bin/bash
# RESUME_SKILL 环境切换脚本 (Linux/macOS)

ENV_NAME="${1:-v24}"

function show_banner() {
    echo "=========================================="
    echo "RESUME_SKILL 环境切换工具"
    echo "=========================================="
    echo ""
}

function show_env_info() {
    local env_name=$1
    
    case $env_name in
        "v24")
            echo "🔧 v2.4 环境配置:"
            echo "  - Python 3.10+"
            echo "  - Node.js v18+"  
            echo "  - chrome-devtools-mcp"
            echo "  - 支持 MCP Agent (--use-mcp)"
            ;;
        "v23")
            echo "🔧 v2.3 环境配置:"
            echo "  - Python 3.9"
            echo "  - 传统自动化模式"
            echo "  - 兼容性最佳"
            ;;
        "base")
            echo "🔧 基础环境:"
            echo "  - 默认系统环境"
            echo "  - 用于开发和测试"
            ;;
        *)
            echo "❌ 未知环境: $env_name"
            exit 1
            ;;
    esac
    echo ""
}

function test_conda() {
    if ! command -v conda &> /dev/null; then
        echo "❌ Conda 未安装或不在 PATH 中"
        echo "请先安装 Anaconda 或 Miniconda"
        return 1
    fi
    return 0
}

function test_env() {
    local env_name=$1
    if conda env list | grep -q "^$env_name\s"; then
        return 0
    else
        echo "❌ 环境 '$env_name' 不存在"
        return 1
    fi
}

function create_v24_env() {
    echo "🔄 创建 v2.4 环境..."
    
    # 检查 Python 和 Node.js 是否可用
    if ! command -v python3 &> /dev/null || ! command -v node &> /dev/null; then
        echo "📦 使用 conda 安装 Python 3.10 和 Node.js..."
        conda create -n resume-skill-v24 python=3.10 nodejs -y
        
        if [ $? -ne 0 ]; then
            echo "❌ 环境创建失败"
            return 1
        fi
    else
        echo "📦 使用 conda 创建环境..."
        conda create -n resume-skill-v24 python=3.10 -y
        
        if [ $? -ne 0 ]; then
            echo "❌ 环境创建失败"
            return 1
        fi
    fi
    
    echo "✅ v2.4 环境创建成功"
    return 0
}

function create_v23_env() {
    echo "🔄 创建 v2.3 环境..."
    conda create -n resume-skill-v23 python=3.9 -y
    
    if [ $? -ne 0 ]; then
        echo "❌ 环境创建失败"
        return 1
    fi
    
    echo "✅ v2.3 环境创建成功"
    return 0
}

function setup_env() {
    local env_name=$1
    
    # 激活环境
    conda activate "resume-skill-$env_name"
    
    if [ $? -ne 0 ]; then
        echo "❌ 环境激活失败"
        return 1
    fi
    
    # 检查环境状态
    echo "🔍 检查环境状态..."
    
    python_version=$(python --version 2>&1)
    echo "  Python: $python_version"
    
    if [ "$env_name" = "v24" ]; then
        node_version=$(node --version 2>&1)
        echo "  Node.js: $node_version"
    fi
    
    echo "✅ 环境已激活: resume-skill-$env_name"
    return 0
}

# 参数验证
if [[ ! "$ENV_NAME" =~ ^(v24|v23|base)$ ]]; then
    echo "用法: source scripts/switch_env.sh [v24|v23|base]"
    echo "  v24  - 激活 v2.4 环境 (Python 3.10+ + Node.js)"
    echo "  v23  - 激活 v2.3 环境 (Python 3.9)"
    echo "  base - 返回基础环境"
    exit 1
fi

# 主程序
show_banner
show_env_info "$ENV_NAME"

# 检查 conda
if ! test_conda; then
    exit 1
fi

# 根据环境名称处理
TARGET_ENV="resume-skill-$ENV_NAME"

# 检查环境是否存在
if [ "$ENV_NAME" = "v24" ] || [ "$ENV_NAME" = "v23" ]; then
    if ! test_env "$TARGET_ENV"; then
        read -p "❓ 环境不存在，是否创建？ (y/N): " create_env
        if [[ "$create_env" =~ ^[Yy]$ ]]; then
            if [ "$ENV_NAME" = "v24" ]; then
                if ! create_v24_env; then exit 1; fi
            elif [ "$ENV_NAME" = "v23" ]; then
                if ! create_v23_env; then exit 1; fi
            fi
        else
            echo "操作取消"
            exit 0
        fi
    fi
fi

# 设置环境
if [ "$ENV_NAME" = "base" ]; then
    conda deactivate
    echo "✅ 已切换到基础环境"
else
    if ! setup_env "$ENV_NAME"; then
        exit 1
    fi
fi

# 显示使用提示
echo ""
echo "📋 环境已切换完成！"
echo ""

case $ENV_NAME in
    "v24")
        echo "🔧 接下来可以："
        echo "  pip install -e .                     # 安装项目依赖"
        echo "  playwright install chromium          # 安装浏览器"
        echo "  npx chrome-devtools-mcp@latest --help # 测试 MCP"
        echo "  resume-skill doctor                  # 验证安装"
        echo "  python scripts/verify_environment.py # 完整环境验证"
        ;;
    "v23")
        echo "🔧 接下来可以："
        echo "  pip install -e .                     # 安装项目依赖"
        echo "  playwright install chromium          # 安装浏览器"
        echo "  resume-skill doctor                  # 验证安装"
        ;;
    "base")
        echo "🔧 已返回到系统默认环境"
        ;;
esac

echo ""
echo "💡 提示：要退出环境，运行 'conda deactivate'"
echo "=========================================="
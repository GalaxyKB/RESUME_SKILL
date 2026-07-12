#!/bin/bash
# v2.4 一键安装脚本 (Linux/macOS)

function show_banner() {
    echo "=========================================="
    echo "RESUME_SKILL v2.4 一键安装工具"
    echo "=========================================="
    echo ""
}

function test_admin() {
    # 检查是否为 root
    if [[ $EUID -eq 0 ]]; then
        echo "🔓 管理员模式"
        return 0
    else
        return 1
    fi
}

function test_conda() {
    if ! command -v conda &> /dev/null; then
        echo "❌ Conda 未安装"
        echo ""
        echo "请安装 Anaconda 或 Miniconda："
        echo "1. 访问 https://docs.anaconda.com/free/anaconda/install/"
        echo "2. 下载 Linux/macOS 版本安装包"
        echo "3. 按照指南安装"
        echo "4. 重启终端后重新运行此脚本"
        return 1
    fi
    return 0
}

function install_nodejs_linux() {
    echo "📦 安装 Node.js (Linux)..."

    if [[ $(command -v apt) ]]; then
        # Ubuntu/Debian
        curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
        sudo apt-get install -y nodejs
    elif [[ $(command -v yum) ]]; then
        # CentOS/RHEL
        curl -fsSL https://rpm.nodesource.com/setup_20.x | sudo bash -
        sudo yum install -y nodejs
    elif [[ $(command -v dnf) ]]; then
        # Fedora
        curl -fsSL https://rpm.nodesource.com/setup_20.x | sudo bash -
        sudo dnf install -y nodejs
    elif [[ $(command -v pacman) ]]; then
        # Arch Linux
        sudo pacman -S nodejs npm
    else
        echo "⚠️  不支持的系统包管理器，请手动安装 Node.js"
        return 1
    fi

    if [[ $? -eq 0 ]]; then
        echo "✅ Node.js 安装成功"
        node_version=$(node --version)
        npm_version=$(npm --version)
        echo "  Node.js: $node_version"
        echo "  npm: $npm_version"
        return 0
    else
        echo "❌ Node.js 安装失败"
        return 1
    fi
}

function install_nodejs_macos() {
    echo "📦 安装 Node.js (macOS)..."

    if command -v brew &> /dev/null; then
        brew install node
    else
        echo "⚠️  Homebrew 未安装，请先安装 Homebrew 或手动安装 Node.js"
        echo "   安装 Homebrew: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
        return 1
    fi

    if [[ $? -eq 0 ]]; then
        echo "✅ Node.js 安装成功"
        node_version=$(node --version)
        npm_version=$(npm --version)
        echo "  Node.js: $node_version"
        echo "  npm: $npm_version"
        return 0
    else
        echo "❌ Node.js 安装失败"
        return 1
    fi
}

function install_nodejs() {
    local os=$(uname -s)
    
    case $os in
        "Linux")
            if ! test_admin; then
                echo "⚠️  需要管理员权限来安装 Node.js"
                echo "   请使用 sudo 重新运行此脚本"
                return 1
            fi
            install_nodejs_linux
            ;;
        "Darwin")
            install_nodejs_macos
            ;;
        *)
            echo "❌ 不支持的操作系统: $os"
            return 1
            ;;
    esac
}

function create_conda_env() {
    echo "🐍 创建 Conda 环境..."

    # 检查是否已有环境
    if conda env list | grep -q "^resume-skill-v24\s"; then
        read -p "❓ 环境已存在，是否重新创建？ (y/N): " recreate
        if [[ ! "$recreate" =~ ^[Yy]$ ]]; then
            echo "✅ 使用现有环境"
            return 0
        fi
    fi

    # 创建新环境
    echo "📦 创建 Python 3.10 + Node.js 环境..."
    conda create -n resume-skill-v24 python=3.10 nodejs -y

    if [[ $? -eq 0 ]]; then
        echo "✅ Conda 环境创建成功"
        return 0
    else
        echo "❌ Conda 环境创建失败"
        return 1
    fi
}

function setup_environment() {
    echo "🔧 配置项目环境..."

    # 激活环境
    conda activate resume-skill-v24

    if [[ $? -ne 0 ]]; then
        echo "❌ 环境激活失败"
        return 1
    fi

    echo "✅ 环境已激活"

    # 验证环境
    echo "🔍 验证环境配置..."

    python_version=$(python --version 2>&1)
    node_version=$(node --version 2>&1)

    echo "  Python: $python_version"
    echo "  Node.js: $node_version"

    return 0
}

function install_dependencies() {
    echo "📦 安装项目依赖..."

    # 检查是否在项目目录
    if [[ ! -f "pyproject.toml" ]]; then
        echo "❌ 不在项目根目录，请确保在 RESUME_SKILL 目录中运行此脚本"
        return 1
    fi

    # 安装 Python 依赖
    echo "1. 安装 Python 包..."
    pip install -e .

    if [[ $? -ne 0 ]]; then
        echo "❌ Python 依赖安装失败"
        return 1
    fi

    echo "✅ Python 依赖安装成功"

    # 安装 Playwright 浏览器
    echo "2. 安装 Playwright 浏览器..."
    playwright install chromium

    if [[ $? -ne 0 ]]; then
        echo "⚠️  Playwright 安装可能有问题，但继续安装"
    else
        echo "✅ Playwright 安装成功"
    fi

    return 0
}

function test_chrome_devtools() {
    echo "🛠️ 测试 chrome-devtools-mcp..."

    result=$(npx chrome-devtools-mcp@latest --help 2>&1)
    if [[ $? -eq 0 ]]; then
        echo "✅ chrome-devtools-mcp 测试成功"
        return 0
    else
        echo "⚠️  chrome-devtools-mcp 测试失败，但继续安装"
        echo "   错误: $result"
        return 1
    fi
}

function final_verification() {
    echo "🔍 最终验证..."

    tests=(
        "Python 版本:python --version"
        "Node.js 版本:node --version"
        "npx 可用性:npx --version"
        "resume-skill 命令:resume-skill --version"
    )

    all_passed=0
    for test in "${tests[@]}"; do
        IFS=':' read -r name command <<< "$test"
        output=$($command 2>&1)
        if [[ $? -eq 0 ]]; then
            echo "  ✅ $name: $(echo "$output" | tr -d '\n')"
            ((all_passed++))
        else
            echo "  ❌ $name: 失败"
        fi
    done

    if [[ $all_passed -eq ${#tests[@]} ]]; then
        return 0
    else
        return 1
    fi
}

function show_installation_complete() {
    echo ""
    echo "🎉 安装完成！"
    echo "=========================================="
    echo ""
    echo "📋 下一步操作："
    echo "1. 配置 API 密钥:"
    echo "   cp .env.example .env"
    echo "   # 编辑 .env 文件，填入你的 API 密钥"
    echo ""
    echo "2. 验证安装:"
    echo "   resume-skill doctor"
    echo "   python scripts/verify_environment.py"
    echo ""
    echo "3. 运行测试:"
    echo "   python tests/test_chrome_full.py"
    echo "   python tests/test_v24_integration.py"
    echo ""
    echo "4. 使用 v2.4 MCP Agent:"
    echo "   resume-skill apply --url \"URL\" --use-mcp --headless"
    echo ""
    echo "💡 提示："
    echo "- 环境已激活为 'resume-skill-v24'"
    echo "- 要退出环境，运行 'conda deactivate'"
    echo "- 要重新激活，运行 'conda activate resume-skill-v24'"
    echo ""
    echo "=========================================="
}

# 主程序
show_banner

# 检查 conda
if ! test_conda; then
    exit 1
fi

# 创建 conda 环境
if ! create_conda_env; then
    exit 1
fi

# 配置环境
if ! setup_environment; then
    exit 1
fi

# 安装依赖
if ! install_dependencies; then
    exit 1
fi

# 测试 chrome-devtools-mcp
test_chrome_devtools

# 最终验证
if ! final_verification; then
    echo "⚠️  验证失败，但安装基本完成"
fi

# 显示完成信息
show_installation_complete
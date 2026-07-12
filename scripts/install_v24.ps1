# v2.4 一键安装脚本 (PowerShell)

function Show-Banner {
    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Host "RESUME_SKILL v2.4 一键安装工具" -ForegroundColor Cyan
    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Host ""
}

function Test-Admin {
    # 检查是否为管理员
    $currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    return $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Test-Conda {
    $condaExists = Get-Command conda -ErrorAction SilentlyContinue
    if (-not $condaExists) {
        Write-Host "❌ Conda 未安装" -ForegroundColor Red
        Write-Host ""
        Write-Host "请安装 Anaconda 或 Miniconda：" -ForegroundColor Yellow
        Write-Host "1. 访问 https://docs.anaconda.com/free/anaconda/install/" -ForegroundColor Gray
        Write-Host "2. 下载 Windows 版本安装包" -ForegroundColor Gray
        Write-Host "3. 安装时选择 'Add to PATH'" -ForegroundColor Gray
        Write-Host "4. 重启终端后重新运行此脚本" -ForegroundColor Gray
        return $false
    }
    return $true
}

function Install-Chocolatey {
    Write-Host "🍫 安装 Chocolatey 包管理器..." -ForegroundColor Yellow
    
    if (!(Test-Admin)) {
        Write-Host "⚠️  需要管理员权限来安装 Chocolatey" -ForegroundColor Yellow
        Write-Host "   请在管理员终端中重新运行此脚本" -ForegroundColor Gray
        return $false
    }
    
    try {
        Set-ExecutionPolicy Bypass -Scope Process -Force
        [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
        Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ Chocolatey 安装成功" -ForegroundColor Green
            return $true
        } else {
            Write-Host "❌ Chocolatey 安装失败" -ForegroundColor Red
            return $false
        }
    } catch {
        Write-Host "❌ Chocolatey 安装错误: $_" -ForegroundColor Red
        return $false
    }
}

function Install-Nodejs {
    Write-Host "📦 安装 Node.js..." -ForegroundColor Yellow
    
    if (!(Test-Admin)) {
        Write-Host "⚠️  需要管理员权限来安装 Node.js" -ForegroundColor Yellow
        Write-Host "   请在管理员终端中重新运行此脚本" -ForegroundColor Gray
        return $false
    }
    
    try {
        choco install nodejs -y
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ Node.js 安装成功" -ForegroundColor Green
            
            # 刷新环境变量
            $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
            
            # 验证安装
            $nodeVersion = node --version 2>&1
            $npmVersion = npm --version 2>&1
            
            Write-Host "  Node.js: $nodeVersion" -ForegroundColor Gray
            Write-Host "  npm: $npmVersion" -ForegroundColor Gray
            
            return $true
        } else {
            Write-Host "❌ Node.js 安装失败" -ForegroundColor Red
            return $false
        }
    } catch {
        Write-Host "❌ Node.js 安装错误: $_" -ForegroundColor Red
        return $false
    }
}

function Create-CondaEnv {
    Write-Host "🐍 创建 Conda 环境..." -ForegroundColor Yellow
    
    # 检查是否已有环境
    $envExists = conda env list | Select-String -Pattern "^resume-skill-v24\s"
    if ($envExists) {
        $recreate = Read-Host "❓ 环境已存在，是否重新创建？ (y/N)"
        if ($recreate.ToLower() -ne "y") {
            Write-Host "✅ 使用现有环境" -ForegroundColor Green
            return $true
        }
    }
    
    # 创建新环境
    Write-Host "📦 创建 Python 3.10 + Node.js 环境..." -ForegroundColor Yellow
    conda create -n resume-skill-v24 python=3.10 nodejs -y
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Conda 环境创建成功" -ForegroundColor Green
        return $true
    } else {
        Write-Host "❌ Conda 环境创建失败" -ForegroundColor Red
        return $false
    }
}

function Setup-Environment {
    Write-Host "🔧 配置项目环境..." -ForegroundColor Yellow
    
    # 激活环境
    conda activate resume-skill-v24
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ 环境激活失败" -ForegroundColor Red
        return $false
    }
    
    Write-Host "✅ 环境已激活" -ForegroundColor Green
    
    # 验证环境
    Write-Host "🔍 验证环境配置..." -ForegroundColor Yellow
    
    $pythonVersion = python --version 2>&1
    $nodeVersion = node --version 2>&1
    
    Write-Host "  Python: $pythonVersion" -ForegroundColor Gray
    Write-Host "  Node.js: $nodeVersion" -ForegroundColor Gray
    
    return $true
}

function Install-Dependencies {
    Write-Host "📦 安装项目依赖..." -ForegroundColor Yellow
    
    # 检查是否在项目目录
    $pyproject = Test-Path "pyproject.toml"
    if (-not $pyproject) {
        Write-Host "❌ 不在项目根目录，请确保在 RESUME_SKILL 目录中运行此脚本" -ForegroundColor Red
        return $false
    }
    
    # 安装 Python 依赖
    Write-Host "1. 安装 Python 包..." -ForegroundColor Gray
    pip install -e .
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Python 依赖安装失败" -ForegroundColor Red
        return $false
    }
    
    Write-Host "✅ Python 依赖安装成功" -ForegroundColor Green
    
    # 安装 Playwright 浏览器
    Write-Host "2. 安装 Playwright 浏览器..." -ForegroundColor Gray
    playwright install chromium
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "⚠️  Playwright 安装可能有问题，但继续安装" -ForegroundColor Yellow
    } else {
        Write-Host "✅ Playwright 安装成功" -ForegroundColor Green
    }
    
    return $true
}

function Test-ChromeDevTools {
    Write-Host "🛠️ 测试 chrome-devtools-mcp..." -ForegroundColor Yellow
    
    try {
        $result = npx chrome-devtools-mcp@latest --help 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ chrome-devtools-mcp 测试成功" -ForegroundColor Green
            return $true
        } else {
            Write-Host "⚠️  chrome-devtools-mcp 测试失败，但继续安装" -ForegroundColor Yellow
            Write-Host "   错误: $result" -ForegroundColor Gray
            return $false
        }
    } catch {
        Write-Host "⚠️  chrome-devtools-mcp 测试异常，但继续安装" -ForegroundColor Yellow
        return $false
    }
}

function Final-Verification {
    Write-Host "🔍 最终验证..." -ForegroundColor Yellow
    
    $tests = @(
        @{ Name = "Python 版本"; Command = "python --version" },
        @{ Name = "Node.js 版本"; Command = "node --version" },
        @{ Name = "npx 可用性"; Command = "npx --version" },
        @{ Name = "resume-skill 命令"; Command = "resume-skill --version" }
    )
    
    $allPassed = $true
    foreach ($test in $tests) {
        try {
            $output = Invoke-Expression $test.Command 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-Host "  ✅ $($test.Name): $($output.Trim())" -ForegroundColor Green
            } else {
                Write-Host "  ❌ $($test.Name): 失败" -ForegroundColor Red
                $allPassed = $false
            }
        } catch {
            Write-Host "  ❌ $($test.Name): 错误" -ForegroundColor Red
            $allPassed = $false
        }
    }
    
    return $allPassed
}

function Show-Installation-Complete {
    Write-Host ""
    Write-Host "🎉 安装完成！" -ForegroundColor Cyan
    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "📋 下一步操作：" -ForegroundColor Yellow
    Write-Host "1. 配置 API 密钥:" -ForegroundColor Gray
    Write-Host "   cp .env.example .env" -ForegroundColor White
    Write-Host "   # 编辑 .env 文件，填入你的 API 密钥" -ForegroundColor Gray
    Write-Host ""
    Write-Host "2. 验证安装:" -ForegroundColor Gray
    Write-Host "   resume-skill doctor" -ForegroundColor White
    Write-Host "   python scripts/verify_environment.py" -ForegroundColor White
    Write-Host ""
    Write-Host "3. 运行测试:" -ForegroundColor Gray
    Write-Host "   python tests/test_chrome_full.py" -ForegroundColor White
    Write-Host "   python tests/test_v24_integration.py" -ForegroundColor White
    Write-Host ""
    Write-Host "4. 使用 v2.4 MCP Agent:" -ForegroundColor Gray
    Write-Host "   resume-skill apply --url \"URL\" --use-mcp --headless" -ForegroundColor White
    Write-Host ""
    Write-Host "💡 提示：" -ForegroundColor Magenta
    Write-Host "- 环境已激活为 'resume-skill-v24'" -ForegroundColor Gray
    Write-Host "- 要退出环境，运行 'conda deactivate'" -ForegroundColor Gray
    Write-Host "- 要重新激活，运行 'conda activate resume-skill-v24'" -ForegroundColor Gray
    Write-Host ""
    Write-Host "==========================================" -ForegroundColor Cyan
}

# 主程序
Show-Banner

# 检查是否在管理员模式下运行
$isAdmin = Test-Admin
if ($isAdmin) {
    Write-Host "🔓 管理员模式" -ForegroundColor Green
}

# 检查 conda
if (!(Test-Conda)) {
    exit 1
}

# 创建 conda 环境
if (!(Create-CondaEnv)) {
    exit 1
}

# 配置环境
if (!(Setup-Environment)) {
    exit 1
}

# 安装依赖
if (!(Install-Dependencies)) {
    exit 1
}

# 测试 chrome-devtools-mcp
Test-ChromeDevTools | Out-Null

# 最终验证
if (!(Final-Verification)) {
    Write-Host "⚠️  验证失败，但安装基本完成" -ForegroundColor Yellow
}

# 显示完成信息
Show-Installation-Complete
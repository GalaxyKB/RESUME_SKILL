# RESUME_SKILL 环境切换脚本 (PowerShell)

param(
    [Parameter(Mandatory=$false)]
    [ValidateSet("v24", "v23", "base")]
    [string]$EnvName = "v24"
)

function Show-Banner {
    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Host "RESUME_SKILL 环境切换工具" -ForegroundColor Cyan
    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Host ""
}

function Show-EnvInfo {
    param([string]$envName)
    
    switch ($envName) {
        "v24" {
            Write-Host "🔧 v2.4 环境配置:" -ForegroundColor Yellow
            Write-Host "  - Python 3.10+" -ForegroundColor Green
            Write-Host "  - Node.js v18+" -ForegroundColor Green  
            Write-Host "  - chrome-devtools-mcp" -ForegroundColor Green
            Write-Host "  - 支持 MCP Agent (--use-mcp)" -ForegroundColor Green
        }
        "v23" {
            Write-Host "🔧 v2.3 环境配置:" -ForegroundColor Yellow
            Write-Host "  - Python 3.9" -ForegroundColor Green
            Write-Host "  - 传统自动化模式" -ForegroundColor Green
            Write-Host "  - 兼容性最佳" -ForegroundColor Green
        }
        "base" {
            Write-Host "🔧 基础环境:" -ForegroundColor Yellow
            Write-Host "  - 默认系统环境" -ForegroundColor Green
            Write-Host "  - 用于开发和测试" -ForegroundColor Green
        }
    }
    Write-Host ""
}

function Test-Conda {
    $condaExists = Get-Command conda -ErrorAction SilentlyContinue
    if (-not $condaExists) {
        Write-Host "❌ Conda 未安装或不在 PATH 中" -ForegroundColor Red
        Write-Host "请先安装 Anaconda 或 Miniconda" -ForegroundColor Yellow
        return $false
    }
    return $true
}

function Test-Env {
    param([string]$envName)
    
    $envs = conda env list | Select-String -Pattern "^$envName\s"
    if ($envs) {
        return $true
    } else {
        Write-Host "❌ 环境 '$envName' 不存在" -ForegroundColor Red
        return $false
    }
}

function Create-v24-Env {
    Write-Host "🔄 创建 v2.4 环境..." -ForegroundColor Yellow
    
    # 检查 Python 和 Node.js 是否可用
    $pythonExists = Get-Command python -ErrorAction SilentlyContinue
    $nodeExists = Get-Command node -ErrorAction SilentlyContinue
    
    if (-not $pythonExists -or -not $nodeExists) {
        Write-Host "📦 使用 conda 安装 Python 3.10 和 Node.js..." -ForegroundColor Yellow
        conda create -n resume-skill-v24 python=3.10 nodejs -y
        
        if ($LASTEXITCODE -ne 0) {
            Write-Host "❌ 环境创建失败" -ForegroundColor Red
            return $false
        }
    } else {
        Write-Host "📦 使用 conda 创建环境..." -ForegroundColor Yellow
        conda create -n resume-skill-v24 python=3.10 -y
        
        if ($LASTEXITCODE -ne 0) {
            Write-Host "❌ 环境创建失败" -ForegroundColor Red
            return $false
        }
    }
    
    Write-Host "✅ v2.4 环境创建成功" -ForegroundColor Green
    return $true
}

function Create-v23-Env {
    Write-Host "🔄 创建 v2.3 环境..." -ForegroundColor Yellow
    conda create -n resume-skill-v23 python=3.9 -y
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ 环境创建失败" -ForegroundColor Red
        return $false
    }
    
    Write-Host "✅ v2.3 环境创建成功" -ForegroundColor Green
    return $true
}

function Setup-Env {
    param([string]$envName)
    
    # 激活环境
    conda activate "resume-skill-$envName"
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ 环境激活失败" -ForegroundColor Red
        return $false
    }
    
    # 检查环境状态
    Write-Host "🔍 检查环境状态..." -ForegroundColor Yellow
    
    $pythonVersion = python --version 2>&1
    Write-Host "  Python: $pythonVersion" -ForegroundColor Gray
    
    if ($envName -eq "v24") {
        $nodeVersion = node --version 2>&1
        Write-Host "  Node.js: $nodeVersion" -ForegroundColor Gray
    }
    
    Write-Host "✅ 环境已激活: resume-skill-$envName" -ForegroundColor Green
    return $true
}

# 主程序
Show-Banner
Show-EnvInfo -envName $EnvName

# 检查 conda
if (-not (Test-Conda)) {
    exit 1
}

# 根据环境名称处理
$targetEnv = "resume-skill-$EnvName"

# 检查环境是否存在
if ($EnvName -eq "v24" -or $EnvName -eq "v23") {
    if (-not (Test-Env -envName $targetEnv)) {
        $createEnv = Read-Host "❓ 环境不存在，是否创建？ (y/N)"
        if ($createEnv.ToLower() -eq "y") {
            if ($EnvName -eq "v24") {
                if (-not (Create-v24-Env)) { exit 1 }
            } elseif ($EnvName -eq "v23") {
                if (-not (Create-v23-Env)) { exit 1 }
            }
        } else {
            Write-Host "操作取消" -ForegroundColor Yellow
            exit 0
        }
    }
}

# 设置环境
if ($EnvName -eq "base") {
    conda deactivate
    Write-Host "✅ 已切换到基础环境" -ForegroundColor Green
} else {
    if (-not (Setup-Env -envName $EnvName)) {
        exit 1
    }
}

# 显示使用提示
Write-Host ""
Write-Host "📋 环境已切换完成！" -ForegroundColor Cyan
Write-Host ""

switch ($EnvName) {
    "v24" {
        Write-Host "🔧 接下来可以：" -ForegroundColor Yellow
        Write-Host "  pip install -e .                     # 安装项目依赖" -ForegroundColor Gray
        Write-Host "  playwright install chromium          # 安装浏览器" -ForegroundColor Gray
        Write-Host "  npx chrome-devtools-mcp@latest --help # 测试 MCP" -ForegroundColor Gray
        Write-Host "  resume-skill doctor                  # 验证安装" -ForegroundColor Gray
        Write-Host "  python scripts/verify_environment.py # 完整环境验证" -ForegroundColor Gray
    }
    "v23" {
        Write-Host "🔧 接下来可以：" -ForegroundColor Yellow
        Write-Host "  pip install -e .                     # 安装项目依赖" -ForegroundColor Gray
        Write-Host "  playwright install chromium          # 安装浏览器" -ForegroundColor Gray
        Write-Host "  resume-skill doctor                  # 验证安装" -ForegroundColor Gray
    }
    "base" {
        Write-Host "🔧 已返回到系统默认环境" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "💡 提示：要退出环境，运行 'conda deactivate'" -ForegroundColor Magenta
Write-Host "==========================================" -ForegroundColor Cyan
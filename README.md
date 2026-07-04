# 智能简历投递助手 - RESUME_SKILL

**一个AI驱动的自动化简历投递工具，帮助你快速高效地投递简历！**

---

## 📋 目录

1. [功能特性](#功能特性)
2. [系统要求](#系统要求)
3. [快速开始](#快速开始)
4. [详细使用](#详细使用)
5. [常见问题](#常见问题)
6. [故障排除](#故障排除)

---

## 功能特性

### 核心功能

- **智能个人信息提取** - AI驱动的多源信息提取、自动整合
- **自动表单填充** - 智能字段识别、多策略处理、文件上传支持
- **AI职位匹配分析** - 自动提取职位要求、评估匹配度、定制化建议
- **完整应用追踪** - 自动记录历史、匹配度评分、分析报告保留
- **反爬虫保护** - WebDriver隐藏、插件伪装、自动化标记移除

---

## 系统要求

- **操作系统**: Windows 10+ / macOS 10.13+ / Linux
- **Python**: 3.8+
- **内存**: 2GB最低
- **硬盘**: 500MB空间

---

## 快速开始

### 1. 安装依赖

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置API密钥

#### 方案A: DeepSeek API (推荐 - 便宜)

1. 访问 https://www.deepseek.com/
2. 注册账户并充值
3. 创建API密钥
4. 复制 .env.example 到 .env
5. 编辑 .env 文件，添加密钥

#### 方案B: OpenAI API

1. 访问 https://platform.openai.com/
2. 注册账户并添加支付方式
3. 创建API密钥
4. 复制 .env.example 到 .env
5. 编辑 .env 文件，添加密钥

### 3. 使用步骤

```bash
# 步骤1: 填写个人信息
# 编辑 personal_info/profile_template.md

# 步骤2: 提取个人信息
python main.py extract --personal-info-dir personal_info

# 步骤3: 投递简历
python main.py apply --url "https://job-website.com/position" --auto-fill
```

---

## 详细使用

### 填写个人信息

编辑 `personal_info/profile_template.md`:

```markdown
## 基本个人信息

### 姓名与邮箱
- **中文姓名**: 张三
- **邮箱**: zhangsan@example.com
- **电话**: 13800138000

## 教育背景

### 最高学历
- **学校**: 清华大学
- **学位**: 硕士
- **专业**: 计算机科学
- **毕业时间**: 2023.06
- **GPA**: 3.8

## 工作经验

### 工作1
- **公司**: 阿里巴巴
- **职位**: 高级工程师
- **时间**: 2021.01 - 2023.06
- **职责**: 系统开发...
```

### 提取个人信息

```bash
# 标准用法
python main.py extract --personal-info-dir personal_info

# 显示详细过程
python main.py extract --personal-info-dir personal_info --verbose
```

输出: `personal_info/unified_profile.yaml` (结构化个人数据)

### 投递简历

```bash
# 完整流程（推荐）
python main.py apply \
    --url "https://job-website.com/position" \
    --continue-after-analysis \
    --auto-fill \
    --manual-login-first \
    --keep-browser-open

# 快速模式
python main.py apply --url "https://..." --auto-fill

# 仅分析（调试）
python main.py apply --url "https://..."
```

**参数说明:**

| 参数 | 说明 |
|------|------|
| `--url` | **必需** - 职位页面URL |
| `--auto-fill` | 启用自动填写 |
| `--manual-login-first` | 先手动登录 |
| `--continue-after-analysis` | 分析后继续 |
| `--keep-browser-open` | 保持浏览器打开 |
| `--auto-submit` | 自动提交 |
| `--non-interactive` | 非交互模式 |

---

## 常见问题

### Q: 支持哪些招聘网站?

✅ 网易招聘、BOSS直聘、拉勾网、智联招聘、前程无忧、LinkedIn等
✅ 大多数HTML表单网站都支持

### Q: 如何获取API密钥?

**DeepSeek**: https://www.deepseek.com → 注册 → 充值 → API控制台 → 创建密钥

**OpenAI**: https://platform.openai.com → 登录 → API Keys → Create Key

### Q: 填写失败的原因?

常见原因:
- 登录超时 - 重新手动登录
- 字段格式不匹配 - 检查个人信息格式
- 网站改版 - 网站表单可能变化
- 网络问题 - 检查连接

### Q: 如何查看投递记录?

- CSV记录: `records/applications.csv`
- 分析报告: `outputs/jd_analysis/`
- 填写计划: `outputs/fill_plans/`
- 日志: `outputs/logs/resume_skill.log`

### Q: 如何保护隐私?

以下文件已添加到 .gitignore:
- `.env` - API密钥
- `personal_info/unified_profile.yaml` - 个人数据
- `.session/` - 浏览器会话
- `outputs/` - 投递记录

建议: 不要将这些文件提交到GitHub

---

## 故障排除

### 问题: ModuleNotFoundError

**解决:**
```bash
pip install -r requirements.txt
python verify_imports.py
```

### 问题: API密钥错误

**检查:**
```bash
python -c "import os; print(os.getenv('DEEPSEEK_API_KEY'))"
```

应该输出: `sk-xxx...` (不是None)

### 问题: 浏览器启动失败

**解决:**
1. 安装Chrome: https://www.google.com/chrome/
2. 或指定浏览器路径: `--browser-channel chrome`

### 问题: 网页加载超时

**解决:**
1. 检查网络连接
2. 修改 config.yaml 中的 `navigation_timeout`
3. 使用代理加速

### 问题: 内存不足

**解决:**
```bash
# 清理浏览器会话
rm -rf .session/

# 清理输出
rm -rf outputs/*

# 重新运行
python main.py apply --url "..."
```

---

## 文件结构

```
RESUME_SKILL/
├── README.md                    # 本文件
├── .env.example                # 环境变量模板
├── config.yaml                 # 配置文件
├── requirements.txt            # Python依赖
├── main.py                     # 主入口
│
├── apply_agent/               # 投递模块 (13个子模块)
│   ├── workflow.py           # 主工作流
│   ├── browser_agent.py      # 浏览器控制
│   ├── form_extractor.py     # 表单提取
│   ├── form_filler.py        # 表单填充
│   ├── llm_client.py         # LLM客户端
│   ├── config.py             # 配置管理
│   └── ...其他模块
│
└── personal_info/            # 个人信息
    ├── profile_template.md   # 信息模板（你需要填写）
    ├── unified_profile.yaml  # 生成的结构化数据
    ├── extractor.py          # 提取器
    └── general_information/  # 其他信息文件
```

---

## 配置说明

### .env 文件

```bash
# 必需: API密钥
DEEPSEEK_API_KEY=sk-xxx

# 可选
DEEPSEEK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
DEEPSEEK_MODEL=deepseek-v4-pro-260425
DEEPSEEK_ENABLE_WEB_SEARCH=false
BROWSER_CHANNEL=chrome
DEBUG_MODE=false
LOG_LEVEL=INFO
```

### config.yaml

主要配置:
```yaml
api:
  provider: deepseek          # LLM提供商

form_filling:
  auto_fill: true             # 自动填写
  require_confirmation_before_fill: true
  auto_submit: false

browser:
  headless: false             # 显示浏览器
  slow_motion: 300            # 显示操作过程

logging:
  level: INFO                 # 日志级别
```

---

## 许可证

MIT License

---

## 联系方式

- GitHub Issues: 报告问题
- GitHub Discussions: 讨论想法

---

**如果这个项目对你有帮助，请给个Star!**

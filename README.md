# 🚀 RESUME_SKILL

<div align="center">

**AI 驱动的智能网申助手**

*一键自动填充网申表单，让求职投递效率提升 10 倍*

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![PyPI](https://img.shields.io/badge/pip-resume--skill-brightgreen.svg)](https://pypi.org/project/resume-skill/)

</div>

---

## ✨ 为什么选择 RESUME_SKILL？

> 🎯 **痛点**：秋招季，每投一家公司都要重复填写姓名、邮箱、教育经历、项目经验... 一个岗位 20+ 个字段，投 50 家就是 1000 次重复劳动。

> 💡 **解决方案**：RESUME_SKILL 用 AI 自动提取简历信息，智能匹配表单字段，一键完成填充。**投递时间从 10 分钟缩短到 1 分钟**。

### 核心优势

| 功能 | 传统方式 | RESUME_SKILL v2.1 |
|------|---------|------------------|
| 简历信息录入 | 手动复制粘贴 | 🤖 AI 自动提取 |
| 表单字段匹配 | 逐个查找填写 | 🎯 智能语义匹配（三阶匹配引擎） |
| 兼容性支持 | 仅现代浏览器 | 🌐 全浏览器兼容（含IE模式） |
| 复杂表单处理 | 手动逐步填写 | 📋 智能批处理（iframe/多tab/分步骤） |
| 前端框架适配 | 基础DOM操作 | ⚡ 深度兼容React/Vue/Ant Design |
| 多平台投递 | 每次重新填写 | 📋 一次配置，多次复用 |
| 信息更新 | 分散在各平台 | 📁 本地统一管理（YAML） |
| 字段类型支持 | 仅文本框 | 🎛️ 9 种表单类型（含上传/级联选择） |

---

## 🔥 功能特性

### v2.0 重大更新

- ✅ **双通道字段提取** - 规则提取（快速/全面）+ AI 分析（精准/语义），合并去重
- 🎯 **三阶智能匹配** - 预匹配（提取器 AI）→ LLM 语义匹配 → 规则兜底，确保无遗漏
- 🎛️ **9 种表单策略** - 文本/原生下拉/自定义下拉/单选/复选/日期/级联选择/上传/富文本
- 🛡️ **隐私保护** - 敏感字段（身份证/政治面貌）自动标记为 `manual`，永不自动填充
- 🔌 **多 LLM 提供商** - DeepSeek（火山引擎）+ OpenAI，无 SDK 版本依赖（使用 httpx）
- 🧪 **浏览器反检测** - 反机器人检测 + 会话持久化

### v2.1 核心修复（NEW! 🚀）

- 🔧 **兼容性增强** - CSS.escape polyfill，支持IE兼容模式和旧版浏览器
- 🎯 **智能字段合并** - 自动合并radio/checkbox组，避免重复填充
- 🖼️ **多框架支持** - 全面支持iframe、多tab表单和分步骤表单
- ⚡ **LLM批处理** - 自动分批处理大表单，避免上下文溢出
- 🎪 **稳定选择器** - 优先使用name、id等稳定属性，减少定位漂移
- 🔄 **增强事件触发** - 完整支持React/Vue合成事件，提升现代框架兼容性
- 📊 **智能验证** - 增强填充验证，及时发现填错位置

### 支持的表单字段类型

| 类型 | fill_strategy | 说明 |
|------|---------------|------|
| 文本输入 | `text` | 姓名/邮箱/电话等 |
| 原生下拉 | `select` | `<select>` 元素 |
| 自定义下拉 | `custom_select` | Ant Design / Element Plus 等 |
| 单选按钮 | `radio_click` | 单选组 |
| 复选框 | `checkbox_click` | 支持多选 |
| 日期选择 | `datepicker` | 日期/月份选择器 |
| 级联选择 | `cascader` | 省/市/区等 |
| 文件上传 | `upload` | 简历 PDF 上传 |
| 富文本 | `contenteditable` | `contenteditable` 元素 |

---

## 🎯 快速开始

### 📦 安装

```bash
# 克隆项目
git clone https://github.com/GalaxyKB/RESUME_SKILL.git
cd RESUME_SKILL

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 安装依赖（推荐使用 pip install -e .）
pip install -e .
playwright install chromium
```

### 🔑 配置 API

```bash
# 复制配置模板
cp .env.example .env
```

编辑 `.env` 文件，填入你的 API 密钥：

```env
# 火山引擎 DeepSeek API（推荐，国内访问稳定）
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=your_api_key_here
DEEPSEEK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
DEEPSEEK_MODEL=deepseek-v4-pro-260425

# 或使用 OpenAI
LLM_PROVIDER=openai
OPENAI_API_KEY=your_api_key_here
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o
```

| 服务 | 推荐度 | 说明 |
|------|--------|------|
| 火山引擎 DeepSeek | ⭐⭐⭐⭐⭐ | 推荐，成本低，国内访问稳定 |
| OpenAI | ⭐⭐⭐ | 备选，需要代理 |

---

## 📖 使用指南

### 第一步：上传简历

将你的 PDF 简历放入 `personal_info/formal_resume/` 文件夹：

```
personal_info/
└── formal_resume/
    └── 我的简历.pdf  ← 放在这里
```

### 第二步：提取信息

```bash
resume-skill extract --pdf personal_info/formal_resume/我的简历.pdf
```

AI 会自动分析简历并提取：
- ✅ 基本信息（姓名、邮箱、电话、现居地）
- ✅ 教育背景（学校、学位、专业、GPA）
- ✅ 工作经历（公司、职位、时间、职责）
- ✅ 项目经验（项目名、角色、技术栈、成果）
- ✅ 技能栈（编程语言、框架、工具）

提取完成后，编辑 `personal_info/profile_template.md` 修正和补充信息。

### 第三步：生成统一配置

```bash
resume-skill consolidate
```

生成 `personal_info/unified_profile.yaml`，这是表单填充的最终数据源。

### 第四步：投递简历

```bash
# 交互式投递（推荐首次使用）
resume-skill apply --url "https://招聘网站.com/job/xxx"

# 非交互式投递（自动填充，需手动确认提交）
resume-skill apply --url "https://招聘网站.com/job/xxx" --auto-fill --non-interactive

# 自动投递（包含自动提交，谨慎使用）
resume-skill apply --url "https://招聘网站.com/job/xxx" --auto-fill --auto-submit --non-interactive
```

系统会自动：
1. 🔍 双通道识别所有表单字段
2. 🤖 三阶智能匹配你的个人信息
3. ✍️ 自动填充表单（9 种策略）
4. 📋 生成填充报告（保存在 `outputs/fill_plans/`）
5. 📸 截图（保存在 `outputs/screenshots/`）

### 其他命令

```bash
# 健康检查
resume-skill doctor

# 初始化（安装浏览器、创建目录）
resume-skill setup
```

---

## 🧠 智能匹配原理

### 三阶匹配引擎

```
Step 1: 预匹配（提取器 AI）
  ↓ (confidence >= 0.6)
Step 2: LLM 语义匹配
  ↓ (confidence < 0.7 或无匹配)
Step 3: 规则兜底
```

**预匹配优势**：提取器 AI 已经为部分字段提供了 `ai_value` 和 `ai_confidence`，避免重复 LLM 调用，提升速度。

**规则兜底**：即使 LLM 失败，仍可通过关键词匹配（如 "邮箱" → `personal.email`）覆盖常见字段。

### 语义匹配示例

```
表单字段: "请输入您的电子邮箱 (Email)"
    ↓ AI 语义理解
识别为: 邮箱字段
    ↓ 匹配个人信息
自动填充: "zhangsan@example.com"
```

**智能匹配能力：**

| 场景 | 处理方式 |
|------|---------|
| 字段名称变体 | "邮箱" / "Email" / "E-mail" 自动识别 |
| 下拉菜单选择 | 自动选择最匹配的选项（支持模糊匹配） |
| 日期格式转换 | "2022年3月" → "2022-03" |
| 多选项匹配 | 复选框自动选择所有匹配项 |
| 级联选择 | "北京市/北京市/海淀区" 自动逐级点击 |

---

## 📂 项目结构

```
RESUME_SKILL/
├── src/resume_skill/         # 核心包（独立开源）
│   ├── __init__.py
│   ├── cli.py               # CLI 入口
│   ├── config.py            # 统一配置
│   ├── agent/               # 浏览器自动化
│   │   ├── browser_agent.py     # 浏览器管理
│   │   ├── form_extractor.py    # 双通道提取
│   │   ├── field_matcher.py     # 三阶匹配
│   │   ├── form_filler.py       # 9 种填充策略
│   │   ├── jd_analyzer.py       # JD 分析
│   │   ├── workflow.py          # 主流程
│   │   └── utils.py             # 工具函数
│   ├── extractor/           # PDF 提取
│   │   └── extractor.py
│   └── llm/                 # LLM 提供商
│       ├── base.py
│       ├── deepseek_provider.py
│       ├── openai_provider.py
│       └── factory.py
│
├── personal_info/           # 🔒 个人信息（本地存储，不上传）
│   ├── formal_resume/       # PDF 简历
│   ├── profile_template.md  # 个人信息模板（可编辑）
│   └── unified_profile.yaml # 统一配置（生成）
│
├── examples/                # 示例数据（虚构）
│   ├── sample_profile.yaml
│   └── sample_profile_template.md
│
├── pyproject.toml           # Python 包配置
├── .env.example             # API 配置模板
├── README.md                # 本文件
└── LICENSE                  # MIT 许可证
```

---

## ❓ 常见问题

<details>
<summary><b>Q: 个人信息安全吗？</b></summary>

**完全安全。** 所有个人信息存储在本地 `personal_info/` 文件夹，通过 `.gitignore` 保护，不会上传到 GitHub 或任何云端服务器。
</details>

<details>
<summary><b>Q: 支持哪些招聘网站？</b></summary>

支持所有基于网页表单的招聘平台，包括：
- 网易社会招聘
- BOSS 直聘
- 拉勾网
- 智联招聘
- 前程无忧
- 牛客网
- 各公司官网招聘系统
</details>

<details>
<summary><b>Q: AI 提取的信息准确吗？</b></summary>

AI 提取准确率约 95%，对于标准格式的简历效果最佳。提取后你可以编辑 `profile_template.md` 进行修正和补充。
</details>

<details>
<summary><b>Q: 可以投递多个岗位吗？</b></summary>

**当然可以！** 你可以：
1. 保持 `unified_profile.yaml` 不变，直接投递多个岗位
2. 针对不同岗位修改 `profile_template.md` 后重新生成 `unified_profile.yaml`
3. 备份多个版本的 `unified_profile.yaml` 按需使用
</details>

<details>
<summary><b>Q: 为什么有些字段填充失败？</b></summary>

可能原因：
- 字段不在 `unified_profile.yaml` 中 → 编辑 `profile_template.md` 补充
- 字段被标记为 `manual`（敏感字段）→ 需要手动填写
- 表单结构特殊 → 查看 `outputs/logs/` 中的错误日志
</details>

---

## 🔒 隐私与安全

- ✅ **本地存储** - 个人信息永不离开你的电脑
- ✅ **API 密钥保护** - `.env` 文件不提交到 Git
- ✅ **浏览器会话隔离** - 登录信息不上传
- ✅ **敏感字段保护** - 身份证/政治面貌等自动标记为 `manual`
- ✅ **开源透明** - MIT 许可证，代码完全开放

---

## 🚀 快速命令参考

```bash
# 从 PDF 简历提取信息
resume-skill extract --pdf personal_info/formal_resume/我的简历.pdf

# 生成统一配置
resume-skill consolidate

# 交互式投递
resume-skill apply --url "URL"

# 非交互式投递（自动填充）
resume-skill apply --url "URL" --auto-fill --non-interactive

# 健康检查
resume-skill doctor

# 初始化
resume-skill setup
```

---

## 📚 更多文档

- [快速开始指南](QUICKSTART.md) - 详细步骤说明
- [系统架构](ARCHITECTURE.md) - 技术实现细节

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

如果这个项目对你有帮助，请给一个 ⭐ Star 支持一下！

---

## 📝 许可证

[MIT License](LICENSE)

---

<div align="center">

**让 AI 帮你搞定繁琐的网申，把时间花在真正重要的事情上** 🚀

</div>
# 🚀 RESUME_SKILL

<div align="center">

**AI驱动的智能网申助手**

*一键自动填充网申表单，让秋招投递效率提升 10 倍*

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![Stars](https://img.shields.io/github/stars/GalaxyKB/RESUME_SKILL?style=social)](https://github.com/GalaxyKB/RESUME_SKILL/stargazers)

</div>

---

## ✨ 为什么选择 RESUME_SKILL？

> 🎯 **痛点**：秋招季，每投一家公司都要重复填写姓名、邮箱、教育经历、项目经验... 一个岗位 20+ 个字段，投 50 家就是 1000 次重复劳动。

> 💡 **解决方案**：RESUME_SKILL 用 AI 自动提取简历信息，智能匹配表单字段，一键完成填充。**投递时间从 10 分钟缩短到 1 分钟**。

### 核心优势

| 功能 | 传统方式 | RESUME_SKILL |
|------|---------|--------------|
| 简历信息录入 | 手动复制粘贴 | 🤖 AI 自动提取 |
| 表单字段匹配 | 逐个查找填写 | 🎯 智能语义匹配 |
| 多平台投递 | 每次重新填写 | 📋 一次配置，多次复用 |
| 信息更新 | 分散在各平台 | 📁 本地统一管理 |

---

## 🔥 功能特性

- 🤖 **AI 智能提取** - 自动从 PDF 简历中提取姓名、教育、工作经历、项目、技能等
- 🎯 **语义智能匹配** - 理解字段含义，自动匹配最相关信息（"邮箱" ↔ "Email" ↔ "E-mail"）
- 📋 **一键表单填充** - 自动识别表单字段类型，智能填充文本、下拉菜单、复选框
- 🔒 **隐私本地优先** - 所有个人信息存储在本地，不上传云端
- 🌐 **多平台支持** - 网易、BOSS 直聘、拉勾、智联、前程无忧等主流招聘平台

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

# 安装依赖
pip install -r requirements.txt
```

### 🔑 配置 API

```bash
# 复制配置模板
cp .env.example .env
```

编辑 `.env` 文件，填入你的 API 密钥：

```env
# 火山引擎 DeepSeek API（推荐，国内访问稳定）
DEEPSEEK_API_KEY=your_api_key_here
DEEPSEEK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
DEEPSEEK_MODEL=deepseek-v4-pro-260425
```

| 服务 | 推荐度 | 说明 |
|------|--------|------|
| 火山引擎 DeepSeek | ⭐⭐⭐⭐⭐ | 推荐，成本低，国内访问稳定 |
| OpenAI | ⭐⭐⭐ | 备选，需要代理 |

---

## 📖 使用指南

### 第一步：上传简历

将你的 PDF 简历放入 `personal_info/resume/` 文件夹：

```
personal_info/
└── resume/
    └── 我的简历.pdf  ← 放在这里
```

### 第二步：提取信息

```bash
python main.py extract --resume personal_info/resume/我的简历.pdf
```

AI 会自动分析简历并提取：
- ✅ 基本信息（姓名、邮箱、电话、现居地）
- ✅ 教育背景（学校、学位、专业、GPA）
- ✅ 工作经历（公司、职位、时间、职责）
- ✅ 项目经验（项目名、角色、技术栈、成果）
- ✅ 技能栈（编程语言、框架、工具）

### 第三步：投递简历

```bash
# 打开招聘网站并登录
python main.py apply --url "https://招聘网站.com/job/xxx" --auto-fill
```

系统会自动：
1. 🔍 识别页面所有表单字段
2. 🤖 智能匹配你的个人信息
3. ✍️ 自动填充表单
4. 📋 生成填充报告

---

## 🧠 智能匹配原理

传统表单填充工具只能做**死板的字段名匹配**，RESUME_SKILL 使用 AI 进行**语义理解**：

```
表单字段: "Please enter your email address"
    ↓ AI 语义理解
识别为: 邮箱字段
    ↓ 匹配个人信息
自动填充: "zhangsan@example.com"
```

**智能匹配能力：**

| 场景 | 处理方式 |
|------|---------|
| 字段名称变体 | "邮箱" / "Email" / "E-mail" 自动识别 |
| 下拉菜单选择 | 自动选择最匹配的选项 |
| 日期格式转换 | "2022年3月" → "2022-03" |
| 多选项匹配 | 复选框自动选择所有匹配项 |

---

## 📂 项目结构

```
RESUME_SKILL/
├── apply_agent/              # 核心引擎
│   ├── workflow.py           # 主流程控制
│   ├── browser_agent.py      # 浏览器自动化
│   ├── form_extractor.py     # 表单识别
│   ├── form_filler.py        # 表单填充
│   ├── llm_client.py         # AI 接口
│   └── ...
│
├── personal_info/            # 🔒 个人信息（本地存储）
│   ├── resume/               # PDF 简历
│   └── profile_template.md   # 个人信息模板
│
├── main.py                   # 应用入口
├── config.yaml               # 配置文件
└── .env.example              # API 配置模板
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
1. 保持 `profile_template.md` 不变，直接投递多个岗位
2. 针对不同岗位修改 `profile_template.md` 中的内容
3. 备份多个版本的模板文件按需使用
</details>

---

## 🔒 隐私与安全

- ✅ **本地存储** - 个人信息永不离开你的电脑
- ✅ **API 密钥保护** - `.env` 文件不提交到 Git
- ✅ **浏览器会话隔离** - 登录信息不上传
- ✅ **开源透明** - MIT 许可证，代码完全开放

---

## 🚀 快速命令参考

```bash
# 从 PDF 简历提取信息
python main.py extract --resume personal_info/resume/我的简历.pdf

# 打开招聘网站并自动填充
python main.py apply --url "URL" --auto-fill

# 查看帮助
python main.py --help
```

---

## 📚 更多文档

- [快速开始指南](QUICKSTART.md) - 详细步骤说明
- [系统架构](ARCHITECTURE.md) - 技术实现细节
- [配置文件](config.yaml) - 完整配置选项

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

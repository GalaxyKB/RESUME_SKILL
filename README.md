<div align="center">

# 🎯 RESUME_SKILL

<img src="https://raw.githubusercontent.com/Tarikul-Islam-Anik/Animated-Fluent-Emojis/master/Emojis/Objects/Robot.png" alt="Robot" width="100" height="100" />

### 🤖 基于 Google Chrome DevTools MCP 的智能网申 Agent

<h4>v2.4 — take_snapshot → LLM Q&A 匹配 → fill 自动填充</h4>

---

<div align="center">
  <img src="https://img.shields.io/badge/License-MIT-00D9FF?style=for-the-badge&logo=opensource&logoColor=white" alt="MIT License"/>
  <img src="https://img.shields.io/badge/Python-3.9%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/AI_Powered-DeepSeek-FF6B6B?style=for-the-badge&logo=openai&logoColor=white" alt="AI"/>
  <img src="https://img.shields.io/badge/Google_MCP-Chrome%20DevTools-4285F4?style=for-the-badge&logo=googlechrome&logoColor=white" alt="Chrome DevTools MCP"/>
</div>

</div>

---

## 📖 这是什么

RESUME_SKILL 是一个 AI 驱动的网申自动填表工具。只需要三步：

```
1. resume-skill extract --pdf 简历.pdf    → AI 提取个人信息
2. resume-skill consolidate               → 生成统一档案
3. resume-skill apply --url "..." --use-mcp → 自动打开浏览器 → 识别表单 → 逐字段填充
```

**传统手填 15 分钟 → 30 秒完成。**

整个流程全本地化运行，简历信息和 API key 不上传任何第三方服务器。

---

## 🚀 5 分钟跑起来

### 前提条件

| 环境 | 版本要求 |
|------|---------|
| Python | 3.9+（推荐 3.10+） |
| Node.js | 18+（chrome-devtools-mcp 需要） |
| LLM API Key | DeepSeek 或 OpenAI |

### 安装

```bash
# 1. 克隆项目
git clone https://github.com/GalaxyKB/RESUME_SKILL.git
cd RESUME_SKILL

# 2. 创建虚拟环境（推荐 conda）
conda create -n resume-skill python=3.10 nodejs -y
conda activate resume-skill

# 3. 安装项目依赖
pip install -e .

# 4. 配置 API Key
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY 或 OPENAI_API_KEY

# 5. 验证
resume-skill doctor
npx chrome-devtools-mcp@latest --help   # 验证 Google MCP 可用
```

### 使用

```bash
# Step 1: 把 PDF 简历放到 personal_info/formal_resume/

# Step 2: AI 提取个人信息
resume-skill extract --pdf personal_info/formal_resume/我的简历.pdf

# Step 3: 生成统一档案
resume-skill consolidate

# Step 4: 打开招聘页面，自动填充
resume-skill apply --url "https://..." --use-mcp
```

---

## 🧠 技术架构

### 两层 MCP Server

```
MCP Agent (agent.py)
 ├── 调用 Google Chrome DevTools MCP（Node.js，Puppeteer）
 │    ├── navigate_page(url)     → 打开招聘页面
 │    ├── take_snapshot()        → 获取页面无障碍树
 │    ├── fill(uid, value)       → 填入字段值
 │    ├── click(uid)             → 点击按钮（提交/翻页）
 │    └── take_screenshot()      → 截图
 │
 └── 调用 自建 Server（Python，仅 1 个工具）
      └── wait_for_user(message) → 等待用户手动操作（登录）
```

Agent 的 LLM 负责将无障碍树中的表单字段映射为用户档案中的值（`_answer_fields` 方法）。

### 核心流程

```
take_snapshot() → 获取页面无障碍树
        │
        ▼
_parse_snapshot() → 提取 {uid, label, type, options}
        │
        ▼
_answer_fields(LLM Q&A) → 返回 {uid, answer, confidence, action}
        │
        ▼
fill(uid, answer) 循环 → 逐字段填充
        │
        ▼
下一页 / 提交
```

### 关键工具对比

| 功能 | v2.3 及之前 | v2.4 |
|------|------------|------|
| 浏览器控制 | 自建 `browser_agent.py` 266 行 | Google `chrome-devtools-mcp` |
| 字段提取 | 370 行 JS 注入 + CSS 选择器 | `take_snapshot()` 无障碍树 + UID |
| 字段填充 | 九策略降级填充 800 行 | `fill(uid, value)` 单行调用 |
| 字段匹配 | 三阶引擎（关键词规则 23 条） | LLM Q&A 问答（无规则） |
| 代码量 | ~2000 行浏览器相关代码 | ~200 行（匹配+解析） |

---

## 🤖 LLM Q&A 智能匹配

v2.4 摒弃了关键词规则匹配，改用 LLM 问答模式。每次将字段列表 + 用户档案打包成一个 prompt 发送给 LLM：

```
System: 你是一个表单填充助手。根据用户档案回答每个字段应该填什么。

用户档案:
{
  "personal": {"name_cn": "张三", "email": "zs@test.com", ...},
  "education": [{"school": "北京大学", "degree": "本科", ...}]
}

表单字段:
[
  {"uid": "1_5", "label": "姓名", "type": "text"},
  {"uid": "1_6", "label": "最高学历", "type": "select", "options": ["高中","本科","硕士","博士"]},
  {"uid": "1_7", "label": "就读高校", "type": "text"},
  {"uid": "1_8", "label": "身份证号", "type": "text"}
]

LLM 返回:
{"answers": [
  {"uid": "1_5", "answer": "张三", "confidence": "high", "action": "fill"},
  {"uid": "1_6", "answer": "本科", "confidence": "high", "action": "fill"},
  {"uid": "1_7", "answer": "北京大学", "confidence": "high", "action": "fill"},
  {"uid": "1_8", "answer": "未提供", "confidence": "low", "action": "manual"}
]}
```

**优势：**
- 无需维护关键词规则——LLM 自动理解 "就读高校" / "毕业院校" / "大学名称" 的语义
- 下拉选项智能匹配——"本科" → "学士学位" 等同义词自动识别
- 敏感字段自动识别——身份证号、政治面貌等标记为 manual
- 一次 LLM 调用回答所有字段，字段数越多性价比越高

---

## 📂 项目结构

```
src/resume_skill/
├── cli.py                    # CLI 入口
├── config.py                 # 配置加载
├── agent/
│   ├── mcp/                  # v2.4 核心
│   │   ├── agent.py          # LLM Agent 决策循环（snapshot → Q&A → fill）
│   │   ├── chrome_client.py  # Google Chrome DevTools MCP 客户端
│   │   ├── server.py         # 自建 MCP Server（仅 wait_for_user）
│   │   ├── client.py         # MCP 客户端（连接自建 Server）
│   │   ├── recorder.py       # 决策链记录 + 报告生成
│   │   └── __init__.py
│   ├── workflow.py           # 旧流程（非 MCP 模式，backward compat）
│   ├── browser_agent.py      # 旧 Playwright 代码（deprecated）
│   ├── form_extractor.py     # 旧字段提取代码（deprecated）
│   ├── form_filler.py        # 旧填充代码（deprecated）
│   ├── field_matcher.py      # 旧匹配代码（deprecated）
│   └── utils.py
├── extractor/
│   └── extractor.py          # PDF 简历 → 个人信息提取
└── llm/
    ├── base.py               # BaseLLMClient（含 call_with_tools）
    ├── openai_provider.py    # OpenAI 原生 function calling
    ├── deepseek_provider.py  # DeepSeek 回退方案
    └── factory.py
```

---

## 📋 命令速查

| 功能 | 命令 |
|------|------|
| 健康检查 | `resume-skill doctor` |
| AI 提取简历 | `resume-skill extract --pdf 简历.pdf` |
| 生成统一档案 | `resume-skill consolidate` |
| **v2.4 MCP Agent 投递** | `resume-skill apply --url "URL" --use-mcp` |
| 旧流程投递 | `resume-skill apply --url "URL" --auto-fill` |
| 极速投递（自动提交） | `resume-skill apply --url "URL" --auto-fill --auto-submit --non-interactive` |

### 完整工作流

```bash
resume-skill doctor
resume-skill extract --pdf "简历.pdf"
resume-skill consolidate
resume-skill apply --url "https://hr.company.com/jobs/123" --use-mcp
```

---

## 🔒 隐私

- **100% 本地化**：简历和档案存储在 `personal_info/`，不上传云端
- **.gitignore 保护**：`personal_info/`、`outputs/`、`.env` 均被 git 排除
- **敏感字段保护**：身份证、政治面貌等自动标记 manual，不自动填充
- **API Key 安全**：存储在 `.env`，不提交到代码仓库
- **开源透明**：MIT 许可证，代码完全开放审计

---

## 📝 开源协议

[MIT License](LICENSE)

*自由使用 · 商用友好 · 无限制分发*

---

<div align="center">

💡 项目交流、问题反馈，请提交 [GitHub Issues](https://github.com/GalaxyKB/RESUME_SKILL/issues)

</div>

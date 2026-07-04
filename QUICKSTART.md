# 快速开始指南 (Quick Start Guide)

> 简体中文 | [English](#english-version)

## 5分钟快速上手

### 第一步：准备环境

```bash
# 1. 进入RESUME_SKILL目录
cd RESUME_SKILL

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 4. 安装Playwright
playwright install chromium
```

### 第二步：填写个人信息

```bash
# 编辑个人信息模板
nano personal_info/profile_template.md
# 或用编辑器打开并填写
```

最小填写示例：

```markdown
## 📋 基本个人信息

### 姓名与邮箱
- **中文姓名**: 张三
- **邮箱**: zhangsan@example.com
- **电话**: 13800000000

## 🎓 教育背景

### 最高学历
- **学校**: 北京大学
- **学位**: 本科
- **专业**: 计算机科学与技术
- **毕业时间**: 2023.06
```

### 第三步：提取个人信息

```bash
# 方式1：不需要LLM（快速）
python main.py extract

# 方式2：使用AI（更智能，需要API密钥）
export OPENAI_API_KEY=sk-xxx
python main.py extract --llm-api-key $OPENAI_API_KEY
```

### 第四步：开始应聘

```bash
# 完整流程（推荐首次使用）
python main.py apply \
  --url "https://hr.163.com/user.html/resume/modify?type=add" \
  --full-workflow \
  --auto-fill

# 或仅使用现有档案应聘
python main.py apply \
  --url "https://hr.163.com/..." \
  --auto-fill
```

---

## 🎯 核心概念

### personal_info/ 文件夹说明

```
personal_info/
├── profile_template.md          ← 👤 你的个人信息（填这个）
├── general_information/         ← 📁 其他信息文件
│   ├── skills.txt              ← 可选：技能总结
│   ├── projects.md             ← 可选：项目列表
│   └── ...
├── formal_resume/              ← 📄 简历PDF/Word
│   ├── resume.pdf
│   └── ...
└── unified_profile.yaml        ← 🤖 AI生成的整合档案（自动生成）
```

### 工作流程

```
填写 profile_template.md
          ↓
    python main.py extract
          ↓
    生成 unified_profile.yaml
          ↓
    python main.py apply --url <url>
          ↓
    打开浏览器→自动填表→人工确认→完成
```

---

## 🔑 常用命令

```bash
# 仅提取个人信息
python main.py extract

# 提取 + 打开填表网站
python main.py apply --url "https://..." --full-workflow --auto-fill

# 使用已有档案填表（最快）
python main.py apply --url "https://..." --auto-fill

# 保持浏览器打开供手动填表
python main.py apply --url "https://..." --auto-fill --keep-browser-open

# 显示帮助
python main.py --help
python main.py extract --help
python main.py apply --help
```

---

## ⚙️ 配置说明

### 使用LLM（可选但推荐）

在第一次使用前配置API密钥：

```bash
# Linux/Mac
export OPENAI_API_KEY="sk-xxx"

# Windows PowerShell
$env:OPENAI_API_KEY="sk-xxx"

# 或编辑 config.yaml
```

如果使用自定义DS接口：

```bash
export DS_API_KEY="your_key"
export DS_API_ENDPOINT="https://your-api.com"
```

---

## 📋 检查清单 (Checklist)

进行应聘前，确保：

- [ ] `profile_template.md` 已填写至少基本信息
- [ ] `personal_info/formal_resume/` 中有简历文件
- [ ] 已运行 `python main.py extract`
- [ ] `unified_profile.yaml` 文件已生成
- [ ] 准备好应聘网站的URL
- [ ] 网络连接正常

---

## 🆘 常见问题

### Q1: 如何跳过自动填写某个字段？

A: 在表单填写时，看到 "是否填写此字段?" 时选择 "n" 即可。

### Q2: 如何更新个人信息？

A: 编辑 `profile_template.md` 后，重新运行 `python main.py extract` 即可。

### Q3: 可以保存多个不同的档案吗？

A: 可以。将 `unified_profile.yaml` 备份到其他名字，如 `profile_v1.yaml`。

### Q4: 支持哪些招聘网站？

A: 支持任何网页表单，包括：
- 网易社会招聘
- 拉勾网
- BOSS直聘
- 牛客网
- 等等...

### Q5: 信息会上传到服务器吗？

A: 
- 不使用LLM：所有数据本地存储，不上传
- 使用LLM：仅发送给你配置的LLM服务（OpenAI等）

---

## 🚀 下一步

1. ✅ 完成快速开始
2. 📖 阅读详细的 README.md
3. 🔧 根据需要调整 config.yaml
4. 💾 定期备份 `unified_profile.yaml`
5. 🎯 开始大规模投递

---

## 📞 获得帮助

- 查看 README.md 中的详细说明
- 检查 [故障排查](README.md#-故障排查-troubleshooting) 部分
- 查看输出的错误日志
- 在 GitHub Issues 中提问

---

祝求职顺利！🎉

---

# English Version

## Quick Start in 5 Minutes

### Step 1: Prepare Environment

```bash
cd RESUME_SKILL
python -m venv venv
source venv/bin/activate  # Linux/Mac or venv\Scripts\activate on Windows
pip install -r requirements.txt
playwright install chromium
```

### Step 2: Fill Personal Information

Edit `personal_info/profile_template.md` with your information:

```markdown
## Personal Information
- **Name**: John Doe
- **Email**: john@example.com
- **Phone**: 13800000000

## Education
- **University**: MIT
- **Degree**: Bachelor
- **Major**: Computer Science
- **Graduation**: 2023.06
```

### Step 3: Extract Information

```bash
python main.py extract
```

### Step 4: Apply to Job

```bash
python main.py apply --url "https://..." --auto-fill
```

Done! 🎉

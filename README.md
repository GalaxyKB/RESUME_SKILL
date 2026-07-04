# 🚀 RESUME_SKILL

**AI驱动的智能网申助手** - 一键自动填充网申表单，解放双手！

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/downloads/)

---

## ✨ 功能特性

- 🤖 **AI智能匹配** - 自动分析职位要求，匹配个人信息
- 📋 **自动表单填充** - 识别表单字段，智能填充内容
- 🔍 **简历信息提取** - AI自动从PDF简历中提取和分析个人信息
- 📝 **灵活信息管理** - 支持手动编辑补充，应对简历未涵盖的内容
- 🛡️ **反爬虫保护** - 模拟真实用户行为，规避检测
- 🌐 **多平台支持** - 网易、BOSS、拉勾、智联等主流平台

---

## 🎯 完整使用流程

### 📋 第一阶段：初始设置

#### 1️⃣ 环境准备

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

#### 2️⃣ 配置API密钥

```bash
# 复制配置模板
cp .env.example .env

# 用编辑器打开 .env，填入你的API密钥
# 推荐使用 DeepSeek（更便宜）
# 备选使用 OpenAI
```

| 服务 | 推荐度 | 说明 |
|------|--------|------|
| DeepSeek | ⭐⭐⭐⭐⭐ | 推荐，成本低 |
| OpenAI | ⭐⭐⭐ | 备选，质量稳定 |

---

### 📄 第二阶段：准备个人信息

#### 3️⃣ 上传正式简历PDF

**将你的正式简历PDF文件放入：** `personal_info/resume/` 文件夹

```
RESUME_SKILL/
└── personal_info/
    └── resume/
        └── 你的简历.pdf  ← 放在这里
```

#### 4️⃣ 提取简历信息（AI自动分析）

**执行提取命令**（使用AI自动从PDF中提取信息）：

```bash
# 从PDF简历中提取信息并自动填充profile_template.md
python main.py extract --resume personal_info/resume/你的简历.pdf

# 输出示例：
# 📄 开始从简历提取信息: personal_info/resume/你的简历.pdf
# 📖 Reading PDF: personal_info/resume/你的简历.pdf
# ✅ Extracted 15284 characters from resume
# 🤖 Using AI to analyze and extract information...
# ✅ Successfully extracted information from resume
# ✅ Updated profile template: personal_info/profile_template.md
```

**这一步会：**
1. 📄 读取你上传的PDF简历
2. 🤖 使用配置的AI（DeepSeek或OpenAI）自动分析和提取信息
3. 💾 自动生成/覆盖 `personal_info/profile_template.md`，包含：
   - 基本信息（姓名、邮箱、电话等）
   - 教育背景
   - 工作经历
   - 项目经验
   - 技能
   - 其他信息

#### 5️⃣ 编辑个人信息模板

**编辑文件：** `personal_info/profile_template.md`

这个文件包含从简历中提取的所有信息。你可以：
- ✏️ 编辑已有内容
- ➕ 补充简历中没有的内容
- 🗑️ 删除不需要的部分
- ⚙️ 调整格式和内容

这个文件会作为后续网申表单填充的数据源。

---

### 🌐 第三阶段：自动填充网申表单

#### 6️⃣ 启动应用并拉起网页

```bash
# 启动应用（带浏览器自动打开）
python main.py apply --url "网申表单URL" --manual-login-first

# 示例：
python main.py apply --url "https://hr.163.com/user.html/resume/modify?type=add" --manual-login-first
```

**命令参数说明：**
- `--url` - 网申表单页面的完整网址（从浏览器地址栏复制）
- `--manual-login-first` - 首先由用户手动登录

#### 7️⃣ 手动登录和导航

1. 浏览器会自动打开并访问你提供的网址
2. **手动完成登录** 登录到招聘网站
3. 登录后，**导航到个人资料填写界面**

**重要：** 等待系统准备完毕，然后执行第8步

#### 8️⃣ 执行自动填充

所有准备就绪后，在个人资料填写界面上，执行填充命令：

```bash
# 自动识别表单并填充信息
python main.py fill

# 或者带完整参数：
python main.py fill --continue-after-analysis --auto-fill
```

**命令参数说明：**
- `--continue-after-analysis` - 分析完成后继续自动填充
- `--auto-fill` - 自动填充所有识别到的字段

系统会执行以下步骤：

1. 🔍 **智能字段识别** - 识别页面上的所有表单字段
   - 文本输入框
   - 下拉菜单
   - 复选框和单选框
   - 上传文件区域等

2. 📊 **字段分析** - 分析每个字段的类型和要求
   - 字段名称和标签
   - 是否必填
   - 可用选项（如果是下拉菜单）
   - 字段限制（如字符数、日期格式等）

3. 🤖 **智能匹配** - 使用AI进行**语义匹配**（关键功能！）
   - 使用配置的LLM（DeepSeek或OpenAI）
   - 理解字段的真实含义，而不仅仅是字段名
   - 从 `personal_info/profile_template.md` 中提取最相关的信息
   - 处理信息的变异形式（例如"邮箱" ↔ "Email" ↔ "E-mail"）
   - 对于下拉菜单，自动选择最匹配的选项
   - 对于复选框，选择适用的所有选项
   - 置信度评分（显示匹配的可靠性）

4. ✍️ **自动填充** - 将匹配的信息填入表单
   - 逐个填充识别的字段
   - 处理不同的字段类型
   - 验证填充结果

5. 📋 **生成日志** - 生成填充报告供你查看
   - 哪些字段成功填充
   - 哪些字段无法填充及原因
   - 填充的置信度

### 示例：智能匹配如何工作

假设网申表单有这些字段：

| 表单字段 | 标签 | 类型 |
|---------|------|------|
| company_name | 公司名称 | 文本 |
| job_title | 职位 | 下拉菜单 |
| start_date | 开始时间 | 日期 |
| skills | 技能 | 复选框 |

而你的 `profile_template.md` 包含：

```
- **工作单位**: 阿里巴巴
- **职位名称**: 高级工程师
- **入职日期**: 2022年3月
- **技能**: Python, JavaScript, React
```

系统会自动：
- ✅ "公司名称" ← 匹配到 "阿里巴巴"（置信度 0.98）
- ✅ "职位" ← 匹配到下拉菜单中最接近"高级工程师"的选项
- ✅ "开始时间" ← 转换日期格式：2022-03-01
- ✅ "技能" ← 选择复选框中匹配的所有技能项目

---

## 📂 项目结构

```
RESUME_SKILL/
├── apply_agent/                    # 核心引擎（13个模块）
│   ├── workflow.py                 # 主流程控制
│   ├── browser_agent.py            # 浏览器自动化
│   ├── form_extractor.py           # 表单识别
│   ├── form_filler.py              # 表单填充
│   ├── llm_client.py               # AI接口
│   ├── jd_analyzer.py              # 职位分析
│   └── ...其他模块
│
├── personal_info/                  # 🔒 个人信息（隐私保护）
│   ├── resume/                     # 📄 你的正式简历PDF
│   │   └── 你的简历.pdf
│   └── profile_template.md         # ✏️ 个人信息模板（用户编辑）
│
├── main.py                         # 应用入口
├── config.yaml                     # 配置文件（详细注释）
├── .env.example                    # API配置模板
├── requirements.txt                # Python依赖
├── README.md                       # 本文件
├── QUICKSTART.md                   # 快速开始（更多细节）
├── ARCHITECTURE.md                 # 系统架构（技术文档）
└── LICENSE                         # MIT开源许可
```

---

## 💡 常见问题

### Q: 为什么需要上传正式简历PDF？
A: 系统需要从PDF中提取你的核心信息（工作经历、技能等），作为网申表单填充的基础。PDF格式更标准化，易于信息提取。

### Q: profile_template.md 可以修改吗？
A: **完全可以！** 这个文件是为了补充简历中没有的内容或针对特定岗位的定制。你可以：
- 编辑由AI提取的内容
- 补充简历中没有的内容
- 针对不同岗位修改相关部分

### Q: 提取简历的命令中，AI是如何工作的？
A: AI提取过程：
1. 读取你的PDF简历
2. 提取所有文本内容
3. 使用配置的LLM（DeepSeek或OpenAI）理解并分析内容
4. 识别关键信息（姓名、学位、工作经历、技能等）
5. 自动生成结构化的markdown格式信息
6. 覆盖/更新 `personal_info/profile_template.md`

这个过程完全自动化，无需手动干预！

### Q: 填表时的"智能匹配"是什么意思？
A: 传统的表单填充系统是死板的直接匹配（字段名 → 信息）。
智能匹配的优势：

| 特性 | 传统匹配 | 智能匹配 |
|------|--------|--------|
| 理解字段含义 | ❌ 仅匹配名称 | ✅ 理解真实意图 |
| 处理变异形式 | ❌ "邮箱" ≠ "Email" | ✅ 自动理解等价关系 |
| 下拉菜单 | ❌ 只能完全匹配 | ✅ 选择最接近的选项 |
| 格式转换 | ❌ 无法处理 | ✅ 自动调整格式 |
| 置信度评分 | ❌ 无法判断 | ✅ 显示匹配可靠性 |

例如：
- 字段"Please enter your email address" → 智能识别为邮箱字段 → 自动填充
- 字段"Position"有下拉选项[Engineer, Manager, Analyst]，而你的档案中是"高级工程师" → 自动选"Engineer"
- 字段要求"YYYY-MM-DD"格式，档案中是"2022年3月1日" → 自动转换为"2022-03-01"

### Q: 没有提取到某些信息怎么办？
A: 你可以在 `personal_info/profile_template.md` 中手动添加：
1. 打开文件
2. 在适当的部分添加内容
3. 保存文件
4. 下次填表时系统会使用更新后的信息

### Q: 能支持中英文简历吗？
A: 完全支持！建议使用中文简历以获得最佳识别效果。系统的LLM支持多语言理解和转换。

### Q: 表单填充失败了怎么办？
A: 检查以下几点：
1. **登录状态** - 确保成功登录到网站
2. **页面位置** - 确保在正确的表单页面
3. **个人信息** - 检查 `personal_info/profile_template.md` 中的信息是否完整
4. **API配置** - 确保API密钥配置正确（`python main.py extract --resume xxx.pdf` 能成功运行）
5. **查看日志** - 检查生成的填充日志，查看哪些字段失败及原因

### Q: 系统会保存我的个人信息吗？
A: 所有个人信息只存储在本地 `personal_info/` 文件夹中。Git仓库通过 `.gitignore` 保护这些文件，不会上传到GitHub。

### Q: 多个岗位投递时怎么办？
A: 有两种方式：

**方式1：直接编辑（快速）**
- 修改 `personal_info/profile_template.md` 中岗位相关的内容
- 执行填充命令
- 适合差异较小的岗位

**方式2：多份备份（严谨）**
- 备份 `personal_info/profile_template.md` （如 `profile_template_backup.md`）
- 为不同岗位修改 `profile_template.md`
- 使用各自的版本执行填充
- 适合差异较大的岗位

### Q: 为什么有时候AI匹配的置信度较低？
A: 几个可能原因：
1. **字段表述差异大** - 如"工作地点"vs"期望工作城市"
2. **信息不匹配** - 档案中没有相关信息
3. **格式不确定** - 不确定应该如何格式化信息
4. **多选项匹配** - 多个信息都可能适配，需要权衡

在这些情况下，系统会提示但不会强行填充，以避免错误。

---

## 🔒 隐私与安全

- ✅ 所有个人信息存储在本地
- ✅ API密钥存储在 `.env` 文件（不提交到Git）
- ✅ 浏览器会话和登录信息不上传
- ✅ GitHub仓库不包含任何个人数据
- ✅ MIT开源许可

---

## 🚀 快速命令参考

```bash
# 第4步：从简历PDF提取信息（使用AI自动分析）
python main.py extract --resume personal_info/resume/my_resume.pdf

# 第6步：启动应用（拉起浏览器，手动登录）
python main.py apply --url "URL" --manual-login-first

# 第8步：执行表单填充（智能匹配并自动填充）
python main.py fill --continue-after-analysis --auto-fill

# 查看帮助
python main.py --help
```

---

## 📚 更多文档

- [快速开始指南](QUICKSTART.md) - 更详细的步骤说明
- [系统架构](ARCHITECTURE.md) - 技术细节和模块说明
- [配置文件](config.yaml) - 所有配置选项详解

---

## 📝 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

---

## 🤝 贡献

欢迎提交Issue和Pull Request！

---

**准备好了？** 按照上面的 [完整使用流程](#-完整使用流程) 开始吧！🎉

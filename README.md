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

#### 4️⃣ 提取简历信息（可选 - 自动进行）

系统会自动从PDF简历中提取以下信息：
- 基本个人信息（姓名、电话、邮箱等）
- 工作经历和项目经验
- 教育背景和技能
- 其他核心内容

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

系统会：
1. 🔍 识别页面上的所有表单字段
2. 📊 分析字段类型和要求
3. 💾 从 `personal_info/profile_template.md` 中匹配信息
4. ✍️ 自动填充到对应的表单字段
5. 📝 生成填充日志供你查看

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
A: 系统需要从PDF中提取你的核心信息（工作经历、技能等），作为网申表单填充的基础。

### Q: profile_template.md 可以修改吗？
A: **完全可以！** 这个文件是为了补充简历中没有的内容。你可以根据具体岗位需求进行编辑。

### Q: 能支持中英文简历吗？
A: 支持中文简历。建议使用中文简历以获得最佳识别效果。

### Q: 表单填充失败了怎么办？
A: 检查：
1. 是否登录成功
2. 是否在正确的表单页面
3. profile_template.md 中的信息是否完整
4. API密钥配置是否正确

### Q: 系统会保存我的个人信息吗？
A: 所有个人信息只存储在本地 `personal_info/` 文件夹中。Git仓库通过 `.gitignore` 保护这些文件，不会上传到GitHub。

### Q: 多个岗位投递时怎么办？
A: 可以为不同岗位创建不同版本的 `profile_template.md`，但系统会使用同一个文件。如需针对不同岗位优化，建议：
1. 修改 `profile_template.md` 中的岗位相关内容
2. 执行填充命令
3. 或使用不同的分支/备份

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
# 启动应用（拉起浏览器，手动登录）
python main.py apply --url "URL" --manual-login-first

# 执行表单填充
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

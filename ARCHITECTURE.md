# RESUME_SKILL 框架设计说明

## 📐 架构设计 (Architecture)

### 分层架构

```
┌──────────────────────────────────────────────────┐
│           用户交互层 (User Interface)              │
│         main.py (CLI命令行界面)                    │
└──────────────────────────────────────────────────┘
                     ↓ ↑
┌──────────────────────────────────────────────────┐
│         业务逻辑层 (Business Logic)                │
│  ┌────────────────────────────────────────────┐  │
│  │ 个人信息处理 (Personal Info Processing)    │  │
│  │ - extractor.py (信息提取和整合)           │  │
│  │ - profile_template.md (用户模板)          │  │
│  │ - unified_profile.yaml (最终档案)         │  │
│  └────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────┐  │
│  │ 网站应聘处理 (Job Application)             │  │
│  │ - apply_agent/ (表单填写引擎)              │  │
│  │ - 表单识别、字段匹配、自动填写             │  │
│  └────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
                     ↓ ↑
┌──────────────────────────────────────────────────┐
│         数据层 (Data Layer)                       │
│  ┌────────────────────────────────────────────┐  │
│  │ 个人信息存储 (Personal Info Storage)       │  │
│  │ - general_information/ (通用文件)          │  │
│  │ - formal_resume/ (简历文件)               │  │
│  │ - profile_template.md (模板)              │  │
│  │ - unified_profile.yaml (整合档案)         │  │
│  └────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────┐  │
│  │ 外部系统 (External Systems)               │  │
│  │ - LLM API (信息提取和整合)                │  │
│  │ - 招聘网站 (Job Websites)                │  │
│  └────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
```

### 工作流程 (Workflow)

#### Phase 1: 个人信息处理

```
用户操作                          系统处理
────────────────────────────────────────────
1. 编辑profile_template.md    →  模板解析
2. 上传general_information/   →  文件扫描
3. 放置formal_resume/         →  简历识别
4. 运行 extract 命令           →  ┌──────────────┐
                                │ LLM提取       │
                                │ (可选)         │
                                └──────────────┘
                                      ↓
                                生成unified_profile.yaml
```

#### Phase 2: 网站应聘

```
用户操作                              系统处理
─────────────────────────────────────────────────
1. 运行 apply 命令              →  加载unified_profile.yaml
2. 输入招聘网站URL              →  打开浏览器
3. 浏览器加载完成               →  ┌──────────────────────┐
                                  │ 表单扫描和识别        │
                                  │ (提取所有字段)        │
                                  └──────────────────────┘
                                        ↓
4. 显示填写计划                   ┌──────────────────────┐
   (用户确认)                      │ 字段匹配              │
                                  │ (匹配到个人档案)      │
                                  └──────────────────────┘
                                        ↓
5. 执行填写操作                   ┌──────────────────────┐
   (展示结果)                      │ 自动填写              │
                                  │ (按优先级)            │
                                  └──────────────────────┘
                                        ↓
6. 最终审核和提交                  用户手工确认+提交
```

---

## 🗂️ 文件结构详解 (File Structure)

### 个人信息区 (personal_info/)

```
personal_info/
│
├── profile_template.md
│   ├── 用途: 用户填写个人信息的模板
│   ├── 格式: Markdown，包含预设的全面字段
│   ├── 特点: 
│   │   - 可中可英混合
│   │   - 支持自由扩展
│   │   - 有清晰的章节组织
│   └── 输出: 结构化字段 → 供LLM提取
│
├── general_information/
│   ├── 用途: 存储各类补充信息文件
│   ├── 支持格式: txt, md, pdf, docx, json, yaml等
│   ├── 使用场景:
│   │   - skills_summary.txt (技能总结)
│   │   - projects.md (项目详情)
│   │   - awards.json (获奖记录)
│   │   - experiences.md (经历补充)
│   └── 输出: 文件内容 → 供LLM提取
│
├── formal_resume/
│   ├── 用途: 存储正式简历文件
│   ├── 支持格式: PDF, DOCX, DOC
│   ├── 特点:
│   │   - 避免系统上传错误文件
│   │   - 保持简历的统一性
│   │   - 支持多版本管理
│   └── 输出: 简历路径 → 供表单上传
│
├── unified_profile.yaml
│   ├── 用途: 最终的整合个人档案
│   ├── 格式: YAML结构化格式
│   ├── 生成方式: AI智能提取 (从上述三个来源)
│   ├── 包含内容:
│   │   - 基本个人信息
│   │   - 教育背景
│   │   - 工作经历
│   │   - 实习经验
│   │   - 科研成果
│   │   - 项目经历
│   │   - 技能特长
│   │   - 获奖荣誉
│   └── 用途: 表单填写时的数据源
│
└── extractor.py
    ├── 类: PersonalInfoExtractor
    ├── 功能:
    │   - 收集general_information/中的文件
    │   - 收集formal_resume/中的简历
    │   - 解析profile_template.md
    │   - 调用LLM进行提取和整合
    │   - 保存为unified_profile.yaml
    └── 核心方法:
        - collect_general_information()
        - collect_formal_resume_info()
        - extract_template_content()
        - extract_with_llm()
        - save_unified_profile()
```

### 应聘处理区 (apply_agent/)

```
apply_agent/
│
├── browser_agent.py
│   ├── 功能: 浏览器自动化控制
│   ├── 特点:
│   │   - 反爬虫对策
│   │   - 会话管理
│   │   - 页面等待
│   └── 使用: 打开URL、等待加载、导航
│
├── form_extractor.py
│   ├── 功能: 表单字段识别和提取
│   ├── 能力:
│   │   - 识别input、select、textarea等
│   │   - 提取标签和提示文本
│   │   - 生成选择器
│   └── 输出: 字段列表(包含label、placeholder等)
│
├── form_mapper.py
│   ├── 功能: 字段匹配和填写计划生成
│   ├── 工作流:
│   │   1. 接收表单字段列表
│   │   2. 与unified_profile.yaml中的字段匹配
│   │   3. 生成填写计划(action: auto_fill/review/manual)
│   │   4. 计算匹配置信度
│   └── 输出: Fill Plan JSON (包含所有字段的填写策略)
│
├── form_filler.py
│   ├── 功能: 表单字段填写
│   ├── 支持类型:
│   │   - 文本输入 (input[type=text])
│   │   - 下拉选择 (select, combobox)
│   │   - 文本区 (textarea)
│   │   - 单选按钮 (radio)
│   │   - 复选框 (checkbox)
│   │   - 文件上传 (input[type=file])
│   └── 特点: 多策略降级、容错处理
│
└── workflow.py
    ├── 功能: 整个应聘流程的编排
    ├── 核心函数: run_apply_flow()
    ├── 流程:
    │   1. 初始化浏览器
    │   2. 打开应聘网站
    │   3. 扫描表单
    │   4. 生成填写计划
    │   5. 展示用户确认
    │   6. 执行填写
    │   7. 显示结果
    └── 输出: 填写结果报告
```

---

## 🔄 数据流转 (Data Flow)

### Extract阶段

```
用户文件输入:

profile_template.md (用户编写)
├─ 基本信息: 姓名, 邮箱, 电话
├─ 教育信息: 学校, 专业, 毕业时间
├─ 工作经历: 公司, 职位, 成就
└─ ...其他字段

general_information/ (用户上传)
├─ skills.txt
├─ projects.md
└─ awards.json

formal_resume/ (用户放置)
└─ resume.pdf

           ↓ [PersonalInfoExtractor]

LLM处理:

```python
prompt = """
提取以下信息中的所有个人信息:

1. 模板内容
2. 文件内容  
3. 简历文件列表

请返回结构化JSON...
"""
response = llm.extract(prompt)
```

           ↓ [JSON解析]

统一档案输出:

unified_profile.yaml:
```yaml
personal:
  name_cn: 王吉安
  email: abc@example.com
  ...

education:
  - school: 北京邮电大学
    degree: 本科
    ...

projects:
  - name: RAG系统
    ...
```
```

### Apply阶段

```
输入数据:

URL: https://hr.163.com/user.html/resume/modify?type=add

加载档案:
unified_profile.yaml

           ↓ [打开浏览器]

页面元素:

<input id="applicantName" placeholder="请输入姓名">
<input id="email" placeholder="请输入邮箱">
<select id="school">...</select>
<textarea id="skills">...</textarea>
...

           ↓ [FormExtractor]

提取字段列表:

[
  {field_id: "applicantName", label: "姓名", type: "text", ...},
  {field_id: "email", label: "邮箱", type: "text", ...},
  {field_id: "school", label: "学校", type: "select", ...},
  ...
]

           ↓ [FormMapper]

生成填写计划:

[
  {field: "applicantName", value: "王吉安", action: "auto_fill", confidence: 1.0},
  {field: "email", value: "abc@example.com", action: "auto_fill", confidence: 1.0},
  {field: "school", value: "北京邮电大学", action: "auto_fill", confidence: 0.98},
  {field: "skills", value: "...", action: "review_then_fill", confidence: 0.95},
  ...
]

           ↓ [用户确认]

执行填写:

fill_form([
  {field: "applicantName", value: "王吉安", action: "auto_fill"},
  ...
])

           ↓ [FormFiller]

结果:

表单已填写
Ready for user confirmation before submit
```

---

## 🛡️ 设计原则 (Design Principles)

### 1. 人工控制优先 (Human-in-the-Loop First)

```
自动操作流程:
auto_fill → review_then_fill → user_manual

所有关键操作都需要人工确认:
- 填写数据预览
- 提交前最终检查
- 敏感字段必须人工处理
```

### 2. 分离关注点 (Separation of Concerns)

```
个人信息处理     →  personal_info/
表单识别和填写  →  apply_agent/
用户交互        →  main.py
配置管理        →  config.yaml
```

### 3. 容错和降级 (Fault Tolerance)

```
字段匹配失败 → 标记为user_manual
LLM提取失败 → 使用模板信息
浏览器操作失败 → 重试或跳过
```

### 4. 信息完整性 (Information Integrity)

```
多源信息汇聚:
- 模板信息 (优先级高，用户主动填写)
- 补充文件 (优先级中，用户上传)
- 简历文件 (优先级低，参考)

去重和冲突处理:
- 检测重复信息
- 选择最可靠的版本
- 记录处理过程
```

---

## 🔌 扩展点 (Extension Points)

### 1. 添加新的LLM提供商

编辑 `personal_info/extractor.py`:

```python
async def extract_with_llm(self, ...):
    if self.llm_client.provider == "custom_ds":
        # 调用自定义API
        response = await self.llm_client.call_custom_api(...)
    elif self.llm_client.provider == "openai":
        # 调用OpenAI API
        response = await self.llm_client.call_openai(...)
```

### 2. 添加新的表单字段规则

编辑 `apply_agent/form_mapper.py`:

```python
FIELD_RULES = [
    # 新增规则
    ("new_field", ["新字段", "new field"], "profile.path.to.field", 0.95, "auto_fill"),
    ...
]
```

### 3. 自定义信息提取逻辑

创建 `personal_info/custom_extractor.py`:

```python
class CustomExtractor(PersonalInfoExtractor):
    async def extract_and_consolidate(self):
        # 自定义提取逻辑
        pass
```

### 4. 支持新的招聘网站

编辑 `apply_agent/form_extractor.py`:

```python
# 针对特定网站的特殊处理
if "example.com" in page.url:
    # 特殊的选择器和处理
    pass
```

---

## 📊 数据模型 (Data Models)

### PersonalProfile (个人档案)

```yaml
personal:          # 基本信息
  name_cn: str
  email: str
  phone: str
  gender: str
  age: int
  ...

education:         # 教育背景 (数组)
  - school: str
    degree: str
    major: str
    gpa: str
    ...

experience:        # 工作经历
  jobs:           # 工作
    - company: str
      position: str
      period: str
      highlights: [str]
      
  internships:    # 实习
    - company: str
      ...

projects:          # 项目 (数组)
  - name: str
    role: str
    highlights: [str]
    ...

skills: [str]      # 技能列表

awards: [dict]     # 获奖
```

### FillPlan (填写计划)

```json
[
  {
    "field_id": "field_001",
    "field_label": "姓名",
    "field_type": "input/text",
    "value": "王吉安",
    "source": "profile.personal.name_cn",
    "confidence": 1.0,
    "action": "auto_fill",
    "reason": "匹配关键词: 姓名"
  },
  ...
]
```

---

## 🎯 设计亮点 (Design Highlights)

1. **多源信息汇聚** - 从模板、文件、简历三个源头提取信息
2. **AI智能提取** - 使用LLM进行理解和整合，而不是简单的正则匹配
3. **灵活的表单填写** - 支持文本、选择、文件上传等多种控件
4. **人工审核机制** - 所有关键操作都支持中止和确认
5. **模块化设计** - 容易扩展和自定义
6. **错误恢复** - 完善的容错机制和降级策略

---

## 🚀 性能优化 (Performance Optimization)

1. **缓存管理** - 缓存提取结果避免重复调用LLM
2. **异步处理** - 使用async/await提高性能
3. **批量操作** - 合并多个表单操作减少往返
4. **智能超时** - 根据操作类型设置合理的超时时间

---

这就是RESUME_SKILL的完整架构设计！

Happy coding! 🚀

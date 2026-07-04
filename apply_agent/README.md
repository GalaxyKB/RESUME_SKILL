# apply_agent Module Reference

## 模块概览

`apply_agent` 是RESUME_SKILL中负责自动化简历投递的核心模块，包含13个专业化的子模块。

## 模块清单

### 核心模块 (Core Modules)

#### 1. **utils.py** - 通用工具函数
```python
# 常用函数
timestamp()              # 生成时间戳
safe_filename()         # 安全文件名处理
print_section()         # 打印分隔符
normalize_whitespace()  # 规范化空白符
clip_text()            # 截断文本
to_plain_text()        # 转换为纯文本
```

#### 2. **storage.py** - 文件I/O层
```python
# 数据持久化
load_yaml()            # 加载YAML配置
save_json()            # 保存JSON数据
load_text()            # 加载文本文件
ensure_dirs()          # 确保目录存在
append_application_record()  # 记录应用
```

#### 3. **config.py** - 配置管理
```python
# 配置类和路径定义
AppConfig              # 应用配置数据类
load_config()          # 加载配置
PROJECT_ROOT           # 项目根路径
DATA_DIR              # 数据目录
OUTPUTS_DIR           # 输出目录
RECORDS_DIR           # 记录目录
```

### 浏览器自动化 (Browser Automation)

#### 4. **browser_agent.py** - 浏览器生命周期管理
```python
class BrowserAgent:
    start()                    # 启动浏览器
    open_url()                # 打开URL
    get_page_text()           # 获取页面文本
    save_screenshot()         # 保存截图
    close()                   # 关闭浏览器
    click_apply_button()      # 点击申请按钮
    click_submit_button()     # 点击提交按钮
    _harden_context()         # 反爬虫加固
```

**特性**:
- Playwright同步API
- 用户数据目录持久化
- 反Bot指纹识别
- WebDriver隐藏

### 表单处理 (Form Processing)

#### 5. **form_extractor.py** - 表单字段提取
```python
extract_form_fields(page)  # 提取所有表单字段
```

**功能**:
- JavaScript DOM分析
- 生成CSS选择器和XPath
- 检测隐藏/禁用字段
- 支持iframe和多框架
- 字段去重

#### 6. **form_mapper.py** - 字段匹配与填充计划
```python
FIELD_RULES           # 40+字段匹配规则
create_fill_plan()    # 生成填充计划
```

**覆盖字段** (~40+):
- 个人信息：姓名、邮箱、电话、微信等
- 教育背景：学校、专业、学位、GPA等
- 工作经历：公司、职位、时间等
- 技能、项目、奖项等

#### 7. **form_filler.py** - 表单填充执行
```python
fill_form(page, fill_plan, resume_path)  # 执行填充
```

**策略**:
- 三层下拉框处理策略
- 文件上传支持
- 日期字段识别
- 文本框/选择框/单选按钮
- 用户确认模式

### LLM集成 (LLM Integration)

#### 8. **llm_client.py** - LLM API客户端
```python
class LLMClient:
    call_text()       # 文本生成
    call_json()       # JSON生成
```

**支持**:
- OpenAI API
- DeepSeek API
- 自动重试
- JSON解析
- 请求日志

#### 9. **jd_analyzer.py** - 职位描述分析
```python
analyze_and_tailor()  # 分析JD并定制内容
```

**分析内容**:
- 公司和职位识别
- 核心要求提取
- 关键词识别
- 匹配度评分
- 定制化回答建议

### 数据管理 (Data Management)

#### 10. **profile_summary.py** - 个人资料汇总
```python
build_personal_summary()       # 构建资料摘要
build_personal_summary_text()  # 文本格式
```

#### 11. **recorder.py** - 应用记录跟踪
```python
init_records()        # 初始化记录
append_application()  # 记录应用
```

**跟踪数据**:
- 日期、公司、职位
- URL、状态、匹配度
- 填充计划、JD分析路径

### 工作流 (Workflow)

#### 12. **workflow.py** - 主要编排 (~800行)
```python
class RunOptions       # 运行配置选项 (40+参数)
run_apply_flow()      # 主工作流
```

**工作流模式**:
- LOGIN_ONLY: 仅手动登录
- FILL_ONLY: 使用已保存会话
- 标准模式: 分析→规划→填充→提交

**配置项**:
- 交互模式
- 自动填充选项
- 浏览器配置
- 信号处理
- 日志选项

#### 13. **__init__.py** - 包标记

## 使用示例

### 基础使用

```python
from apply_agent.workflow import run_apply_flow, RunOptions

# 创建运行选项
options = RunOptions(
    interactive=True,
    auto_fill=True,
    continue_after_analysis=True
)

# 运行投递流程
result = run_apply_flow("https://job-site.com/position/123", options=options)
```

### 低级API

```python
from apply_agent.browser_agent import BrowserAgent
from apply_agent.form_extractor import extract_form_fields
from apply_agent.form_filler import fill_form

# 浏览器自动化
browser = BrowserAgent(session_profile_dir=".session/chrome")
browser.start()
browser.open_url("https://example.com/apply")

# 提取表单
fields = extract_form_fields(browser.page)
print(f"找到 {len(fields)} 个表单字段")

# 填充表单
fill_form(browser.page, fill_plan, resume_path)

browser.close()
```

## 配置

在项目根目录创建 `.env` 文件：

```env
# LLM配置
DEEPSEEK_API_KEY=your_api_key_here
DEEPSEEK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
DEEPSEEK_MODEL=deepseek-v4-pro-260425
DEEPSEEK_ENABLE_WEB_SEARCH=false

# 可选：使用OpenAI
OPENAI_API_KEY=your_openai_key
```

## 目录结构

```
apply_agent/
├── __init__.py
├── utils.py              # 工具函数
├── storage.py            # 文件I/O
├── config.py             # 配置管理
├── browser_agent.py      # 浏览器控制
├── form_extractor.py     # 表单提取
├── form_mapper.py        # 字段映射
├── form_filler.py        # 表单填充
├── llm_client.py         # LLM客户端
├── jd_analyzer.py        # JD分析
├── profile_summary.py    # 资料汇总
├── recorder.py           # 记录跟踪
└── workflow.py           # 工作流编排
```

## 数据流

```
URL
 ↓
[browser_agent] 打开网页
 ↓
[form_extractor] 提取表单字段
 ↓
[form_mapper] 匹配用户资料字段
 ↓
[jd_analyzer] LLM分析职位要求
 ↓
[form_filler] 填充表单
 ↓
[recorder] 记录应用
 ↓
Success/Failure
```

## 反爬虫特性

- `navigator.webdriver` 隐藏
- 模拟插件数组
- 语言/时区设置
- Chrome对象伪装
- 自动化标记移除
- 广泛的启动参数配置

## 错误处理

所有模块都包含：
- 自动重试机制
- 详细日志
- 优雅降级
- 用户反馈

## 扩展

要添加新的字段匹配规则，编辑 `form_mapper.py` 中的 `FIELD_RULES` 列表。

## 许可

作为RESUME_SKILL的一部分开源发布。

---

**版本**: 1.0
**最后更新**: 2024
**维护者**: RESUME_SKILL Team

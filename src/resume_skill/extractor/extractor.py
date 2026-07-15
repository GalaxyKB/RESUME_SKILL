"""
Personal information extraction and consolidation.

Flow: PDF extract → profile_template.md (user reviews & supplements) → unified_profile.yaml
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from ..config import AppConfig, CONFIG
from ..llm.factory import create_llm_client


class PersonalInfoExtractor:
    def __init__(self, personal_info_dir: str | Path, config: AppConfig | None = None) -> None:
        self.config = config or CONFIG
        self.personal_info_dir = Path(personal_info_dir)
        self.formal_resume_dir = self.personal_info_dir / "formal_resume"
        self.profile_template_path = self.personal_info_dir / "profile_template.md"
        self._llm_client = None

    @property
    def llm_client(self):
        if self._llm_client is None:
            try:
                self._llm_client = create_llm_client(self.config)
            except RuntimeError as e:
                print(f"[WARNING] LLM client initialization failed: {e}")
                # Return None to let caller handle the missing LLM gracefully
                return None
        return self._llm_client

    @llm_client.setter
    def llm_client(self, value):
        self._llm_client = value

    # ──────────────────────────────────────────────
    # Step 1: Extract from PDF → write profile_template.md
    # ──────────────────────────────────────────────

    def extract_from_resume_pdf(self, resume_path: str, output_to_template: bool = True) -> dict[str, Any]:
        """Extract info from a PDF resume, write results into profile_template.md
        so the user can review and supplement before consolidation."""
        try:
            from pypdf import PdfReader
        except ImportError:
            print("[ERROR] pypdf not installed. Run: pip install pypdf")
            return {}

        resume_file = Path(resume_path)
        if not resume_file.exists():
            print(f"[ERROR] Resume not found: {resume_path}")
            return {}

        print(f"[1/3] Reading PDF: {resume_path}")
        try:
            reader = PdfReader(str(resume_file))
            pdf_text = "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as e:
            print(f"[ERROR] Failed to read PDF: {e}")
            return {}

        if not pdf_text.strip():
            print("[ERROR] Could not extract text from PDF (possibly scanned image)")
            return {}

        print(f"       Extracted {len(pdf_text)} characters")

        fallback_text = self._extract_basic_profile_from_text(pdf_text)

        if not self.llm_client:
            print("[WARNING] No LLM client available. Using local PDF text extraction fallback.")
            if output_to_template:
                self._write_profile_template(fallback_text)
            return {"extracted_text": fallback_text, "source": "local_fallback"}

        print("[2/3] AI analyzing resume content...")
        extraction_prompt = f"""你是专业简历解析AI。请从以下简历中提取**所有信息**，不能有任何遗漏。

## 简历内容

{pdf_text[:6000]}{'... (已截取)' if len(pdf_text) > 6000 else ''}

## 核心原则

1. **提取所有能提取的信息**，下面的字段清单只是举例，不限于此
2. 简历中出现的任何数字、日期、名称、地点、公司、学校、技术名词、证书编号、网址链接、百分比、金额，全部提取
3. 如果简历中有出生日期，自动计算**年龄**（用当前时间2026年）
4. 如果简历中有实习/工作起止时间，自动计算**持续时长**（如"3个月"、"2年"）
5. 有多段教育/工作/项目，**全部列出**，不要合并，不要只取第一条
6. 即使简历中只有一行字的信息也要提取出来

## 需要提取的字段（请逐项检查，简历中有就提取）

**个人基本信息：**
中文姓名、英文/拼音姓名、性别、出生日期、**年龄**、邮箱、手机号、微信号、QQ、现居住地（完整地址）、期望工作城市、户口所在地、籍贯、民族、政治面貌、婚姻状况、到岗时间、求职状态、身份证号、护照号、个人主页/GitHub/博客链接、照片

**教育背景（每段都要）：**
学校名称、学院/系、学位/学历、专业、研究方向、入学时间、毕业时间、GPA、专业排名、主修课程（全部列出）、荣誉

**工作经历（每段都要）：**
公司名称、公司规模/性质、部门、职位、开始时间、结束时间、持续时长、工作职责（逐条列出）、主要成就、汇报对象、下属人数、薪资

**实习经历（每段都要）：**
公司名称、职位、开始时间、结束时间、持续时长、工作内容（逐条）、成果

**项目经验（每段都要）：**
项目名称、项目规模、角色、开始时间、结束时间、技术栈（全部列出）、项目描述、你的贡献、成果/数据

**技能（全部列出，不分类）：**
- 编程语言（Java、Python、C++等全部列出）
- 框架（Spring、Vue、React等全部列出）
- 工具（Git、Docker等全部列出）
- 数据库、云服务、AI框架、设计工具
- 语言能力及等级（英语 CET-4/CET-6、雅思、托福分数）
- 软技能（沟通、团队协作等）

**获奖/证书（每项都要）：**
奖项名称、获奖时间、颁发机构、等级（国家级/省级/校级）、排名/名次

**其他：**
论文/专利（名称、期刊、发表时间）、竞赛经历、兴趣爱好、自我评价、职业规划、期望薪资、社会活动、公益经历

## 输出格式

以 Markdown 列表返回，每行一个字段：

- **字段名称**: 字段值

多条记录编号标注：

- **教育1 - 学校名称**: xxx
- **教育1 - 专业**: xxx
- **教育2 - 学校名称**: xxx
- **项目1 - 名称**: xxx
"""

        try:
            extracted_text = self.llm_client.call_text("", extraction_prompt)
        except Exception as e:
            print(f"[WARNING] LLM call failed: {e}. Using local PDF text extraction fallback.")
            if output_to_template:
                self._write_profile_template(fallback_text)
            return {"extracted_text": fallback_text, "source": "local_fallback", "warning": str(e)}

        if not extracted_text:
            print("[WARNING] LLM returned empty result. Using local PDF text extraction fallback.")
            if output_to_template:
                self._write_profile_template(fallback_text)
            return {"extracted_text": fallback_text, "source": "local_fallback"}

        print("[3/3] Writing profile template...")
        if output_to_template:
            self._write_profile_template(extracted_text)

        return {"extracted_text": extracted_text}

    def _extract_basic_profile_from_text(self, pdf_text: str) -> str:
        """Extract enough structured information locally when the LLM is unavailable."""
        lines = [line.strip() for line in pdf_text.splitlines() if line.strip()]
        compact_text = "\n".join(lines)

        email_match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", compact_text)
        phone_match = re.search(r"(?<!\d)(?:\+?86[-\s]?)?1[3-9]\d[-\s]?\d{4}[-\s]?\d{4}(?!\d)", compact_text)
        link_matches = re.findall(r"https?://[^\s)）]+|(?:github|linkedin)\.com/[^\s)）]+", compact_text, re.I)

        name = ""
        for line in lines[:12]:
            cleaned = re.sub(r"\s+", "", line)
            if 2 <= len(cleaned) <= 8 and re.fullmatch(r"[\u4e00-\u9fffA-Za-z·.]+", cleaned):
                if not any(word in cleaned.lower() for word in ["resume", "cv", "简历", "个人"]):
                    name = line
                    break

        sections = []
        if name:
            sections.append(f"- **姓名**: {name}")
        if email_match:
            sections.append(f"- **邮箱**: {email_match.group(0)}")
        if phone_match:
            sections.append(f"- **手机号**: {phone_match.group(0)}")
        for idx, link in enumerate(dict.fromkeys(link_matches), start=1):
            sections.append(f"- **链接{idx}**: {link}")

        sections.append("- **原始简历文本**:")
        for line in lines:
            sections.append(f"  - {line}")

        return "\n".join(sections)

    def _write_profile_template(self, extracted_content: str) -> None:
        """Write profile_template.md with extracted content + supplement sections."""
        self.personal_info_dir.mkdir(parents=True, exist_ok=True)

        template = f"""# 个人信息档案 (Personal Information Profile)

> 本文件由 AI 从简历自动提取生成。请仔细核对，并在下方"补充信息"部分补全缺失内容。
> 填写完成后运行 `resume-skill consolidate` 生成结构化档案。

---

## AI 自动提取信息

{extracted_content}

---

## 补充信息（请手动填写简历中没有、但网申需要的信息）

### 常用网申补充

- **民族**:
- **政治面貌**:
- **婚姻状况**:
- **到岗时间**:
- **期望薪资**:
- **籍贯/户口**:
- **身份证号**:
- **紧急联系人**:

### 针对某类岗位的补充说明

-

### 特殊技能或经历

-

### 其他相关信息

-

---

**最后更新**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        try:
            self.profile_template_path.write_text(template, encoding="utf-8")
            print(f"       Profile template saved: {self.profile_template_path}")
            print("       >>> 请打开此文件检查并补充缺失信息 <<<")
        except Exception as e:
            print(f"[ERROR] Failed to write template: {e}")

    # ──────────────────────────────────────────────
    # Step 2: Read template (user-edited) → generate unified_profile.yaml
    # ──────────────────────────────────────────────

    def generate_unified_profile(self) -> dict[str, Any]:
        """Read user-confirmed profile_template.md, use LLM to produce
        structured unified_profile.yaml."""
        if not self.profile_template_path.exists():
            print(f"[ERROR] profile_template.md not found at {self.profile_template_path}")
            print("        Run `resume-skill extract --pdf <path>` first.")
            return {}

        template_content = self.profile_template_path.read_text(encoding="utf-8")
        if not template_content.strip():
            print("[ERROR] profile_template.md is empty")
            return {}

        if not self.llm_client:
            print("[ERROR] No LLM client. Set DEEPSEEK_API_KEY or OPENAI_API_KEY in .env")
            return {}

        print("[1/2] AI converting template to structured profile...")
        prompt = f"""你是专业简历结构化AI。请将以下个人信息转换为严格的JSON格式。

## 个人信息内容

{template_content[:8000]}

## 输出JSON结构

```json
{{
  "personal": {{
    "name_cn": "",
    "name_en": "",
    "gender": "",
    "birthday": "",
    "age": "",
    "email": "",
    "phone": "",
    "wechat": "",
    "location": "",
    "target_location": "",
    "ethnicity": "",
    "political_status": "",
    "marital_status": "",
    "availability": "",
    "hometown": "",
    "id_number": ""
  }},
  "education": [
    {{
      "school": "",
      "college": "",
      "degree": "",
      "major": "",
      "start_date": "",
      "end_date": "",
      "gpa": "",
      "rank": ""
    }}
  ],
  "experience": {{
    "jobs": [
      {{
        "company": "",
        "position": "",
        "start_date": "",
        "end_date": "",
        "description": ""
      }}
    ],
    "internships": [
      {{
        "company": "",
        "position": "",
        "start_date": "",
        "end_date": "",
        "description": ""
      }}
    ]
  }},
  "projects": [
    {{
      "name": "",
      "role": "",
      "start_date": "",
      "end_date": "",
      "description": "",
      "tech_stack": ""
    }}
  ],
  "skills": {{
    "programming_languages": [],
    "frameworks": [],
    "tools": [],
    "domains": []
  }},
  "awards": [
    {{
      "name": "",
      "date": "",
      "description": ""
    }}
  ],
  "self_introduction": {{
    "short": "",
    "medium": ""
  }},
  "additional": {{
    "publications": [],
    "certifications": [],
    "languages": []
  }},
  "supplementary": {{
    "raw_skills": [],
    "self_assessment": "",
    "other_info": []
  }}
}}
```

## 要求

1. 所有字段必须存在，无数据则留空字符串或空数组
2. 日期统一为 YYYY.MM 格式
3. 多条教育/实习/项目全部保留，不要只取第一条
4. 只输出JSON，不要任何其他文字
5. self_introduction 基于提取的完整信息自动生成：short 不超过100字，medium 不超过300字
6. supplementary 存放所有结构化字段无法覆盖的信息：raw_skills 放简历中的技能关键词（即使用户技能不在编程语言/框架/工具分类中），self_assessment 放自我评价段落，other_info 放其他所有无法归类的字段（如竞赛经历、兴趣爱好、证书编号等）
"""
        try:
            result = self.llm_client.call_json("", prompt)
        except Exception as e:
            print(f"[ERROR] LLM call failed: {e}")
            return {}

        if not result:
            print("[ERROR] LLM returned empty result")
            return {}

        # Ensure top-level keys exist
        defaults = {
            "personal": {}, "education": [], "experience": {"jobs": [], "internships": []},
            "projects": [], "skills": {"programming_languages": [], "frameworks": [], "tools": [], "domains": []},
            "awards": [], "self_introduction": {"short": "", "medium": ""},
            "additional": {"publications": [], "certifications": [], "languages": []},
            "supplementary": {"raw_skills": [], "self_assessment": "", "other_info": []},
        }
        for k, v in defaults.items():
            if k not in result:
                result[k] = v

        print("[2/2] Saving unified profile...")
        output_path = self._save_unified_profile(result)
        print(f"       Saved to: {output_path}")
        return result

    # ──────────────────────────────────────────────
    # New: Analyze MD vs reference → find missing fields
    # ──────────────────────────────────────────────

    def analyze_missing_fields(self, md_content: str) -> list[str]:
        """Compare resume MD with job fields reference, return missing field names."""
        ref_path = Path(__file__).parent / "job_fields_reference.md"
        if not ref_path.exists():
            return ["（参考模板不存在，请确认 job_fields_reference.md 存在）"]

        reference = ref_path.read_text(encoding="utf-8")
        if not self.llm_client:
            return ["请配置 LLM API Key"]

        prompt = f"""你是一个简历分析AI。比较以下两部分内容：

## 申请人的简历信息（MD格式）
{md_content[:6000]}

## 网申表单常用字段清单
{reference[:3000]}

请分析：简历信息中**缺失**或简历中有但未明确写出的网申常用字段有哪些？
注意：
- 年龄：如果简历中有出生日期但没写年龄，也算缺失
- 简历中提到的信息但没明确列出字段的，也算缺失（例如简历写了"2024年毕业"但没有"毕业时间"字段名，算缺失）
- 列出的缺失项要全面，不要遗漏
- 所有参考清单中的字段都应该检查一遍

返回 JSON 格式：{{"missing": ["缺失字段1", "缺失字段2", ...], "reason": "列出3-5个最常见的缺失项"}}"""
        try:
            result = self.llm_client.call_json("", prompt)
            if isinstance(result, dict) and "missing" in result:
                return result["missing"]
        except Exception:
            pass
        return []

    @staticmethod
    def prepend_missing_fields(md_content: str, missing_fields: list[str]) -> str:
        """Prepend missing fields as a '待补全的信息' section to the top of MD."""
        if not missing_fields:
            return md_content

        header = "## 待补全的信息（请填写以下缺少的信息）\n\n"
        items = "\n".join(f"- [ ] {f}" for f in missing_fields)
        note = "\n\n--- 简历原始内容 ---\n\n"

        return header + items + note + md_content.lstrip()

    def _save_unified_profile(self, profile: dict[str, Any]) -> str:
        output_path = self.personal_info_dir / "unified_profile.yaml"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            yaml.dump(profile, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        return str(output_path)

    # ──────────────────────────────────────────────
    # Helper: find resume PDFs
    # ──────────────────────────────────────────────

    def find_resume_pdfs(self) -> list[str]:
        """Return list of PDF file paths in formal_resume/ directory."""
        if not self.formal_resume_dir.exists():
            return []
        return [str(p) for p in sorted(self.formal_resume_dir.glob("*.pdf"))]

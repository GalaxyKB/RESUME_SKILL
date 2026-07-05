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

        if not self.llm_client:
            print("[ERROR] No LLM client available. Set API key in .env first.")
            return {}

        print("[2/3] AI analyzing resume content...")
        extraction_prompt = f"""你是专业简历解析AI。请从以下简历中提取**所有**个人信息。

## 简历内容

{pdf_text[:6000]}{'... (已截取)' if len(pdf_text) > 6000 else ''}

## 提取要求

请提取以下全部信息，缺失的留空：

**个人基本信息：**
- 中文姓名、英文/拼音姓名、性别、出生日期、邮箱、手机号、微信号、现居住地、期望工作城市、民族、政治面貌、婚姻状况、到岗时间

**教育背景（每段）：**
- 学校名称、学院、学位/学历、专业、入学时间、毕业时间、GPA、排名

**实习/工作经历（每段）：**
- 公司名称、职位、开始时间、结束时间、职责与成就

**项目经验（每段）：**
- 项目名称、角色、开始时间、结束时间、技术栈、成就

**技能：**
- 编程语言、框架、工具、领域

**其他：**
- 获奖/证书、论文/专利、自我评价

## 输出格式

以 Markdown 列表返回，每行一个字段：

- **字段名称**: 字段值

对于多条记录（多段教育/实习/项目），编号标注：

- **教育1 - 学校名称**: xxx
- **教育1 - 专业**: xxx
- **教育2 - 学校名称**: xxx
- **项目1 - 名称**: xxx
"""

        try:
            extracted_text = self.llm_client.call_text("", extraction_prompt)
        except Exception as e:
            print(f"[ERROR] LLM call failed: {e}")
            return {}

        if not extracted_text:
            print("[ERROR] LLM returned empty result")
            return {}

        print("[3/3] Writing profile template...")
        if output_to_template:
            self._write_profile_template(extracted_text)

        return {"extracted_text": extracted_text}

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
  }}
}}
```

## 要求

1. 所有字段必须存在，无数据则留空字符串或空数组
2. 日期统一为 YYYY.MM 格式
3. 多条教育/实习/项目全部保留，不要只取第一条
4. 只输出JSON，不要任何其他文字
5. self_introduction 基于提取的完整信息自动生成：short 不超过100字，medium 不超过300字
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
        }
        for k, v in defaults.items():
            if k not in result:
                result[k] = v

        print("[2/2] Saving unified profile...")
        output_path = self._save_unified_profile(result)
        print(f"       Saved to: {output_path}")
        return result

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

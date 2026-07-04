"""
AI-powered personal information extraction and consolidation module.
使用LLM提取和整合个人信息从多个来源。
"""

import os
import json
import re
from pathlib import Path
from typing import Any, Optional
import yaml


class PersonalInfoExtractor:
    """Extract and consolidate personal information from multiple sources."""
    
    def __init__(self, personal_info_dir: str, llm_client: Optional[Any] = None):
        """
        Initialize the extractor.
        
        Args:
            personal_info_dir: Path to personal_info directory
            llm_client: LLM client instance (e.g., from llm_client.py)
        """
        self.personal_info_dir = Path(personal_info_dir)
        self.general_info_dir = self.personal_info_dir / "general_information"
        self.formal_resume_dir = self.personal_info_dir / "formal_resume"
        self.profile_template_path = self.personal_info_dir / "profile_template.md"
        self.llm_client = llm_client
    
    def collect_general_information(self) -> dict[str, Any]:
        """Collect all files from general_information directory."""
        info = {
            "files": [],
            "content": ""
        }
        
        if not self.general_info_dir.exists():
            return info
        
        # Collect file names and metadata
        for file_path in self.general_info_dir.rglob("*"):
            if file_path.is_file():
                info["files"].append({
                    "name": file_path.name,
                    "path": str(file_path),
                    "size": file_path.stat().st_size,
                    "type": file_path.suffix
                })
                
                # Try to read text content
                try:
                    if file_path.suffix in [".txt", ".md", ".json", ".yaml", ".yml"]:
                        content = file_path.read_text(encoding="utf-8")
                        info["content"] += f"\n\n--- File: {file_path.name} ---\n{content}"
                except Exception as e:
                    print(f"⚠️ Cannot read {file_path.name}: {e}")
        
        return info
    
    def collect_formal_resume_info(self) -> dict[str, Any]:
        """Collect formal resume information."""
        info = {
            "files": [],
            "paths": []
        }
        
        if not self.formal_resume_dir.exists():
            return info
        
        for file_path in self.formal_resume_dir.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in [".pdf", ".docx", ".doc"]:
                info["files"].append({
                    "name": file_path.name,
                    "path": str(file_path),
                    "type": file_path.suffix
                })
                info["paths"].append(str(file_path))
        
        return info
    
    def extract_template_content(self) -> str:
        """Extract user-filled content from profile_template.md."""
        if not self.profile_template_path.exists():
            return ""
        
        content = self.profile_template_path.read_text(encoding="utf-8")
        # Remove lines that are just section headers and placeholders
        lines = []
        for line in content.split("\n"):
            if line.strip() and not line.strip().startswith("#"):
                # Keep non-empty, non-header lines
                lines.append(line)
        
        return "\n".join(lines)
    
    def parse_template_to_fields(self) -> dict[str, str]:
        """Parse template content into structured fields."""
        content = self.extract_template_content()
        fields = {}
        
        # Extract key-value pairs (e.g., "- **中文姓名** (Chinese Name): 张三")
        pattern = r'- \*\*([^*]+)\*\*[^:]*:\s*(.+)'
        for match in re.finditer(pattern, content):
            key = match.group(1).strip()
            value = match.group(2).strip()
            if value:  # Only store non-empty values
                fields[key] = value
        
        return fields
    
    async def extract_with_llm(self, general_info: dict, resume_paths: list, template_fields: dict) -> dict[str, Any]:
        """
        Use LLM to extract and consolidate information.
        
        Args:
            general_info: Collected general information
            resume_paths: Paths to formal resume files
            template_fields: Structured fields from template
        
        Returns:
            Consolidated personal profile
        """
        if not self.llm_client:
            raise ValueError("LLM client not provided. Cannot extract information.")
        
        prompt = self._build_extraction_prompt(general_info, resume_paths, template_fields)
        
        # Call LLM to extract information
        response = await self.llm_client.acompute_text(prompt)
        
        # Parse LLM response to structured format
        try:
            # Try to extract JSON from response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                extracted = json.loads(json_match.group())
            else:
                extracted = self._parse_llm_response(response)
        except Exception as e:
            print(f"⚠️ Error parsing LLM response: {e}")
            extracted = {}
        
        return extracted
    
    def _build_extraction_prompt(self, general_info: dict, resume_paths: list, template_fields: dict) -> str:
        """Build a comprehensive extraction prompt for the LLM."""
        
        prompt = """
你是一个专业的简历信息提取AI助手。你的任务是从以下多个信息源中提取和整合个人信息，生成一个完整的结构化个人档案。

## 信息源

### 1. 通用文件信息 (General Information Files)
以下是用户上传的通用文件中的内容：
{general_info_content}

### 2. 正式简历 (Formal Resume)
用户上传的正式简历文件列表：
{resume_files}

### 3. 模板填写 (Template Filled Information)
用户在个人信息模板中填写的字段：
{template_content}

## 任务

请提取所有可能的个人信息，并按照以下JSON结构返回：

```json
{{
  "personal": {{
    "name_cn": "中文姓名",
    "name_en": "English Name",
    "gender": "性别",
    "age": 年龄,
    "birthday": "YYYY-MM-DD",
    "marital_status": "婚姻状况",
    "email": "邮箱",
    "phone": "手机号",
    "wechat": "微信号",
    "location": "现居住地",
    "hometown": "家乡",
    "target_city": "期望城市",
    "school": "最后学校",
    "degree": "学历",
    "major": "专业",
    "work_mode": "工作模式"
  }},
  "education": [
    {{
      "school": "学校",
      "degree": "学位",
      "major": "专业",
      "start_date": "YYYY.MM",
      "graduation_date": "YYYY.MM",
      "gpa": "GPA",
      "rank": "排名"
    }}
  ],
  "experience": {{
    "jobs": [
      {{
        "company": "公司",
        "position": "职位",
        "period": "YYYY.MM - YYYY.MM",
        "highlights": ["成就1", "成就2"]
      }}
    ],
    "internships": [
      {{
        "company": "公司",
        "position": "职位",
        "period": "YYYY.MM - YYYY.MM",
        "highlights": ["成就1"]
      }}
    ]
  }},
  "projects": [
    {{
      "name": "项目名称",
      "role": "角色",
      "period": "YYYY.MM - YYYY.MM",
      "description": "项目描述",
      "highlights": ["成就1"]
    }}
  ],
  "research": [
    {{
      "title": "研究题目",
      "organization": "组织",
      "period": "YYYY.MM - YYYY.MM",
      "highlights": ["创新点1"]
    }}
  ],
  "skills": ["技能1", "技能2"],
  "awards": [
    {{
      "name": "奖项",
      "date": "YYYY.MM",
      "level": "等级"
    }}
  ],
  "self_introduction": {{
    "short": "100字版本",
    "medium": "300字版本",
    "long": "500字版本"
  }},
  "open_questions": {{
    "why_position": "为什么选择该岗位",
    "why_company": "为什么选择该公司",
    "representative_project": "最有代表性的项目"
  }},
  "additional_info": {{
    "publications": ["论文1", "论文2"],
    "languages": [
      {{"language": "语言", "level": "水平"}}
    ],
    "certifications": ["证书1"]
  }}
}}
```

## 注意事项

1. **提取所有可用信息**：尽可能从多个源中提取信息
2. **信息验证**：如果有重复或矛盾，选择最可能正确的版本
3. **格式统一**：日期统一为 YYYY.MM 或 YYYY-MM-DD 格式
4. **字段完整性**：即使字段为空，也应该保留在JSON中
5. **中英混合**：内容可以是中文或英文，保持原样

请直接返回结构化的JSON，不需要其他说明。
"""
        
        general_info_content = general_info.get("content", "")[:2000]  # Limit content size
        resume_files_str = "\n".join([f"- {f['name']}" for f in resume_paths]) if resume_paths else "无"
        template_str = "\n".join([f"- {k}: {v}" for k, v in template_fields.items()])[:2000]
        
        return prompt.format(
            general_info_content=general_info_content or "无",
            resume_files=resume_files_str,
            template_content=template_str or "无"
        )
    
    def _parse_llm_response(self, response: str) -> dict[str, Any]:
        """Parse LLM response when JSON parsing fails."""
        # Fallback parser for non-JSON responses
        # This is a simple fallback - in production, you'd want more robust parsing
        return {}
    
    def save_unified_profile(self, profile: dict[str, Any], output_path: Optional[str] = None) -> str:
        """
        Save unified profile to YAML file.
        
        Args:
            profile: Extracted profile dictionary
            output_path: Optional custom output path
        
        Returns:
            Path to saved file
        """
        if output_path is None:
            output_path = str(self.personal_info_dir / "unified_profile.yaml")
        
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert to YAML and save
        with open(output_file, 'w', encoding='utf-8') as f:
            yaml.dump(profile, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        
        return str(output_file)
    
    async def extract_and_consolidate(self) -> dict[str, Any]:
        """
        Main method: Extract and consolidate all information.
        
        Returns:
            Consolidated personal profile
        """
        # Step 1: Collect information from all sources
        general_info = self.collect_general_information()
        resume_info = self.collect_formal_resume_info()
        template_fields = self.parse_template_to_fields()
        
        # Step 2: Use LLM to extract and consolidate
        if self.llm_client:
            print("🤖 使用AI提取个人信息...")
            profile = await self.extract_with_llm(
                general_info,
                resume_info["paths"],
                template_fields
            )
        else:
            # Fallback: just use template fields
            print("⚠️ 未配置LLM客户端，使用模板信息...")
            profile = self._convert_template_to_profile(template_fields)
        
        # Step 3: Save consolidated profile
        output_path = self.save_unified_profile(profile)
        print(f"✅ 个人信息已保存到: {output_path}")
        
        return profile
    
    def _convert_template_to_profile(self, template_fields: dict[str, str]) -> dict[str, Any]:
        """Convert template fields to profile structure (fallback method)."""
        profile = {
            "personal": {},
            "education": [],
            "experience": {"jobs": [], "internships": []},
            "projects": [],
            "research": [],
            "skills": [],
            "awards": [],
            "self_introduction": {},
            "open_questions": {},
            "additional_info": {}
        }
        
        # Simple mapping (in production, use a more sophisticated approach)
        name_cn_patterns = ["中文姓名", "姓名", "name"]
        for pattern in name_cn_patterns:
            for k, v in template_fields.items():
                if pattern.lower() in k.lower() and v:
                    profile["personal"]["name_cn"] = v
                    break
        
        return profile
    
    def extract_from_resume_pdf(self, resume_path: str, llm_client: Any, output_to_template: bool = True) -> dict:
        """
        Extract information directly from a resume PDF file and optionally update profile_template.md.
        
        Args:
            resume_path: Path to the resume PDF file
            llm_client: LLM client instance for AI extraction
            output_to_template: Whether to automatically update profile_template.md
        
        Returns:
            Extracted profile dictionary
        """
        from pathlib import Path
        try:
            from pypdf import PdfReader
        except ImportError:
            print("❌ Error: pypdf not installed. Please run: pip install pypdf")
            return {}
        
        resume_file = Path(resume_path)
        if not resume_file.exists():
            print(f"❌ Error: Resume file not found: {resume_path}")
            return {}
        
        print(f"📖 Reading PDF: {resume_path}")
        
        # Extract text from PDF
        try:
            reader = PdfReader(str(resume_file))
            pdf_text = ""
            for page in reader.pages:
                pdf_text += page.extract_text() + "\n"
        except Exception as e:
            print(f"❌ Error reading PDF: {e}")
            return {}
        
        if not pdf_text.strip():
            print("❌ Error: Could not extract text from PDF")
            return {}
        
        print(f"✅ Extracted {len(pdf_text)} characters from resume")
        
        # Use LLM to extract structured information
        print("🤖 Using AI to analyze and extract information...")
        
        extraction_prompt = f"""
你是一个专业的简历解析AI。请从以下简历内容中提取所有个人信息，返回结构化的JSON格式。

## 简历内容

{pdf_text[:5000]}  {('... (内容过长，已截取前5000字)' if len(pdf_text) > 5000 else '')}

## 提取要求

请提取以下信息（如果简历中没有某项内容，请留空）：

1. **个人基本信息**
   - 姓名 (中文)
   - 姓名 (英文/拼音)
   - 性别
   - 出生日期
   - 邮箱
   - 手机号
   - 微信号
   - 现居住地
   - 期望工作城市

2. **教育背景**
   - 学校名称
   - 学位
   - 专业
   - 入学时间
   - 毕业时间
   - GPA

3. **工作经历**
   - 每份工作的公司、职位、时间、主要职责、成就

4. **项目经验**
   - 项目名称、角色、技术栈、成就

5. **技能**
   - 编程语言、框架、工具等

6. **其他**
   - 获奖、证书、论文等

## 响应格式

请以Markdown列表格式返回，每行一个字段，格式如下：

- **字段名称**: 字段值

例如：
- **中文姓名**: 张三
- **邮箱**: zhangsan@example.com
- **手机号**: 13912345678
"""
        
        try:
            import asyncio
            # If llm_client is async
            if hasattr(llm_client, 'acall_text'):
                extracted_text = asyncio.run(llm_client.acall_text("", extraction_prompt))
            elif hasattr(llm_client, 'call_text'):
                extracted_text = llm_client.call_text("", extraction_prompt)
            elif hasattr(llm_client, 'compute_text'):
                extracted_text = llm_client.compute_text(extraction_prompt)
            else:
                print("❌ Error: LLM client does not have call_text or compute_text method")
                extracted_text = ""
        except Exception as e:
            print(f"❌ Error calling LLM: {e}")
            extracted_text = ""
        
        if not extracted_text:
            print("❌ Error: Failed to extract information using AI")
            return {}
        
        print("✅ Successfully extracted information from resume")
        
        # Update profile_template.md with extracted information
        if output_to_template:
            self._update_profile_template(extracted_text)
        
        return {"extracted_text": extracted_text}
    
    def _update_profile_template(self, extracted_content: str) -> None:
        """
        Update or create profile_template.md with extracted information.
        
        Args:
            extracted_content: Extracted information in markdown format
        """
        template_content = f"""# 个人信息档案模板 (Personal Information Profile)

## 说明 (Instructions)

本文档包含从你的简历中自动提取的个人信息。请根据具体岗位需求进行补充和修改。

This document contains personal information automatically extracted from your resume. 
Please supplement and modify according to specific job requirements.

---

## 自动提取信息 (Auto-extracted Information)

{extracted_content}

---

## 补充信息 (Supplementary Information)

请在以下部分添加简历中没有的、但对岗位申请重要的信息：

### 针对某类岗位的补充说明
- 

### 特殊技能或经历
- 

### 其他相关信息
- 

---

**最后更新**: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        try:
            self.profile_template_path.write_text(template_content, encoding="utf-8")
            print(f"✅ Updated profile template: {self.profile_template_path}")
        except Exception as e:
            print(f"❌ Error writing profile template: {e}")


# Usage example
if __name__ == "__main__":
    import asyncio
    
    async def main():
        extractor = PersonalInfoExtractor(
            "RESUME_SKILL/personal_info",
            llm_client=None  # Replace with actual LLM client
        )
        
        profile = await extractor.extract_and_consolidate()
        print("\n提取的个人信息:")
        print(json.dumps(profile, ensure_ascii=False, indent=2))
    
    asyncio.run(main())

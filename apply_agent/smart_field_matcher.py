"""
AI-powered intelligent field matching for job application forms.
使用LLM进行智能字段匹配，将个人信息模板中的内容与网申表单字段进行语义匹配。
"""

import re
import json
from typing import Dict, List, Any, Optional
from pathlib import Path


class SmartFieldMatcher:
    """Intelligent field matcher using LLM for semantic matching."""
    
    def __init__(self, llm_client: Optional[Any] = None):
        """
        Initialize the smart field matcher.
        
        Args:
            llm_client: LLM client instance for AI-powered matching
        """
        self.llm_client = llm_client
    
    def extract_profile_information(self, profile_template_path: str) -> Dict[str, str]:
        """
        Extract all information from profile_template.md.
        
        Args:
            profile_template_path: Path to profile_template.md
        
        Returns:
            Dictionary of extracted key-value pairs
        """
        try:
            with open(profile_template_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except FileNotFoundError:
            print(f"⚠️ Profile template not found: {profile_template_path}")
            return {}
        
        # Extract all markdown lists
        profile_info = {}
        
        # Pattern for "- **Key**: Value"
        pattern = r'-\s*\*\*([^*]+)\*\*[^:]*:\s*(.+?)(?=\n-|\n#|$)'
        matches = re.findall(pattern, content, re.DOTALL | re.MULTILINE)
        
        for key, value in matches:
            key = key.strip()
            value = value.strip()
            if value and value not in ['', 'N/A']:
                profile_info[key] = value
        
        # Also extract regular list items
        pattern_simple = r'-\s+(.+?)(?=\n-|\n#|$)'
        matches_simple = re.findall(pattern_simple, content, re.DOTALL | re.MULTILINE)
        
        for value in matches_simple:
            value = value.strip()
            if value and not value.startswith('**'):
                # Add as misc_info if not already captured
                if 'misc_info' not in profile_info:
                    profile_info['misc_info'] = value
                else:
                    profile_info['misc_info'] += '\n' + value
        
        return profile_info
    
    def create_matching_prompt(self, form_fields: List[Dict[str, Any]], profile_info: Dict[str, str]) -> str:
        """
        Create a prompt for LLM to match form fields with profile information.
        
        Args:
            form_fields: List of form fields with name, label, type, options, etc.
            profile_info: Extracted profile information
        
        Returns:
            Prompt string for LLM
        """
        
        fields_desc = "\n".join([
            f"- [{i}] {field.get('label', field.get('name', 'Unknown'))} "
            f"(type: {field.get('type', 'text')}, "
            f"required: {field.get('required', False)})"
            + (f"\n      Options: {', '.join(field.get('options', []))}" if field.get('options') else "")
            for i, field in enumerate(form_fields)
        ])
        
        profile_desc = "\n".join([
            f"- {k}: {v}"
            for k, v in profile_info.items()
        ])
        
        prompt = f"""你是一个网申表单填充专家。给定网申表单的字段和个人信息档案，请进行智能的语义匹配，
找到最合适的信息来填充每个表单字段。

## 网申表单字段

{fields_desc}

## 个人信息档案

{profile_desc}

## 任务

请为每个表单字段找到最相关的个人信息，返回JSON格式的匹配结果。

### 匹配规则

1. **语义匹配** - 理解字段的真实含义，不仅仅是字段名
2. **智能推理** - 例如，如果字段要求"工作城市"，而档案中没有直接的工作城市，可以从地址中推断
3. **优先级** - 如果有多个可能的匹配，优先选择最相关的
4. **格式调整** - 如果需要，调整信息格式以符合字段要求（例如日期格式）
5. **保守匹配** - 如果不确定，不要强行匹配，返回空值

### 响应格式

请返回以下JSON格式：

```json
{{
  "matches": [
    {{
      "field_index": 0,
      "field_name": "字段名",
      "matched_value": "匹配的值",
      "confidence": 0.95,
      "source_key": "个人档案中的来源字段",
      "notes": "匹配说明（可选）"
    }},
    ...
  ],
  "unmatchable_fields": [
    {{
      "field_index": 1,
      "field_name": "字段名",
      "reason": "无法匹配的原因"
    }},
    ...
  ]
}}
```

## 重要说明

- confidence: 置信度 0.0-1.0
- 对于必填字段（required=true），如果无法匹配，请仍然返回但confidence设为0
- 对于下拉菜单字段（type=select），matched_value必须是选项中的一个
- 对于复选框（type=checkbox），需要返回匹配的选项列表
"""
        
        return prompt
    
    async def match_fields(self, form_fields: List[Dict[str, Any]], profile_template_path: str) -> Dict[str, Any]:
        """
        Use LLM to intelligently match form fields with profile information.
        
        Args:
            form_fields: List of form fields
            profile_template_path: Path to profile_template.md
        
        Returns:
            Matching results with field-value pairs and confidence scores
        """
        
        if not self.llm_client:
            print("⚠️ No LLM client provided, cannot perform intelligent matching")
            return {"error": "No LLM client available"}
        
        # Extract profile information
        profile_info = self.extract_profile_information(profile_template_path)
        
        if not profile_info:
            print("⚠️ No profile information found")
            return {"error": "No profile information available"}
        
        # Create matching prompt
        prompt = self.create_matching_prompt(form_fields, profile_info)
        
        print("🤖 Using AI to match form fields with your profile...")
        
        try:
            # Call LLM
            if hasattr(self.llm_client, 'acompute_text'):
                response = await self.llm_client.acompute_text(prompt)
            elif hasattr(self.llm_client, 'compute_text'):
                response = self.llm_client.compute_text(prompt)
            else:
                print("❌ Error: LLM client does not have compute_text method")
                return {"error": "LLM client error"}
            
            # Parse JSON response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return result
            else:
                print("⚠️ Warning: Could not extract JSON from LLM response")
                return {"raw_response": response}
        
        except Exception as e:
            print(f"❌ Error during field matching: {e}")
            return {"error": str(e)}
    
    def get_field_value_with_fallback(self, field_name: str, profile_info: Dict[str, str], 
                                     similarity_threshold: float = 0.6) -> Optional[str]:
        """
        Get field value with simple fallback matching (when LLM is not available).
        
        Args:
            field_name: Form field name
            profile_info: Profile information dictionary
            similarity_threshold: Minimum similarity score for matching
        
        Returns:
            Matched value or None
        """
        
        # Direct match
        if field_name in profile_info:
            return profile_info[field_name]
        
        # Case-insensitive match
        field_lower = field_name.lower()
        for key, value in profile_info.items():
            if key.lower() == field_lower:
                return value
        
        # Partial match (simple heuristic)
        keywords = re.split(r'[_\-\s]+', field_lower)
        best_match = None
        best_score = 0
        
        for key, value in profile_info.items():
            key_lower = key.lower()
            matches = sum(1 for keyword in keywords if keyword in key_lower and len(keyword) > 2)
            score = matches / len([k for k in keywords if len(k) > 2]) if keywords else 0
            
            if score > best_score and score >= similarity_threshold:
                best_score = score
                best_match = value
        
        return best_match


# Utility function for integration with form filler
def create_matcher(llm_client: Optional[Any] = None) -> SmartFieldMatcher:
    """Create a SmartFieldMatcher instance."""
    return SmartFieldMatcher(llm_client)

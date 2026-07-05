"""
LLM-powered semantic field matching engine.

Replaces the old hardcoded FIELD_RULES with AI-driven semantic matching.
Falls back to rule-based matching when LLM is unavailable.
"""

from __future__ import annotations

import json
from typing import Any

from ..llm.base import BaseLLMClient
from .utils import normalize_whitespace, to_plain_text


SENSITIVE_KEYWORDS = [
    "身份证", "证件号", "详细住址", "家庭住址", "紧急联系人",
    "政治面貌", "银行卡", "护照", "社保",
]

EXCLUDE_KEYWORDS = ["证件照", "照片", "头像", "验证码", "captcha"]

RESUME_FILE_KEYWORDS = ["简历", "resume", "cv", "上传简历", "简历上传", "附件简历"]

FIELD_RULES_FALLBACK = [
    # 基本信息
    ("name_cn", ["姓名", "真实姓名", "中文姓名", "申请人姓名", "name"], "personal.name_cn", 1.0),
    ("email", ["邮箱", "电子邮箱", "email", "e-mail", "邮件"], "personal.email", 1.0),
    ("phone", ["手机", "手机号", "电话", "phone", "mobile", "联系电话"], "personal.phone", 1.0),
    ("wechat", ["微信", "wechat", "微信号"], "personal.wechat", 0.95),
    ("gender", ["性别", "gender"], "personal.gender", 0.98),
    ("birthday", ["出生", "生日", "birthday", "出生日期", "出生年月"], "personal.birthday", 0.95),
    
    # 求职相关
    ("target_salary", ["期望薪资", "期望薪酬", "expected salary", "薪资要求", "薪酬期望"], "personal.target_salary", 0.95),
    ("current_salary", ["目前薪资", "当前年薪", "目前年薪", "现在薪资", "current salary"], "personal.current_salary", 0.95),
    ("availability", ["到岗时间", "入职时间", "可到岗时间", "availability"], "personal.availability", 0.95),
    ("job_status", ["求职状态", "目前状态", "在职状态", "job status"], "personal.job_status", 0.95),
    ("work_type", ["工作性质", "全职", "实习", "求职类型", "工作类型"], "personal.work_type", 0.95),
    ("target_position", ["应聘岗位", "申请职位", "意向岗位", "target position"], "personal.target_position", 0.95),
    
    # 个人详细信息  
    ("ethnicity", ["民族", "ethnicity"], "personal.ethnicity", 0.95),
    ("hometown", ["籍贯", "户口", "户籍", "hometown"], "personal.hometown", 0.95),
    ("marital_status", ["婚姻状况", "marital", "婚姻"], "personal.marital_status", 0.95),
    ("website", ["个人主页", "博客", "github", "portfolio", "网站"], "personal.website", 0.90),
    ("english_level", ["英语", "英语等级", "CET-4", "CET-6", "english level"], "personal.english_level", 0.95),
    
    # 教育背景
    ("school", ["学校", "院校", "毕业院校", "university", "school"], "education.0.school", 0.98),
    ("major", ["专业", "major", "所学专业", "专业方向"], "education.0.major", 0.98),
    ("degree", ["学历", "学位", "degree", "最高学历"], "education.0.degree", 0.98),
    ("gpa", ["gpa", "绩点", "平均分", "加权"], "education.0.gpa", 0.98),
    ("graduation_date", ["毕业时间", "毕业日期", "graduation"], "education.0.graduation_date", 0.95),
    
    # 其他
    ("location", ["居住", "所在城市", "现居", "location", "城市"], "personal.location", 0.92),
    ("self_introduction", ["自我介绍", "个人介绍", "self introduction"], "self_introduction.medium", 0.9),
    ("skills", ["技能", "skills", "技能描述"], "skills_summary", 0.9),
    ("project_experience", ["项目经历", "项目经验", "project"], "project_experience", 0.9),
    ("internship", ["实习", "internship"], "internship_experience", 0.9),
    ("awards", ["获奖", "奖项", "荣誉", "awards"], "awards.0.name", 0.90),
]


def match_fields_with_llm(
    fields: list[dict[str, Any]],
    profile: dict[str, Any],
    llm_client: BaseLLMClient,
    jd_analysis: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Primary matching engine: LLM semantic matching with rule-based validation.

    If fields already contain AI enrichment from the dual-channel extractor
    (ai_value / ai_confidence / fill_strategy), those are used as a first
    pass and the LLM only fills gaps.
    """
    if not fields:
        return []

    # Separate fields that already have AI matches from those that don't
    pre_matched: list[dict[str, Any]] = []
    needs_llm: list[dict[str, Any]] = []
    needs_llm_indices: set[int] = set()
    needs_llm_order: list[int] = []

    for i, field in enumerate(fields):
        ai_val = field.get("ai_value", "")
        if ai_val and field.get("ai_confidence", 0) >= 0.6:
            pre_matched.append(i)
        else:
            needs_llm.append(field)
            needs_llm_indices.add(i)
            needs_llm_order.append(i)

    # Run LLM matching only for fields that need it (with batching for large forms)
    llm_matches: dict[int, dict[str, Any]] = {}
    if needs_llm:
        # Split into batches to avoid token limits
        max_fields_per_batch = 30
        for batch_start in range(0, len(needs_llm), max_fields_per_batch):
            batch_end = min(batch_start + max_fields_per_batch, len(needs_llm))
            batch_fields = needs_llm[batch_start:batch_end]
            batch_indices = needs_llm_order[batch_start:batch_end]
            
            fields_summary = _prepare_fields_for_prompt(batch_fields)
            profile_json = json.dumps(profile, ensure_ascii=False, indent=2)
            if len(profile_json) > 8000:
                profile_json = profile_json[:8000] + "..."

            jd_context = ""
            if jd_analysis:
                tailored = jd_analysis.get("tailored_texts", {})
                jd_context = f"\n## 岗位定制化文本（优先填写开放性问题）\n```json\n{json.dumps(tailored, ensure_ascii=False, indent=2)}\n```"

            prompt = f"""你是专业网申表单语义匹配AI。请将以下表单字段与用户档案精确匹配。

## 表单字段

{fields_summary}

## 用户档案数据

```json
{profile_json}
```
{jd_context}

## 匹配规则

1. **语义理解** - "联系方式"→手机号, "就读高校"→学校, "毕业院校"→学校, "到岗时间"→availability
2. **格式适配** - 日期转目标格式, 电话加区号等
3. **多值选择** - 教育取最高学历, 实习取最相关的
4. **保守策略** - 不确定标confidence<0.7, action标review
5. **敏感字段** - 身份证/政治面貌等标action=manual
6. **填写策略** - 每个字段指定fill_strategy

### fill_strategy 枚举
- text: 文本输入
- select: 原生下拉
- custom_select: 自定义下拉组件
- radio_click: 单选按钮组
- checkbox_click: 复选框
- datepicker: 日期选择器
- cascader: 级联选择(省/市/区)
- upload: 文件上传
- contenteditable: 富文本/可编辑区域

### 输出JSON
{{
  "matches": [
    {{
      "field_index": 0,
      "field_id": "field_001",
      "matched_value": "值",
      "confidence": 0.95,
      "source_path": "personal.name_cn",
      "fill_strategy": "text",
      "action": "auto_fill",
      "reason": "语义匹配：姓名"
    }}
  ],
  "no_matches": [
    {{"field_index": 1, "field_id": "field_002", "reason": "无匹配数据"}}
  ]
}}

每个字段都必须出现在matches或no_matches中。"""

            try:
                result = llm_client.call_json("", prompt)
                if isinstance(result, dict):
                    for m in result.get("matches", []):
                        idx = m.get("field_index", -1)
                        if 0 <= idx < len(batch_fields):
                            # Map batch index to global index
                            global_idx = batch_indices[idx]
                            batch_idx = needs_llm_order.index(global_idx)
                            llm_matches[batch_idx] = m
            except Exception as e:
                print(f"[Matcher] LLM batch {batch_start//max_fields_per_batch + 1} matching failed: {e}")

        print(f"[Matcher] LLM processed {len(needs_llm)} fields in {(len(needs_llm)-1)//max_fields_per_batch + 1} batches")

    # Build final fill plan
    fill_plan: list[dict[str, Any]] = []
    for i, field in enumerate(fields):
        tag = str(field.get("tag", "")).lower()
        ftype = str(field.get("type", "")).lower()
        field_text = _compose_field_text(field)

        # Case 1: Pre-matched from extractor AI
        if i in pre_matched:
            value = str(field.get("ai_value", ""))
            confidence = float(field.get("ai_confidence", 0.0))
            fill_strategy = field.get("fill_strategy", _infer_fill_strategy(field))
            source = field.get("ai_source", "")
            reason = field.get("ai_reason", "")
            action = _determine_action(value, confidence, field_text, fill_strategy)

            fill_plan.append({
                "field_id": field.get("field_id", ""),
                "selector": field.get("selector", ""),
                "xpath": field.get("xpath", ""),
                "frame_url": field.get("frame_url", ""),
                "field_label": field.get("field_label", ""),
                "field_type": f"{tag}/{ftype}".strip("/") if ftype else tag,
                "role": field.get("role", ""),
                "fill_strategy": fill_strategy,
                "value": value,
                "source": source,
                "confidence": round(confidence, 2),
                "action": action,
                "reason": reason,
                "options": field.get("options", field.get("ai_options", [])),
            })
            continue

        # Case 2: LLM matched
        if i in needs_llm_indices:
            llm_idx = needs_llm_order.index(i)
            if llm_idx in llm_matches:
                m = llm_matches[llm_idx]
                value = str(m.get("matched_value", ""))
                confidence = float(m.get("confidence", 0.0))
                fill_strategy = str(m.get("fill_strategy", _infer_fill_strategy(field)))
                action = str(m.get("action", "auto_fill" if confidence >= 0.7 else "review"))
                if _is_sensitive(field_text):
                    action = "manual"

                fill_plan.append({
                    "field_id": field.get("field_id", ""),
                    "selector": field.get("selector", ""),
                    "xpath": field.get("xpath", ""),
                    "frame_url": field.get("frame_url", ""),
                    "field_label": field.get("field_label", ""),
                    "field_type": f"{tag}/{ftype}".strip("/") if ftype else tag,
                    "role": field.get("role", ""),
                    "fill_strategy": fill_strategy,
                    "value": value,
                    "source": str(m.get("source_path", "")),
                    "confidence": round(confidence, 2),
                    "action": action,
                    "reason": str(m.get("reason", "")),
                    "options": field.get("options", []),
                })
                continue

        # Case 3: Rule-based fallback
        _apply_rule_fallback(fill_plan, field, profile)

    return fill_plan


def match_fields_rule_based(
    fields: list[dict[str, Any]],
    profile: dict[str, Any],
) -> list[dict[str, Any]]:
    """Fallback: rule-based keyword matching."""
    fill_plan: list[dict[str, Any]] = []

    for field in fields:
        field_text = _compose_field_text(field)
        tag = str(field.get("tag", "")).lower()
        field_type = str(field.get("type", "")).lower()
        value = ""
        source = ""
        confidence = 0.0
        action = "manual"
        fill_strategy = _infer_fill_strategy(field)
        reason = "No match found"

        if _is_sensitive(field_text):
            action = "manual"
            reason = "Sensitive field, manual handling required"
        elif _is_excluded(field_text):
            action = "skip"
            reason = "Excluded field"
        elif tag == "input" and field_type == "file":
            if _match_keywords(field_text, RESUME_FILE_KEYWORDS):
                value = "RESUME_FILE_PATH"
                confidence = 0.99
                action = "auto_fill"
                fill_strategy = "upload"
                reason = "Resume upload field"
        else:
            for rule_key, keywords, source_path, rule_conf in FIELD_RULES_FALLBACK:
                if _match_keywords(field_text, keywords):
                    value = _resolve_profile_value(profile, source_path)
                    source = source_path
                    confidence = rule_conf
                    action = "auto_fill" if confidence >= 0.9 and value else "review"
                    reason = f"Keyword match: {keywords[0]}"
                    if not value:
                        confidence *= 0.5
                        action = "review"
                        reason = f"Matched but no data for: {keywords[0]}"
                    break

        fill_plan.append({
            "field_id": field.get("field_id", ""),
            "selector": field.get("selector", ""),
            "xpath": field.get("xpath", ""),
            "frame_url": field.get("frame_url", ""),
            "field_label": field.get("field_label", field.get("label", "")),
            "field_type": f"{tag}/{field_type}".strip("/") if field_type else tag,
            "role": field.get("role", ""),
            "fill_strategy": fill_strategy,
            "value": value,
            "source": source,
            "confidence": round(float(confidence), 2),
            "action": action,
            "reason": reason,
            "options": field.get("options", []),
        })

    return fill_plan


def _prepare_fields_for_prompt(fields: list[dict[str, Any]]) -> str:
    lines = []
    for i, f in enumerate(fields):
        info = {
            "index": i,
            "field_id": f.get("field_id", ""),  # Add field_id for robust mapping
            "label": f.get("field_label", f.get("label", "")),
            "placeholder": f.get("placeholder", ""),
            "name": f.get("name", ""),
            "id": f.get("id", ""),
            "type": f.get("type", ""),
            "tag": f.get("tag", ""),
            "role": f.get("role", ""),
            "required": f.get("required", False),
            "nearby_text": (f.get("nearby_text", "") or "")[:200],
            "context_text": (f.get("context_text", "") or "")[:200],
            "options": f.get("options", []),
        }
        lines.append(f"[{i}] {json.dumps(info, ensure_ascii=False)}")
    return "\n".join(lines)


def _apply_llm_matches(
    fields: list[dict[str, Any]],
    llm_result: dict[str, Any],
) -> list[dict[str, Any]]:
    matches = {m["field_index"]: m for m in llm_result.get("matches", []) if isinstance(m, dict)}
    no_matches = {nm["field_index"]: nm for nm in llm_result.get("no_matches", []) if isinstance(nm, dict)}

    fill_plan = []
    for i, field in enumerate(fields):
        tag = str(field.get("tag", "")).lower()
        field_type = str(field.get("type", "")).lower()

        if i in matches:
            m = matches[i]
            value = str(m.get("matched_value", ""))
            confidence = float(m.get("confidence", 0.0))
            fill_strategy = str(m.get("fill_strategy", _infer_fill_strategy(field)))
            action = str(m.get("action", "auto_fill" if confidence >= 0.7 else "review"))

            field_text = _compose_field_text(field)
            if _is_sensitive(field_text):
                action = "manual"

            fill_plan.append({
                "field_id": field.get("field_id", ""),
                "selector": field.get("selector", ""),
                "xpath": field.get("xpath", ""),
                "frame_url": field.get("frame_url", ""),
                "field_label": field.get("field_label", field.get("label", "")),
                "field_type": f"{tag}/{field_type}".strip("/") if field_type else tag,
                "role": field.get("role", ""),
                "fill_strategy": fill_strategy,
                "value": value,
                "source": str(m.get("source_path", "")),
                "confidence": round(confidence, 2),
                "action": action,
                "reason": str(m.get("reason", "")),
                "options": field.get("options", []),
            })
        else:
            fill_strategy = _infer_fill_strategy(field)
            reason = no_matches.get(i, {}).get("reason", "No match") if i in no_matches else "Not matched by AI"
            fill_plan.append({
                "field_id": field.get("field_id", ""),
                "selector": field.get("selector", ""),
                "xpath": field.get("xpath", ""),
                "frame_url": field.get("frame_url", ""),
                "field_label": field.get("field_label", field.get("label", "")),
                "field_type": f"{tag}/{field_type}".strip("/") if field_type else tag,
                "role": field.get("role", ""),
                "fill_strategy": fill_strategy,
                "value": "",
                "source": "",
                "confidence": 0.0,
                "action": "manual",
                "reason": reason,
                "options": field.get("options", []),
            })

    return fill_plan


def _compose_field_text(field: dict[str, Any]) -> str:
    return normalize_whitespace(
        " ".join(
            str(v)
            for v in [
                field.get("field_label", ""),
                field.get("label", ""),
                field.get("placeholder", ""),
                field.get("name", ""),
                field.get("id", ""),
                field.get("aria_label", ""),
                field.get("title", ""),
                field.get("data_field", ""),
                field.get("nearby_text", ""),
                field.get("context_text", ""),
            ]
            if v
        )
    )


def _match_keywords(text: str, keywords: list[str]) -> bool:
    lower = normalize_whitespace(text).lower()
    return any(kw.lower() in lower for kw in keywords)


def _is_sensitive(text: str) -> bool:
    return _match_keywords(text, SENSITIVE_KEYWORDS)


def _is_excluded(text: str) -> bool:
    return _match_keywords(text, EXCLUDE_KEYWORDS)


def _infer_fill_strategy(field: dict[str, Any]) -> str:
    tag = str(field.get("tag", "")).lower()
    ftype = str(field.get("type", "")).lower()
    role = str(field.get("role", "")).lower()

    if ftype == "file":
        return "upload"
    if tag == "select":
        return "select"
    if role == "combobox":
        return "custom_select"
    if ftype == "radio":
        return "radio_click"
    if ftype == "checkbox":
        return "checkbox_click"
    if ftype == "date" or ftype == "month":
        return "datepicker"
    if "contenteditable" in ftype or "textbox" in role:
        return "contenteditable"
    return "text"


def _resolve_profile_value(profile: dict[str, Any], path: str) -> str:
    if not path:
        return ""
    current: Any = profile
    for segment in path.split("."):
        if "[" in segment:
            key = segment.split("[")[0]
            idx = int(segment.split("[")[1].rstrip("]"))
            if isinstance(current, dict):
                current = current.get(key, [])
            if isinstance(current, list) and len(current) > idx:
                current = current[idx]
            else:
                return ""
        else:
            if isinstance(current, dict):
                current = current.get(segment, "")
            else:
                return ""
    return to_plain_text(current) if current else ""


def _determine_action(value: str, confidence: float, field_text: str, fill_strategy: str) -> str:
    """Determine the action for a field based on value, confidence, and sensitivity."""
    if _is_sensitive(field_text):
        return "manual"
    if _is_excluded(field_text):
        return "skip"
    if not value:
        return "manual"
    if fill_strategy == "upload":
        return "auto_fill"
    if confidence >= 0.9:
        return "auto_fill"
    if confidence >= 0.7:
        return "review"
    return "review"


def _apply_rule_fallback(fill_plan: list[dict[str, Any]], field: dict[str, Any], profile: dict[str, Any]) -> None:
    """Apply rule-based matching for a single unmatched field and append to fill_plan."""
    field_text = _compose_field_text(field)
    tag = str(field.get("tag", "")).lower()
    ftype = str(field.get("type", "")).lower()
    value = ""
    source = ""
    confidence = 0.0
    action = "manual"
    fill_strategy = _infer_fill_strategy(field)
    reason = "No match found"

    if _is_sensitive(field_text):
        action = "manual"
        reason = "Sensitive field"
    elif _is_excluded(field_text):
        action = "skip"
        reason = "Excluded field"
    elif tag == "input" and ftype == "file":
        if _match_keywords(field_text, RESUME_FILE_KEYWORDS):
            value = "RESUME_FILE_PATH"
            confidence = 0.99
            action = "auto_fill"
            fill_strategy = "upload"
            reason = "Resume upload"
    else:
        for rule_key, keywords, source_path, rule_conf in FIELD_RULES_FALLBACK:
            if _match_keywords(field_text, keywords):
                value = _resolve_profile_value(profile, source_path)
                source = source_path
                confidence = rule_conf
                action = _determine_action(value, confidence, field_text, fill_strategy)
                reason = f"Rule: {keywords[0]}" if value else f"Rule matched but no data: {keywords[0]}"
                if not value:
                    confidence *= 0.5
                break

    fill_plan.append({
        "field_id": field.get("field_id", ""),
        "selector": field.get("selector", ""),
        "xpath": field.get("xpath", ""),
        "frame_url": field.get("frame_url", ""),
        "field_label": field.get("field_label", ""),
        "field_type": f"{tag}/{ftype}".strip("/") if ftype else tag,
        "role": field.get("role", ""),
        "fill_strategy": fill_strategy,
        "value": value,
        "source": source,
        "confidence": round(confidence, 2),
        "action": action,
        "reason": reason,
        "options": field.get("options", []),
    })

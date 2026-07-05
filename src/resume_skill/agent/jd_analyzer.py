"""
JD analyzer with generic prompts (no hardcoded personal info).
"""

from __future__ import annotations

from typing import Any

from ..llm.base import BaseLLMClient
from .utils import clip_text, normalize_whitespace, to_plain_text


EXPECTED_KEYS = {
    "company": "",
    "position": "",
    "job_summary": "",
    "core_requirements": [],
    "keywords": [],
    "match_score": 0.0,
    "matched_experiences": [],
    "risks": [],
    "resume_strategy": "",
    "tailored_texts": {
        "self_introduction_100": "",
        "self_introduction_300": "",
        "skills_summary": "",
        "project_experience_short": "",
        "project_experience_long": "",
        "why_this_role": "",
        "why_this_company": "",
        "most_representative_project": "",
        "research_experience": "",
        "internship_experience": "",
        "work_experience": "",
    },
}


def _coerce_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


SYSTEM_PROMPT = """你是专业求职申请分析助手。
只能基于候选人提供的 profile 数据推断，不得编造实习、论文、奖项、成绩。
根据候选人的实际经历，选择最匹配岗位要求的项目和技能来突出。
输出必须是合法JSON，对象结构完整，字段不得缺失。"""


def analyze_and_tailor(
    raw_page_text: str,
    profile: dict[str, Any],
    preferences: dict[str, Any],
    resume_md: str,
    llm_client: BaseLLMClient,
) -> dict[str, Any]:
    profile_str = str(profile)[:8000]
    preferences_str = str(preferences)[:2000]
    resume_str = resume_md[:2000]

    user_prompt = f"""
候选人 profile:
{profile_str}

候选人 preferences:
{preferences_str}

候选人 resume:
{resume_str}

岗位页面正文:
{clip_text(raw_page_text, 30000)}

请输出以下JSON结构：
{EXPECTED_KEYS}

要求：
- 只能基于上述候选人信息，不得编造
- 根据候选人实际经历，选择与岗位最匹配的内容突出
- match_score 取 0 到 1 的小数
- tailored_texts 中的每个字段都要基于候选人真实经历生成
- 输出必须是合法JSON，不要输出多余解释
"""
    try:
        result = llm_client.call_json(SYSTEM_PROMPT, user_prompt)
    except Exception:
        result = _fallback_analysis(raw_page_text, profile)

    return _merge_defaults(result)


def _fallback_analysis(raw_page_text: str, profile: dict[str, Any]) -> dict[str, Any]:
    text = normalize_whitespace(raw_page_text)
    personal = profile.get("personal", {})
    intro = to_plain_text(personal.get("profile_summary", "")) or clip_text(text, 280)
    skills_data = profile.get("skills", {})
    skills_list = []
    if isinstance(skills_data, dict):
        for v in skills_data.values():
            if isinstance(v, list):
                skills_list.extend(v)
    elif isinstance(skills_data, list):
        skills_list = skills_data

    tailored_texts = {
        "self_introduction_100": clip_text(intro, 120),
        "self_introduction_300": clip_text(intro, 320),
        "skills_summary": ", ".join(skills_list[:15]) if skills_list else "",
        "project_experience_short": "",
        "project_experience_long": "",
        "why_this_role": "",
        "why_this_company": "",
        "most_representative_project": "",
        "research_experience": "",
        "internship_experience": "",
        "work_experience": "",
    }

    return {
        "company": "",
        "position": "",
        "job_summary": clip_text(text, 600),
        "core_requirements": [],
        "keywords": [],
        "match_score": 0.0,
        "matched_experiences": [],
        "risks": ["JD analysis fallback - LLM unavailable"],
        "resume_strategy": "Fill basic fields first",
        "tailored_texts": tailored_texts,
    }


def _merge_defaults(result: dict[str, Any]) -> dict[str, Any]:
    merged = dict(EXPECTED_KEYS)
    merged.update(result or {})
    tailored = dict(EXPECTED_KEYS["tailored_texts"])
    tailored.update((result or {}).get("tailored_texts", {}) if isinstance((result or {}).get("tailored_texts", {}), dict) else {})
    merged["tailored_texts"] = tailored
    merged["core_requirements"] = _coerce_list(merged.get("core_requirements", []))
    merged["keywords"] = _coerce_list(merged.get("keywords", []))
    merged["matched_experiences"] = _coerce_list(merged.get("matched_experiences", []))
    merged["risks"] = _coerce_list(merged.get("risks", []))
    return merged

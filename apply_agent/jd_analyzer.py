from __future__ import annotations

import re
from typing import Any

from .llm_client import LLMClient
from .utils import clip_text, normalize_whitespace


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
    },
}


SYSTEM_PROMPT = """你是专业求职申请分析助手。
只能基于候选人的 profile.yaml 和 resume.md 推断，不得编造实习、论文、奖项、成绩。
如果岗位是 RAG / LLM Agent / 大模型应用，优先突出中信数字科技金融长文档 RAG Agent 实习。
如果岗位是 AI 安全 / 大模型安全 / Agent 安全 / 安全研究，优先突出 Mobile Agent Security 科研。
如果岗位偏工程，突出 Python、检索、评测、自动化框架和 ApplyAgent 项目。
输出必须是合法 JSON，对象结构要完整，字段不得缺失。
"""


def _coerce_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


def _fallback_analysis(raw_page_text: str, profile: dict[str, Any], preferences: dict[str, Any], resume_md: str) -> dict[str, Any]:
    text = normalize_whitespace(raw_page_text)
    lowered = text.lower()
    role_keywords = ["rag", "agent", "llm", "大模型", "ai", "安全", "python", "工程"]
    match_score = 0.55
    if any(keyword.lower() in lowered for keyword in ["rag", "agent", "llm"]):
        match_score = 0.85
    if any(keyword in text for keyword in ["安全", "攻击", "红队", "mobile"]):
        match_score = max(match_score, 0.8)
    core_requirements = []
    for keyword in ["Python", "RAG", "Agent", "LLM", "安全", "自动化", "评测", "检索"]:
        if keyword.lower() in lowered:
            core_requirements.append(keyword)
    if not core_requirements:
        core_requirements = ["Python", "业务理解", "沟通协作"]
    tailored_texts = {
        "self_introduction_100": "我具备 Python、RAG、Agent 和自动化工程经验，能够快速理解岗位需求并结合项目背景输出可落地方案。",
        "self_introduction_300": "我目前主要积累在 Python、RAG、Agent 与自动化方向：在中信数字科技集团完成金融长文档 RAG Agent 实习，参与检索、评测和证据引用链路；同时在 Mobile Agent Security 课题中负责移动端智能体安全攻防相关实现。若岗位强调工程能力，我可以结合检索评测、自动化框架和 ApplyAgent 项目快速适配业务。",
        "skills_summary": "Python、RAG、Agentic RAG、TF-IDF、Embedding、Hybrid Retrieval、RRF、LLM-as-Judge、自动化框架",
        "project_experience_short": "ApplyAgent：本地半自动投递助手，支持 JD 分析、简历定制、表单扫描和受控自动填写。",
        "project_experience_long": "ApplyAgent 是面向秋招网申的本地半自动投递助手，支持岗位 JD 分析、简历定制、表单扫描、非敏感字段自动填写和人工确认提交。系统将简历、项目经历和开放题答案结构化存储，并结合岗位信息生成定制化申请文本。",
        "why_this_role": "希望在真实业务场景中继续发挥我在 Python、RAG、Agent 和自动化方面的积累，将分析、生成和工程落地结合起来。",
        "why_this_company": "该岗位/公司与我的技术栈和关注方向较匹配，我希望在更复杂的业务约束下持续提升工程落地能力。",
        "most_representative_project": "中信数字科技集团金融长文档 RAG Agent：完成解析、检索、证据引用、生成和评测全链路。",
        "research_experience": "Mobile Agent Security：围绕移动端智能体安全攻防，负责红队算法模块和自动化攻击生成框架。",
    }
    return {
        "company": "",
        "position": "",
        "job_summary": clip_text(text, 600),
        "core_requirements": core_requirements,
        "keywords": [keyword for keyword in role_keywords if keyword.lower() in lowered] or ["Python", "工程落地"],
        "match_score": match_score,
        "matched_experiences": ["中信数字科技集团金融长文档 RAG Agent", "Mobile Agent Security", "ApplyAgent"],
        "risks": ["JD 文本中未明确解析出所有要求，需人工复核"],
        "resume_strategy": "优先突出最匹配的项目和实习经历，并根据 JD 关键词微调表述侧重。",
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


def analyze_and_tailor(raw_page_text: str, profile: dict[str, Any], preferences: dict[str, Any], resume_md: str) -> dict[str, Any]:
    client = LLMClient()
    user_prompt = f"""
候选人 profile.yaml:
{profile}

候选人 preferences.yaml:
{preferences}

候选人 resume.md:
{resume_md}

岗位页面正文:
{clip_text(raw_page_text, 30000)}

请输出以下 JSON 结构：
{EXPECTED_KEYS}

要求：
- 只能基于上述候选人信息，不得编造。
- 如果岗位是 RAG / LLM Agent / 大模型应用，优先突出中信数字科技金融长文档 RAG Agent 实习。
- 如果岗位是 AI 安全 / 大模型安全 / Agent 安全 / 安全研究，优先突出 Mobile Agent Security 科研。
- 如果岗位偏工程，突出 Python、检索、评测、自动化框架和 ApplyAgent 项目。
- match_score 取 0 到 1 的小数。
- 输出必须是合法 JSON，不要输出多余解释。
"""
    try:
        result = client.call_json(SYSTEM_PROMPT, user_prompt)
    except Exception:
        result = _fallback_analysis(raw_page_text, profile, preferences, resume_md)
    return _merge_defaults(result)

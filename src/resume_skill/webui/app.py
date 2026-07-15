"""
Web UI Flask application - API + frontend for RESUME_SKILL v2.4.
"""
from __future__ import annotations

import json
import os
import base64
import re
import threading
import time
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, send_from_directory, request

from ..config import CONFIG, load_app_config
from ..cli import cmd_extract, cmd_consolidate
from ..agent.utils import load_yaml, save_json
from .task_manager import task_manager, FillTask
from ..agent.resume_analyzer_node import analyze_resume
from ..llm.vision import VisionWorkflowAdapter

app = Flask(__name__, template_folder="templates")

# ─── 全局状态 ────────────────────────────────────────────
_scout_progress: dict[str, Any] = {"running": False, "log": [], "results": []}
_chrome_instance: Any = None  # Keep Chrome alive across requests
_chrome_lock = threading.Lock()


def _ensure_dirs():
    CONFIG.personal_info_dir.mkdir(parents=True, exist_ok=True)
    CONFIG.resume_dir.mkdir(parents=True, exist_ok=True)
    (CONFIG.personal_info_dir / "general_information").mkdir(parents=True, exist_ok=True)


def _chrome_is_alive(chrome: Any) -> bool:
    process = getattr(chrome, "_process", None)
    return bool(process is not None and process.poll() is None)


def _get_or_start_chrome(headless: bool = False) -> Any:
    global _chrome_instance
    from resume_skill.agent.mcp.chrome_client import ChromeDevToolsClient

    with _chrome_lock:
        if _chrome_instance is not None and _chrome_is_alive(_chrome_instance):
            return _chrome_instance
        if _chrome_instance is not None:
            try:
                _chrome_instance.close()
            except Exception:
                pass
        _chrome_instance = ChromeDevToolsClient(headless=headless)
        _chrome_instance.connect()
        return _chrome_instance


def _screenshot_to_bytes(screenshot: Any) -> bytes:
    if isinstance(screenshot, bytes):
        return screenshot
    if isinstance(screenshot, dict):
        for key in ("data", "image", "base64"):
            value = screenshot.get(key)
            if isinstance(value, str) and value:
                return base64.b64decode(value.split(",")[-1])
        value = screenshot.get("path")
        if isinstance(value, str) and Path(value).exists():
            return Path(value).read_bytes()
    if isinstance(screenshot, str):
        text = screenshot.strip()
        if text.startswith("data:image"):
            return base64.b64decode(text.split(",", 1)[1])
        if Path(text).exists():
            return Path(text).read_bytes()
        try:
            return base64.b64decode(text)
        except Exception:
            return b""
    return b""


def _combine_screenshots(screenshots: list[Any]) -> bytes:
    images = []
    try:
        from PIL import Image
        import io

        for screenshot in screenshots:
            data = _screenshot_to_bytes(screenshot)
            if not data:
                continue
            img = Image.open(io.BytesIO(data)).convert("RGB")
            if img.width > 960:
                ratio = 960 / float(img.width)
                img = img.resize((960, max(1, int(img.height * ratio))))
            images.append(img)
        if not images:
            return b""
        width = max(img.width for img in images)
        height = sum(img.height for img in images)
        canvas = Image.new("RGB", (width, height), "white")
        y = 0
        for img in images:
            canvas.paste(img, (0, y))
            y += img.height
        out = io.BytesIO()
        canvas.save(out, format="JPEG", quality=75, optimize=True)
        return out.getvalue()
    except Exception:
        return _screenshot_to_bytes(screenshots[0]) if screenshots else b""


def _capture_scrolled_screenshot(chrome: Any, rounds: int = 3) -> bytes:
    screenshots = []
    for idx in range(max(1, rounds)):
        try:
            screenshots.append(chrome.call_tool("take_screenshot", {}, timeout=20))
        except Exception:
            break
        if idx < rounds - 1:
            try:
                chrome.call_tool("press_key", {"key": "PageDown"})
                time.sleep(0.6)
            except Exception:
                break
    try:
        chrome.call_tool("press_key", {"key": "Home"})
    except Exception:
        pass
    return _combine_screenshots(screenshots)


def _snapshot_to_text(snapshot: Any) -> str:
    if isinstance(snapshot, str):
        return snapshot
    if isinstance(snapshot, dict):
        if "content" in snapshot and isinstance(snapshot["content"], list):
            parts = []
            for item in snapshot["content"]:
                if isinstance(item, dict) and item.get("text"):
                    parts.append(str(item["text"]))
            if parts:
                return "\n".join(parts)
        try:
            return json.dumps(snapshot, ensure_ascii=False)
        except Exception:
            return str(snapshot)
    return str(snapshot or "")


def _parse_snapshot_fields(snapshot: Any) -> list[dict[str, Any]]:
    def _is_generic_label(label: str) -> bool:
        text = str(label or "").strip().lower()
        return text in {"", "select", "请选择", "请选择...", "please select", "下拉选择"}

    def _is_file_control(label: str, role: str) -> bool:
        label_text = str(label or "")
        if re.search(r"本人承诺|申请此职位|工作需知|支持扩展名|单文件|最多可上传|真实、准确、完整", label_text):
            return False
        if role not in {"button", "textbox", "input", "file", "link", "generic"}:
            return False
        return bool(re.search(r"^(我的简历|上传简历|附件上传)$|上传.*(简历|附件|作品|文件)|选择文件|resume|cv|upload|attach|attachment", label_text, re.I))

    if isinstance(snapshot, dict) and isinstance(snapshot.get("nodes"), list):
        fields = []
        previous_label = ""
        for node in snapshot["nodes"]:
            uid = str(node.get("uid", ""))
            label = str(node.get("label", node.get("name", "")))
            role = str(node.get("role", node.get("type", "text"))).lower()
            if role not in {"textbox", "textarea", "searchbox", "combobox", "listbox", "checkbox", "radio", "button", "input", "file", "link", "generic"}:
                if label and not _is_generic_label(label):
                    previous_label = label
                continue
            if _is_generic_label(label) and previous_label:
                label = previous_label
            if not uid:
                continue
            field_type = {"textbox": "text", "textarea": "text", "searchbox": "text", "combobox": "select", "listbox": "select", "generic": "text"}.get(role, role)
            if _is_file_control(label, role):
                field_type = "file"
            if field_type in {"text", "select", "checkbox", "radio", "file"}:
                fields.append({"uid": uid, "label": label, "type": field_type, "required": True, "value": ""})
        return fields

    text = _snapshot_to_text(snapshot)
    fields = []
    type_map = {"textbox": "text", "textarea": "text", "searchbox": "text", "combobox": "select", "listbox": "select", "checkbox": "checkbox", "radio": "radio", "button": "button", "generic": "text"}
    previous_label = ""
    for raw_line in text.splitlines():
        line = raw_line.strip()
        match = re.match(r'(\w+)\s+"([^"]*)"\s+uid=([\w_]+)', line) or re.match(r'uid=([\w_]+)\s+(\w+)\s+"([^"]*)"', line)
        if not match:
            uid_match = re.search(r"uid=([\w_]+)", line)
            if uid_match and re.search(r"上传|附件|简历|作品|选择文件|resume|cv|upload|attach|attachment", line, re.I):
                label = re.sub(r"uid=[\w_]+", "", line).strip(' -:："')[:80] or "附件上传"
                if _is_file_control(label, "button"):
                    fields.append({"uid": uid_match.group(1), "label": label, "type": "file", "required": True, "value": ""})
            continue
        if raw_line.strip().startswith("uid="):
            uid, role, label = match.group(1), match.group(2), match.group(3)
        else:
            role, label, uid = match.group(1), match.group(2), match.group(3)
        if role not in type_map and label and not _is_generic_label(label):
            previous_label = label
            continue
        if _is_generic_label(label) and previous_label:
            label = previous_label
        field_type = type_map.get(role)
        if _is_file_control(label, role):
            field_type = "file"
        elif role == "button":
            continue
        if field_type in {"text", "select", "checkbox", "radio", "file"}:
            fields.append({"uid": uid, "label": label, "type": field_type, "required": True, "value": ""})
    return fields


def _profile_to_text(profile: Any) -> str:
    if isinstance(profile, str):
        return profile
    try:
        return json.dumps(profile, ensure_ascii=False, indent=2)
    except Exception:
        return str(profile)


def _first_value(profile: Any, paths: list[str]) -> str:
    if not isinstance(profile, dict):
        return ""
    for path in paths:
        cur: Any = profile
        for part in path.split("."):
            if isinstance(cur, dict):
                cur = cur.get(part)
            elif isinstance(cur, list):
                try:
                    cur = cur[int(part)]
                except Exception:
                    cur = None
            else:
                cur = None
            if cur in (None, ""):
                break
        if isinstance(cur, list):
            value = "、".join(str(x) for x in cur if x)
        elif isinstance(cur, dict):
            value = json.dumps(cur, ensure_ascii=False)
        else:
            value = str(cur) if cur not in (None, "") else ""
        if value:
            return value
    return ""


def _format_items(items: Any, fields: list[str]) -> str:
    if not isinstance(items, list):
        return ""
    lines = []
    for item in items:
        if not isinstance(item, dict):
            lines.append(str(item))
            continue
        parts = [str(item.get(field, "")) for field in fields if item.get(field)]
        if parts:
            lines.append("；".join(parts))
    return "\n".join(lines)


def _md_value(profile_text: str, keys: list[str], join_all: bool = False) -> str:
    if not profile_text:
        return ""
    values = []
    for raw_line in profile_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        for key in keys:
            if key in line and ":" in line:
                value = line.split(":", 1)[1].strip()
                if value:
                    values.append(value)
                break
    if not values:
        return ""
    return "\n".join(values) if join_all else values[0]


def _field_evidence_from_md(label: str, profile_text: str, max_chars: int = 1200) -> str:
    if not profile_text:
        return ""
    label_text = str(label or "")
    keyword_groups = [
        (r"公司|组织|职位|职责|工作|项目|经历|起始|结束", ["项目", "职责", "项目时间", "项目角色", "项目简介", "核心职责", "实习", "工作"]),
        (r"大赛|奖励|荣誉|获奖|竞赛", ["荣誉", "奖", "竞赛", "大赛"]),
        (r"学校|院校|专业|学历|学位|GPA|排名|入学|毕业", ["院校", "专业", "学历", "GPA", "排名", "入学", "毕业"]),
        (r"技能|技术|证书|语言|英语", ["技能", "证书", "英语", "Java", "Python", "Spring", "Agent"]),
        (r"姓名|性别|年龄|民族|政治|婚姻|电话|手机|邮箱|城市|地址|到岗", ["姓名", "性别", "年龄", "民族", "政治", "婚姻", "电话", "邮箱", "城市", "到岗", "地址"]),
        (r"自我|评价|优势|其它|其他|问题", ["自我评价", "学习能力", "团队协作", "求职意向", "兴趣爱好"]),
    ]
    keywords = [label_text]
    for pattern, group in keyword_groups:
        if re.search(pattern, label_text, re.I):
            keywords.extend(group)

    lines = [line.strip(" -\t\r\n\u0001") for line in profile_text.splitlines() if line.strip()]
    hits: list[str] = []
    for line in lines:
        if any(k and k.lower() in line.lower() for k in keywords):
            hits.append(line)
    if not hits:
        hits = lines[:80]
    evidence = "\n".join(hits)
    return evidence[:max_chars]


SECTION_DEFS = [
    ("basic", "基本信息", r"姓名|性别|年龄|出生|民族|政治|婚姻|电话|手机|邮箱|城市|地址|籍贯|户籍|到岗|证件"),
    ("education", "教育经历", r"学校|院校|学院|院系|专业|学历|学位|GPA|绩点|排名|入学|毕业|教育"),
    ("work", "实习/工作经历", r"实习|工作|公司|组织|单位|职位|岗位|职责|在职|离职|雇主"),
    ("project", "项目经历", r"项目|课题|大赛|竞赛|作品|描述|角色|成果"),
    ("skill", "技能/证书/语言", r"技能|技术|证书|语言|英语|资格|奖|荣誉"),
    ("attachment", "附件上传", r"简历|附件|上传|文件|作品集|resume|cv|attach|upload"),
    ("agreement", "协议确认", r"承诺|同意|协议|真实|准确|申请此职位|工作需知"),
]


def _field_section(field: dict[str, Any]) -> str:
    label = f"{field.get('label', '')} {field.get('uid', '')} {field.get('type', '')}"
    if field.get("type") == "file":
        return "attachment"
    if field.get("type") in {"checkbox", "radio"} and re.search(r"承诺|同意|协议|真实|申请", label):
        return "agreement"
    for section_id, _, pattern in SECTION_DEFS:
        if re.search(pattern, label, re.I):
            return section_id
    return "basic"


def _build_form_plan(fields: list[dict[str, Any]], snapshot: Any, hints: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    section_map = {section_id: {"section_id": section_id, "label": label, "fields": [], "repeatable": section_id in {"education", "work", "project"}, "add_button_uid": "", "save_button_uid": "", "upload_candidates": []} for section_id, label, _ in SECTION_DEFS}
    for field in fields:
        section_id = _field_section(field)
        field["section"] = section_id
        section = section_map.setdefault(section_id, {"section_id": section_id, "label": section_id, "fields": [], "repeatable": False, "add_button_uid": "", "save_button_uid": "", "upload_candidates": []})
        section["fields"].append(field)
        if field.get("type") == "file":
            section["upload_candidates"].append({"uid": field.get("uid"), "label": field.get("label"), "source": "snapshot"})

    text = _snapshot_to_text(snapshot)
    for line in text.splitlines():
        uid_match = re.search(r"uid=([\w_]+)", line)
        if not uid_match:
            continue
        uid = uid_match.group(1)
        if re.search(r"新增|添加|增加|add", line, re.I):
            target = "education" if re.search(r"教育|学校|学历", line) else "work" if re.search(r"实习|工作|公司", line) else "project" if re.search(r"项目|作品", line) else "basic"
            section_map[target]["add_button_uid"] = uid
        if _is_local_section_save_line(line):
            for sec in section_map.values():
                if sec["fields"] and not sec.get("save_button_uid"):
                    sec["save_button_uid"] = uid

    for hint in hints or []:
        if str(hint.get("type", "")).lower() == "file" and hint.get("uid"):
            section_map["attachment"]["upload_candidates"].append({"uid": hint.get("uid"), "label": hint.get("label", ""), "source": "vision"})

    sections = [section for section in section_map.values() if section["fields"] or section.get("upload_candidates")]
    return {"sections": sections, "section_order": [section["section_id"] for section in sections], "field_count": len(fields)}


def _is_local_section_save_line(line: str) -> bool:
    text = str(line or "")
    if not re.search(r"保存|确定|完成|确认|提交本段|save|ok", text, re.I):
        return False
    # Never treat final application submission buttons as section-level saves.
    if re.search(r"提交申请|申请此职位|立即申请|投递|提交简历|submit application|apply now", text, re.I):
        return False
    return True


def _fallback_answer(field: dict[str, Any], profile: Any) -> str:
    label = f"{field.get('label', '')} {field.get('uid', '')}".lower()
    data = profile if isinstance(profile, dict) else {}
    flat = json.dumps(data, ensure_ascii=False) if data else _profile_to_text(profile)
    structured = data.get("structured", data) if isinstance(data, dict) else {}
    profile_text = str(data.get("profile_template") or data.get("raw_text") or "") if isinstance(data, dict) else ""
    projects = structured.get("projects", []) if isinstance(structured, dict) else []
    first_project = projects[0] if projects and isinstance(projects[0], dict) else {}

    if any(k in label for k in ["本人承诺", "申请此职位", "工作需知", "同意", "承诺"]):
        return "true"
    if "请问你有什么问题" in label or "有什么问题" in label:
        return "暂无，感谢您的关注。"
    if any(k in label for k in ["公司或组织", "公司名称", "组织名称", "单位名称"]):
        return _md_value(profile_text, ["实习1 - 公司名称", "工作1 - 公司名称"]) or first_project.get("name", "")
    if any(k in label for k in ["部门", "所属部门"]):
        return _md_value(profile_text, ["实习1 - 所属部门", "工作1 - 所属部门"])
    if any(k in label for k in ["工作内容", "实习内容", "工作职责", "主要职责", "工作业绩", "工作成果", "经历描述"]):
        return _md_value(profile_text, ["实习1 - 工作内容", "实习1 - 实习成果", "工作1 - 工作内容"], join_all=True)

    mapping = [
        (["姓名", "name", "full name"], ["personal.name_cn", "personal.name_en", "name", "full_name"]),
        (["性别", "gender"], ["personal.gender"]),
        (["年龄", "age"], ["personal.age"]),
        (["出生", "生日", "birthday", "birth"], ["personal.birthday"]),
        (["民族", "ethnicity"], ["personal.ethnicity"]),
        (["政治", "political"], ["personal.political_status"]),
        (["婚姻", "marital"], ["personal.marital_status"]),
        (["电话", "手机", "手机号", "mobile", "phone"], ["personal.phone", "phone", "mobile"]),
        (["邮箱", "email", "mail"], ["personal.email", "email"]),
        (["所在地", "所在城市", "现居", "城市", "location"], ["personal.location", "personal.hometown"]),
        (["籍贯", "户籍", "户口", "hometown"], ["personal.hometown"]),
        (["到岗", "可入职", "availability"], ["personal.availability"]),
        (["学历", "最高学历", "学历类型", "当前学历", "学位", "degree"], ["education.0.degree"]),
        (["学校", "院校", "毕业院校", "school", "university"], ["education.0.school"]),
        (["学院", "院系", "college"], ["education.0.college"]),
        (["专业", "major"], ["education.0.major"]),
        (["gpa", "绩点"], ["education.0.gpa"]),
        (["排名", "rank"], ["education.0.rank"]),
        (["入学"], ["education.0.start_date"]),
        (["毕业"], ["education.0.end_date"]),
        (["起始日期", "开始日期", "开始时间", "start date"], ["projects.0.start_date", "education.0.start_date"]),
        (["结束日期", "结束时间", "end date"], ["projects.0.end_date", "education.0.end_date"]),
        (["职位", "职责", "角色", "岗位"], ["projects.0.role", "supplementary.other_info.2"]),
        (["工作描述", "项目描述", "经历描述", "描述"], ["projects.0.description", "supplementary.self_assessment"]),
        (["技能", "技术栈", "skill"], ["skills.programming_languages", "skills.frameworks", "skills.tools", "skills.domains"]),
        (["自我评价", "个人评价", "自我介绍", "优势"], ["self_introduction.medium", "supplementary.self_assessment"]),
        (["证书", "certification", "certificate"], ["additional.certifications"]),
        (["语言", "英语", "language"], ["additional.languages"]),
        (["奖励", "荣誉", "获奖", "大赛", "竞赛", "award"], []),
        (["其他", "其它"], ["self_introduction.short", "supplementary.other_info"]),
    ]

    for markers, paths in mapping:
        if any(marker.lower() in label for marker in markers):
            if any(marker in ["起始日期", "开始日期", "开始时间", "start date"] for marker in markers) and field.get("section") == "work":
                value = _md_value(profile_text, ["实习1 - 开始时间", "工作1 - 开始时间"])
                if value:
                    return value
            if any(marker in ["结束日期", "结束时间", "end date"] for marker in markers) and field.get("section") == "work":
                value = _md_value(profile_text, ["实习1 - 结束时间", "工作1 - 结束时间"])
                if value:
                    return value
            if any(marker in ["职位", "职责", "角色", "岗位"] for marker in markers) and field.get("section") == "work":
                value = _md_value(profile_text, ["实习1 - 职位", "工作1 - 职位"])
                if value:
                    return value
            if any(marker in ["奖励", "荣誉", "获奖", "大赛", "竞赛", "award"] for marker in markers):
                awards = _format_items(structured.get("awards"), ["name", "date", "description"])
                if awards:
                    return awards
            value = _first_value(structured, paths)
            if value:
                return value

    key_map = [
        (["name", "姓名", "full name"], ["name", "full_name", "姓名", "name_cn"]),
        (["email", "邮箱", "mail"], ["email", "邮箱"]),
        (["phone", "mobile", "电话", "手机"], ["phone", "mobile", "telephone", "电话", "手机"]),
        (["github"], ["github", "github_url"]),
        (["linkedin"], ["linkedin", "linkedin_url"]),
    ]
    for markers, keys in key_map:
        if any(marker in label for marker in markers):
            for key in keys:
                value = data.get(key) if isinstance(data, dict) else None
                if value:
                    return str(value)
    if any(k in label for k in ["email", "邮箱", "mail"]):
        match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", flat)
        return match.group(0) if match else ""
    if any(k in label for k in ["phone", "mobile", "电话", "手机"]):
        match = re.search(r"(?<!\d)(?:\+?86[-\s]?)?1[3-9]\d[-\s]?\d{4}[-\s]?\d{4}(?!\d)", flat)
        return match.group(0) if match else ""
    return ""


def _answer_fields_for_fill(llm: Any, fields: list[dict[str, Any]], profile: Any, form_plan: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    profile_text = ""
    if isinstance(profile, dict):
        profile_text = str(profile.get("profile_template") or profile.get("raw_text") or "")
    def _answer_batch(batch: list[dict[str, Any]], section: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        evidence_pack = [
            {
                "uid": field.get("uid"),
                "label": field.get("label"),
                "type": field.get("type"),
                "evidence": _field_evidence_from_md(str(field.get("label", "")), profile_text),
            }
            for field in batch
        ]
        section_label = (section or {}).get("label", "未分区")
        section_id = (section or {}).get("section_id", "unknown")
        repeatable = bool((section or {}).get("repeatable"))
        prompt = f"""你是网申表单填写助手。请根据用户档案为当前页面章节生成答案。

要求：
1. 只返回 JSON，不要 markdown。
2. 不知道就 action=manual 或 answer 为空，不要编造。
3. 应填尽填：只要用户档案中有依据，就给出可填写答案，不要因为字段敏感而跳过。
4. 可填写字段 action=fill，confidence 为 high 或 medium；确实没有依据才 action=manual 或空答案。
5. 当前章节是 {section_label} ({section_id})，repeatable={repeatable}。教育/实习/项目等经历字段必须作为同一条经历理解，不要拆散上下文。

用户档案：
{_profile_to_text(profile)[:8000]}

按字段从 markdown 档案检索到的相关片段（优先使用这些证据回答）：
{json.dumps(evidence_pack, ensure_ascii=False)[:10000]}

字段：
{json.dumps(batch, ensure_ascii=False)[:8000]}

返回格式：
{{"answers":[{{"uid":"...","answer":"...","confidence":"high|medium|low","action":"fill|manual","reason":"..."}}]}}
"""
        try:
            if hasattr(llm, "call_json"):
                result = llm.call_json("", prompt)
            else:
                text = llm.call_text("", prompt)
                match = re.search(r"\{.*\}", text, re.S)
                result = json.loads(match.group(0)) if match else {}
            if isinstance(result, dict) and isinstance(result.get("answers"), list):
                return result["answers"]
        except Exception:
            return []
        return []

    answers = []
    if form_plan and isinstance(form_plan.get("sections"), list):
        for section in form_plan["sections"]:
            section_fields = section.get("fields") or []
            for start in range(0, len(section_fields), 12):
                answers.extend(_answer_batch(section_fields[start:start + 12], section))
    else:
        for start in range(0, len(fields), 8):
            answers.extend(_answer_batch(fields[start:start + 8]))

    by_uid = {str(item.get("uid")): item for item in answers if item.get("uid")}
    merged = []
    for field in fields:
        uid = field["uid"]
        item = dict(by_uid.get(uid, {}))
        item.setdefault("uid", uid)
        item.setdefault("action", "fill")
        item.setdefault("confidence", "medium")
        fallback = _fallback_answer(field, profile)
        if not str(item.get("answer") or "").strip() and fallback:
            item["answer"] = fallback
            item["confidence"] = item.get("confidence") or "medium"
            item["action"] = "fill"
            item["reason"] = "local_profile_fallback"
        else:
            item.setdefault("answer", fallback)
        item["label"] = field.get("label", "")
        item["type"] = field.get("type", "text")
        merged.append(item)
    return merged


def _default_resume_pdf_path() -> str:
    resume_dir = CONFIG.resume_dir
    if not resume_dir.exists():
        return ""
    pdfs = [p for p in resume_dir.glob("*.pdf") if p.is_file()]
    if not pdfs:
        return ""
    return str(max(pdfs, key=lambda p: p.stat().st_mtime))


def _apply_vision_actions(chrome: Any, task: FillTask, actions: list[dict[str, Any]], resume_path: str = "") -> int:
    applied = 0
    for action in actions[:5]:
        action_type = str(action.get("type", "")).lower()
        uid = action.get("uid")
        if not uid or action_type not in {"fill", "upload_file"}:
            continue
        try:
            if action_type == "upload_file":
                file_path = action.get("file_path") or resume_path or _default_resume_pdf_path()
                if not file_path:
                    continue
                chrome.call_tool("upload_file", {"uid": uid, "filePath": file_path})
                value_preview = file_path
            else:
                value = str(action.get("value") or action.get("answer") or "").strip()
                if not value:
                    continue
                chrome.call_tool("fill", {"uid": uid, "value": value})
                value_preview = value
            applied += 1
            task.add_log(f"视觉复核补填: {action_type} uid={uid} value={value_preview[:80]}")
            task.execution_history.append({
                "step": f"vision_repair.{action_type}",
                "status": "completed",
                "action_type": action_type,
                "uid": uid,
                "value_preview": value_preview[:80],
            })
        except Exception as exc:
            task.add_log(f"视觉复核补填失败 uid={uid}: {exc}")
    return applied


def _visual_field_hints(chrome: Any, vision: Any, snapshot: Any, fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not vision:
        return []
    try:
        image_bytes = _capture_scrolled_screenshot(chrome, rounds=3)
        if not image_bytes:
            return []
        prompt = f"""你是网申页面 GUI 字段识别助手。请结合截图和 accessibility snapshot，识别页面中真实可操作字段。

重点找出：
1. 简历/附件/作品集上传控件
2. 学历、日期、城市、是否至今等下拉框或单选/复选控件
3. snapshot 中 label 只显示为 select/请选择 的控件真实含义

只返回 JSON：
{{"fields":[{{"uid":"可从snapshot判断则填写，否则空","label":"字段名","type":"text|select|checkbox|radio|file","reason":"依据"}}]}}

当前 snapshot 字段：
{json.dumps(fields, ensure_ascii=False)[:6000]}
"""
        provider = getattr(vision, "provider", vision)
        if not hasattr(provider, "call_vision_text"):
            return []
        response = ""
        last_error = None
        for max_width, quality, max_height in ((960, 78, 2600), (720, 74, 2200), (520, 70, 1800)):
            try:
                compressed = VisionWorkflowAdapter._compress_image(image_bytes, max_width=max_width, quality=quality, max_height=max_height)
                response = provider.call_vision_text(prompt, compressed, mime_type="image/jpeg")
                break
            except Exception as exc:
                last_error = exc
        if not response:
            raise RuntimeError(str(last_error) if last_error else "vision field hints failed")
        match = re.search(r"\{.*\}", response, re.S)
        data = json.loads(match.group(0)) if match else {}
        hints = data.get("fields", []) if isinstance(data, dict) else []
        return [h for h in hints if isinstance(h, dict)]
    except Exception:
        return []


def _merge_visual_field_hints(fields: list[dict[str, Any]], hints: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not hints:
        return fields
    by_uid = {str(f.get("uid")): f for f in fields if f.get("uid")}
    for hint in hints:
        uid = str(hint.get("uid") or "")
        label = str(hint.get("label") or "").strip()
        field_type = str(hint.get("type") or "").strip().lower()
        if uid and uid in by_uid:
            field = by_uid[uid]
            if label and _is_generic_display_label(str(field.get("label", ""))):
                field["label"] = label
            if field_type in {"text", "select", "checkbox", "radio", "file"}:
                field["type"] = field_type
        elif uid and label and field_type in {"text", "select", "checkbox", "radio", "file"}:
            fields.append({"uid": uid, "label": label, "type": field_type, "required": True, "value": "", "visual_only": True})
    return fields


def _is_generic_display_label(label: str) -> bool:
    text = str(label or "").strip().lower()
    return text in {"", "select", "请选择", "请选择...", "please select", "下拉选择"}


def _upload_file_with_retries(chrome: Any, uid: str, file_path: str) -> str:
    return _upload_resume_and_confirm(chrome, uid, file_path, [uid])["action"]


def _file_name_markers(file_path: str) -> list[str]:
    path = Path(file_path)
    stem = path.stem
    return [path.name, stem, "上传成功", "已上传", "重新上传", "已选择", "selected", "uploaded"]


def _upload_confirmed(chrome: Any, file_path: str) -> bool:
    try:
        snapshot = chrome.call_tool("take_snapshot", {})
    except Exception:
        return False
    text = _snapshot_to_text(snapshot)
    normalized = text.lower()
    return any(marker and marker.lower() in normalized for marker in _file_name_markers(file_path))


def _evaluate_file_inputs(chrome: Any) -> list[dict[str, Any]]:
    script = """
() => Array.from(document.querySelectorAll('input[type="file"]')).map((el, index) => {
  const rect = el.getBoundingClientRect();
  const style = window.getComputedStyle(el);
  return {
    index,
    name: el.getAttribute('name') || '',
    id: el.id || '',
    accept: el.getAttribute('accept') || '',
    multiple: !!el.multiple,
    visible: rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none',
    outerHTML: el.outerHTML.slice(0, 300)
  };
})
"""
    for tool_name in ("evaluate_script", "evaluate"):
        try:
            result = chrome.call_tool(tool_name, {"function": script}, timeout=10)
            if isinstance(result, list):
                return result
            if isinstance(result, dict):
                value = result.get("result") or result.get("value") or result.get("data")
                if isinstance(value, list):
                    return value
        except Exception:
            continue
    return []


def _upload_diagnostics(chrome: Any, uid: str, file_path: str, fields: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    path = Path(file_path) if file_path else None
    snapshot_candidates = []
    for field in fields or []:
        label = str(field.get("label", ""))
        if field.get("type") == "file" or re.search(r"上传|附件|简历|作品|文件|resume|cv|attach|upload", label, re.I):
            snapshot_candidates.append({"uid": field.get("uid"), "label": label, "type": field.get("type")})
    return {
        "requested_uid": uid,
        "file_path": file_path,
        "file_exists": bool(path and path.exists()),
        "file_size": path.stat().st_size if path and path.exists() else 0,
        "snapshot_candidates": snapshot_candidates,
        "dom_file_inputs": _evaluate_file_inputs(chrome),
    }


def _upload_resume_and_confirm(chrome: Any, uid: str, file_path: str, candidate_uids: list[str] | None = None) -> dict[str, Any]:
    path = Path(file_path)
    if not path.exists():
        raise RuntimeError(f"resume file not found: {file_path}")
    last_error = None
    seen = set()
    candidates = []
    for candidate in candidate_uids or []:
        if candidate and candidate not in seen:
            candidates.append(candidate)
            seen.add(candidate)
    if uid and uid not in seen:
        candidates.append(uid)

    def _try_upload(target_uid: str, click_first: bool = False) -> str:
        if click_first:
            chrome.call_tool("click", {"uid": target_uid})
            time.sleep(0.8)
        chrome.call_tool("upload_file", {"uid": target_uid, "filePath": str(path)}, timeout=45)
        time.sleep(1.5)
        if _upload_confirmed(chrome, str(path)):
            return "click_then_upload_confirmed" if click_first else "upload_file_confirmed"
        raise RuntimeError("upload not confirmed in snapshot")

    for candidate in candidates:
        for click_first in (False, True):
            try:
                return {"ok": True, "action": _try_upload(candidate, click_first), "uid": candidate, "confirmed": True}
            except Exception as exc:
                last_error = exc

    # Some sites expose the real file input only after opening the upload panel.
    for candidate in candidates:
        try:
            chrome.call_tool("click", {"uid": candidate})
            time.sleep(1.0)
            refreshed = chrome.call_tool("take_snapshot", {})
            fresh_fields = _parse_snapshot_fields(refreshed)
            fresh_uids = [f.get("uid") for f in fresh_fields if f.get("type") == "file"]
            for fresh_uid in fresh_uids:
                try:
                    return {"ok": True, "action": _try_upload(str(fresh_uid), False), "uid": fresh_uid, "confirmed": True}
                except Exception as exc:
                    last_error = exc
        except Exception as exc:
            last_error = exc

    raise RuntimeError(f"upload unconfirmed: {last_error}" if last_error else "upload unconfirmed")


def _try_section_save(chrome: Any, task: FillTask, section: dict[str, Any]) -> None:
    section_id = section.get("section_id")
    save_uid = section.get("save_button_uid")
    if section_id not in {"education", "work", "project"} or not save_uid:
        return
    try:
        chrome.call_tool("click", {"uid": save_uid})
        time.sleep(1.0)
        task.add_log(f"章节保存: {section.get('label')} uid={save_uid}")
        task.execution_history.append({"step": "section.save", "status": "completed", "action_type": "click", "uid": save_uid, "label": section.get("label", "")})
    except Exception as exc:
        task.add_log(f"章节保存失败: {section.get('label')} uid={save_uid} error={exc}")
        task.execution_history.append({"step": "section.save", "status": "error", "uid": save_uid, "label": section.get("label", ""), "error": str(exc)})


def _fill_select_with_fallbacks(chrome: Any, uid: str, value: str) -> str:
    return _select_and_confirm(chrome, uid, value)["action"]


def _normalize_option_text(value: str) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[\._/-]", "", text)
    text = text.replace("年", "").replace("月", "").replace("日", "")
    replacements = {
        "大学本科": "本科",
        "学士学位": "本科",
        "硕士研究生": "硕士",
        "研究生": "硕士",
        "博士研究生": "博士",
        "至今": "现在",
        "present": "现在",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return text


def _snapshot_contains_value(snapshot: Any, uid: str, value: str) -> bool:
    text = _snapshot_to_text(snapshot)
    target = _normalize_option_text(value)
    if not target:
        return False
    normalized_text = _normalize_option_text(text)
    if target in normalized_text:
        return True
    for line in text.splitlines():
        if uid and uid in line and target in _normalize_option_text(line):
            return True
    return any(target and target in _normalize_option_text(line) for line in text.splitlines())


def _extract_snapshot_options(snapshot: Any, target_value: str) -> list[dict[str, str]]:
    options = []
    text = _snapshot_to_text(snapshot)
    target = _normalize_option_text(target_value)
    for line in text.splitlines():
        uid_match = re.search(r"uid=([\w_]+)", line)
        if not uid_match:
            continue
        label_match = re.search(r'"([^"]+)"', line)
        label = label_match.group(1) if label_match else re.sub(r"uid=[\w_]+", "", line).strip()[:80]
        if not label:
            continue
        norm = _normalize_option_text(label)
        if target and (target == norm or target in norm or norm in target):
            options.append({"uid": uid_match.group(1), "label": label})
    return options


def _select_and_confirm(chrome: Any, uid: str, value: str) -> dict[str, Any]:
    last_error = None
    attempts = []
    def _fill_attempt():
        chrome.call_tool("fill", {"uid": uid, "value": value})
        chrome.call_tool("press_key", {"key": "Tab"})

    def _click_type_enter():
        chrome.call_tool("click", {"uid": uid})
        time.sleep(0.3)
        chrome.call_tool("type_text", {"uid": uid, "text": value})
        time.sleep(0.3)
        chrome.call_tool("press_key", {"key": "Enter"})
        time.sleep(0.2)
        chrome.call_tool("press_key", {"key": "Tab"})

    def _click_option_attempt():
        chrome.call_tool("click", {"uid": uid})
        time.sleep(0.5)
        option_snapshot = chrome.call_tool("take_snapshot", {})
        options = _extract_snapshot_options(option_snapshot, value)
        if not options:
            raise RuntimeError("no matching dropdown option found")
        chrome.call_tool("click", {"uid": options[0]["uid"]})
        time.sleep(0.3)
        chrome.call_tool("press_key", {"key": "Tab"})

    def _keyboard_attempt():
        chrome.call_tool("click", {"uid": uid})
        time.sleep(0.2)
        chrome.call_tool("press_key", {"key": "ArrowDown"})
        time.sleep(0.1)
        chrome.call_tool("press_key", {"key": "Enter"})
        time.sleep(0.2)
        chrome.call_tool("press_key", {"key": "Tab"})

    attempts.extend([
        ("select_option_click_confirm", _click_option_attempt),
        ("select_fill_confirm", _fill_attempt),
        ("select_click_type_enter_confirm", _click_type_enter),
        ("select_keyboard_confirm", _keyboard_attempt),
    ])
    for name, fn in attempts:
        try:
            fn()
            time.sleep(1.1)
            snapshot = chrome.call_tool("take_snapshot", {})
            if _snapshot_contains_value(snapshot, uid, value):
                return {"ok": True, "action": name, "confirmed": True}
            last_error = RuntimeError("dropdown value not confirmed in snapshot")
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"select unconfirmed: {last_error}" if last_error else "select unconfirmed")


def _vision_review_fill(chrome: Any, fields: list[dict], snapshot_text: str) -> dict[str, Any]:
    from ..llm.vision import VisionWorkflowAdapter, create_vision_client

    vision_provider = create_vision_client(CONFIG)
    if vision_provider is None:
        return {}
    vision = VisionWorkflowAdapter(vision_provider)

    screenshot = chrome.call_tool("take_screenshot", {}, timeout=20)
    image_bytes = _screenshot_to_bytes(screenshot)
    if not image_bytes:
        return {"ok": False, "summary": "截图为空，无法视觉评估"}

    prompt = f"""你是网申表单填写验收助手。请结合截图和页面无障碍树，严格判断字段是否已经正确填写。

要求：
1. 只返回 JSON，不要 markdown。
2. 只有所有应填字段都在视觉上确认成功、附件上传状态也可见时，ok 才能为 true。
3. 如果下拉框、单选、多选、自定义组件、附件上传控件未成功，ok 必须为 false。
4. 对失败项给出可执行建议，例如点击哪个控件、选择哪个选项、需要用户手动处理什么。
5. 如果能判断下一步自动化动作，请放入 next_actions。动作类型只允许 click、fill、upload_file、manual。

已尝试填写字段：
{json.dumps(fields, ensure_ascii=False)[:5000]}

页面无障碍树：
{snapshot_text[:5000]}

返回格式：
{{"ok": true, "summary": "...", "issues": [{{"uid":"...", "label":"...", "problem":"...", "suggestion":"..."}}], "next_actions": [{{"type":"manual", "uid":"...", "reason":"..."}}]}}
"""
    try:
        result = vision.provider.call_vision_text(prompt, image_bytes)
        from ..llm.base import BaseLLMClient
        return BaseLLMClient._strip_json_fence(result) and json.loads(BaseLLMClient._strip_json_fence(result))
    except Exception as exc:
        return {"ok": False, "summary": f"视觉评估失败: {exc}", "issues": []}


@app.route("/")
def index():
    return send_from_directory(
        Path(__file__).parent / "templates",
        "index.html",
        mimetype="text/html",
    )


# ─── 个人信息 API ──────────────────────────────────────────

@app.route("/api/profile", methods=["GET"])
def api_get_profile():
    path = CONFIG.unified_profile_path
    if path.exists():
        return jsonify({"exists": True, "data": load_yaml(path)})
    return jsonify({"exists": False, "data": {}})


@app.route("/api/vision/health", methods=["GET"])
def api_vision_health():
    from resume_skill.llm.vision import check_vision_health

    return jsonify(check_vision_health(CONFIG))


@app.route("/api/extract", methods=["POST"])
def api_extract():
    """Extract resume information using ResumeAnalyzerNode."""
    if "file" not in request.files:
        return jsonify({"error": "未上传文件"}), 400
    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "文件名不能为空"}), 400

    _ensure_dirs()
    pdf_path = CONFIG.resume_dir / file.filename
    file.save(str(pdf_path))

    try:
        from ..agent.resume_analyzer_node import analyze_resume
        
        # Use ResumeAnalyzerNode to analyze
        result = analyze_resume(str(pdf_path))
        
        if result["status"] == "extracted":
            return jsonify(result)
        else:
            # Failed to extract - return 422
            return jsonify({
                "status": "failed",
                "error": result.get("error", "简历解析失败：请确认 PDF 可复制文本、不是扫描件，并检查模型配置是否可用"),
            }), 422
    except Exception as e:
        import traceback
        traceback.print_exc()
        # Exception also returns 422 for consistency
        return jsonify({
            "status": "failed",
            "error": str(e)
        }), 422


@app.route("/api/consolidate", methods=["POST"])
def api_consolidate():
    try:
        from ..extractor.extractor import PersonalInfoExtractor

        extractor = PersonalInfoExtractor(personal_info_dir=str(CONFIG.personal_info_dir))
        profile = extractor.generate_unified_profile()
        return jsonify({"status": "consolidated", "profile": profile})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── 档案编辑 API ──────────────────────────────────────────

@app.route("/api/profile/template", methods=["GET", "POST"])
def api_profile_template():
    """读写 profile_template.md"""
    path = CONFIG.personal_info_dir / "profile_template.md"
    if request.method == "POST":
        data = request.get_json()
        content = data.get("content", "")
        path.write_text(content, encoding="utf-8")
        return jsonify({"status": "saved"})
    if path.exists():
        return jsonify({"exists": True, "content": path.read_text(encoding="utf-8")})
    return jsonify({"exists": False, "content": ""})


@app.route("/api/profile/analyze", methods=["POST"])
def api_profile_analyze():
    """Analyze MD vs reference, return missing fields."""
    try:
        from ..extractor.extractor import PersonalInfoExtractor
        data = request.get_json() or {}
        md_content = data.get("content", "")
        if not md_content:
            return jsonify({"missing": [], "error": "内容为空"})

        extractor = PersonalInfoExtractor(personal_info_dir=str(CONFIG.personal_info_dir))
        missing = extractor.analyze_missing_fields(md_content)
        return jsonify({"missing": missing})
    except Exception as e:
        return jsonify({"missing": [], "error": str(e)}), 500


@app.route("/api/profile/prepare", methods=["POST"])
def api_profile_prepare():
    """Add missing fields prompt to MD top, return updated MD."""
    try:
        from ..extractor.extractor import PersonalInfoExtractor
        data = request.get_json() or {}
        md_content = data.get("content", "")
        missing = data.get("missing", [])
        updated = PersonalInfoExtractor.prepend_missing_fields(md_content, missing)
        return jsonify({"content": updated})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── 偏好设置 API ──────────────────────────────────────────

PREFERENCES_PATH = CONFIG.project_root / "job_preferences.yaml"

DEFAULT_PREFERENCES = {
    "personal_info": {"base_city": "", "job_type": "校招", "preferred_industries": []},
    "target_companies": [],
}


def _load_preferences() -> dict:
    if PREFERENCES_PATH.exists():
        return load_yaml(PREFERENCES_PATH) or DEFAULT_PREFERENCES.copy()
    return DEFAULT_PREFERENCES.copy()


def _save_preferences(data: dict):
    import yaml
    PREFERENCES_PATH.write_text(
        yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )


@app.route("/api/preferences", methods=["GET", "POST"])
def api_preferences():
    if request.method == "POST":
        data = request.get_json()
        _save_preferences(data)
        return jsonify({"status": "saved"})
    return jsonify(_load_preferences())


# ─── 批量登录 API ──────────────────────────────────────────

@app.route("/api/scout/login", methods=["POST"])
def api_scout_login():
    """Open all company websites in Chrome for user to login."""
    data = request.get_json() or {}
    companies = data.get("companies", [])
    if not companies:
        return jsonify({"error": "没有公司"}), 400

    global _chrome_instance
    from resume_skill.agent.mcp.chrome_client import ChromeDevToolsClient

    def _open_chrome_background():
        global _chrome_instance
        try:
            _chrome_instance = _get_or_start_chrome(headless=False)
            for i, c in enumerate(companies):
                name = c.get("name", "?")
                url = c.get("url", "")
                if not url:
                    continue
                if i == 0:
                    _chrome_instance.call_tool("navigate_page", {"url": url})
                else:
                    _chrome_instance.call_tool("new_page", {"url": url})
        except Exception as e:
            print(f"[scout] Chrome 启动失败: {e}")

    thread = threading.Thread(target=_open_chrome_background, daemon=True)
    thread.start()
    return jsonify({"status": "starting", "message": "Chrome 正在后台启动，请等待..."})


# ─── 后台任务执行函数 ──────────────────────────────────────

def _execute_fill_task(task: FillTask):
    """Execute fill task in background thread using LangGraph workflow."""
    global _chrome_instance
    
    task.status = "running"
    task.started_at = datetime.now()
    task.add_log("任务开始执行")

    def _format_history_entry(entry: dict) -> str:
        step = entry.get("step", "workflow")
        status = entry.get("status", "")
        parts = [entry.get("action_type", "")]
        if entry.get("uid"):
            parts.append(f"uid={entry.get('uid')}")
        if entry.get("label"):
            parts.append(f"label={entry.get('label')}")
        if entry.get("value_preview"):
            parts.append(f"value={entry.get('value_preview')}")
        if entry.get("value"):
            parts.append(f"value={entry.get('value')}")
        if entry.get("field_count") is not None:
            parts.append(f"fields={entry.get('field_count')}")
        parts.append(entry.get("message") or entry.get("reason") or entry.get("error") or "")
        detail = " ".join(str(p) for p in parts if p)
        return f"{step}: {status} {detail}".strip()

    def _sync_task_from_state(state: dict, node_name: str = ""):
        if not state:
            return
        if node_name:
            task.current_task = f"正在执行：{node_name}"
        task.success = state.get("success", False)
        task.manual_required = state.get("manual_required", False)
        task.errors = state.get("errors", [])
        task.execution_history = state.get("execution_history", [])
        task.fields = list((state.get("application_form") or {}).values())
        task.failed_count = len([f for f in task.fields if f.get("required") and not f.get("value")])
        task.vision_review = state.get("visual_verification_result", {}) or {}
    
    try:
        from resume_skill.workflow import build_application_graph, ApplicationState
        from resume_skill.llm.factory import create_llm_client
        from resume_skill.llm.vision import VisionWorkflowAdapter, create_vision_client
        from resume_skill.extractor.extractor import PersonalInfoExtractor
        
        # 步骤 1: 初始化状态
        task.current_task = "正在初始化工作流..."
        task.add_log("初始化 ApplicationState")
        
        # 加载用户档案。填表阶段不要重新调用 LLM consolidate，直接使用已确认的 YAML + 原始模板。
        structured_profile = load_yaml(CONFIG.unified_profile_path) if CONFIG.unified_profile_path.exists() else {}
        template_path = CONFIG.personal_info_dir / "profile_template.md"
        template_profile = template_path.read_text(encoding="utf-8") if template_path.exists() else ""
        user_profile = {
            "structured": structured_profile,
            "profile_template": template_profile,
            "raw_text": template_profile,
        }
        
        # 创建应用状态
        initial_state = {
            "task_id": task.task_id,
            "user_profile": user_profile,
            "resume_pdf_path": task.resume_path or "",
            "application_form": {},
            "browser_context": {},
            "execution_history": [],
            "errors": [],
            "success": False,
            "manual_required": False,
            "gui_recovery_needed": False,
            "retry_count": 0,
            "max_retries": 20,
        }
        
        # 步骤 2: 获取 Chrome 实例
        task.current_task = "正在连接 Chrome..."
        task.add_log("获取 Chrome 实例")
        chrome = _get_or_start_chrome(headless=False)
        
        # 步骤 3: 创建 LLM 和视觉客户端
        task.current_task = "正在初始化 LLM..."
        task.add_log("创建 LLM 客户端")
        llm = create_llm_client()
        vision_provider = create_vision_client(CONFIG)
        vision = VisionWorkflowAdapter(vision_provider) if vision_provider else None
        
        # 步骤 4: 直接执行填表闭环，避免 planner 反复返回 wait/done 等不可执行动作。
        task.current_task = "正在读取当前页面表单..."
        task.add_log("读取 Chrome 当前页 snapshot")
        snapshot = chrome.call_tool("take_snapshot", {})
        snapshot_text = _snapshot_to_text(snapshot)
        fields = _parse_snapshot_fields(snapshot)
        hints = _visual_field_hints(chrome, vision, snapshot, fields)
        if hints:
            task.add_log(f"视觉辅助识别到 {len(hints)} 个字段提示")
            fields = _merge_visual_field_hints(fields, hints)
        form_plan = _build_form_plan(fields, snapshot, hints)
        section_summary = "、".join(f"{s['label']}({len(s.get('fields') or [])})" for s in form_plan.get("sections", []))
        task.add_log(f"页面结构计划: {section_summary}")
        task.fields = fields
        task.add_log(f"解析到 {len(fields)} 个可处理字段")
        task.execution_history.append({"step": "direct_fill.parse_snapshot", "status": "completed", "field_count": len(fields), "message": section_summary})

        if not fields:
            task.status = "failed"
            task.errors.append("当前页面没有识别到可填写字段，请确认 Chrome 停留在真实网申表单页")
            task.add_log(f"错误: {task.errors[-1]}")
            task.completed_at = datetime.now()
            return

        task.current_task = "正在生成字段答案..."
        task.add_log("调用 LLM 生成字段答案")
        answers = _answer_fields_for_fill(llm, fields, user_profile, form_plan)
        task.add_log(f"生成 {len(answers)} 个字段答案")

        answers_by_uid = {str(item.get("uid")): item for item in answers if item.get("uid")}
        filled_count = 0
        skipped_count = 0
        failed_count = 0
        task.current_task = "正在逐字段填写..."
        sections_to_run = form_plan.get("sections", []) or [{"label": "全部字段", "section_id": "all", "fields": fields}]
        for section in sections_to_run:
            section_fields = section.get("fields") or []
            task.add_log(f"开始章节: {section.get('label')} fields={len(section_fields)}")
            section_attempted = 0
            for field in section_fields:
                uid = field.get("uid", "")
                label = field.get("label", uid)
                field_type = field.get("type", "text")
                answer = answers_by_uid.get(uid, {})
                value = str(answer.get("answer") or "").strip()
                confidence = str(answer.get("confidence") or "medium").lower()
                action = str(answer.get("action") or "fill").lower()

                if field_type == "file":
                    value = task.resume_path or _default_resume_pdf_path()
                    action = "upload_file" if value else "manual"
                elif field_type in {"checkbox", "radio"} or str(value).lower() in {"true", "yes", "是", "同意"}:
                    action = "click"

                if action == "manual" and not value:
                    skipped_count += 1
                    field.update({"action": "manual", "answer": value, "value": "", "filled": False, "confirmed": False})
                    task.add_log(f"跳过人工字段 uid={uid} label={label}")
                    continue

                if not value or value == "未提供":
                    skipped_count += 1
                    field.update({"action": "skip", "answer": value, "value": "", "filled": False, "confirmed": False})
                    task.add_log(f"跳过无答案字段 uid={uid} label={label}")
                    continue

                try:
                    if action == "upload_file" or field_type == "file":
                        upload_candidates = [f.get("uid") for f in fields if f.get("type") == "file"]
                        diagnostics = _upload_diagnostics(chrome, uid, value, fields)
                        task.add_log(f"上传诊断: file_exists={diagnostics['file_exists']} size={diagnostics['file_size']} snapshot_candidates={len(diagnostics['snapshot_candidates'])} dom_file_inputs={len(diagnostics['dom_file_inputs'])}")
                        upload_result = _upload_resume_and_confirm(chrome, uid, value, upload_candidates)
                        action_type = upload_result["action"]
                        uid = str(upload_result.get("uid") or uid)
                    elif action == "click":
                        chrome.call_tool("click", {"uid": uid})
                        action_type = "click"
                    elif field_type == "select":
                        select_result = _select_and_confirm(chrome, uid, value)
                        action_type = select_result["action"]
                    else:
                        chrome.call_tool("fill", {"uid": uid, "value": value})
                        time.sleep(0.2)
                        try:
                            chrome.call_tool("press_key", {"key": "Tab"})
                        except Exception:
                            pass
                        action_type = "fill"
                    filled_count += 1
                    section_attempted += 1
                    field.update({"action": action_type, "answer": value, "value": value, "filled": True, "confirmed": field_type in {"select", "file"}, "confidence": confidence})
                    entry = {"step": f"direct_fill.{action_type}", "status": "completed", "action_type": action_type, "uid": uid, "label": label, "value_preview": value[:80]}
                    task.execution_history.append(entry)
                    task.add_log(_format_history_entry(entry))
                    task.add_log(f"字段进度: {filled_count}/{len(fields)} 已填")
                    if field_type == "select" or action_type.startswith("select"):
                        time.sleep(0.9)
                    else:
                        time.sleep(0.3)
                except Exception as exc:
                    failed_count += 1
                    field.update({"action": action, "answer": value, "value": "", "filled": False, "confirmed": False, "fill_error": str(exc)})
                    entry = {"step": "direct_fill.fill", "status": "error", "uid": uid, "label": label, "error": str(exc)}
                    task.execution_history.append(entry)
                    task.add_log(_format_history_entry(entry))
            if section_attempted:
                _try_section_save(chrome, task, section)

        task.failed_count = failed_count + skipped_count

        task.current_task = "正在进行视觉复核..."
        for review_round in range(1, 3):
            task.add_log(f"视觉复核第 {review_round} 轮")
            try:
                verify_snapshot = chrome.call_tool("take_snapshot", {})
                verify_screenshot = _capture_scrolled_screenshot(chrome, rounds=3)
                if not vision or filled_count <= 0:
                    break
                response = vision.verify(
                    screenshot=verify_screenshot,
                    snapshot=verify_snapshot,
                    prompt="请判断网申表单是否已经出现刚刚填写的字段内容，并找出漏填/填错项。只返回 JSON：{\"action_success\":true/false,\"page_success\":true/false,\"summary\":\"...\",\"issues\":[{\"uid\":\"...\",\"label\":\"...\",\"problem\":\"...\",\"suggestion\":\"...\"}],\"next_actions\":[{\"type\":\"fill|upload_file|manual\",\"uid\":\"...\",\"value\":\"...\",\"reason\":\"...\"}],\"manual_required\":false}",
                )
                try:
                    task.vision_review = json.loads(re.search(r"\{.*\}", response, re.S).group(0))
                except Exception:
                    task.vision_review = {"summary": str(response)[:500], "action_success": False, "page_success": False, "next_actions": []}
                task.add_log(f"视觉复核: {task.vision_review.get('summary', '')}")
                if task.vision_review.get("page_success") or task.vision_review.get("ok"):
                    break
                repaired = _apply_vision_actions(chrome, task, task.vision_review.get("next_actions") or [], task.resume_path)
                if repaired <= 0:
                    break
                filled_count += repaired
            except Exception as exc:
                task.errors.append(f"验收失败: {exc}")
                task.add_log(f"错误: {task.errors[-1]}")
                break

        task.success = filled_count > 0 and failed_count == 0
        task.manual_required = skipped_count > 0 or failed_count > 0
        task.add_log(f"填写完成: 成功 {filled_count}，跳过 {skipped_count}，失败 {failed_count}")

        if filled_count > 0:
            task.status = "completed"
            task.add_log("✓ 已执行真实填写动作")
        else:
            task.status = "failed"
            task.errors.append("没有任何字段被成功填写")
            task.add_log(f"✗ {task.errors[-1]}")

        task.completed_at = datetime.now()
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        task.status = "failed"
        task.errors.append(str(e))
        task.add_log(f"任务失败: {e}")
        task.completed_at = datetime.now()
    finally:
        # Do not delete the uploaded PDF immediately. Some web upload controls read
        # the selected file asynchronously after the MCP call returns.
        pass


# ─── 网申填写 API (后台任务模式) ────────────────────────────

@app.route("/api/fill/start", methods=["POST"])
def api_fill_start():
    """启动后台填写任务"""
    # 保存上传的简历文件（如果有）
    resume_path = ""
    if "resume" in request.files:
        f = request.files["resume"]
        fd, resume_path = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        f.save(resume_path)
    
    # 创建后台任务
    task = task_manager.create_task(resume_path)
    
    # 启动后台线程执行任务
    thread = threading.Thread(
        target=_execute_fill_task,
        args=(task,),
        daemon=True
    )
    task.thread = thread
    thread.start()
    
    # 立即返回任务ID和状态
    return jsonify({
        "task_id": task.task_id,
        "status": "started"
    })


@app.route("/api/fill/status/<task_id>", methods=["GET"])
def api_fill_status(task_id):
    """获取任务状态"""
    task = task_manager.get_task(task_id)
    if not task:
        return jsonify({"error": "任务不存在"}), 404
    
    return jsonify(task.to_dict())


@app.route("/api/fill/cancel/<task_id>", methods=["POST"])
def api_fill_cancel(task_id):
    """取消任务"""
    success = task_manager.cancel_task(task_id)
    if success:
        return jsonify({"status": "cancelled"})
    else:
        return jsonify({"error": "任务无法取消"}), 400


# ─── 勘探（Scout）API ─────────────────────────────────────

@app.route("/api/scout/start", methods=["POST"])
def api_scout_start():
    global _scout_progress, _chrome_instance
    if _scout_progress.get("running"):
        return jsonify({"error": "勘探任务已在运行"}), 400

    md_path = CONFIG.personal_info_dir / "profile_template.md"
    profile_text = md_path.read_text(encoding="utf-8") if md_path.exists() else ""
    prefs = _load_preferences()
    companies = prefs.get("target_companies", [])
    if not companies:
        return jsonify({"error": "请在偏好设置中至少添加一个目标公司"}), 400

    def _full_scout_worker():
        global _chrome_instance, _scout_progress
        _scout_progress["running"] = True
        _scout_progress["log"] = []
        _scout_progress["results"] = []

        def log(msg):
            _scout_progress["log"].append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

        # 复用已有 Chrome 或新建
        if _chrome_instance is None or not _chrome_is_alive(_chrome_instance):
            log("正在启动 Chrome...")
            try:
                _chrome_instance = _get_or_start_chrome(headless=False)
                log("Chrome 已启动（全程保持，不会关闭）")
            except Exception as e:
                log(f"Chrome 启动失败: {e}")
                _scout_progress["running"] = False
                return
        else:
            log("使用已有的 Chrome 会话")

        from resume_skill.llm.factory import create_llm_client
        llm = create_llm_client()

        for i, c in enumerate(companies[:3]):
            name = c.get("name", f"公司{i+1}")
            url = c.get("url", "")
            if not url:
                continue

            matched_jobs = []
            log(f"[{name}] 打开页面...")
            try:
                if i == 0:
                    _chrome_instance.call_tool("navigate_page", {"url": url})
                else:
                    _chrome_instance.call_tool("new_page", {"url": url})
                time.sleep(3)

                # LLM 快速提取岗位列表
                log(f"[{name}] 正在分析岗位...")
                import concurrent.futures
                try:
                    snapshot = _chrome_instance.call_tool("take_snapshot", {})
                    snapshot_short = str(snapshot)[:2500]
                    prompt = f"""从页面无障碍树提取职位名称。只返回JSON: {{"jobs":[{{"title":"职位名"}}]}}
页面：{name}
无障碍树：{snapshot_short[:2500]}"""
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                        future = pool.submit(llm.call_json, "", prompt)
                        result = future.result(timeout=10)
                        raw_jobs = result.get("jobs", []) if isinstance(result, dict) else []
                        matched_jobs = [{"title": j["title"], "link": url} for j in raw_jobs[:5]]
                        if matched_jobs:
                            log(f"[{name}] 找到 {len(matched_jobs)} 个岗位")
                except concurrent.futures.TimeoutError:
                    log(f"[{name}] 分析超时")
                except Exception as e:
                    log(f"[{name}] 分析: {str(e)[:60]}")

                if not matched_jobs:
                    try:
                        snap = _chrome_instance.call_tool("take_snapshot", {}, timeout=10)
                        first_line = str(snap).split("\n")[0] if snap else ""
                        page_title = first_line[:60] if first_line else name
                        matched_jobs = [{"title": f"{name} - {page_title}", "link": url}]
                    except:
                        matched_jobs = [{"title": name, "link": url}]

                _scout_progress["results"].append({
                    "company": name,
                    "url": url,
                    "matched_jobs": matched_jobs,
                })
                log(f"[{name}] 完成")
            except Exception as e:
                log(f"[{name}] 出错: {str(e)[:80]}")
                _scout_progress["results"].append({
                    "company": name,
                    "url": url,
                    "matched_jobs": [{"title": name, "link": url}],
                })

        _scout_progress["running"] = False
        log("勘探结束（Chrome 保持打开，可继续后续步骤）")

    thread = threading.Thread(target=_full_scout_worker, daemon=True)
    thread.start()
    return jsonify({"status": "started"})


@app.route("/api/scout/debug", methods=["GET"])
def api_scout_debug():
    """Debug endpoint to check scout state."""
    global _chrome_instance, _scout_progress
    return jsonify({
        "chrome_alive": _chrome_instance is not None and _chrome_is_alive(_chrome_instance),
        "scout_running": _scout_progress.get("running", False),
        "scout_log_count": len(_scout_progress.get("log", [])),
        "scout_result_count": len(_scout_progress.get("results", [])),
    })


@app.route("/api/scout/status", methods=["GET"])
def api_scout_status():
    global _scout_progress
    return jsonify({
        "running": _scout_progress["running"],
        "log": _scout_progress["log"][-50:],
        "results": _scout_progress["results"],
    })


# ─── 投递 API ──────────────────────────────────────────────

@app.route("/api/apply/start", methods=["POST"])
def api_apply_start():
    data = request.get_json() or {}
    urls = data.get("urls", [])
    if not urls:
        return jsonify({"error": "请提供至少一个投递链接"}), 400

    def _worker(target_urls: list[str]):
        from resume_skill.agent.mcp.agent import run_agent
        for u in target_urls:
            try:
                run_agent(u)
            except Exception:
                pass

    thread = threading.Thread(target=_worker, args=(urls,), daemon=True)
    thread.start()
    return jsonify({"status": "started", "count": len(urls)})


# ─── 启动 ──────────────────────────────────────────────────

def _clean_previous_run():
    """Remove generated files from previous runs so each session starts fresh."""
    for f in ["profile_template.md", "unified_profile.yaml"]:
        p = CONFIG.personal_info_dir / f
        if p.exists():
            p.unlink()
            print(f"  [clean] removed: {f}")


def _safe_print(msg: str):
    try:
        print(msg)
    except UnicodeEncodeError:
        safe = msg.encode("utf-8", errors="replace").decode("gbk", errors="replace")
        print(safe)


def run_webui(host: str = "127.0.0.1", port: int = 5000, debug: bool = False, clean: bool = False):
    if clean:
        _clean_previous_run()
    _safe_print("\n  [RESUME_SKILL] Web UI started")
    _safe_print(f"  URL: http://{host}:{port}")
    _safe_print("  Press Ctrl+C to stop\n")
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--clean", action="store_true", help="清理上次运行的记录")
    p.add_argument("--port", type=int, default=5000)
    args, _ = p.parse_known_args()
    run_webui(port=args.port, clean=args.clean)

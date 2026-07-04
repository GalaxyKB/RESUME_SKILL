from __future__ import annotations

from pathlib import Path
from typing import Any

from .utils import normalize_whitespace, to_plain_text


SENSITIVE_KEYWORDS = [
    "身份证",
    "证件号",
    "详细住址",
    "家庭住址",
    "紧急联系人",
    "亲属任职",
    "是否接受调剂",
    "期望薪资",
    "政治面貌",
    "健康状况",
    "婚育情况",
    "银行卡",
    "护照",
]


FIELD_RULES = [
    # 基本个人信息
    ("name_cn", ["姓名", "真实姓名", "name", "candidate name", "全名"], "profile.personal.name_cn", 1.0, "auto_fill"),
    ("name_en", ["英文名", "english name", "name in english"], "profile.personal.name_en", 0.95, "auto_fill"),
    ("email", ["邮箱", "电子邮箱", "email", "e-mail", "邮件"], "profile.personal.email", 1.0, "auto_fill"),
    ("phone", ["手机", "手机号", "电话", "phone", "mobile", "tel", "手机号码", "联系电话"], "profile.personal.phone", 1.0, "auto_fill"),
    ("wechat", ["微信", "wechat", "微信号"], "profile.personal.wechat", 0.95, "auto_fill"),
    
    # 个人特征
    ("gender", ["性别", "gender", "男", "女"], "profile.personal.gender", 0.98, "auto_fill"),
    ("age", ["年龄", "age", "岁"], "profile.personal.age", 0.95, "auto_fill"),
    ("birthday", ["出生年月", "生日", "出生日期", "birthday", "生日日期", "出生"], "profile.personal.birthday", 0.95, "auto_fill"),
    ("marital_status", ["婚姻状况", "婚姻", "married", "status", "未婚", "已婚"], "profile.personal.marital_status", 0.95, "auto_fill"),
    
    # 教育信息
    ("school", ["学校", "毕业院校", "院校", "大学", "university", "school", "学园"], "profile.education[0].school", 0.98, "auto_fill"),
    ("major", ["专业", "专业方向", "major", "学科"], "profile.education[0].major", 0.98, "auto_fill"),
    ("degree", ["学历", "学位", "degree", "education level", "学历水平", "最高学历"], "profile.education[0].degree", 0.98, "auto_fill"),
    ("graduation_year", ["毕业时间", "毕业年份", "毕业年月", "graduation", "毕业"], "profile.education[0].graduation_year", 0.95, "auto_fill"),
    ("graduation_date", ["毕业日期", "毕业"], "profile.education[0].graduation_date", 0.95, "auto_fill"),
    ("start_date", ["入学时间", "入学年份", "入学", "开始日期"], "profile.education[0].start_date", 0.95, "auto_fill"),
    ("gpa", ["gpa", "绩点", "平均分", "绩点分数", "平均绩点", "加权平均分"], "profile.education[0].gpa", 0.98, "auto_fill"),
    ("rank", ["排名", "名次", "专业排名", "rank", "专业名次"], "profile.education[0].rank", 0.95, "auto_fill"),
    
    # 工作信息
    ("work_start_date", ["参加工作日期", "工作开始", "参加工作", "work start"], "profile.personal.work_start_date", 0.95, "auto_fill"),
    ("work_mode", ["工作模式", "工作方式", "work mode", "日常实习", "兼职", "全职"], "profile.personal.work_mode", 0.95, "auto_fill"),
    
    # 地址信息
    ("current_location", ["现居住地", "居住地", "所在城市", "现住地", "location", "城市"], "profile.personal.location", 0.92, "auto_fill"),
    ("target_location", ["期望工作地", "期望城市", "意向城市", "目标城市", "target city", "工作地点"], "preferences.location_preferences[0]", 0.92, "auto_fill"),
    ("hometown", ["家乡", "籍贯", "hometown"], "profile.personal.hometown", 0.90, "auto_fill"),
    
    # 经历和技能
    ("skills", ["技能", "skills", "技能描述", "掌握的技能"], "jd_analysis.tailored_texts.skills_summary", 0.95, "review_then_fill"),
    ("project_experience", ["项目经历", "项目经验", "project experience", "项目"], "jd_analysis.tailored_texts.project_experience_long", 0.95, "review_then_fill"),
    ("self_introduction", ["自我介绍", "个人介绍", "self introduction", "介绍", "自我描述"], "jd_analysis.tailored_texts.self_introduction_300", 0.95, "review_then_fill"),
    ("research_experience", ["研究经历", "科研经历", "research experience", "研究"], "jd_analysis.tailored_texts.research_experience", 0.95, "review_then_fill"),
    ("work_experience", ["工作经历", "工作经验", "work experience", "工作"], "jd_analysis.tailored_texts.work_experience", 0.95, "review_then_fill"),
    ("internship_experience", ["实习经历", "实习经验", "internship experience", "实习"], "jd_analysis.tailored_texts.internship_experience", 0.95, "review_then_fill"),
    ("why_this_role", ["为什么选择该岗位", "why this role", "应聘理由", "应聘原因"], "jd_analysis.tailored_texts.why_this_role", 0.95, "review_then_fill"),
    ("why_this_company", ["为什么选择公司", "why this company", "公司", "为什么"], "jd_analysis.tailored_texts.why_this_company", 0.95, "review_then_fill"),
    ("most_representative_project", ["最有代表性的项目", "代表性项目", "most representative project"], "jd_analysis.tailored_texts.most_representative_project", 0.95, "review_then_fill"),
    ("competition_awards", ["竞赛", "比赛", "竞赛经历", "competition", "contest", "获奖经历", "award experience", "比赛获奖"], "qa_bank.competition_awards_summary", 0.95, "review_then_fill"),
    ("honors_awards", ["获奖", "荣誉", "honor", "award", "荣誉称号", "获得"], "qa_bank.honors_awards_summary", 0.95, "review_then_fill"),
]


def _get_nested_value(data: dict[str, Any], path: str) -> Any:
    current: Any = data
    for segment in path.split("."):
        if "[0]" in segment:
            key = segment.replace("[0]", "")
            current = current.get(key, []) if isinstance(current, dict) else []
            current = current[0] if current else {}
        else:
            current = current.get(segment, {}) if isinstance(current, dict) else {}
    return current if current not in ({}, []) else ""


def _resolve_path_value(profile: dict[str, Any], preferences: dict[str, Any], resume_md: str, qa_bank: dict[str, Any], jd_analysis: dict[str, Any], path: str) -> str:
    if path.startswith("profile."):
        return to_plain_text(_get_nested_value(profile, path[len("profile.") :]))
    if path.startswith("preferences."):
        return to_plain_text(_get_nested_value(preferences, path[len("preferences.") :]))
    if path == "resume_md":
        return resume_md
    if path.startswith("qa_bank."):
        return to_plain_text(_get_nested_value(qa_bank, path[len("qa_bank.") :]))
    if path.startswith("jd_analysis."):
        remainder = path[len("jd_analysis.") :]
        current: Any = jd_analysis
        for segment in remainder.split("."):
            if isinstance(current, dict):
                current = current.get(segment, {})
            else:
                current = {}
        return to_plain_text(current)
    return ""


def _match_keywords(field_text: str, keywords: list[str]) -> bool:
    normalized = normalize_whitespace(field_text).lower()
    return any(keyword.lower() in normalized for keyword in keywords)


def _is_sensitive(field_text: str) -> bool:
    return _match_keywords(field_text, SENSITIVE_KEYWORDS)


def _compose_field_text(field: dict[str, Any]) -> str:
    return normalize_whitespace(
        " ".join(
            str(value)
            for value in [field.get("label", ""), field.get("placeholder", ""), field.get("name", ""), field.get("id", ""), field.get("aria_label", ""), field.get("nearby_text", "")]
            if value
        )
    )


def _value_for_rule(rule_key: str, profile: dict[str, Any], preferences: dict[str, Any], resume_md: str, qa_bank: dict[str, Any], jd_analysis: dict[str, Any]) -> str:
    if rule_key == "name_cn":
        return to_plain_text(profile.get("personal", {}).get("name_cn", ""))
    if rule_key == "name_en":
        return to_plain_text(profile.get("personal", {}).get("name_en", ""))
    if rule_key == "email":
        return to_plain_text(profile.get("personal", {}).get("email", ""))
    if rule_key == "phone":
        return to_plain_text(profile.get("personal", {}).get("phone", ""))
    if rule_key == "wechat":
        return to_plain_text(profile.get("personal", {}).get("wechat", ""))
    if rule_key == "gender":
        return to_plain_text(profile.get("personal", {}).get("gender", ""))
    if rule_key == "age":
        age = profile.get("personal", {}).get("age", "")
        return to_plain_text(str(age)) if age else ""
    if rule_key == "birthday":
        return to_plain_text(profile.get("personal", {}).get("birthday", ""))
    if rule_key == "marital_status":
        return to_plain_text(profile.get("personal", {}).get("marital_status", ""))
    if rule_key == "work_start_date":
        return to_plain_text(profile.get("personal", {}).get("work_start_date", ""))
    if rule_key == "work_mode":
        return to_plain_text(profile.get("personal", {}).get("work_mode", ""))
    if rule_key == "hometown":
        return to_plain_text(profile.get("personal", {}).get("hometown", ""))
    if rule_key in {"school", "major", "degree", "graduation_year", "graduation_date", "start_date", "gpa", "rank"}:
        first_edu = (profile.get("education") or [{}])[0] if isinstance(profile.get("education"), list) else {}
        return to_plain_text(first_edu.get(rule_key, profile.get("personal", {}).get(rule_key, "")))
    if rule_key == "current_location":
        return to_plain_text(profile.get("personal", {}).get("location", ""))
    if rule_key == "target_location":
        locations = preferences.get("location_preferences", []) if isinstance(preferences, dict) else []
        if isinstance(locations, list) and locations:
            return to_plain_text(locations[0])
        return ""
    if rule_key in {"skills", "project_experience", "self_introduction", "research_experience", "work_experience", "internship_experience", "why_this_role", "why_this_company", "most_representative_project"}:
        return _resolve_path_value(profile, preferences, resume_md, qa_bank, jd_analysis, f"jd_analysis.tailored_texts.{rule_key}")
    if rule_key == "competition_awards":
        return _resolve_path_value(profile, preferences, resume_md, qa_bank, jd_analysis, "qa_bank.competition_awards_summary")
    if rule_key == "honors_awards":
        return _resolve_path_value(profile, preferences, resume_md, qa_bank, jd_analysis, "qa_bank.honors_awards_summary")
    return ""


def create_fill_plan(fields: list[dict[str, Any]], profile: dict[str, Any], preferences: dict[str, Any], resume_md: str, qa_bank: dict[str, Any], jd_analysis: dict[str, Any], resume_pdf_path: str) -> list[dict[str, Any]]:
    fill_plan: list[dict[str, Any]] = []
    
    # Group radio buttons and checkboxes by name to handle them specially
    radio_groups = {}
    checkbox_groups = {}
    for field in fields:
        field_type = str(field.get("type", "")).lower()
        name = field.get("name", "")
        if name and field_type == "radio":
            if name not in radio_groups:
                radio_groups[name] = []
            radio_groups[name].append(field)
        elif name and field_type == "checkbox":
            if name not in checkbox_groups:
                checkbox_groups[name] = []
            checkbox_groups[name].append(field)
    
    for field in fields:
        field_text = _compose_field_text(field)
        tag = str(field.get("tag", "")).lower()
        field_type = str(field.get("type", "")).lower()
        selector = field.get("selector", "")
        label = field.get("label", "")
        value = ""
        source = ""
        confidence = 0.0
        action = "user_manual"
        reason = "无法可靠匹配，建议人工填写"
        matched_rule_action = None  # Track the suggested action from matched rule

        if _is_sensitive(field_text):
            action = "user_manual"
            reason = "敏感字段，必须人工处理"
        elif tag == "input" and field_type == "file":
            lower_text = field_text.lower()
            if _match_keywords(field_text, ["简历", "resume", "cv"]):
                value = resume_pdf_path
                source = resume_pdf_path
                confidence = 0.99
                action = "auto_fill"
                reason = "简历上传字段"
            elif _match_keywords(field_text, ["作品附件", "证明材料", "附件", "portfolio", "attachment"]):
                action = "user_manual"
                reason = "附件字段未提供文件路径，按策略不自动填"
        elif tag == "input" and field_type == "radio":
            # For radio buttons, check if this is the first one in the group to handle entire group
            name = field.get("name", "")
            if name and radio_groups.get(name, []) and field == radio_groups[name][0]:
                # Only process first radio in group
                # Check what kind of radio group this is based on the options
                option_labels = [f.get("label", "") for f in radio_groups.get(name, [])]
                gender_keywords = ["男", "女", "其他", "保密", "prefer not to say"]
                marital_keywords = ["未婚", "已婚", "离异", "丧偶", "保密", "divorced", "married", "single"]
                
                if any(kw in opt for opt in option_labels for kw in gender_keywords if opt):
                    # This is a gender field
                    gender_val = profile.get("personal", {}).get("gender", "")
                    if gender_val:
                        value = to_plain_text(gender_val)
                        source = "profile.personal.gender"
                        confidence = 0.98
                        action = "auto_fill"
                        reason = "性别字段"
                elif any(kw in opt for opt in option_labels for kw in marital_keywords if opt):
                    # This is a marital status field
                    marital_val = profile.get("personal", {}).get("marital_status", "")
                    if marital_val:
                        value = to_plain_text(marital_val)
                        source = "profile.personal.marital_status"
                        confidence = 0.98
                        action = "auto_fill"
                        reason = "婚姻状况字段"
                else:
                    action = "user_manual"
                    reason = "单选按钮组，需人工确认"
            else:
                # Skip subsequent radio buttons in the group (they'll be handled by form_filler)
                action = "user_manual"
                reason = "单选按钮组的其他选项"
        else:
            for rule_key, keywords, source_path, rule_confidence, suggested_action in FIELD_RULES:
                if _match_keywords(field_text, keywords):
                    value = _value_for_rule(rule_key, profile, preferences, resume_md, qa_bank, jd_analysis)
                    source = source_path
                    confidence = rule_confidence
                    matched_rule_action = suggested_action  # Save it for later use
                    action = suggested_action if tag == "textarea" else ("auto_fill" if rule_confidence >= 0.9 and suggested_action != "review_then_fill" else suggested_action)
                    if tag == "textarea" and action == "auto_fill":
                        action = "review_then_fill"
                    reason = f"匹配关键词: {keywords[0]}"
                    break

        if tag == "textarea" and action == "auto_fill":
            action = "review_then_fill"
        
        # If no value but matched, keep the matched action
        if not value and action != "user_manual" and tag != "textarea":
            if matched_rule_action == "review_then_fill":
                action = "review_then_fill"
                reason = "字段已匹配，但内容需要手工审核"
            else:
                # For auto_fill fields without values, skip them
                action = "user_manual"
                reason = "字段已匹配但无数据"
            confidence = max(0.0, confidence * 0.5)

        if tag == "textarea" and action == "user_manual" and value:
            action = "review_then_fill"

        fill_plan.append(
            {
                "field_id": field.get("field_id", ""),
                "selector": selector,
                "xpath": field.get("xpath", ""),
                "frame_url": field.get("frame_url", ""),
                "field_label": label,
                "field_type": f"{tag}/{field_type}".strip("/") if field_type else tag,
                "role": field.get("role", ""),
                "value": value,
                "source": source,
                "confidence": round(float(confidence), 2),
                "action": action,
                "reason": reason,
            }
        )
    return fill_plan

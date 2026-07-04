from __future__ import annotations

from typing import Any


def build_personal_summary(profile: dict[str, Any]) -> dict[str, Any]:
    personal = profile.get("personal", {}) if isinstance(profile, dict) else {}
    education = profile.get("education", []) if isinstance(profile, dict) else []
    first_edu = education[0] if education else {}

    summary = {
        "name": personal.get("name_cn", ""),
        "name_en": personal.get("name_en", ""),
        "gender": personal.get("gender", ""),
        "age": personal.get("age", ""),
        "school": first_edu.get("school", personal.get("school", "")),
        "degree": first_edu.get("degree", personal.get("degree", "")),
        "major": first_edu.get("major", personal.get("major", "")),
        "graduation_year": first_edu.get("graduation_year", personal.get("graduation_year", "")),
        "graduation_date": first_edu.get("graduation_date", ""),
        "start_date": first_edu.get("start_date", ""),
        "gpa": first_edu.get("gpa", personal.get("gpa", "")),
        "weighted_average": first_edu.get("weighted_average", personal.get("weighted_average", "")),
        "rank": first_edu.get("rank", personal.get("rank", "")),
        "phone": personal.get("phone", ""),
        "email": personal.get("email", ""),
        "location": personal.get("location", ""),
        "hometown": personal.get("hometown", ""),
        "id_number": personal.get("id_number", ""),
        "work_mode": personal.get("work_mode", ""),
    }
    return summary


def build_personal_summary_text(profile: dict[str, Any]) -> str:
    summary = build_personal_summary(profile)
    lines = [
        f"姓名：{summary['name']}",
        f"性别：{summary['gender']}",
        f"年龄：{summary['age']}",
        f"学校：{summary['school']}",
        f"学历：{summary['degree']}",
        f"专业：{summary['major']}",
        f"入学-毕业：{summary['start_date']} - {summary['graduation_date']}",
        f"毕业届别：{summary['graduation_year']}",
        f"GPA：{summary['gpa']}",
        f"加权平均分：{summary['weighted_average']}",
        f"专业排名：{summary['rank']}",
        f"手机：{summary['phone']}",
        f"邮箱：{summary['email']}",
        f"所在地：{summary['location']}",
        f"家乡：{summary['hometown']}",
        f"工作模式：{summary['work_mode']}",
    ]
    return "\n".join(line for line in lines if not line.endswith("："))

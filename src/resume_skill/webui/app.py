"""
Web UI Flask application - API + frontend for RESUME_SKILL v2.4.
"""
from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, send_from_directory, request

from ..config import CONFIG, load_app_config
from ..cli import cmd_extract, cmd_consolidate
from ..agent.utils import load_yaml, save_json

app = Flask(__name__, template_folder="templates")

# ─── 全局状态 ────────────────────────────────────────────
_scout_progress: dict[str, Any] = {"running": False, "log": [], "results": []}
_chrome_instance: Any = None  # Keep Chrome alive across requests


def _ensure_dirs():
    CONFIG.personal_info_dir.mkdir(parents=True, exist_ok=True)
    CONFIG.resume_dir.mkdir(parents=True, exist_ok=True)
    (CONFIG.personal_info_dir / "general_information").mkdir(parents=True, exist_ok=True)


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


@app.route("/api/extract", methods=["POST"])
def api_extract():
    if "file" not in request.files:
        return jsonify({"error": "未上传文件"}), 400
    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "文件名不能为空"}), 400

    _ensure_dirs()
    pdf_path = CONFIG.resume_dir / file.filename
    file.save(str(pdf_path))

    try:
        from ..extractor.extractor import PersonalInfoExtractor

        extractor = PersonalInfoExtractor(personal_info_dir=str(CONFIG.personal_info_dir))
        result = extractor.extract_from_resume_pdf(str(pdf_path))
        return jsonify({"status": "extracted", "data": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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
    _chrome_instance = ChromeDevToolsClient(headless=False)
    try:
        print("[scout] 正在启动 Chrome...")
        _chrome_instance.connect()
        print(f"[scout] Chrome 已启动，正在打开 {len(companies)} 个页面...")
        for i, c in enumerate(companies):
            name = c.get("name", "?")
            url = c.get("url", "")
            if not url:
                continue
            if i == 0:
                _chrome_instance.call_tool("navigate_page", {"url": url})
            else:
                _chrome_instance.call_tool("new_page", {"url": url})
            print(f"[scout] 已打开 {name}: {url}")
        return jsonify({"status": "opened", "count": len(companies)})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"打开 Chrome 失败: {str(e)}"}), 500


# ─── 网申填写 API ─────────────────────────────────────────

@app.route("/api/fill/start", methods=["POST"])
def api_fill_start():
    """Use the already-open Chrome (from scout login) to snapshot current page
    and AI-fill form fields. User should have manually navigated to the app page."""
    global _chrome_instance

    from resume_skill.agent.mcp.agent import MCPAgent
    import tempfile, os

    # Save uploaded resume if provided
    resume_path = ""
    if "resume" in request.files:
        f = request.files["resume"]
        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        f.save(tmp.name)
        resume_path = tmp.name

    chrome = _chrome_instance
    if chrome is None:
        return jsonify({"error": "请先在步骤4中拉起 Chrome 并登录"}), 400

    try:
        snapshot = chrome.call_tool("take_snapshot", {})
        print(f"[fill] Snapshot: {len(str(snapshot))} chars")

        # Parse snapshot to fields using the same logic as agent.py
        agent = MCPAgent.__new__(MCPAgent)
        fields = agent._parse_snapshot(str(snapshot))
        print(f"[fill] Found {len(fields)} form fields")

        # Load MD profile and run LLM Q&A
        md_path = CONFIG.personal_info_dir / "profile_template.md"
        profile_text = md_path.read_text(encoding="utf-8") if md_path.exists() else ""
        if profile_text:
            from ..llm.factory import create_llm_client
            agent.profile = profile_text
            agent.llm = create_llm_client()
            answers = agent._answer_fields(fields)
            print(f"[fill] Got {len(answers)} LLM answers")

            # Merge answers into fields
            answer_map = {a.get("uid", ""): a for a in answers}
            for f in fields:
                uid = f.get("uid", "")
                if uid in answer_map:
                    ans = answer_map[uid]
                    f["answer"] = ans.get("answer", "")
                    f["confidence"] = ans.get("confidence", "low")
                    f["action"] = ans.get("action", "fill")

        if resume_path:
            os.unlink(resume_path)

        return jsonify({"fields": fields, "count": len(fields)})

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ─── 勘探（Scout）API ─────────────────────────────────────

def _scout_worker(profile_text: str, preferences: dict):
    global _chrome_instance, _scout_progress
    _scout_progress["running"] = True
    _scout_progress["log"] = []
    _scout_progress["results"] = []

    def log(msg: str):
        _scout_progress["log"].append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

    chrome = _chrome_instance
    if chrome is None:
        log("错误：请先拉起公司官网进行登录")
        _scout_progress["running"] = False
        return

    from resume_skill.llm.factory import create_llm_client
    llm = create_llm_client()

    def _get_page_ids() -> list[int]:
        try:
            result = chrome.call_tool("list_pages", {})
            text = str(result)
            ids = []
            for line in text.split("\n"):
                if "pageId=" in line:
                    import re
                    m = re.search(r"pageId=(\d+)", line)
                    if m:
                        ids.append(int(m.group(1)))
            return ids
        except:
            return list(range(1, 20))

    def _llm_analyze_jobs(company_name: str, snapshot_text: str) -> list[dict]:
        log(f"[{company_name}] LLM分析中...")
        prompt = f"""你是一个招聘页面分析AI。分析以下招聘页面的无障碍树，完成以下任务：

## 任务
1. 找到页面中的所有职位信息（标题、链接等）
2. 根据用户档案（如下）判断哪些职位可能是该用户感兴趣的

## \u7528\u6237\u6863\u6848
{profile_text[:4000]}

## \u9875\u9762\u65e0\u969c\u788d\u6811
{snapshot_text[:6000]}

\u8fd4\u56de JSON\uff08\u4e0d\u8981\u4ee3\u7801\u5757\uff09：
{{"found_jobs": [{{\u201ctitle\u201d:\u201d\u5c97\u4f4d\u540d\u79f0\u201d}}],
  \u201canalysis\u201d: \u201c\u7b80\u8981\u5206\u6790\u8bf4\u660e\u201d}}"""
        try:
            result = llm.call_json("", prompt)
            if isinstance(result, dict):
                return result.get("found_jobs", [])
        except Exception as e:
            log(f"  LLM\u5206\u6790\u5931\u8d25: {e}")
        return []

    try:
        page_ids = _get_page_ids()
        companies = preferences.get("target_companies", [])
        for i, company in enumerate(companies):
            name = company.get("name", f"公司{i+1}")
            if i >= 3:
                log(f"[{name}] 跳过：最多分析3个公司")
                continue

            log(f"[{name}] 正在分析...")
            try:
                if i > 0 and i < len(page_ids):
                    try:
                        chrome.call_tool("select_page", {"pageId": page_ids[i]})
                        time.sleep(1)
                    except Exception as e:
                        log(f"[{name}] 无法选择标签页: {str(e)[:60]}")

                snapshot = chrome.call_tool("take_snapshot", {})
                log(f"[{name}] 页面已读取")

                found_jobs = _llm_analyze_jobs(name, str(snapshot))
                if found_jobs:
                    log(f"[{name}] 找到 {len(found_jobs)} 个匹配岗位")
                else:
                    log(f"[{name}] 暂无匹配岗位")

                company_results = []
                for j in found_jobs[:5]:
                    title = j.get("title", "未知岗位")
                    link = company.get("url", "")
                    company_results.append({"title": title, "link": link})

                if not company_results:
                    company_results.append({"title": "(暂无匹配岗位)", "link": company.get("url", "")})

                _scout_progress["results"].append({
                    "company": name,
                    "url": company.get("url", ""),
                    "matched_jobs": company_results,
                })
                log(f"[{name}] 完成")
            except Exception as e:
                log(f"[{name}] 出错: {e}")

    except Exception as e:
        log(f"勘探失败: {e}")
    finally:
        _scout_progress["running"] = False
        log("勘探结束")


@app.route("/api/scout/start", methods=["POST"])
def api_scout_start():
    global _scout_progress
    if _scout_progress.get("running"):
        return jsonify({"error": "勘探任务已在运行"}), 400

    md_path = CONFIG.personal_info_dir / "profile_template.md"
    profile_text = md_path.read_text(encoding="utf-8") if md_path.exists() else ""
    prefs = _load_preferences()
    if not prefs.get("target_companies"):
        return jsonify({"error": "请在偏好设置中至少添加一个目标公司"}), 400

    thread = threading.Thread(target=_scout_worker, args=(profile_text, prefs), daemon=True)
    thread.start()
    return jsonify({"status": "started"})


@app.route("/api/scout/debug", methods=["GET"])
def api_scout_debug():
    """Debug endpoint to check scout state."""
    global _chrome_instance, _scout_progress
    return jsonify({
        "chrome_alive": _chrome_instance is not None,
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

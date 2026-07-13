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

    def _open_chrome_background():
        global _chrome_instance
        _chrome_instance = ChromeDevToolsClient(headless=False)
        try:
            _chrome_instance.connect()
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
        # Take snapshot with timeout
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(chrome.call_tool, "take_snapshot", {})
            try:
                snapshot = future.result(timeout=8)
            except concurrent.futures.TimeoutError:
                return jsonify({"error": "页面读取超时，请确认 Chrome 已打开且页面已加载"}), 504

        print(f"[fill] Snapshot: {len(str(snapshot))} chars")

        agent = MCPAgent.__new__(MCPAgent)
        fields = agent._parse_snapshot(str(snapshot))
        print(f"[fill] Found {len(fields)} form fields")

        # Load MD profile and run LLM Q&A (with timeout)
        md_path = CONFIG.personal_info_dir / "profile_template.md"
        profile_text = md_path.read_text(encoding="utf-8") if md_path.exists() else ""
        if profile_text:
            from ..llm.factory import create_llm_client
            agent.profile = profile_text
            agent.llm = create_llm_client()

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(agent._answer_fields, fields)
                try:
                    answers = future.result(timeout=30)
                except concurrent.futures.TimeoutError:
                    answers = []
                    print("[fill] LLM 匹配超时")

            if answers:
                print(f"[fill] Got {len(answers)} LLM answers")
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

@app.route("/api/scout/start", methods=["POST"])
def api_scout_start():
    global _scout_progress, _chrome_instance
    if _scout_progress.get("running"):
        return jsonify({"error": "勘探任务已在运行"}), 400

    md_path = CONFIG.personal_info_dir / "profile_template.md"
    profile_text = md_path.read_text(encoding="utf-8") if md_path.exists() else ""
    prefs = _load_preferences()
    companies = prefs.get("target_companies", [])

    def _full_scout_worker():
        global _chrome_instance, _scout_progress
        _scout_progress["running"] = True
        _scout_progress["log"] = []
        _scout_progress["results"] = []

        def log(msg):
            _scout_progress["log"].append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

        # 复用已有 Chrome 或新建
        if _chrome_instance is None:
            log("正在启动 Chrome...")
            from resume_skill.agent.mcp.chrome_client import ChromeDevToolsClient
            _chrome_instance = ChromeDevToolsClient(headless=False)
            try:
                _chrome_instance.connect()
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
                        title = _chrome_instance.call_tool("evaluate_script", {"script": "document.title"})
                        page_title = str(title)[:60] if title else name
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

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

    def _open_all():
        from .mcp.chrome_client import ChromeDevToolsClient
        chrome = ChromeDevToolsClient(headless=False)
        try:
            chrome.connect()
            for c in companies:
                name = c.get("name", "?")
                url = c.get("url", "")
                if url:
                    chrome.call_tool("navigate_page", {"url": url})
            print(f"[scout] 已打开 {len(companies)} 个公司页面，等待用户登录")
        except Exception as e:
            print(f"[scout] 打开页面失败: {e}")

    thread = threading.Thread(target=_open_all, daemon=True)
    thread.start()
    return jsonify({"status": "opened", "count": len(companies)})


# ─── 勘探（Scout）API ─────────────────────────────────────

def _scout_worker(profile: dict, preferences: dict):
    global _scout_progress
    _scout_progress["running"] = True
    _scout_progress["log"] = []
    _scout_progress["results"] = []

    def log(msg: str):
        _scout_progress["log"].append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

    from .mcp.chrome_client import ChromeDevToolsClient
    chrome = ChromeDevToolsClient(headless=False)

    try:
        chrome.connect()
        log("Chrome 已启动")

        companies = preferences.get("target_companies", [])
        for i, company in enumerate(companies):
            name = company.get("name", f"公司{i+1}")
            url = company.get("url", "")
            if not url:
                log(f"[{name}] 跳过：无 URL")
                continue

            log(f"[{name}] 正在打开 {url}...")
            try:
                chrome.call_tool("navigate_page", {"url": url})
                time.sleep(2)

                snapshot = chrome.call_tool("take_snapshot", {})
                log(f"[{name}] 页面无障碍树已获取")

                # TODO: LLM 分析 + 搜索职位 + 匹配简历
                # 当前版本：输出占位结果
                _scout_progress["results"].append({
                    "company": name,
                    "url": url,
                    "matched_jobs": [
                        {"title": "示例岗位 (搜索功能开发中)", "link": url}
                    ],
                })
                log(f"[{name}] 完成")
            except Exception as e:
                log(f"[{name}] 出错: {e}")

    except Exception as e:
        log(f"勘探失败: {e}")
    finally:
        try:
            chrome.close()
        except Exception:
            pass
        _scout_progress["running"] = False
        log("勘探结束")


@app.route("/api/scout/start", methods=["POST"])
def api_scout_start():
    global _scout_progress
    if _scout_progress.get("running"):
        return jsonify({"error": "勘探任务已在运行"}), 400

    profile = load_yaml(CONFIG.unified_profile_path) or {}
    prefs = _load_preferences()
    if not prefs.get("target_companies"):
        return jsonify({"error": "请在偏好设置中至少添加一个目标公司"}), 400

    thread = threading.Thread(target=_scout_worker, args=(profile, prefs), daemon=True)
    thread.start()
    return jsonify({"status": "started"})


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
        from .mcp.agent import run_agent
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

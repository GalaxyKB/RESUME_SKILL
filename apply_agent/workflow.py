from __future__ import annotations

import argparse
import json
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rich.table import Table

from .browser_agent import BrowserAgent
from .config import CONFIG, DATA_DIR, OUTPUTS_DIR, RECORDS_DIR, PROJECT_ROOT
from .form_extractor import extract_form_fields
from .form_filler import fill_form
from .form_mapper import create_fill_plan
from .jd_analyzer import analyze_and_tailor
from .llm_client import LLMClient
from .profile_summary import build_personal_summary, build_personal_summary_text
from .recorder import append_application, init_records
from .storage import ensure_dirs, load_text, load_yaml, save_json
from .utils import clip_text, console, normalize_whitespace, print_section, safe_filename, timestamp, to_plain_text


@dataclass(frozen=True)
class RunOptions:
    interactive: bool = True
    continue_after_analysis: bool = False
    auto_fill: bool = False
    auto_submit: bool = False
    wait_for_login: bool = True
    session_profile_dir: str = str(PROJECT_ROOT / ".session" / "chrome")
    cdp_endpoint: str = ""
    reuse_existing_tab: bool = False
    use_current_page: bool = False
    keep_browser_open: bool = False
    browser_channel: str = "chrome"
    browser_executable_path: str = ""
    manual_login_first: bool = False
    signal_mode: bool = False
    start_signal: str = "OPEN_READY"
    fill_signal: str = "FILL_NOW"
    next_page_signal: str = "NEXT_PAGE"
    done_signal: str = "DONE"
    max_fill_rounds: int = 3
    form_only: bool = False
    login_only: bool = False
    fill_only: bool = False


def _load_local_files() -> tuple[dict[str, Any], dict[str, Any], str, dict[str, Any]]:
    profile = load_yaml(DATA_DIR / "profile.yaml")
    preferences = load_yaml(DATA_DIR / "preferences.yaml")
    resume_md = load_text(DATA_DIR / "resume.md")
    qa_bank = load_yaml(DATA_DIR / "qa_bank.yaml")
    return profile if isinstance(profile, dict) else {}, preferences if isinstance(preferences, dict) else {}, resume_md, qa_bank if isinstance(qa_bank, dict) else {}


def _print_local_context(profile: dict[str, Any], preferences: dict[str, Any], resume_md: str) -> None:
    from rich.table import Table

    personal = profile.get("personal", {})
    education = profile.get("education", [])
    first_edu = education[0] if education else {}

    profile_table = Table(title="用户基本信息", show_header=False, box=None)
    for label, value in [
        ("姓名", personal.get("name_cn", "")),
        ("学校", first_edu.get("school", personal.get("school", ""))),
        ("学历", first_edu.get("degree", personal.get("degree", ""))),
        ("专业", first_edu.get("major", personal.get("major", ""))),
        ("GPA", first_edu.get("gpa", personal.get("gpa", ""))),
        ("专业排名", first_edu.get("rank", personal.get("rank", ""))),
    ]:
        profile_table.add_row(label, to_plain_text(value))

    preference_table = Table(title="目标岗位偏好", show_header=False, box=None)
    for label, value in [
        ("目标岗位", preferences.get("target_roles", [])),
        ("目标方向", preferences.get("preferred_domains", [])),
        ("目标城市", preferences.get("location_preferences", [])),
    ]:
        preference_table.add_row(label, to_plain_text(value))

    resume_table = Table(title="简历摘要", show_header=False, box=None)
    resume_table.add_row("简历文本长度", str(len(resume_md)))
    resume_table.add_row("预览", clip_text(normalize_whitespace(resume_md), 200))

    summary_table = Table(title="统一个人信息摘要", show_header=False, box=None)
    personal_summary = build_personal_summary(profile)
    for label, value in [
        ("姓名", personal_summary.get("name", "")),
        ("年龄", personal_summary.get("age", "")),
        ("学校", personal_summary.get("school", "")),
        ("学历", personal_summary.get("degree", "")),
        ("专业", personal_summary.get("major", "")),
        ("入学-毕业", f"{personal_summary.get('start_date', '')} - {personal_summary.get('graduation_date', '')}"),
        ("毕业届别", personal_summary.get("graduation_year", "")),
        ("所在地", personal_summary.get("location", "")),
        ("家乡", personal_summary.get("hometown", "")),
        ("工作模式", personal_summary.get("work_mode", "")),
    ]:
        summary_table.add_row(label, to_plain_text(value))

    print_section("本地资料检查")
    console.print(profile_table)
    console.print(preference_table)
    console.print(resume_table)
    console.print(summary_table)


def _ensure_resume_pdf() -> str:
    """Find resume PDF with priority:
    1. personal_info/formal_resume/ (user's formal resume)
    2. data/resume.pdf (default location)
    3. project root resume.pdf
    4. any PDF in project root
    """
    # Priority 1: Check personal_info/formal_resume/ folder
    formal_resume_dir = PROJECT_ROOT / "personal_info" / "formal_resume"
    if formal_resume_dir.exists():
        pdf_files_in_formal = sorted(formal_resume_dir.glob("*.pdf"))
        if pdf_files_in_formal:
            # Prefer Chinese-named PDFs (likely user-named resume)
            chinese_pdfs = [p for p in pdf_files_in_formal if any(ord(c) > 0x4E00 for c in p.stem)]
            if chinese_pdfs:
                selected = max(chinese_pdfs, key=lambda p: len(p.stem))
                print(f"✅ Found resume in personal_info/formal_resume/: {selected.name}")
                return str(selected)
            # Otherwise use first PDF found
            selected = pdf_files_in_formal[0]
            print(f"✅ Found resume in personal_info/formal_resume/: {selected.name}")
            return str(selected)
    
    # Priority 2: Check standard locations
    candidates = [
        PROJECT_ROOT / "data" / "resume.pdf",
        PROJECT_ROOT / "resume.pdf",
    ]
    for candidate in candidates:
        if candidate.exists():
            print(f"✅ Found resume at: {candidate}")
            return str(candidate)
    
    # Priority 3: Look for any PDF in project root
    pdf_files = sorted(PROJECT_ROOT.glob("*.pdf"))
    if pdf_files:
        # Prefer PDFs with Chinese names (likely user-named resume)
        chinese_pdfs = [p for p in pdf_files if any(ord(c) > 0x4E00 for c in p.stem)]
        if chinese_pdfs:
            selected = max(chinese_pdfs, key=lambda p: len(p.stem))
            print(f"✅ Found resume in project root: {selected.name}")
            return str(selected)
        # Otherwise use first PDF found
        selected = pdf_files[0]
        print(f"✅ Found resume in project root: {selected.name}")
        return str(selected)
    
    # Fallback: return default path (will likely fail, but indicates user needs to add resume)
    default_path = PROJECT_ROOT / "data" / "resume.pdf"
    print(f"⚠️ Warning: No resume PDF found. Expected one of:")
    print(f"   - {formal_resume_dir}/*.pdf (recommended)")
    print(f"   - {PROJECT_ROOT / 'resume.pdf'}")
    print(f"   - {PROJECT_ROOT / 'data' / 'resume.pdf'}")
    return str(default_path)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _log_error(stage: str, error: BaseException) -> Path:
    error_dir = OUTPUTS_DIR / "logs"
    error_dir.mkdir(parents=True, exist_ok=True)
    error_path = error_dir / f"{timestamp()}_{safe_filename(stage)}.log"
    error_path.write_text(traceback.format_exc(), encoding="utf-8")
    return error_path


def _print_analysis_summary(analysis: dict[str, Any]) -> None:
    try:
        match_score = float(analysis.get("match_score", 0.0) or 0.0)
    except Exception:
        match_score = 0.0
    table = Table(title="岗位分析摘要", show_header=False, box=None)
    table.add_row("公司", to_plain_text(analysis.get("company", "")))
    table.add_row("岗位", to_plain_text(analysis.get("position", "")))
    table.add_row("匹配度", f"{match_score:.2f}")
    table.add_row("推荐突出经历", to_plain_text(analysis.get("matched_experiences", [])))
    table.add_row("风险", to_plain_text(analysis.get("risks", [])))
    table.add_row("100字自我介绍", clip_text(to_plain_text(analysis.get("tailored_texts", {}).get("self_introduction_100", "")), 120))
    table.add_row("项目经历短版", clip_text(to_plain_text(analysis.get("tailored_texts", {}).get("project_experience_short", "")), 120))
    console.print(table)


def _print_fill_plan_summary(fill_plan: list[dict[str, Any]]) -> None:
    table = Table(title="Fill Plan 摘要", show_header=True, box=None)
    table.add_column("field_label")
    table.add_column("action")
    table.add_column("value 前 80 字")
    table.add_column("confidence")
    table.add_column("reason")
    for item in fill_plan:
        table.add_row(
            to_plain_text(item.get("field_label", "")),
            to_plain_text(item.get("action", "")),
            clip_text(normalize_whitespace(to_plain_text(item.get("value", ""))), 80),
            f"{float(item.get('confidence', 0.0)):.2f}",
            clip_text(to_plain_text(item.get("reason", "")), 60),
        )
    console.print(table)


def _prompt_yes_no(message: str) -> bool:
    answer = input(message).strip().lower()
    return answer in {"y", "yes", "是"}


def _prompt_confirm_submit() -> bool:
    answer = input("如果确认提交，请输入 CONFIRM_SUBMIT；否则直接回车跳过提交：").strip()
    return answer == "CONFIRM_SUBMIT"


def _wait_for_signal(expected: str, message: str) -> None:
    while True:
        answer = input(message).strip()
        if answer == expected:
            return
        print(f"信号不匹配，请输入 {expected} 继续。")


def _extract_fields_with_retry(browser: BrowserAgent, max_attempts: int = 8, wait_ms: int = 1200) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []
    for _ in range(max_attempts):
        fields = extract_form_fields(browser.page)
        if fields:
            return fields
        try:
            browser.page.wait_for_timeout(wait_ms)
        except Exception:
            break
    return fields


def _fallback_probe_fields(browser: BrowserAgent) -> list[dict[str, Any]]:
        try:
                items = browser.page.evaluate(
                        """
                        () => {
                            const nodes = Array.from(document.querySelectorAll('input, textarea, select, [role="textbox"], [role="combobox"], [contenteditable="true"], button'));
                            return nodes.slice(0, 80).map((el, idx) => ({
                                field_id: `fallback_${idx + 1}`,
                                selector: el.id ? `#${el.id}` : '',
                                xpath: '',
                                tag: (el.tagName || '').toLowerCase(),
                                type: (el.getAttribute('type') || '').toLowerCase(),
                                role: (el.getAttribute('role') || '').toLowerCase(),
                                label: (el.getAttribute('aria-label') || '').trim(),
                                placeholder: (el.getAttribute('placeholder') || '').trim(),
                                name: (el.getAttribute('name') || '').trim(),
                                id: (el.getAttribute('id') || '').trim(),
                                aria_label: (el.getAttribute('aria-label') || '').trim(),
                                nearby_text: ((el.closest('div, li, section, article') || el.parentElement || el).innerText || '').slice(0, 200),
                                options: [],
                                frame_url: window.location.href,
                            }));
                        }
                        """
                )
                return items if isinstance(items, list) else []
        except Exception:
                return []


def _print_runtime_mode(options: RunOptions) -> None:
    table = Table(title="运行模式", show_header=False, box=None)
    table.add_row("interactive", str(options.interactive))
    table.add_row("continue_after_analysis", str(options.continue_after_analysis))
    table.add_row("auto_fill", str(options.auto_fill))
    table.add_row("auto_submit", str(options.auto_submit))
    table.add_row("wait_for_login", str(options.wait_for_login))
    table.add_row("session_profile_dir", options.session_profile_dir)
    table.add_row("cdp_endpoint", options.cdp_endpoint or "(none)")
    table.add_row("reuse_existing_tab", str(options.reuse_existing_tab))
    table.add_row("use_current_page", str(options.use_current_page))
    table.add_row("keep_browser_open", str(options.keep_browser_open))
    table.add_row("browser_channel", options.browser_channel)
    table.add_row("browser_executable_path", options.browser_executable_path or "(none)")
    table.add_row("manual_login_first", str(options.manual_login_first))
    table.add_row("signal_mode", str(options.signal_mode))
    if options.signal_mode:
        table.add_row("start_signal", options.start_signal)
        table.add_row("fill_signal", options.fill_signal)
        table.add_row("next_page_signal", options.next_page_signal)
        table.add_row("done_signal", options.done_signal)
        table.add_row("max_fill_rounds", str(options.max_fill_rounds))
    table.add_row("form_only", str(options.form_only))
    console.print(table)


def _build_form_only_analysis(profile: dict[str, Any], resume_md: str, page_text: str) -> dict[str, Any]:
    personal = profile.get("personal", {}) if isinstance(profile, dict) else {}
    intro = to_plain_text(personal.get("profile_summary", "")) or clip_text(normalize_whitespace(resume_md), 280)
    return {
        "company": "",
        "position": "表单直填模式",
        "match_score": 0.0,
        "keywords": [],
        "core_requirements": [],
        "matched_experiences": [],
        "risks": ["已启用表单直填模式，跳过岗位分析"],
        "job_summary": clip_text(normalize_whitespace(page_text), 200),
        "resume_strategy": "优先完成基础资料填写",
        "tailored_texts": {
            "self_introduction_100": clip_text(intro, 120),
            "self_introduction_300": clip_text(intro, 320),
            "project_experience_short": "",
            "project_experience_long": "",
            "skills_summary": "",
            "research_experience": "",
            "why_this_role": "",
            "why_this_company": "",
            "most_representative_project": "",
        },
    }


def run_apply_flow(url: str, options: RunOptions | None = None) -> int:
    run_options = options or RunOptions()
    ensure_dirs()
    init_records()
    
    # ===== LOGIN_ONLY 模式：纯登录 =====
    if run_options.login_only:
        print_section("登录模式：拉起浏览器进行手动登录")
        browser = BrowserAgent(
            session_profile_dir=run_options.session_profile_dir,
            cdp_endpoint=run_options.cdp_endpoint,
            reuse_existing_tab=run_options.reuse_existing_tab,
            keep_browser_open=True,  # 保持浏览器打开让用户登录
            browser_channel=run_options.browser_channel,
            browser_executable_path=run_options.browser_executable_path,
        )
        try:
            browser.start()
            browser.open_url(url)
            console.print("[bold cyan]📌 浏览器已打开，请在浏览器中完成以下步骤：[/]")
            console.print("[yellow]1. 输入账号密码[/]")
            console.print("[yellow]2. 完成所有验证（如验证码、二次验证等）[/]")
            console.print("[yellow]3. 登录成功后停留在目标页面[/]")
            console.print("[bold green]✅ 完成上述所有步骤后，按 Enter 键继续...[/]")
            browser.wait_for_user_ready("按 Enter 继续: ")
            console.print("[bold green]✅ 登录成功！登录状态已保存到本地会话。[/]")
            console.print(f"[bold cyan]会话保存路径：{run_options.session_profile_dir}[/]")
            console.print("[bold cyan]下一步可以运行 --fill-only 模式自动填写表单。[/]")
            return 0
        except Exception as error:
            log_path = _log_error("login_phase", error)
            console.print(f"[bold red]❌ 登录阶段失败，错误已写入 {log_path}[/]")
            return 1
        finally:
            browser.close()
    
    # ===== FILL_ONLY 模式：纯填写 =====
    if run_options.fill_only:
        print_section("填写模式：使用已保存登录态进行自动填写")
        console.print(f"[bold cyan]📌 正在加载已保存的登录状态：{run_options.session_profile_dir}[/]")
        run_options = RunOptions(
            **{**run_options.__dict__, 'continue_after_analysis': True, 'auto_fill': True, 'form_only': True}
        )
    
    # ===== 常规模式（分析+填写）=====
    profile, preferences, resume_md, qa_bank = _load_local_files()
    if not run_options.fill_only:
        _print_local_context(profile, preferences, resume_md)
    _print_runtime_mode(run_options)

    browser = BrowserAgent(
        session_profile_dir=run_options.session_profile_dir,
        cdp_endpoint=run_options.cdp_endpoint,
        reuse_existing_tab=run_options.reuse_existing_tab,
        keep_browser_open=run_options.keep_browser_open,
        browser_channel=run_options.browser_channel,
        browser_executable_path=run_options.browser_executable_path,
    )
    ts = timestamp()
    raw_page_text = ""
    jd_analysis: dict[str, Any] = {}
    fill_plan: list[dict[str, Any]] = []
    fields: list[dict[str, Any]] = []
    jd_analysis_path = OUTPUTS_DIR / "jd_analysis" / f"{ts}_jd_analysis.json"
    tailored_texts_path = OUTPUTS_DIR / "tailored_texts" / f"{ts}_tailored_texts.json"
    raw_page_path = OUTPUTS_DIR / "jd_analysis" / f"{ts}_raw_page.txt"
    fields_path = OUTPUTS_DIR / "fill_plans" / f"{ts}_fields.json"
    fill_plan_path = OUTPUTS_DIR / "fill_plans" / f"{ts}_fill_plan.json"
    status = "analysis_only"
    company = ""
    position = ""
    notes = ""
    match_score: float = 0.0
    try:
        browser.start()
        if not run_options.use_current_page:
            browser.open_url(url)
        if run_options.manual_login_first:
            if run_options.signal_mode:
                _wait_for_signal(
                    run_options.start_signal,
                    f"请先完成登录并停留在目标页面，输入 {run_options.start_signal} 后继续：",
                )
            else:
                browser.wait_for_user_ready("请先在新打开的浏览器中完成登录并停留在目标页面，完成后按 Enter 继续")
        try:
            browser.save_screenshot("job_page_initial")
        except Exception:
            print("截图失败：页面可能被关闭，已跳过截图并继续流程。")
        raw_page_text = browser.get_page_text()
        _write_text(raw_page_path, raw_page_text)
        if not raw_page_text.strip():
            print("页面正文为空，可能需要登录或页面动态加载失败。")
        print_section("页面正文预览")
        print(clip_text(raw_page_text, 1000))

        if run_options.form_only:
            jd_analysis = _build_form_only_analysis(profile, resume_md, raw_page_text)
        else:
            jd_analysis = analyze_and_tailor(raw_page_text, profile, preferences, resume_md)
        company = to_plain_text(jd_analysis.get("company", ""))
        position = to_plain_text(jd_analysis.get("position", ""))
        match_score = float(jd_analysis.get("match_score", 0.0) or 0.0)
        save_json(jd_analysis_path, jd_analysis)
        save_json(tailored_texts_path, jd_analysis.get("tailored_texts", {}))
        _print_analysis_summary(jd_analysis)

        should_continue = run_options.continue_after_analysis
        if run_options.interactive:
            should_continue = _prompt_yes_no("是否继续进入申请流程？y/n: ")
        if not should_continue:
            notes = "用户停止在分析阶段"
            return 0

        clicked = browser.click_apply_button()
        if not clicked:
            print("未能自动定位申请按钮，请手动进入申请表单页面。")
        if run_options.wait_for_login:
            browser.wait_for_user_ready("请完成登录并进入申请表单页面，完成后按 Enter")

        round_index = 1
        while True:
            current_fields_path = OUTPUTS_DIR / "fill_plans" / f"{ts}_fields_r{round_index}.json"
            current_fill_plan_path = OUTPUTS_DIR / "fill_plans" / f"{ts}_fill_plan_r{round_index}.json"
            fields = _extract_fields_with_retry(browser)
            if not fields:
                print("未提取到可填写字段：该页面可能尚未完成动态渲染，或使用了当前规则未覆盖的自定义控件。")
                fallback_fields = _fallback_probe_fields(browser)
                if fallback_fields:
                    print(f"已启用 fallback 抽取，捕获到 {len(fallback_fields)} 个候选控件。")
                    fields = fallback_fields
            save_json(current_fields_path, fields)
            fill_plan = create_fill_plan(fields, profile, preferences, resume_md, qa_bank, jd_analysis, _ensure_resume_pdf())
            save_json(current_fill_plan_path, fill_plan)
            fields_path = current_fields_path
            fill_plan_path = current_fill_plan_path
            _print_fill_plan_summary(fill_plan)

            should_fill = run_options.auto_fill
            if run_options.interactive:
                if run_options.signal_mode:
                    _wait_for_signal(
                        run_options.fill_signal,
                        f"如果确认开始填写，请输入 {run_options.fill_signal}：",
                    )
                    should_fill = True
                else:
                    should_fill = _prompt_yes_no("是否开始自动填写？y/n: ")

            if should_fill:
                fill_result = fill_form(browser.page, fill_plan, resume_path=_ensure_resume_pdf(), allow_review_then_fill=True)
                print(f"filled: {len(fill_result.get('filled', []))}")
                print(f"skipped: {len(fill_result.get('skipped', []))}")
                print(f"failed: {len(fill_result.get('failed', []))}")
                print("请在浏览器中检查页面填写结果。")
                status = "filled"
            else:
                status = "manual_review"
                break

            if not run_options.interactive or not run_options.signal_mode:
                break

            if round_index >= max(1, int(run_options.max_fill_rounds)):
                print("已达到最大填写轮次，停止继续跳转填写。")
                break

            action = input(
                f"如需跳转到下一页继续填写请输入 {run_options.next_page_signal}；完成则输入 {run_options.done_signal}："
            ).strip()
            if action == run_options.next_page_signal:
                round_index += 1
                continue
            if action == run_options.done_signal:
                break
            print("未识别的信号，默认结束本次填写流程。")
            break

        should_submit = run_options.auto_submit
        if run_options.interactive:
            should_submit = _prompt_confirm_submit()
        if should_submit:
            if browser.click_submit_button():
                status = "submitted"
            else:
                status = "manual_review"
                print("未能自动点击提交按钮，请手动完成最终提交。")

        notes = "流程已执行到表单阶段"
        return 0
    except Exception as error:
        log_path = _log_error("apply_flow", error)
        print(f"运行失败，错误已写入 {log_path}")
        raise
    finally:
        append_application(
            {
                "date": ts,
                "company": company,
                "position": position,
                "url": url,
                "status": status,
                "match_score": match_score,
                "notes": notes,
                "fill_plan_path": str(fill_plan_path) if fill_plan else str(fields_path) if fields else "",
                "jd_analysis_path": str(jd_analysis_path),
            }
        )
        browser.close()


def run_doctor() -> int:
    print_section("ApplyAgent Doctor")
    masked_key = f"***{CONFIG.deepseek_api_key[-4:]}" if CONFIG.deepseek_api_key else "(empty)"
    table = Table(title="模型配置检查", show_header=False, box=None)
    table.add_row("DEEPSEEK_BASE_URL", CONFIG.deepseek_base_url)
    table.add_row("DEEPSEEK_MODEL", CONFIG.deepseek_model)
    table.add_row("DEEPSEEK_API_KEY", masked_key)
    console.print(table)

    if not CONFIG.deepseek_api_key:
        print("未检测到 DEEPSEEK_API_KEY，请先配置 .env")
        return 1

    client = LLMClient()
    try:
        output = client.call_text(
            "你是系统健康检查助手。只返回 OK。",
            "请输出 OK",
        )
    except Exception as exc:
        print(f"模型连通性失败: {exc}")
        return 2

    print(f"模型连通性成功，返回: {clip_text(normalize_whitespace(output), 80)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ApplyAgent v0.1")
    subparsers = parser.add_subparsers(dest="command")

    apply_parser = subparsers.add_parser("apply", help="Run the full ApplyAgent flow")
    apply_parser.add_argument("--url", default="", help="岗位详情页 URL")
    apply_parser.add_argument("--non-interactive", action="store_true", help="无交互模式，按参数自动执行")
    apply_parser.add_argument("--continue-after-analysis", action="store_true", help="分析完成后自动进入申请流程")
    apply_parser.add_argument("--auto-fill", action="store_true", help="自动执行表单填写")
    apply_parser.add_argument("--auto-submit", action="store_true", help="自动尝试点击提交")
    apply_parser.add_argument("--skip-login-wait", action="store_true", help="跳过登录等待步骤")
    apply_parser.add_argument("--session-dir", default=str(PROJECT_ROOT / ".session" / "chrome"), help="浏览器持久化会话目录（默认复用登录态）")
    apply_parser.add_argument("--cdp-endpoint", default="", help="连接已打开浏览器的 CDP 地址，如 http://127.0.0.1:9222")
    apply_parser.add_argument("--reuse-existing-tab", action="store_true", help="优先复用已打开标签页（配合 --cdp-endpoint）")
    apply_parser.add_argument("--use-current-page", action="store_true", help="不跳转 URL，直接在当前页面继续执行")
    apply_parser.add_argument("--keep-browser-open", action="store_true", help="流程结束后保持浏览器不关闭")
    apply_parser.add_argument("--browser-channel", default="chrome", help="浏览器通道：chromium / chrome / msedge")
    apply_parser.add_argument("--browser-executable-path", default="", help="指定浏览器可执行文件路径")
    apply_parser.add_argument("--manual-login-first", action="store_true", help="先打开页面并等待手动登录，回车后再继续执行")
    apply_parser.add_argument("--signal-mode", action="store_true", help="启用双信号流程控制")
    apply_parser.add_argument("--start-signal", default="OPEN_READY", help="拉起后开始信号")
    apply_parser.add_argument("--fill-signal", default="FILL_NOW", help="开始填写信号")
    apply_parser.add_argument("--next-page-signal", default="NEXT_PAGE", help="跳转后继续填写信号")
    apply_parser.add_argument("--done-signal", default="DONE", help="完成信号")
    apply_parser.add_argument("--max-fill-rounds", type=int, default=3, help="最多连续填写轮次")
    apply_parser.add_argument("--form-only", action="store_true", help="表单直填模式：跳过岗位分析，直接填写")
    apply_parser.add_argument("--login-only", action="store_true", help="仅登录模式：打开浏览器→用户手动登录→保存登录态→退出")
    apply_parser.add_argument("--fill-only", action="store_true", help="仅填写模式：使用已保存登录态→直接提取表单→自动填写")

    subparsers.add_parser("doctor", help="检查 DS 接口配置与连通性")

    return parser


def interactive_mode() -> int:
    print_section("ApplyAgent v0.1")
    url = input("请输入岗位详情页 URL: ").strip()
    if not url:
        return 0
    return run_apply_flow(url)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "apply":
        url = args.url.strip() or input("请输入岗位详情页 URL: ").strip()
        if not url:
            print("未提供 URL，已退出。")
            return 0
        options = RunOptions(
            interactive=not bool(args.non_interactive),
            continue_after_analysis=bool(args.continue_after_analysis),
            auto_fill=bool(args.auto_fill),
            auto_submit=bool(args.auto_submit),
            wait_for_login=not bool(args.skip_login_wait),
            session_profile_dir=str(args.session_dir or "").strip(),
            cdp_endpoint=str(args.cdp_endpoint or "").strip(),
            reuse_existing_tab=bool(args.reuse_existing_tab),
            use_current_page=bool(args.use_current_page),
            keep_browser_open=bool(args.keep_browser_open),
            browser_channel=str(args.browser_channel or "chrome").strip(),
            browser_executable_path=str(args.browser_executable_path or "").strip(),
            manual_login_first=bool(args.manual_login_first),
            signal_mode=bool(args.signal_mode),
            start_signal=str(args.start_signal or "OPEN_READY").strip() or "OPEN_READY",
            fill_signal=str(args.fill_signal or "FILL_NOW").strip() or "FILL_NOW",
            next_page_signal=str(args.next_page_signal or "NEXT_PAGE").strip() or "NEXT_PAGE",
            done_signal=str(args.done_signal or "DONE").strip() or "DONE",
            max_fill_rounds=max(1, int(args.max_fill_rounds or 3)),
            form_only=bool(args.form_only),
            login_only=bool(args.login_only),
            fill_only=bool(args.fill_only),
        )
        return run_apply_flow(url, options=options)
    if args.command == "doctor":
        return run_doctor()
    if args.command is None:
        return interactive_mode()
    return 0

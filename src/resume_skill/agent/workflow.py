"""
Main workflow orchestrator for the apply flow.

Coordinates browser, extraction, matching, JD analysis, and filling.
"""

from __future__ import annotations

import argparse
import json
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rich.table import Table

from ..config import CONFIG
from ..llm.factory import create_llm_client
from .browser_agent import BrowserAgent
from .field_matcher import match_fields_with_llm, match_fields_rule_based
from .form_extractor import extract_form_fields
from .form_filler import fill_form
from .jd_analyzer import analyze_and_tailor
from .utils import (
    append_application,
    clip_text,
    console,
    ensure_dirs,
    find_resume_pdf,
    init_records,
    load_yaml,
    normalize_whitespace,
    print_section,
    save_json,
    timestamp,
    to_plain_text,
)


@dataclass(frozen=True)
class RunOptions:
    interactive: bool = True
    continue_after_analysis: bool = False
    auto_fill: bool = False
    auto_submit: bool = False
    wait_for_login: bool = True
    session_profile_dir: str = ""
    cdp_endpoint: str = ""
    reuse_existing_tab: bool = False
    use_current_page: bool = False
    keep_browser_open: bool = False
    browser_channel: str = ""
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
    headless: bool = False
    slow_motion: int = 300


def _load_profile() -> dict[str, Any]:
    profile_path = CONFIG.unified_profile_path
    if profile_path.exists():
        return load_yaml(profile_path) or {}
    
    print(f"❌ Profile not found at {profile_path}")
    print("💡 Please run: resume-skill consolidate")
    return {}


def _print_profile_summary(profile: dict[str, Any]) -> None:
    personal = profile.get("personal", {})
    education = profile.get("education", [])
    first_edu = education[0] if education else {}

    table = Table(title="User Profile Summary", show_header=False, box=None)
    table.add_row("Name", to_plain_text(personal.get("name_cn", "")))
    table.add_row("Email", to_plain_text(personal.get("email", "")))
    table.add_row("Phone", to_plain_text(personal.get("phone", "")))
    table.add_row("School", to_plain_text(first_edu.get("school", "")))
    table.add_row("Degree", to_plain_text(first_edu.get("degree", "")))
    table.add_row("Major", to_plain_text(first_edu.get("major", "")))
    console.print(table)


def _print_fill_plan_summary(fill_plan: list[dict[str, Any]]) -> None:
    table = Table(title="Fill Plan Summary", show_header=True, box=None)
    table.add_column("Field")
    table.add_column("Strategy")
    table.add_column("Action")
    table.add_column("Value (first 60 chars)")
    table.add_column("Conf")
    for item in fill_plan:
        table.add_row(
            to_plain_text(item.get("field_label", "")),
            to_plain_text(item.get("fill_strategy", "")),
            to_plain_text(item.get("action", "")),
            clip_text(normalize_whitespace(to_plain_text(item.get("value", ""))), 60),
            f"{float(item.get('confidence', 0.0)):.2f}",
        )
    console.print(table)


def _prompt_yes_no(message: str) -> bool:
    return input(message).strip().lower() in {"y", "yes", ""}


def _wait_for_signal(expected: str, message: str) -> None:
    while True:
        answer = input(message).strip()
        if answer == expected:
            return
        print(f"Signal mismatch. Enter {expected} to continue.")


def _extract_fields_with_retry(browser: BrowserAgent, profile: dict[str, Any], llm_client: Any, max_attempts: int = 8, wait_ms: int = 1200) -> list[dict[str, Any]]:
    for attempt in range(max_attempts):
        fields = extract_form_fields(browser.page, profile, llm_client)
        if fields:
            return fields
        try:
            browser.page.wait_for_timeout(wait_ms)
        except Exception:
            break
    return []


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _log_error(stage: str, error: BaseException) -> Path:
    from .utils import safe_filename
    error_dir = CONFIG.outputs_dir / "logs"
    error_dir.mkdir(parents=True, exist_ok=True)
    error_path = error_dir / f"{timestamp()}_{safe_filename(stage)}.log"
    error_path.write_text(traceback.format_exc(), encoding="utf-8")
    return error_path


def run_apply_flow(url: str, options: RunOptions | None = None) -> int:
    run_options = options or RunOptions()
    ensure_dirs()
    init_records()

    if run_options.session_profile_dir:
        session_dir = run_options.session_profile_dir
    else:
        session_dir = str(CONFIG.session_dir)

    if run_options.login_only:
        print_section("Login Mode")
        browser = BrowserAgent(
            session_profile_dir=session_dir,
            cdp_endpoint=run_options.cdp_endpoint,
            reuse_existing_tab=run_options.reuse_existing_tab,
            keep_browser_open=True,
            browser_channel=run_options.browser_channel,
            browser_executable_path=run_options.browser_executable_path,
            headless=run_options.headless,
            slow_motion=run_options.slow_motion,
        )
        try:
            browser.start()
            browser.open_url(url)
            console.print("[bold cyan]Browser opened. Please complete login in the browser.[/]")
            browser.wait_for_user_ready("Press Enter after login is complete: ")
            console.print("[bold green]Login saved![/]")
            return 0
        except Exception as error:
            _log_error("login_phase", error)
            console.print(f"[bold red]Login failed: {error}[/]")
            return 1
        finally:
            browser.close()

    if run_options.fill_only:
        print_section("Fill Mode (using saved session)")
        run_options = RunOptions(
            **{**run_options.__dict__, 'continue_after_analysis': True, 'auto_fill': True, 'form_only': True}
        )

    # Load profile
    profile = _load_profile()
    if not run_options.fill_only:
        _print_profile_summary(profile)

    # Create LLM client
    try:
        llm_client = create_llm_client()
    except RuntimeError as e:
        print(f"Warning: {e}")
        llm_client = None

    browser = BrowserAgent(
        session_profile_dir=session_dir,
        cdp_endpoint=run_options.cdp_endpoint,
        reuse_existing_tab=run_options.reuse_existing_tab,
        keep_browser_open=run_options.keep_browser_open,
        browser_channel=run_options.browser_channel,
        browser_executable_path=run_options.browser_executable_path,
        headless=run_options.headless,
        slow_motion=run_options.slow_motion,
    )

    ts = timestamp()
    jd_analysis: dict[str, Any] = {}
    fill_plan: list[dict[str, Any]] = []
    fields: list[dict[str, Any]] = []
    jd_analysis_path = CONFIG.outputs_dir / "jd_analysis" / f"{ts}_jd_analysis.json"
    fill_plan_path = CONFIG.outputs_dir / "fill_plans" / f"{ts}_fill_plan.json"
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
            browser.wait_for_user_ready("Login in the browser, then press Enter: ")

        try:
            browser.save_screenshot("job_page_initial")
        except Exception:
            pass

        raw_page_text = browser.get_page_text()
        _write_text(CONFIG.outputs_dir / "jd_analysis" / f"{ts}_raw_page.txt", raw_page_text)

        # JD Analysis (skip in form_only mode)
        if run_options.form_only:
            personal = profile.get("personal", {}) if isinstance(profile, dict) else {}
            intro = to_plain_text(personal.get("self_introduction", {}).get("medium", "")) or clip_text(normalize_whitespace(raw_page_text), 280)
            jd_analysis = {
                "company": "",
                "position": "Form-only mode",
                "match_score": 0.0,
                "keywords": [],
                "core_requirements": [],
                "matched_experiences": [],
                "risks": ["Form-only mode - JD analysis skipped"],
                "job_summary": clip_text(raw_page_text, 200),
                "resume_strategy": "Fill basic fields first",
                "tailored_texts": {
                    "self_introduction_100": clip_text(intro, 120),
                    "self_introduction_300": clip_text(intro, 320),
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
        elif llm_client:
            jd_analysis = analyze_and_tailor(raw_page_text, profile, {}, "", llm_client)
        else:
            jd_analysis = {
                "company": "", "position": "", "match_score": 0.0,
                "keywords": [], "core_requirements": [], "matched_experiences": [],
                "risks": ["No LLM client available"], "tailored_texts": {},
            }

        company = to_plain_text(jd_analysis.get("company", ""))
        position = to_plain_text(jd_analysis.get("position", ""))
        match_score = float(jd_analysis.get("match_score", 0.0) or 0.0)
        save_json(jd_analysis_path, jd_analysis)

        should_continue = run_options.continue_after_analysis
        if run_options.interactive:
            should_continue = _prompt_yes_no("Continue to application? y/n: ")
        if not should_continue:
            return 0

        # Navigate to form
        clicked = browser.click_apply_button()
        if not clicked:
            print("Could not auto-find apply button. Please navigate manually.")
        if run_options.wait_for_login:
            browser.wait_for_user_ready("Login and navigate to the application form, then press Enter: ")

        # Multi-round filling
        round_index = 1
        while True:
            print_section(f"Form Analysis - Round {round_index}")

            # Dual-channel extraction with retry
            if llm_client:
                fields = _extract_fields_with_retry(browser, profile, llm_client)
            else:
                from .form_extractor import extract_fields_rule_based
                fields = extract_fields_rule_based(browser.page)

            if not fields:
                print("No form fields extracted. The page may not have loaded properly.")
                break

            save_json(CONFIG.outputs_dir / "fill_plans" / f"{ts}_fields_r{round_index}.json", fields)

            # Smart matching
            if llm_client:
                fill_plan = match_fields_with_llm(fields, profile, llm_client, jd_analysis)
            else:
                fill_plan = match_fields_rule_based(fields, profile)

            save_json(fill_plan_path, fill_plan)
            _print_fill_plan_summary(fill_plan)

            should_fill = run_options.auto_fill
            if run_options.interactive:
                if run_options.signal_mode:
                    _wait_for_signal(run_options.fill_signal, f"Enter {run_options.fill_signal} to start filling: ")
                    should_fill = True
                else:
                    should_fill = _prompt_yes_no("Start auto-fill? y/n: ")

            if should_fill:
                resume_pdf = find_resume_pdf()
                fill_result = fill_form(browser.page, fill_plan, resume_path=resume_pdf)
                filled_count = len(fill_result.get("filled", []))
                review_count = len(fill_result.get("review", []))
                skipped_count = len(fill_result.get("skipped", []))
                failed_count = len(fill_result.get("failed", []))
                print(f"Filled: {filled_count} | Review: {review_count} | Skipped: {skipped_count} | Failed: {failed_count}")
                status = "filled"
            else:
                status = "manual_review"
                break

            if not run_options.interactive or not run_options.signal_mode:
                break

            if round_index >= run_options.max_fill_rounds:
                print("Max fill rounds reached.")
                break

            action = input(f"Enter {run_options.next_page_signal} to continue to next page, or {run_options.done_signal}: ").strip()
            if action == run_options.next_page_signal:
                print("⏳ Waiting for page refresh...")
                browser.page.wait_for_timeout(2000)  # Wait for page to update
                round_index += 1
                continue
            break

        # Submit
        should_submit = run_options.auto_submit
        if run_options.interactive:
            confirm = input("Type CONFIRM_SUBMIT to submit, or press Enter to skip: ").strip()
            should_submit = confirm == "CONFIRM_SUBMIT"
        if should_submit:
            if browser.click_submit_button():
                status = "submitted"
            else:
                status = "manual_review"
                print("Could not auto-submit. Please submit manually.")

        return 0

    except Exception as error:
        _log_error("apply_flow", error)
        print(f"Error: {error}")
        raise
    finally:
        append_application({
            "date": ts,
            "company": company,
            "position": position,
            "url": url,
            "status": status,
            "match_score": match_score,
            "notes": notes,
            "fill_plan_path": str(fill_plan_path),
            "jd_analysis_path": str(jd_analysis_path),
        })
        browser.close()


def run_doctor() -> int:
    print_section("Doctor Check")
    masked_key = ""
    provider = CONFIG.llm.provider
    if provider == "deepseek" and CONFIG.llm.deepseek_api_key:
        masked_key = f"***{CONFIG.llm.deepseek_api_key[-4:]}"
    elif provider == "openai" and CONFIG.llm.openai_api_key:
        masked_key = f"***{CONFIG.llm.openai_api_key[-4:]}"

    table = Table(title="Config Check", show_header=False, box=None)
    table.add_row("Provider", provider)
    table.add_row("API Key", masked_key or "(empty)")
    console.print(table)

    if not masked_key:
        print("No API key detected. Configure .env first.")
        return 1

    try:
        llm_client = create_llm_client()
        output = llm_client.call_text("You are a health check assistant.", "Reply OK")
        print(f"Connection successful: {clip_text(normalize_whitespace(output), 80)}")
        return 0
    except Exception as exc:
        print(f"Connection failed: {exc}")
        return 2

#!/usr/bin/env python3
"""
Resume Skill CLI - AI-powered smart resume auto-fill assistant.

Usage:
    resume-skill extract --pdf <path>
    resume-skill consolidate
    resume-skill apply --url <url> [--auto-fill]
    resume-skill setup
    resume-skill doctor
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Version info
__version__ = "0.2.2"


def _json_output(data: dict[str, Any]) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def cmd_extract(args: argparse.Namespace) -> int:
    from .config import CONFIG
    from .extractor import PersonalInfoExtractor

    personal_info_dir = Path(args.personal_info_dir) if args.personal_info_dir else CONFIG.personal_info_dir
    extractor = PersonalInfoExtractor(personal_info_dir, CONFIG)

    if args.pdf:
        pdf_path = Path(args.pdf)
        if not pdf_path.exists():
            print(f"Error: PDF not found: {args.pdf}")
            return 1

        result = extractor.extract_from_resume_pdf(
            str(pdf_path),
            output_to_template=not args.no_template,
        )

        if args.json:
            _json_output({"status": "success", "action": "extract", "data": {"pdf": str(pdf_path), "fields_extracted": bool(result)}})
        else:
            if result:
                print("Extraction complete! Profile template updated.")
            else:
                print("Extraction failed.")
        return 0 if result else 1
    else:
        profile = extractor.generate_unified_profile()
        if args.json:
            _json_output({"status": "success", "action": "extract", "profile_path": str(extractor.personal_info_dir / "unified_profile.yaml")})
        else:
            if profile:
                print("Unified profile generated!")
            else:
                print("Generation failed. Ensure profile_template.md has content and API key is set.")
        return 0 if profile else 1


def cmd_consolidate(args: argparse.Namespace) -> int:
    from .config import CONFIG
    from .extractor import PersonalInfoExtractor

    personal_info_dir = Path(args.personal_info_dir) if args.personal_info_dir else CONFIG.personal_info_dir
    extractor = PersonalInfoExtractor(personal_info_dir, CONFIG)
    profile = extractor.generate_unified_profile()

    if args.json:
        _json_output({
            "status": "success" if profile else "failed",
            "action": "consolidate",
            "profile_path": str(extractor.personal_info_dir / "unified_profile.yaml"),
        })
    else:
        if profile:
            print("Unified profile generated successfully!")
        else:
            print("Generation failed. Check profile_template.md and API key.")
    return 0 if profile else 1


def cmd_apply(args: argparse.Namespace) -> int:
    url = args.url
    if not url:
        print("Error: --url is required")
        return 1

    if args.use_mcp:
        from .agent.mcp.agent import run_agent
        # v2.4暂时不支持resume功能
        run_agent(url, headless=args.headless)
        return 0

    from .agent.workflow import run_apply_flow, RunOptions

    mode = getattr(args, "mode", "full")
    login_only = mode == "login"
    fill_only = mode == "fill"
    form_only = mode in ("fill", "form")

    options = RunOptions(
        interactive=not args.non_interactive,
        continue_after_analysis=args.continue_after_analysis,
        auto_fill=args.auto_fill,
        auto_submit=args.auto_submit,
        wait_for_login=not args.skip_login_wait,
        session_profile_dir=args.session_dir,
        cdp_endpoint=args.cdp_endpoint,
        keep_browser_open=args.keep_browser_open,
        browser_channel=args.browser_channel,
        browser_executable_path=args.browser_executable_path,
        manual_login_first=args.manual_login_first,
        form_only=form_only,
        login_only=login_only,
        fill_only=fill_only,
        headless=args.headless,
        max_fill_rounds=args.max_fill_rounds,
    )

    result = run_apply_flow(url, options)
    return result


def cmd_setup(args: argparse.Namespace) -> int:
    """Install Playwright browsers and create default config."""
    import subprocess

    print("Installing Playwright browsers...")
    try:
        subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
        print("Playwright browsers installed!")
    except Exception as e:
        print(f"Warning: Playwright install failed: {e}")
        print("You can manually run: playwright install chromium")

    # Create default personal_info directory
    from .config import CONFIG

    personal_dir = CONFIG.personal_info_dir
    (personal_dir / "formal_resume").mkdir(parents=True, exist_ok=True)
    (personal_dir / "general_information").mkdir(parents=True, exist_ok=True)

    # Create .env template if not exists
    env_path = CONFIG.project_root / ".env"
    if not env_path.exists():
        env_path.write_text(
            "# Resume Skill Configuration\n"
            "LLM_PROVIDER=deepseek\n"
            "DEEPSEEK_API_KEY=your_api_key_here\n"
            "DEEPSEEK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3\n"
            "DEEPSEEK_MODEL=deepseek-v4-pro-260425\n",
            encoding="utf-8",
        )
        print(f"Created .env template at {env_path}")

    print("Setup complete!")
    return 0


def cmd_webui(args: argparse.Namespace) -> int:
    """Start the Web UI."""
    print_section("RESUME_SKILL Web UI")
    from .webui.app import run_webui
    run_webui(host=args.host, port=args.port, debug=args.debug, clean=args.clean)
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    from .agent.workflow import run_doctor
    return run_doctor()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Resume Skill - AI-powered smart resume auto-fill assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--version', action='version', version=f'resume-skill {__version__}')

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # extract
    extract_p = subparsers.add_parser("extract", help="Extract info from resume PDF")
    extract_p.add_argument("--pdf", help="Path to resume PDF")
    extract_p.add_argument("--personal-info-dir", default=None, help="Personal info directory")
    extract_p.add_argument("--no-template", action="store_true", help="Don't update profile_template.md")
    extract_p.add_argument("--json", action="store_true", help="Output in JSON format")

    # consolidate
    cons_p = subparsers.add_parser("consolidate", help="Generate unified_profile.yaml from profile_template.md")
    cons_p.add_argument("--personal-info-dir", default=None, help="Personal info directory")
    cons_p.add_argument("--json", action="store_true", help="Output in JSON format")

    # apply
    apply_p = subparsers.add_parser("apply", help="Apply to job position")
    apply_p.add_argument("--url", required=True, help="Job application URL")
    apply_p.add_argument("--mode", choices=["full", "login", "fill", "form"], default="full", help="Run mode")
    apply_p.add_argument("--auto-fill", action="store_true", help="Enable auto-fill")
    apply_p.add_argument("--auto-submit", action="store_true", help="Auto-submit form")
    apply_p.add_argument("--non-interactive", action="store_true", help="Non-interactive mode")
    apply_p.add_argument("--continue-after-analysis", action="store_true")
    apply_p.add_argument("--skip-login-wait", action="store_true")
    apply_p.add_argument("--session-dir", default="")
    apply_p.add_argument("--cdp-endpoint", default="")
    apply_p.add_argument("--keep-browser-open", action="store_true")
    apply_p.add_argument("--browser-channel", default="chrome")
    apply_p.add_argument("--browser-executable-path", default="")
    apply_p.add_argument("--manual-login-first", action="store_true")
    apply_p.add_argument("--headless", action="store_true")
    apply_p.add_argument("--max-fill-rounds", type=int, default=3)
    apply_p.add_argument("--use-mcp", action="store_true", help="Use MCP Agent mode (LLM dynamically decides next step)")
    apply_p.add_argument("--resume", default="", help="从指定 checkpoint 文件恢复 MCP Agent session")

    # setup
    subparsers.add_parser("setup", help="Install dependencies and create default config")

    # doctor
    subparsers.add_parser("doctor", help="Check LLM connectivity and configuration")

    # webui
    webui_p = subparsers.add_parser("webui", help="Start web management interface")
    webui_p.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    webui_p.add_argument("--port", type=int, default=5000, help="Port to bind (default: 5000)")
    webui_p.add_argument("--debug", action="store_true", help="Enable Flask debug mode")
    webui_p.add_argument("--clean", action="store_true", help="清理上次运行的旧记录")

    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 1

    commands = {
        "extract": cmd_extract,
        "consolidate": cmd_consolidate,
        "apply": cmd_apply,
        "setup": cmd_setup,
        "doctor": cmd_doctor,
        "webui": cmd_webui,
    }

    handler = commands.get(args.command)
    if handler:
        return handler(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())

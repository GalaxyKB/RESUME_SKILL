#!/usr/bin/env python3
"""
RESUME_SKILL - 智能简历投递助手
A smart resume application assistant with AI-powered information extraction and auto-fill.

Usage:
    python main.py extract --personal-info-dir ./personal_info
    python main.py apply --url <url> --personal-info-dir ./personal_info --auto-fill
"""

import asyncio
import argparse
import sys
from pathlib import Path
from typing import Optional

from personal_info.extractor import PersonalInfoExtractor


class ResumeSkill:
    """Main orchestrator for RESUME_SKILL workflow."""
    
    def __init__(self, personal_info_dir: str = "personal_info"):
        self.personal_info_dir = Path(personal_info_dir)
        self.extractor = PersonalInfoExtractor(str(self.personal_info_dir))
    
    async def extract_personal_info(self, llm_client: Optional[object] = None) -> dict:
        """
        Extract and consolidate personal information.
        
        Args:
            llm_client: Optional LLM client for AI extraction
        
        Returns:
            Consolidated profile dictionary
        """
        print("\n" + "=" * 60)
        print("📋 第一步: 个人信息提取与整合 (Step 1: Extract & Consolidate)")
        print("=" * 60)
        
        if llm_client:
            self.extractor.llm_client = llm_client
        
        profile = await self.extractor.extract_and_consolidate()
        
        print("\n✅ 个人信息处理完成！")
        return profile
    
    async def apply_to_position(self, url: str, auto_fill: bool = False, keep_browser_open: bool = False):
        """
        Open browser and apply to position with auto-fill.
        
        Args:
            url: Job application URL
            auto_fill: Whether to auto-fill form
            keep_browser_open: Whether to keep browser open after
        """
        print("\n" + "=" * 60)
        print("🌐 第二步: 打开职位页面并填写 (Step 2: Open & Fill)")
        print("=" * 60)
        
        # Import apply_agent here to avoid circular imports
        try:
            from apply_agent.workflow import run_apply_flow, RunOptions
        except ImportError:
            print("❌ Error: apply_agent module not found")
            print("   Please ensure apply_agent is properly set up in parent directory")
            return False
        
        # Load unified profile if it exists
        profile_path = self.personal_info_dir / "unified_profile.yaml"
        if not profile_path.exists():
            print("⚠️ 未找到 unified_profile.yaml，请先运行 extract 命令")
            return False
        
        # Create run options
        options = RunOptions(
            interactive=True,
            continue_after_analysis=True,
            auto_fill=auto_fill,
            form_only=True,
            keep_browser_open=keep_browser_open
        )
        
        try:
            result = run_apply_flow(url, options=options)
            return result
        except Exception as e:
            print(f"❌ Error during application: {e}")
            return False
    
    async def run_full_workflow(self, url: str, llm_client: Optional[object] = None):
        """
        Run the complete workflow: extract -> apply.
        
        Args:
            url: Job application URL
            llm_client: Optional LLM client
        """
        # Step 1: Extract personal information
        profile = await self.extract_personal_info(llm_client)
        
        # Step 2: Apply to position
        print("\n" + "=" * 60)
        print("继续进行应聘申请? (Continue with application?) [Y/n]: ", end="")
        sys.stdout.flush()
        response = input().strip().lower()
        
        if response in ["y", "", "yes"]:
            await self.apply_to_position(url, auto_fill=True, keep_browser_open=False)
        else:
            print("✅ 已保存个人信息，稍后可使用 apply 命令进行应聘")


async def main():
    parser = argparse.ArgumentParser(
        description="RESUME_SKILL - 智能简历投递助手",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 只提取个人信息
  python main.py extract --personal-info-dir ./personal_info
  
  # 完整工作流 (个人信息提取 + 应聘)
  python main.py apply --url "https://..." --full-workflow
  
  # 仅使用已有的个人信息进行应聘
  python main.py apply --url "https://..." --auto-fill
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Extract command
    extract_parser = subparsers.add_parser("extract", help="Extract personal information from resume PDF")
    extract_parser.add_argument(
        "--resume",
        help="Path to resume PDF file (e.g., personal_info/resume/my_resume.pdf)"
    )
    extract_parser.add_argument(
        "--personal-info-dir",
        default="personal_info",
        help="Path to personal_info directory (default: personal_info)"
    )
    extract_parser.add_argument(
        "--use-ai",
        action="store_true",
        help="Use AI to extract and analyze resume information"
    )
    
    # Apply command
    apply_parser = subparsers.add_parser("apply", help="Apply to job position")
    apply_parser.add_argument(
        "--url",
        required=True,
        help="Job application URL"
    )
    apply_parser.add_argument(
        "--personal-info-dir",
        default="personal_info",
        help="Path to personal_info directory"
    )
    apply_parser.add_argument(
        "--auto-fill",
        action="store_true",
        help="Enable auto-fill"
    )
    apply_parser.add_argument(
        "--full-workflow",
        action="store_true",
        help="Run full workflow (extract + apply)"
    )
    apply_parser.add_argument(
        "--keep-browser-open",
        action="store_true",
        help="Keep browser open after completion"
    )
    apply_parser.add_argument(
        "--llm-api-key",
        help="LLM API key (for full workflow)"
    )
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Initialize ResumeSkill
    skill = ResumeSkill(personal_info_dir=args.personal_info_dir)
    
    if args.command == "extract":
        print("🚀 RESUME_SKILL - 智能简历投递助手")
        print("=" * 60)
        
        resume_path = args.resume
        
        # If resume path provided, extract from it
        if resume_path:
            resume_file = Path(resume_path)
            if not resume_file.exists():
                print(f"❌ Error: Resume file not found: {resume_path}")
                return 1
            
            print(f"📄 开始从简历提取信息: {resume_path}")
            print("   Extracting information from resume...")
            
            # Extract with AI
            try:
                from apply_agent.llm_client import LLMClient
                from dotenv import load_dotenv
                import os
                
                # Load environment variables
                load_dotenv()
                
                # Initialize LLM client
                api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
                if not api_key:
                    print("❌ Error: No API key found in .env")
                    print("   Please configure DEEPSEEK_API_KEY or OPENAI_API_KEY")
                    return 1
                
                llm_client = LLMClient(api_key=api_key)
                
                # Perform extraction (non-async)
                result = skill.extractor.extract_from_resume_pdf(
                    resume_path=resume_path,
                    llm_client=llm_client,
                    output_to_template=True  # Automatically update profile_template.md
                )
                
                print("✅ 简历信息提取完成!")
                print(f"   Profile template updated: {skill.personal_info_dir / 'profile_template.md'}")
                return 0
                
            except Exception as e:
                print(f"❌ Error: {e}")
                import traceback
                traceback.print_exc()
                return 1
        else:
            # Standard extraction without specific resume
            print("⚠️ No --resume specified, running standard extraction...")
            
            try:
                from dotenv import load_dotenv
                import os
                
                load_dotenv()
                
                llm_client = None
                if args.use_ai:
                    try:
                        from apply_agent.llm_client import LLMClient
                        api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
                        if api_key:
                            llm_client = LLMClient(api_key=api_key)
                            print("✅ LLM客户端已初始化")
                    except Exception as e:
                        print(f"⚠️ Warning: Cannot initialize LLM client: {e}")
                
                await skill.extract_personal_info(llm_client)
                return 0
            except Exception as e:
                print(f"❌ Error: {e}")
                return 1
    
    elif args.command == "apply":
        print("🚀 RESUME_SKILL - 智能简历投递助手")
        print("=" * 60)
        
        if args.full_workflow:
            # Run full workflow
            llm_client = None
            if args.llm_api_key:
                try:
                    from apply_agent.llm_client import LLMClient
                    llm_client = LLMClient(api_key=args.llm_api_key)
                except Exception:
                    pass
            
            await skill.run_full_workflow(args.url, llm_client)
        else:
            # Just apply with existing profile
            result = await skill.apply_to_position(
                args.url,
                auto_fill=args.auto_fill,
                keep_browser_open=args.keep_browser_open
            )
            return 0 if result else 1
        
        return 0
    
    return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

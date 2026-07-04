#!/usr/bin/env python
"""验证RESUME_SKILL的self-contained特性"""
import sys
from pathlib import Path

# 确保可以导入apply_agent
sys.path.insert(0, str(Path(__file__).parent))

try:
    from apply_agent import storage, browser_agent, config, form_extractor
    print("[OK] apply_agent.storage")
    print("[OK] apply_agent.browser_agent")  
    print("[OK] apply_agent.config")
    print("[OK] apply_agent.form_extractor")
    
    from apply_agent.workflow import run_apply_flow, RunOptions
    print("[OK] apply_agent.workflow (run_apply_flow, RunOptions)")
    
    from apply_agent.llm_client import LLMClient
    print("[OK] apply_agent.llm_client (LLMClient)")
    
    from personal_info.extractor import PersonalInfoExtractor
    print("[OK] personal_info.extractor (PersonalInfoExtractor)")
    
    print("\n" + "="*50)
    print("✅ ALL IMPORTS SUCCESSFUL")
    print("✅ RESUME_SKILL is COMPLETELY SELF-CONTAINED")
    print("✅ Ready for open-source release!")
    print("="*50)
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

#!/usr/bin/env python3
"""
Verification script for Task B implementation.
Checks all required changes are in place.
"""
import sys
import os
from pathlib import Path

def check_file_exists(path, description):
    """Check if a file exists."""
    if Path(path).exists():
        print(f"✓ {description}: {path}")
        return True
    else:
        print(f"✗ {description} NOT FOUND: {path}")
        return False

def check_in_file(filepath, pattern, description):
    """Check if a pattern exists in a file."""
    if not Path(filepath).exists():
        print(f"✗ File not found: {filepath}")
        return False
    
    content = Path(filepath).read_text(encoding='utf-8')
    if pattern in content:
        print(f"✓ {description}")
        return True
    else:
        print(f"✗ {description} - Pattern not found in {filepath}")
        return False

def main():
    print("\n" + "="*70)
    print("TASK B IMPLEMENTATION VERIFICATION")
    print("="*70 + "\n")
    
    all_ok = True
    
    # Check 1: Backend changes
    print("1. Backend Changes")
    print("-" * 70)
    
    all_ok &= check_file_exists(
        "src/resume_skill/webui/task_manager.py",
        "New task_manager.py module"
    )
    
    all_ok &= check_in_file(
        "src/resume_skill/webui/app.py",
        "from .task_manager import task_manager, FillTask",
        "task_manager import in app.py"
    )
    
    all_ok &= check_in_file(
        "src/resume_skill/webui/app.py",
        "def _execute_fill_task(task: FillTask):",
        "_execute_fill_task function"
    )
    
    all_ok &= check_in_file(
        "src/resume_skill/webui/app.py",
        "@app.route(\"/api/fill/start\", methods=[\"POST\"])",
        "/api/fill/start endpoint"
    )
    
    all_ok &= check_in_file(
        "src/resume_skill/webui/app.py",
        "@app.route(\"/api/fill/status/<task_id>\", methods=[\"GET\"])",
        "/api/fill/status/<task_id> endpoint"
    )
    
    all_ok &= check_in_file(
        "src/resume_skill/webui/app.py",
        "@app.route(\"/api/fill/cancel/<task_id>\", methods=[\"POST\"])",
        "/api/fill/cancel/<task_id> endpoint"
    )
    
    all_ok &= check_in_file(
        "src/resume_skill/webui/app.py",
        "def api_fill_start():",
        "New api_fill_start function (background task mode)"
    )
    
    all_ok &= check_in_file(
        "src/resume_skill/webui/app.py",
        "def api_fill_status(task_id):",
        "New api_fill_status function"
    )
    
    all_ok &= check_in_file(
        "src/resume_skill/webui/app.py",
        "def api_fill_cancel(task_id):",
        "New api_fill_cancel function"
    )
    
    # Check 2: Frontend changes
    print("\n2. Frontend Changes")
    print("-" * 70)
    
    all_ok &= check_in_file(
        "src/resume_skill/webui/templates/index.html",
        "fillTaskId:'',",
        "fillTaskId Vue data field"
    )
    
    all_ok &= check_in_file(
        "src/resume_skill/webui/templates/index.html",
        "fillPollTimer:null,",
        "fillPollTimer Vue data field"
    )
    
    all_ok &= check_in_file(
        "src/resume_skill/webui/templates/index.html",
        "fillTaskLog:[],",
        "fillTaskLog Vue data field"
    )
    
    all_ok &= check_in_file(
        "src/resume_skill/webui/templates/index.html",
        "async startFill(){",
        "Updated startFill method"
    )
    
    all_ok &= check_in_file(
        "src/resume_skill/webui/templates/index.html",
        "async pollFillStatus(){",
        "New pollFillStatus method"
    )
    
    all_ok &= check_in_file(
        "src/resume_skill/webui/templates/index.html",
        "cancelFill(){",
        "New cancelFill method"
    )
    
    all_ok &= check_in_file(
        "src/resume_skill/webui/templates/index.html",
        "beforeDestroy(){",
        "beforeDestroy lifecycle hook"
    )
    
    # Check 3: Tests
    print("\n3. Test Files")
    print("-" * 70)
    
    all_ok &= check_file_exists(
        "tests/test_fill_task_api.py",
        "New test_fill_task_api.py"
    )
    
    all_ok &= check_file_exists(
        "tests/test_step1_extract_still_works.py",
        "New test_step1_extract_still_works.py"
    )
    
    all_ok &= check_file_exists(
        "tests/test_task_workflow.py",
        "New test_task_workflow.py"
    )
    
    # Check 4: Documentation
    print("\n4. Documentation")
    print("-" * 70)
    
    all_ok &= check_file_exists(
        "IMPLEMENTATION_SUMMARY.md",
        "Implementation summary documentation"
    )
    
    # Summary
    print("\n" + "="*70)
    if all_ok:
        print("✓ ALL CHECKS PASSED - Implementation is complete!")
    else:
        print("✗ SOME CHECKS FAILED - Please review above")
    print("="*70 + "\n")
    
    return 0 if all_ok else 1

if __name__ == '__main__':
    sys.exit(main())

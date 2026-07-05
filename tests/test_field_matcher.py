"""Tests for field matching functionality."""
import pytest

from resume_skill.agent.field_matcher import (
    match_fields_rule_based,
    _rule_match_single_field,
    _match_keywords,
    _compose_field_text,
    _is_sensitive,
    _is_excluded,
)


def test_match_keywords():
    """Test keyword matching functionality."""
    assert _match_keywords("姓名", ["姓名", "name", "full name"])
    assert _match_keywords("Full Name", ["姓名", "name", "full name"])
    assert _match_keywords("用户姓名", ["姓名", "name", "full name"])
    assert not _match_keywords("公司名称", ["姓名", "name", "full name"])


def test_compose_field_text():
    """Test field text composition."""
    field = {
        "field_label": "姓名",
        "placeholder": "请输入您的姓名",
        "name": "fullName",
        "id": "user-name"
    }
    text = _compose_field_text(field)
    assert "姓名" in text
    assert "请输入您的姓名" in text
    assert "fullName" in text
    assert "user-name" in text


def test_is_sensitive():
    """Test sensitive field detection."""
    assert _is_sensitive("密码")
    assert _is_sensitive("Password")
    assert _is_sensitive("验证码")
    assert _is_sensitive("Captcha")
    assert not _is_sensitive("姓名")
    assert not _is_sensitive("邮箱")


def test_is_excluded():
    """Test excluded field detection."""
    assert _is_excluded("提交")
    assert _is_excluded("Submit")
    assert _is_excluded("取消")
    assert _is_excluded("Cancel")
    assert not _is_excluded("姓名")
    assert not _is_excluded("邮箱")


def test_rule_match_single_field():
    """Test single field rule-based matching."""
    profile = {
        "personal": {
            "name": "张三",
            "email": "zhangsan@example.com",
            "phone": "13800138000"
        }
    }
    
    # Test name field matching
    field = {
        "field_id": "field_001",
        "field_label": "姓名",
        "tag": "input",
        "type": "text",
        "selector": "#name",
    }
    
    result = _rule_match_single_field(field, profile)
    assert result["value"] == "张三"
    assert result["source"] == "personal.name"
    assert result["confidence"] > 0.8
    assert result["action"] == "auto_fill"


def test_match_fields_rule_based():
    """Test batch field matching."""
    profile = {
        "personal": {
            "name": "张三",
            "email": "zhangsan@example.com"
        }
    }
    
    fields = [
        {
            "field_id": "field_001",
            "field_label": "姓名",
            "tag": "input",
            "type": "text",
        },
        {
            "field_id": "field_002", 
            "field_label": "邮箱",
            "tag": "input",
            "type": "email",
        },
        {
            "field_id": "field_003",
            "field_label": "未知字段",
            "tag": "input", 
            "type": "text",
        }
    ]
    
    results = match_fields_rule_based(fields, profile)
    assert len(results) == 3
    
    # First field should match name
    assert results[0]["value"] == "张三"
    assert results[0]["action"] == "auto_fill"
    
    # Second field should match email  
    assert results[1]["value"] == "zhangsan@example.com"
    assert results[1]["action"] == "auto_fill"
    
    # Third field should be manual (no match)
    assert results[2]["action"] == "manual"
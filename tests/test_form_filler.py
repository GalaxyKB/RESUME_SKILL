"""Tests for form filling functionality."""
import pytest
from unittest.mock import Mock, MagicMock

from resume_skill.agent.form_filler import (
    _resolve_frame,
    _infer_fill_strategy,
    _determine_action,
)


def test_resolve_frame_main_page():
    """Test frame resolution when no frame_url is provided."""
    mock_page = Mock()
    result = _resolve_frame(mock_page, "")
    assert result == mock_page


def test_resolve_frame_exact_match():
    """Test frame resolution with exact URL match."""
    mock_page = Mock()
    mock_frame1 = Mock()
    mock_frame1.url = "https://example.com/form"
    mock_frame2 = Mock() 
    mock_frame2.url = "https://other.com/iframe"
    mock_page.frames = [mock_frame1, mock_frame2]
    
    result = _resolve_frame(mock_page, "https://example.com/form")
    assert result == mock_frame1


def test_resolve_frame_contains_match():
    """Test frame resolution with URL contains match."""
    mock_page = Mock()
    mock_frame = Mock()
    mock_frame.url = "https://example.com/form?session=abc123"
    mock_page.frames = [mock_frame]
    
    result = _resolve_frame(mock_page, "https://example.com/form")
    assert result == mock_frame


def test_resolve_frame_fallback():
    """Test frame resolution fallback to main page."""
    mock_page = Mock()
    mock_frame = Mock()
    mock_frame.url = "https://other.com/iframe"
    mock_page.frames = [mock_frame]
    
    result = _resolve_frame(mock_page, "https://notfound.com/form")
    assert result == mock_page


def test_infer_fill_strategy():
    """Test fill strategy inference."""
    # Text input
    field = {"tag": "input", "type": "text"}
    assert _infer_fill_strategy(field) == "type"
    
    # Select dropdown
    field = {"tag": "select"}
    assert _infer_fill_strategy(field) == "select"
    
    # Radio button
    field = {"tag": "input", "type": "radio"}
    assert _infer_fill_strategy(field) == "click"
    
    # Checkbox
    field = {"tag": "input", "type": "checkbox"}
    assert _infer_fill_strategy(field) == "click"
    
    # File upload
    field = {"tag": "input", "type": "file"}
    assert _infer_fill_strategy(field) == "upload"


def test_determine_action():
    """Test action determination logic."""
    # High confidence with value should auto-fill
    action = _determine_action("张三", 0.9, "姓名", "type")
    assert action == "auto_fill"
    
    # Low confidence should be manual
    action = _determine_action("张三", 0.3, "姓名", "type")
    assert action == "manual"
    
    # No value should be manual
    action = _determine_action("", 0.9, "姓名", "type")
    assert action == "manual"
    
    # File upload with resume keyword should auto-fill
    action = _determine_action("RESUME_FILE_PATH", 0.9, "简历", "upload")
    assert action == "auto_fill"
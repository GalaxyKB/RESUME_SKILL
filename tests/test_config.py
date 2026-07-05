"""Tests for configuration loading."""
import os
import tempfile
import pytest
from pathlib import Path

from resume_skill.config import load_app_config, AppConfig


def test_load_config_with_env_vars():
    """Test configuration loading with environment variables."""
    # Set test environment variables
    os.environ["LLM_PROVIDER"] = "openai"
    os.environ["OPENAI_API_KEY"] = "test-key"
    
    try:
        config = load_app_config()
        assert config.llm.provider == "openai"
        assert config.llm.openai_api_key == "test-key"
    finally:
        # Clean up
        os.environ.pop("LLM_PROVIDER", None)
        os.environ.pop("OPENAI_API_KEY", None)


def test_load_config_with_yaml():
    """Test configuration loading with YAML file."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.yaml"
        config_path.write_text("""
api:
  provider: deepseek
  deepseek_model: deepseek-chat
  deepseek_enable_web_search: true
browser:
  headless: false
  timeout: 30
""")
        
        config = load_app_config(Path(temp_dir))
        assert config.llm.provider == "deepseek"
        assert config.llm.deepseek_model == "deepseek-chat"
        assert config.llm.deepseek_enable_web_search is True
        assert config.browser.headless is False
        assert config.browser.timeout == 30


def test_config_precedence():
    """Test that environment variables override YAML config."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config.yaml"
        config_path.write_text("""
api:
  provider: deepseek
""")
        
        # Environment variable should override YAML
        os.environ["LLM_PROVIDER"] = "openai"
        
        try:
            config = load_app_config(Path(temp_dir))
            assert config.llm.provider == "openai"  # From env, not YAML
        finally:
            os.environ.pop("LLM_PROVIDER", None)


def test_default_config():
    """Test default configuration values."""
    config = load_app_config()
    assert config.llm.provider == "deepseek"  # Default provider
    assert config.browser.headless is True  # Default headless mode
    assert config.browser.timeout == 30  # Default timeout
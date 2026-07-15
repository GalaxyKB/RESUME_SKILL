from __future__ import annotations

import argparse
import io
from dataclasses import dataclass
from pathlib import Path


def test_profile_prepare_api_prepends_missing_fields():
    from resume_skill.webui.app import app

    client = app.test_client()
    response = client.post(
        "/api/profile/prepare",
        json={"content": "# Profile\n", "missing": ["手机号", "邮箱"]},
    )

    assert response.status_code == 200
    data = response.get_json()
    assert "## 待补全的信息" in data["content"]
    assert "- [ ] 手机号" in data["content"]
    assert data["content"].endswith("# Profile\n")


def test_extract_api_reports_failed_pdf_parse(monkeypatch, tmp_path):
    from resume_skill.webui import app as webapp

    class FakeConfig:
        personal_info_dir = tmp_path
        resume_dir = tmp_path / "formal_resume"

    monkeypatch.setattr(webapp, "CONFIG", FakeConfig)
    monkeypatch.setattr(
        "resume_skill.agent.resume_analyzer_node.analyze_resume",
        lambda resume_path: {"status": "failed", "error": "简历解析失败：mock"},
    )

    response = webapp.app.test_client().post(
        "/api/extract",
        data={"file": (io.BytesIO(b"bad pdf"), "resume.pdf")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 422
    data = response.get_json()
    assert data["status"] == "failed"
    assert "简历解析失败" in data["error"]


def test_cli_apply_mcp_passes_resume(monkeypatch):
    from resume_skill import cli

    calls = []

    def fake_run_agent(url: str, resume_from: str = "", headless: bool = False) -> None:
        calls.append({"url": url, "resume_from": resume_from, "headless": headless})

    monkeypatch.setattr("resume_skill.agent.mcp.agent.run_agent", fake_run_agent)

    args = argparse.Namespace(
        url="https://example.com/apply",
        use_mcp=True,
        resume="checkpoint.json",
        headless=True,
    )

    assert cli.cmd_apply(args) == 0
    assert calls == [{"url": "https://example.com/apply", "resume_from": "checkpoint.json", "headless": True}]


def test_fill_start_returns_llm_answers_without_real_chrome_or_llm(monkeypatch, tmp_path):
    from resume_skill.webui import app as webapp

    client = webapp.app.test_client()
    response = client.post("/api/fill/start")

    assert response.status_code == 200
    data = response.get_json()
    assert "task_id" in data
    status = client.get(f"/api/fill/status/{data['task_id']}").get_json()
    assert "fields" in status
    assert "vision_review" in status


def test_fill_start_returns_vision_review_when_enabled(monkeypatch, tmp_path):
    from resume_skill.webui import app as webapp

    response = webapp.app.test_client().post("/api/fill/start")

    assert response.status_code == 200
    data = response.get_json()
    assert "task_id" in data


def test_fill_start_uploads_resume_file(monkeypatch, tmp_path):
    from resume_skill.webui import app as webapp

    response = webapp.app.test_client().post(
        "/api/fill/start",
        data={"resume": (io.BytesIO(b"%PDF-1.4 test"), "resume.pdf")},
        content_type="multipart/form-data",
    )

    data = response.get_json()
    assert response.status_code == 200
    assert "task_id" in data
    task = webapp.task_manager.get_task(data["task_id"])
    assert task is not None
    assert task.resume_path.endswith(".pdf")


def test_parse_snapshot_supports_current_chrome_devtools_format():
    from resume_skill.agent.mcp.agent import MCPAgent

    agent = MCPAgent.__new__(MCPAgent)
    snapshot = '''## Latest page snapshot
uid=1_0 RootWebArea url="data:text/html"
  uid=1_1 StaticText "Name "
  uid=1_2 textbox "Name"
  uid=1_3 combobox "Degree" options="Bachelor,Master"
  uid=1_4 button "Submit"
  uid=1_5 button "Next"
'''

    fields = agent._parse_snapshot(snapshot)

    assert fields == [
        {"uid": "1_2", "label": "Name", "type": "text", "options": []},
        {"uid": "1_3", "label": "Degree", "type": "select", "options": ["Bachelor", "Master"]},
    ]
    assert agent._find_submit_uid(snapshot) == "1_4"
    assert agent._find_next_uid(snapshot) == "1_5"


def test_vision_factory_uses_ark_chat_provider(tmp_path):
    from resume_skill.config import AppConfig, VisionConfig
    from resume_skill.llm.ark_provider import ArkChatVisionProvider
    from resume_skill.llm.vision import create_vision_client

    cfg = AppConfig()
    cfg.vision = VisionConfig(
        provider="ark_chat",
        api_key="test-key",
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        model="doubao-seed-2-1-turbo-260628",
        enabled=True,
    )

    client = create_vision_client(cfg, outputs_dir=tmp_path)

    assert isinstance(client, ArkChatVisionProvider)
    assert client.model == "doubao-seed-2-1-turbo-260628"

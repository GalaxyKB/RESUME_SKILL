from __future__ import annotations

import sys

sys.path.insert(0, "src")

from resume_skill.webui.app import _is_local_section_save_line, _upload_confirmed, _file_name_markers


def test_local_section_save_rejects_final_submit():
    assert _is_local_section_save_line("提交保存")
    assert not _is_local_section_save_line("提交申请")
    assert not _is_local_section_save_line("立即申请")


def test_upload_markers_focus_on_file_identity():
    markers = _file_name_markers("/tmp/resume_张三.pdf")
    assert "resume_张三.pdf" in markers
    assert "resume_张三" in markers
    assert "已上传" in markers


def test_upload_confirmed_requires_specific_markers(monkeypatch):
    class DummyChrome:
        def call_tool(self, name, params=None, timeout=30):
            if name == "take_snapshot":
                return {"nodes": [{"uid": "1", "label": "附件", "role": "button"}]}
            raise AssertionError(name)

    assert not _upload_confirmed(DummyChrome(), "/tmp/resume.pdf")

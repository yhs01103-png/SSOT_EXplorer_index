"""router_sync.py 전용 테스트 — D-068. main.py의 SyncFormatsDialog에서
뽑아낸 뒤로는 QDialog 인스턴스 없이도 이 로직을 검증할 수 있다(예전엔
`dlg._write_one(...)`처럼 다이얼로그를 만들어야 했던 테스트들을 여기로
옮기고 `router_sync.write_one_format(...)`를 직접 호출하도록 정리 —
Qt 위젯 생성 비용 없이 더 빠르고, 이 모듈이 실제로 GUI-프리인지도 이
테스트 파일 자체가 증명한다)."""
from __future__ import annotations

from pathlib import Path

import router_sync as rs

_REGISTRY_PATH = Path("C:\\fake-registry\\ssot-roots.json")  # 이 파일들은 경로를 문자열로만 박아넣지 실제로 안 읽음


# --------------------------------------------------- generate_init_pointer

def test_init_pointer_marks_web_as_sole_source():
    entry = {"label": "a", "webArtifactUrl": "https://example.com", "primarySource": "web"}
    text = rs.generate_init_pointer(entry, "CLAUDE.md", _REGISTRY_PATH)
    assert "유일한 정본" in text
    assert "⚠️" in text


def test_init_pointer_marks_local_as_reference_only():
    entry = {"label": "a", "webArtifactUrl": "https://example.com", "primarySource": "local"}
    text = rs.generate_init_pointer(entry, "CLAUDE.md", _REGISTRY_PATH)
    assert "참고, 정본 아님" in text
    assert "유일한 정본" not in text


def test_init_pointer_includes_registry_path():
    entry = {"label": "a"}
    text = rs.generate_init_pointer(entry, "CLAUDE.md", _REGISTRY_PATH)
    assert str(_REGISTRY_PATH) in text


# --------------------------------------------- generate_full_export_pointer

def test_full_export_pointer_warns_when_web_primary():
    entry = {
        "label": "a", "webArtifactUrl": "https://example.com",
        "primarySource": "web", "referenceCondition": "x",
    }
    text = rs.generate_full_export_pointer(entry, "CLAUDE.md")
    assert text.split("## 참조 조건")[0].count("⚠️") >= 1


# ------------------------------------------------------------ FORMAT_TARGETS

def test_format_targets_includes_new_directory_formats():
    assert ".cursor/rules/ssot-index.mdc" in rs.FORMAT_TARGETS
    assert ".windsurf/rules/ssot-index.md" in rs.FORMAT_TARGETS
    assert not rs.FORMAT_TARGETS[".cursor/rules/ssot-index.mdc"].get("legacy")
    assert not rs.FORMAT_TARGETS[".windsurf/rules/ssot-index.md"].get("legacy")


def test_format_targets_flat_legacy_files_marked_legacy():
    assert rs.FORMAT_TARGETS[".cursorrules"]["legacy"] is True
    assert rs.FORMAT_TARGETS[".windsurfrules"]["legacy"] is True


def test_resolve_format_target_directory_formats():
    root = Path("C:\\proj")
    assert rs.resolve_format_target(root, ".cursor/rules/ssot-index.mdc") == (
        root / ".cursor" / "rules" / "ssot-index.mdc"
    )
    assert rs.resolve_format_target(root, ".windsurf/rules/ssot-index.md") == (
        root / ".windsurf" / "rules" / "ssot-index.md"
    )


# --------------------------------------------------------- write_one_format

def test_write_one_format_creates_directory_format_with_frontmatter(tmp_path):
    entry = {"label": "a", "path": str(tmp_path)}
    result = rs.write_one_format(tmp_path, entry, ".cursor/rules/ssot-index.mdc", _REGISTRY_PATH, force=False)
    assert result == "ok"
    target = tmp_path / ".cursor" / "rules" / "ssot-index.mdc"
    assert target.exists()
    text = target.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "alwaysApply: true" in text
    assert rs.SYNC_MARKER in text


def test_write_one_format_windsurf_directory_frontmatter(tmp_path):
    entry = {"label": "a", "path": str(tmp_path)}
    result = rs.write_one_format(tmp_path, entry, ".windsurf/rules/ssot-index.md", _REGISTRY_PATH, force=False)
    assert result == "ok"
    text = (tmp_path / ".windsurf" / "rules" / "ssot-index.md").read_text(encoding="utf-8")
    assert "trigger: always_on" in text


def test_write_one_format_legacy_not_created_when_missing(tmp_path):
    entry = {"label": "a", "path": str(tmp_path)}
    result = rs.write_one_format(tmp_path, entry, ".cursorrules", _REGISTRY_PATH, force=False)
    assert result == "skip-legacy"
    assert not (tmp_path / ".cursorrules").exists()


def test_write_one_format_legacy_updated_when_already_exists(tmp_path):
    entry = {"label": "a", "path": str(tmp_path)}
    existing = tmp_path / ".cursorrules"
    existing.write_text(f"old ({rs.SYNC_MARKER})", encoding="utf-8")
    result = rs.write_one_format(tmp_path, entry, ".cursorrules", _REGISTRY_PATH, force=False)
    assert result == "ok"
    assert "old" not in existing.read_text(encoding="utf-8")


def test_write_one_format_skips_hand_edited_file_without_force(tmp_path):
    entry = {"label": "a", "path": str(tmp_path)}
    (tmp_path / "CLAUDE.md").write_text("손으로 쓴 내용", encoding="utf-8")
    result = rs.write_one_format(tmp_path, entry, "CLAUDE.md", _REGISTRY_PATH, force=False)
    assert result == "skip"
    assert (tmp_path / "CLAUDE.md").read_text(encoding="utf-8") == "손으로 쓴 내용"


def test_write_one_format_overwrites_hand_edited_file_with_force(tmp_path):
    entry = {"label": "a", "path": str(tmp_path)}
    (tmp_path / "CLAUDE.md").write_text("손으로 쓴 내용", encoding="utf-8")
    result = rs.write_one_format(tmp_path, entry, "CLAUDE.md", _REGISTRY_PATH, force=True)
    assert result == "ok"
    assert rs.SYNC_MARKER in (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")


# -------------------------------------------------------------- needs_confirmation

def test_needs_confirmation_false_when_file_absent(tmp_path):
    assert rs.needs_confirmation(tmp_path, "CLAUDE.md") is False


def test_needs_confirmation_false_when_marker_present(tmp_path):
    (tmp_path / "CLAUDE.md").write_text(f"x ({rs.SYNC_MARKER})", encoding="utf-8")
    assert rs.needs_confirmation(tmp_path, "CLAUDE.md") is False


def test_needs_confirmation_true_when_hand_edited(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("손으로 쓴 내용", encoding="utf-8")
    assert rs.needs_confirmation(tmp_path, "CLAUDE.md") is True


# -------------------------------------------------------------------- sync_root

def test_sync_root_reports_every_format(tmp_path):
    entry = {"label": "a", "path": str(tmp_path)}
    results = rs.sync_root(tmp_path, entry, _REGISTRY_PATH)
    assert set(results) == set(rs.FORMAT_TARGETS)
    # 레거시 2개는 아직 없으니 건너뜀으로, 나머지 4개는 새로 생성돼 ok로 보고돼야 함
    assert list(results.values()).count("ok") == 4
    assert list(results.values()).count("skip-legacy") == 2


def test_sync_root_restricts_to_given_formats(tmp_path):
    entry = {"label": "a", "path": str(tmp_path)}
    results = rs.sync_root(tmp_path, entry, _REGISTRY_PATH, formats=["CLAUDE.md"])
    assert set(results) == {"CLAUDE.md"}


def test_sync_root_reports_needs_confirmation_without_writing(tmp_path):
    entry = {"label": "a", "path": str(tmp_path)}
    (tmp_path / "CLAUDE.md").write_text("손으로 쓴 내용", encoding="utf-8")
    results = rs.sync_root(tmp_path, entry, _REGISTRY_PATH, formats=["CLAUDE.md"])
    assert results["CLAUDE.md"] == "needs-confirmation"
    assert (tmp_path / "CLAUDE.md").read_text(encoding="utf-8") == "손으로 쓴 내용"


def test_sync_root_force_overwrites_without_confirmation_step(tmp_path):
    entry = {"label": "a", "path": str(tmp_path)}
    (tmp_path / "CLAUDE.md").write_text("손으로 쓴 내용", encoding="utf-8")
    results = rs.sync_root(tmp_path, entry, _REGISTRY_PATH, formats=["CLAUDE.md"], force=True)
    assert results["CLAUDE.md"] == "ok"
    assert rs.SYNC_MARKER in (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")

"""SSOT_Explorer 회귀 테스트 스위트 (pytest).

Lazzy_App_OS_Monorepo/server의 "모듈 1개당 test_*.py 1개, conftest.py 없이
파일 하나로" 컨벤션을 이식(2026-08-13, D-024) — SSOT_Explorer는 지금까지
검증할 때마다 스크래치 폴더에 테스트를 새로 써서 한 번 돌리고 지웠는데,
그래서는 다음에 같은 함수를 건드리다 실수해도 아무것도 안 잡아준다. 이
파일이 그 회귀 방지막.

실행: pip install -r requirements-dev.txt
      pytest -q
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import pytest
from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication, QMessageBox, QStyle

import main as m
import router_proposals


# ------------------------------------------------------------------ fixtures

@pytest.fixture(scope="session", autouse=True)
def qapp():
    """QApplication은 프로세스당 하나만 만들 수 있다 — 세션 스코프로 한 번만."""
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


@pytest.fixture(autouse=True)
def isolated_registry(tmp_path, monkeypatch):
    """모든 테스트가 실제 사용자 레지스트리
    (flutter_App\\.claude\\ssot-roots.json)를 절대 안 건드리게 REGISTRY_PATH를
    임시 경로로 스왑 + 매 테스트 시작 전 _LAST_KNOWN_HASH를 리셋(테스트 간
    상태 누수 방지, D-021 낙관적 동시성 기준선이 이전 테스트 값으로 새는 걸
    막는다)."""
    reg_path = tmp_path / "ssot-roots.json"
    monkeypatch.setattr(m, "REGISTRY_PATH", reg_path)
    m._LAST_KNOWN_HASH = ""
    yield reg_path


@pytest.fixture(autouse=True)
def isolated_router_proposals(tmp_path, monkeypatch):
    """D-029/D-030 — SaveDocumentDialog가 승인/취소 시 router_proposals.
    record_decision을 실제로 호출하는데(내부적으로 신뢰상태 파일도 같이
    씀), 실제 사용자 로그(~/.claude/scripts/ssot_router_proposals.json,
    ssot_router_trust.json)를 절대 안 건드리게 격리. main.py가
    `import router_proposals`로 모듈 자체를 참조하므로 여기서 patch하면
    main.py 쪽 호출에도 그대로 반영된다."""
    monkeypatch.setattr(router_proposals, "PROPOSALS_LOG_PATH", tmp_path / "proposals.json")
    monkeypatch.setattr(router_proposals, "TRUST_STATE_PATH", tmp_path / "trust.json")
    yield


@pytest.fixture(autouse=True)
def isolated_watcher_log(tmp_path, monkeypatch):
    """D-042 — InboxWatcherThread가 새 파일을 감지하면 router_watcher.
    record_new_file_event()를 호출해 실제 사용자 로그(~/.claude/scripts/
    ssot_watcher_log.json)에 쓸 수 있다 — 항상 격리."""
    import router_watcher
    monkeypatch.setattr(router_watcher, "WATCHER_LOG_PATH", tmp_path / "watcher-log.json")
    yield


@pytest.fixture(autouse=True)
def isolated_orchestrator_state(tmp_path, monkeypatch):
    """[실수 발견+수정, D-044] SaveDocumentDialog.run_classification()이
    router_orchestrator.orchestrate()를 log_path 없이 호출하고 있어서,
    이 파일의 기존 테스트들이 그동안 계속 실제 사용자 로그(~/.claude/
    scripts/ssot_orchestrator_log.json)에 "플러터 앱 개발 메모" 같은 테스트
    문자열을 남기고 있었다(D-032 이후 누적 131건 확인, 이번에 D-044 작업
    중 키워드 레지스트리를 같이 격리하다가 발견). 둘 다 여기서 한 번에
    격리."""
    import router_keyword_registry
    import router_orchestrator
    monkeypatch.setattr(router_orchestrator, "ORCHESTRATION_LOG_PATH", tmp_path / "orch-log.json")
    monkeypatch.setattr(router_keyword_registry, "KEYWORD_REGISTRY_PATH", tmp_path / "keywords.json")
    # D-045 — ManagementPanel(D-047 전 이름 ManagementDialog)이
    # SESSION_CONTEXT_LOG_PATH를 읽는다(이 앱은 안 쓰지만, 격리 안 하면
    # 테스트가 실제 사용자 로그 내용에 따라 결과가 갈리는 비결정적
    # 테스트가 된다).
    monkeypatch.setattr(m, "SESSION_CONTEXT_LOG_PATH", tmp_path / "session-context-log.json")
    yield


@pytest.fixture
def isolated_qsettings(tmp_path, monkeypatch):
    """SSOTExplorer 인스턴스화 테스트가 실제 Windows 레지스트리
    (HKCU\\Software\\SSOT_Explorer\\SSOT_Explorer)를 오염시키지 않도록,
    main.QSettings 호출을 임시 ini 파일로 리다이렉트한다."""
    ini_path = str(tmp_path / "settings.ini")

    def fake_qsettings(*_args, **_kwargs):
        return QSettings(ini_path, QSettings.IniFormat)

    monkeypatch.setattr(m, "QSettings", fake_qsettings)
    yield


# --------------------------------------------------- D-039: 레지스트리 경로 해석

def test_resolve_registry_path_uses_env_var_when_set(monkeypatch, tmp_path):
    custom = tmp_path / "custom-roots.json"
    monkeypatch.setenv("SSOT_REGISTRY_PATH", str(custom))
    assert m.resolve_registry_path() == custom


def test_resolve_registry_path_falls_back_to_generic_default(monkeypatch):
    monkeypatch.delenv("SSOT_REGISTRY_PATH", raising=False)
    assert m.resolve_registry_path() == Path.home() / ".claude" / "ssot-roots.json"


def test_router_classifier_default_registry_path_matches_main(monkeypatch, tmp_path):
    import router_classifier
    monkeypatch.delenv("SSOT_REGISTRY_PATH", raising=False)
    assert router_classifier._default_registry_path() == m.resolve_registry_path()
    custom = tmp_path / "custom-roots.json"
    monkeypatch.setenv("SSOT_REGISTRY_PATH", str(custom))
    assert router_classifier._default_registry_path() == custom


# --------------------------------------------------------- load/save 기본 동작

def test_load_roots_missing_file_returns_empty(isolated_registry):
    assert m.load_roots() == []


def test_save_then_load_roundtrip(isolated_registry):
    m.save_roots([{"label": "a", "path": "C:\\a", "referenceCondition": "x"}])
    roots = m.load_roots()
    assert len(roots) == 1
    assert roots[0]["label"] == "a"
    assert roots[0]["primarySource"] == "local"  # D-023 기본값


def test_save_preserves_shared_docs_and_comment(isolated_registry):
    """D-020 버그수정 회귀 테스트 — save_roots가 roots만 담아 파일 전체를
    덮어써서 sharedDocs가 저장할 때마다 사라지던 문제."""
    isolated_registry.write_text(
        json.dumps({
            "$comment": "커스텀 코멘트",
            "roots": [],
            "sharedDocs": [{"label": "doc", "path": "C:\\doc.md"}],
        }),
        encoding="utf-8",
    )
    m._LAST_KNOWN_HASH = m._hash_bytes(isolated_registry.read_bytes())
    m.save_roots([{"label": "a", "path": "C:\\a"}])
    payload = json.loads(isolated_registry.read_text(encoding="utf-8"))
    assert payload["sharedDocs"] == [{"label": "doc", "path": "C:\\doc.md"}]
    assert payload["$comment"] == "커스텀 코멘트"


# --------------------------------------------------- D-021: 원자적 쓰기 + 동시성

def test_save_roots_no_conflict_on_first_write(isolated_registry):
    m.save_roots([{"label": "a", "path": "C:\\a"}])  # 예외 없어야 함


def test_save_roots_normal_roundtrip_no_conflict(isolated_registry):
    m.save_roots([{"label": "a", "path": "C:\\a"}])
    roots = m.load_roots()
    roots.append({"label": "b", "path": "C:\\b"})
    m.save_roots(roots)  # 예외 없어야 함


def test_save_roots_detects_external_write_conflict(isolated_registry):
    m.save_roots([{"label": "a", "path": "C:\\a"}])
    roots = m.load_roots()
    roots.append({"label": "c", "path": "C:\\c"})

    # "다른 기기"가 그 사이 파일을 직접 바꿨다고 시뮬레이션
    external = json.loads(isolated_registry.read_text(encoding="utf-8-sig"))
    external["roots"].append({"label": "external", "path": "C:\\ext"})
    isolated_registry.write_text(json.dumps(external), encoding="utf-8")

    with pytest.raises(m.RegistryConflictError):
        m.save_roots(roots)


def test_conflict_does_not_overwrite_external_write(isolated_registry):
    m.save_roots([{"label": "a", "path": "C:\\a"}])
    roots = m.load_roots()
    roots.append({"label": "c", "path": "C:\\c"})

    external = json.loads(isolated_registry.read_text(encoding="utf-8-sig"))
    external["roots"].append({"label": "external", "path": "C:\\ext"})
    isolated_registry.write_text(json.dumps(external), encoding="utf-8")

    with pytest.raises(m.RegistryConflictError):
        m.save_roots(roots)

    final = json.loads(isolated_registry.read_text(encoding="utf-8"))
    labels = [r["label"] for r in final["roots"]]
    assert "external" in labels
    assert "c" not in labels


def test_save_roots_leaves_no_tmp_file(isolated_registry):
    m.save_roots([{"label": "a", "path": "C:\\a"}])
    leftovers = list(isolated_registry.parent.glob(isolated_registry.name + ".tmp*"))
    assert leftovers == []


# ---------------------------------------------------------- D-023: primarySource

def test_primary_source_defaults_to_local(isolated_registry):
    m.save_roots([{"label": "a", "path": "C:\\a"}])
    assert m.load_roots()[0]["primarySource"] == "local"


def test_primary_source_web_is_preserved(isolated_registry):
    m.save_roots([{"label": "a", "path": "C:\\a", "primarySource": "web"}])
    assert m.load_roots()[0]["primarySource"] == "web"


def test_init_pointer_marks_web_as_sole_source():
    entry = {"label": "a", "webArtifactUrl": "https://example.com", "primarySource": "web"}
    text = m.generate_init_pointer(entry, "CLAUDE.md")
    assert "유일한 정본" in text
    assert "⚠️" in text


def test_init_pointer_marks_local_as_reference_only():
    entry = {"label": "a", "webArtifactUrl": "https://example.com", "primarySource": "local"}
    text = m.generate_init_pointer(entry, "CLAUDE.md")
    assert "참고, 정본 아님" in text
    assert "유일한 정본" not in text


def test_full_export_pointer_warns_when_web_primary():
    entry = {
        "label": "a", "webArtifactUrl": "https://example.com",
        "primarySource": "web", "referenceCondition": "x",
    }
    text = m.generate_full_export_pointer(entry, "CLAUDE.md")
    assert text.split("## 참조 조건")[0].count("⚠️") >= 1


def test_format_registry_text_tags_web_primary():
    entry = {"label": "a", "path": "C:\\a", "primarySource": "web"}
    text = m.format_registry_text([entry])
    assert "🌐웹정본" in text.split("\n\n")[0]


def test_format_registry_text_tags_missing_path(tmp_path):
    """D-052 — 폴더가 삭제/이동됐는데 레지스트리엔 남아있는 경우 개발자
    탭에서 한눈에 보이게(자동 등록해제는 안 함, 감지→알림만)."""
    missing = {"label": "gone", "path": str(tmp_path / "does-not-exist")}
    present = {"label": "here", "path": str(tmp_path)}
    text = m.format_registry_text([missing, present])
    blocks = text.split("\n\n")
    assert "⚠️경로없음" in blocks[0]
    assert "⚠️경로없음" not in blocks[1]


def test_sync_dialog_warns_only_when_web_primary():
    entry_web = {"label": "a", "webArtifactUrl": "https://x", "primarySource": "web"}
    entry_local = {"label": "b", "webArtifactUrl": "https://x", "primarySource": "local"}

    def has_warning(dlg):
        for i in range(dlg.layout().count()):
            w = dlg.layout().itemAt(i).widget()
            if w is not None and hasattr(w, "text") and "정본입니다" in w.text():
                return True
        return False

    assert has_warning(m.SyncFormatsDialog(Path("C:\\a"), entry_web))
    assert not has_warning(m.SyncFormatsDialog(Path("C:\\b"), entry_local))


# ------------------------------------------- D-036/H-006: 디렉토리 포맷 + 레거시 처리

def test_format_targets_includes_new_directory_formats():
    assert ".cursor/rules/ssot-index.mdc" in m.FORMAT_TARGETS
    assert ".windsurf/rules/ssot-index.md" in m.FORMAT_TARGETS
    assert not m.FORMAT_TARGETS[".cursor/rules/ssot-index.mdc"].get("legacy")
    assert not m.FORMAT_TARGETS[".windsurf/rules/ssot-index.md"].get("legacy")


def test_format_targets_flat_legacy_files_marked_legacy():
    assert m.FORMAT_TARGETS[".cursorrules"]["legacy"] is True
    assert m.FORMAT_TARGETS[".windsurfrules"]["legacy"] is True


def test_resolve_format_target_directory_formats():
    root = Path("C:\\proj")
    assert m.resolve_format_target(root, ".cursor/rules/ssot-index.mdc") == (
        root / ".cursor" / "rules" / "ssot-index.mdc"
    )
    assert m.resolve_format_target(root, ".windsurf/rules/ssot-index.md") == (
        root / ".windsurf" / "rules" / "ssot-index.md"
    )


def test_sync_dialog_creates_directory_format_with_frontmatter(tmp_path):
    entry = {"label": "a", "path": str(tmp_path)}
    dlg = m.SyncFormatsDialog(tmp_path, entry)
    result = dlg._write_one(".cursor/rules/ssot-index.mdc", force=False)
    assert result == "ok"
    target = tmp_path / ".cursor" / "rules" / "ssot-index.mdc"
    assert target.exists()
    text = target.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "alwaysApply: true" in text
    assert m.SYNC_MARKER in text


def test_sync_dialog_windsurf_directory_frontmatter(tmp_path):
    entry = {"label": "a", "path": str(tmp_path)}
    dlg = m.SyncFormatsDialog(tmp_path, entry)
    result = dlg._write_one(".windsurf/rules/ssot-index.md", force=False)
    assert result == "ok"
    text = (tmp_path / ".windsurf" / "rules" / "ssot-index.md").read_text(encoding="utf-8")
    assert "trigger: always_on" in text


def test_sync_dialog_legacy_format_not_created_when_missing(tmp_path):
    entry = {"label": "a", "path": str(tmp_path)}
    dlg = m.SyncFormatsDialog(tmp_path, entry)
    result = dlg._write_one(".cursorrules", force=False)
    assert result == "skip-legacy"
    assert not (tmp_path / ".cursorrules").exists()


def test_sync_dialog_legacy_format_updated_when_already_exists(tmp_path):
    entry = {"label": "a", "path": str(tmp_path)}
    existing = tmp_path / ".cursorrules"
    existing.write_text(f"old ({m.SYNC_MARKER})", encoding="utf-8")
    dlg = m.SyncFormatsDialog(tmp_path, entry)
    result = dlg._write_one(".cursorrules", force=False)
    assert result == "ok"
    assert "old" not in existing.read_text(encoding="utf-8")


def test_sync_all_reports_every_format(tmp_path):
    entry = {"label": "a", "path": str(tmp_path)}
    dlg = m.SyncFormatsDialog(tmp_path, entry)
    dlg.sync_all()
    text = dlg.status_label.text()
    for fmt in m.FORMAT_TARGETS:
        assert fmt in text
    # 레거시 2개는 아직 없으니 건너뜀으로, 나머지 4개는 새로 생성돼 ok로 보고돼야 함
    assert text.count("✅") == 4
    assert "레거시" in text


# ---------------------------------------------------------- 기타 순수 로직 함수

def test_review_age_days_handles_missing_and_bad_format():
    assert m.review_age_days({}) is None
    assert m.review_age_days({"lastReviewed": "not-a-date"}) is None
    assert m.review_age_days({"lastReviewed": "2020-01-01"}) is not None


# --------------------------------------------------- D-038: 레지스트리 스키마 검증

def test_validate_registry_accepts_well_formed_data():
    data = {
        "roots": [{"label": "a", "path": "C:\\a", "primarySource": "local",
                   "lastReviewed": "2026-08-14", "dependsOnDocs": ["x"]}],
        "sharedDocs": [{"label": "doc", "path": "C:\\doc.md"}],
        "relations": [{"fromPath": "C:\\a", "toPath": "C:\\b", "bidirectional": True}],
    }
    assert m.validate_registry(data) == []


def test_validate_registry_flags_missing_required_fields():
    errors = m.validate_registry({"roots": [{"label": "a"}]})  # path 없음
    assert any("path" in e for e in errors)


def test_validate_registry_flags_wrong_type():
    errors = m.validate_registry({"roots": [{"label": "a", "path": "C:\\a", "dependsOnDocs": "not-a-list"}]})
    assert errors  # dependsOnDocs는 배열이어야 함


def test_validate_registry_flags_bad_enum_and_date_format():
    errors = m.validate_registry({
        "roots": [{"label": "a", "path": "C:\\a", "primarySource": "cloud", "lastReviewed": "2026/08/14"}]
    })
    assert len(errors) == 2  # primarySource enum 위반 + lastReviewed 날짜형식 위반


def test_validate_registry_allows_unknown_extra_fields():
    # 실측: matchToken처럼 main.py가 안 읽는 필드를 외부 스크립트가 쓸 수 있음 — 막지 않는다
    errors = m.validate_registry({"roots": [{"label": "a", "path": "C:\\a", "matchToken": "C:\\a"}]})
    assert errors == []


def test_validate_registry_flags_duplicate_labels():
    """D-043(code-review 발견) — label이 중복되면 router_orchestrator에서
    한쪽 루트가 조용히 사라지는 실제 버그로 이어짐, 스키마 검증이 잡아야 함."""
    errors = m.validate_registry({
        "roots": [
            {"label": "dup", "path": "C:\\a"},
            {"label": "dup", "path": "C:\\b"},
            {"label": "unique", "path": "C:\\c"},
        ]
    })
    assert any("dup" in e and "중복" in e for e in errors)
    assert not any("unique" in e for e in errors)


def test_format_schema_validation_text_ok_and_errors():
    assert "통과" in m.format_schema_validation_text([])
    text = m.format_schema_validation_text(["roots/0: 'path' is a required property"])
    assert "1건" in text and "roots/0" in text


def test_load_registry_raw_missing_file_returns_empty_dict(isolated_registry):
    assert m.load_registry_raw() == {}


def test_load_registry_raw_roundtrips_actual_content(isolated_registry):
    m.save_roots([{"label": "a", "path": "C:\\a"}])
    raw = m.load_registry_raw()
    assert raw["roots"][0]["label"] == "a"
    # load_registry_raw는 setdefault로 채우지 않은 원본 — primarySource 같은
    # load_roots() 전용 기본값이 여기엔 없어야 함(검증이 "빠진 필드"를 봐야 하므로)
    assert "primarySource" not in raw["roots"][0]


def test_management_panel_shows_schema_validation(isolated_registry, isolated_qsettings):
    m.save_roots([{"label": "a", "path": "C:\\a"}])
    panel = m.ManagementPanel()
    assert "통과" in panel.schema_view.toPlainText()


def test_management_panel_shows_keyword_registry(isolated_registry, isolated_qsettings):
    """D-044 — 빈 상태에서도 안내 문구가 뜨는지(크래시 없이)만 확인, 채워진
    상태 렌더링은 test_router_keyword_registry.py의 format 함수 테스트가 커버."""
    m.save_roots([{"label": "a", "path": "C:\\a"}])
    panel = m.ManagementPanel()
    assert "없음" in panel.keyword_registry_view.toPlainText()


# --------------------------------------------------- D-045: 세션 컨텍스트 로그

def test_load_session_context_log_missing_file_returns_empty(tmp_path):
    assert m.load_session_context_log(tmp_path / "no-such.json") == []


def test_format_session_context_log_text_empty_and_recent_first():
    assert "없음" in m.format_session_context_log_text([])
    entries = [
        {"timestamp": "2026-08-14 10:00:00", "matchedLabel": "a", "relatedCount": 0, "otherRootsCount": 4},
        {"timestamp": "2026-08-14 10:05:00", "matchedLabel": "b", "relatedCount": 1, "otherRootsCount": 4},
    ]
    text = m.format_session_context_log_text(entries)
    assert text.index("b") < text.index("a")  # 최신이 위로


def test_management_panel_shows_session_context_log(isolated_registry, isolated_qsettings):
    m.save_roots([{"label": "a", "path": "C:\\a"}])
    panel = m.ManagementPanel()
    assert "없음" in panel.session_context_log_view.toPlainText()


# ---------------------------------------------- D-041(H-003): 대소문자 중복 방지

def test_pick_canonical_index_file_prefers_canonical_casing():
    upper = Path("C:\\proj\\CLAUDE.md")
    lower = Path("C:\\proj\\claude.md")
    assert m.pick_canonical_index_file("claude.md", [lower, upper]) == upper
    assert m.pick_canonical_index_file("claude.md", [upper, lower]) == upper  # 순서 무관


def test_pick_canonical_index_file_falls_back_to_sorted_name_when_no_canonical():
    a = Path("C:\\proj\\Claude.MD")
    b = Path("C:\\proj\\CLAUDE.MD")
    # 어느 쪽도 CANONICAL_INDEX_NAMES("CLAUDE.md")와 정확히 안 맞음 — 사전순 결정
    assert m.pick_canonical_index_file("claude.md", [b, a]) == sorted([a, b], key=lambda p: p.name)[0]


def test_find_index_files_single_file_normal_case(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("x", encoding="utf-8")
    result = m.find_index_files(tmp_path)
    assert result["claude.md"] == tmp_path / "CLAUDE.md"
    assert "readme.md" not in result


def test_find_index_files_prefers_flat_over_dot_claude_subdir(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("flat", encoding="utf-8")
    dot_claude = tmp_path / ".claude"
    dot_claude.mkdir()
    (dot_claude / "CLAUDE.md").write_text("nested", encoding="utf-8")
    result = m.find_index_files(tmp_path)
    assert result["claude.md"] == tmp_path / "CLAUDE.md"


def test_find_index_files_deterministic_on_case_duplicate(tmp_path, monkeypatch):
    """이 환경(Windows)은 대소문자 구분 파일시스템이 아니라 CLAUDE.md/claude.md를
    실제로 동시에 만들 수 없다(그게 바로 H-003의 전제) — iterdir/is_file을 이
    테스트 범위에서만 목업해서, 케이스-센서티브 파일시스템에서 실제로 이 상황이
    발생했을 때의 동작을 회귀 검증한다."""
    upper = tmp_path / "CLAUDE.md"
    lower = tmp_path / "claude.md"

    def fake_iterdir(self):
        if self == tmp_path:
            return iter([lower, upper])  # 일부러 lower를 먼저 — 예전 setdefault 방식이면 lower가 이겼음
        return iter([])

    monkeypatch.setattr(Path, "iterdir", fake_iterdir)
    monkeypatch.setattr(Path, "is_file", lambda self: self in (upper, lower))
    # 이 분기가 실제 사용자 로그 파일(~/.claude/scripts/ssot_explorer.log)에
    # 쓰지 않게 log.warning 자체를 목업(D-025 기존 테스트와 같은 관례).
    monkeypatch.setattr(m.log, "warning", lambda *a, **k: None)

    result = m.find_index_files(tmp_path)
    assert result["claude.md"] == upper


def test_find_index_files_missing_folder_returns_empty(tmp_path):
    assert m.find_index_files(tmp_path / "no-such-folder") == {}


# -------------------------------------------------------------------- D-022: UI

def test_toolbar_icons_resolve(qapp):
    style = qapp.style()
    for sp in (
        QStyle.SP_FileDialogNewFolder, QStyle.SP_TrashIcon, QStyle.SP_BrowserReload,
        QStyle.SP_DialogApplyButton, QStyle.SP_DriveFDIcon, QStyle.SP_FileDialogDetailedView,
    ):
        assert not style.standardIcon(sp).isNull()


def test_ssot_explorer_instantiates_with_expected_shortcuts(isolated_registry, isolated_qsettings):
    win = m.SSOTExplorer()
    try:
        assert win.windowTitle() == "SSOT Explorer"
        assert hasattr(win, "_remove_root_at")
        assert hasattr(win, "on_delete_key")
        shortcuts = [a.shortcut() for a in win.actions()]
        assert QKeySequence("Ctrl+F") in shortcuts
        tree_shortcuts = [a.shortcut() for a in win.tree.actions()]
        from PySide6.QtCore import Qt
        assert QKeySequence(Qt.Key_Delete) in tree_shortcuts
        win.refresh_tree()  # 예외 없어야 함
    finally:
        win.close()  # closeEvent가 isolated_qsettings로 저장 — 실제 레지스트리 안 건드림


# ------------------------------------------------------- D-047: 개발자 탭 승격

def test_management_panel_is_a_persistent_tab(isolated_registry, isolated_qsettings):
    """모달 다이얼로그였다가 상시 탭으로 승격(D-047, 사용자 요청) — 탭
    2개("탐색기"/"개발자")가 항상 존재하고, 개발자 탭 내용이 ManagementPanel
    인스턴스인지 확인."""
    win = m.SSOTExplorer()
    try:
        assert win.tabs.count() == 2
        assert win.tabs.tabText(0) == "탐색기"
        assert win.tabs.tabText(1) == "개발자"
        assert win.tabs.widget(1) is win.management_panel
    finally:
        win.close()


def test_switching_to_developer_tab_refreshes_panel(isolated_registry, isolated_qsettings, monkeypatch):
    """탭을 볼 때마다 최신 상태를 보여줘야 한다(뒤에서 Inbox 감시/라우터가
    계속 데이터를 쌓을 수 있으므로) — refresh()가 실제로 호출되는지."""
    win = m.SSOTExplorer()
    try:
        calls = []
        monkeypatch.setattr(win.management_panel, "refresh", lambda: calls.append(1))
        win.tabs.setCurrentIndex(1)
        assert calls == [1]
    finally:
        win.close()


def test_open_management_switches_to_developer_tab(isolated_registry, isolated_qsettings):
    """툴바 버튼 하위호환 — 이제 모달을 안 열고 탭 전환만 한다."""
    win = m.SSOTExplorer()
    try:
        win.tabs.setCurrentIndex(0)
        win.open_management()
        assert win.tabs.currentWidget() is win.management_panel
    finally:
        win.close()


# ------------------------------------------------------------- D-042: Inbox 감시

def test_toggle_inbox_watcher_starts_and_stops(isolated_registry, isolated_qsettings, tmp_path, monkeypatch):
    win = m.SSOTExplorer()
    try:
        monkeypatch.setattr(m.QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: str(tmp_path)))
        win.toggle_inbox_watcher()
        assert win.inbox_watcher_thread is not None
        assert win.inbox_watch_action.text() == "Inbox 감시 중지"

        win.toggle_inbox_watcher()
        assert win.inbox_watcher_thread is None
        assert win.inbox_watch_action.text() == "Inbox 감시 시작"
    finally:
        win.close()


def test_toggle_inbox_watcher_cancelled_dialog_does_nothing(isolated_registry, isolated_qsettings, monkeypatch):
    win = m.SSOTExplorer()
    try:
        monkeypatch.setattr(m.QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: ""))
        win.toggle_inbox_watcher()
        assert win.inbox_watcher_thread is None
    finally:
        win.close()


def test_on_inbox_file_detected_shows_status_message(isolated_registry, isolated_qsettings):
    win = m.SSOTExplorer()
    try:
        win._on_inbox_file_detected("C:\\inbox", "new.md")
        assert "new.md" in win.statusBar().currentMessage()
    finally:
        win.close()


def test_format_watcher_log_text_empty_and_recent_first():
    assert "없음" in m.format_watcher_log_text([])
    events = [
        {"timestamp": "2026-08-14 10:00:00", "watchDir": "C:\\in", "fileName": "a.md"},
        {"timestamp": "2026-08-14 10:00:05", "watchDir": "C:\\in", "fileName": "b.md"},
    ]
    text = m.format_watcher_log_text(events)
    assert text.index("b.md") < text.index("a.md")  # 최신이 위로


# ----------------------------------------------------------- O-002: 컨텍스트메뉴

def test_context_menu_has_claude_code_launcher_action():
    """정적 소스 확인 — QMenu는 실제로 우클릭 이벤트를 흉내내기보다, 액션과
    커맨드가 소스에 실제로 존재하는지 확인하는 쪽이 이 케이스에선 더 안정적."""
    src = Path(__file__).with_name("main.py").read_text(encoding="utf-8")
    assert 'act_claude = menu.addAction("여기서 Claude Code 실행")' in src
    assert '"cd /d {folder} && claude"' in src


# ------------------------------------------------------------- D-025: 로깅 인프라

def test_logger_is_configured():
    assert isinstance(m.log, logging.Logger)
    assert m.log.name == "ssot_explorer"
    # StreamHandler + FileHandler 둘 다 붙어있어야 함(파일 로그 없인
    # --windowed exe에서 사후진단이 안 됨)
    handler_types = {type(h).__name__ for h in m.log.handlers}
    assert "StreamHandler" in handler_types


def test_install_crash_logging_sets_custom_excepthook():
    original = sys.excepthook
    try:
        m._install_crash_logging()
        assert sys.excepthook is not original
    finally:
        sys.excepthook = original


def test_excepthook_logs_and_shows_dialog_without_blocking(monkeypatch):
    """QMessageBox.critical은 실제로 부르면 모달로 블로킹되므로 mock으로
    대체 — 훅이 로그 기록 + 다이얼로그 호출 둘 다 실제로 하는지만 확인."""
    logged = []
    monkeypatch.setattr(m.log, "error", lambda *a, **k: logged.append((a, k)))
    shown = []
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: shown.append((a, k))))

    original = sys.excepthook
    try:
        m._install_crash_logging()
        try:
            raise ValueError("test-boom")
        except ValueError:
            sys.excepthook(*sys.exc_info())
        assert logged, "미처리 예외가 log.error로 기록돼야 함"
        assert shown, "미처리 예외가 QMessageBox.critical로 사용자에게 보여야 함"
    finally:
        sys.excepthook = original


# ------------------------------------------------------- D-028: 관계 + 전체탐색기

def test_get_available_drives_includes_current_drive():
    drives = m.get_available_drives()
    current_drive = Path(__file__).drive + "\\"  # 예: "C:\\"
    assert current_drive in drives


def test_is_or_under_matches_equal_and_descendant_but_not_unrelated():
    base = Path("C:\\a\\b")
    assert m._is_or_under(base, base)  # 자기 자신
    assert m._is_or_under(Path("C:\\a\\b\\c"), base)  # 하위
    assert not m._is_or_under(Path("C:\\a\\x"), base)  # 무관
    assert not m._is_or_under(Path("C:\\a"), base)  # 상위(반대 방향은 매치 안 함)


def test_find_relations_for_path_matches_from_side():
    relations = [{"fromPath": "C:\\x", "toPath": "C:\\y", "reason": "테스트", "bidirectional": True}]
    matches = m.find_relations_for_path(Path("C:\\x\\sub"), relations)
    assert len(matches) == 1
    assert matches[0]["otherPath"] == "C:\\y"
    assert matches[0]["direction"] == "from"


def test_find_relations_for_path_matches_to_side_when_bidirectional():
    relations = [{"fromPath": "C:\\x", "toPath": "C:\\y", "reason": "테스트", "bidirectional": True}]
    matches = m.find_relations_for_path(Path("C:\\y"), relations)
    assert len(matches) == 1
    assert matches[0]["otherPath"] == "C:\\x"
    assert matches[0]["direction"] == "to"


def test_find_relations_for_path_ignores_to_side_when_not_bidirectional():
    relations = [{"fromPath": "C:\\x", "toPath": "C:\\y", "reason": "단방향", "bidirectional": False}]
    assert m.find_relations_for_path(Path("C:\\y"), relations) == []
    assert len(m.find_relations_for_path(Path("C:\\x"), relations)) == 1


def test_find_relations_for_path_no_match_returns_empty():
    relations = [{"fromPath": "C:\\x", "toPath": "C:\\y", "reason": "테스트", "bidirectional": True}]
    assert m.find_relations_for_path(Path("C:\\completely\\unrelated"), relations) == []


def test_load_relations_defaults_bidirectional_true(isolated_registry):
    isolated_registry.write_text(
        json.dumps({
            "roots": [],
            "relations": [{"fromPath": "C:\\x", "toPath": "C:\\y", "reason": "필드 생략 테스트"}],
        }),
        encoding="utf-8",
    )
    m._LAST_KNOWN_HASH = m._hash_bytes(isolated_registry.read_bytes())
    relations = m.load_relations()
    assert relations[0]["bidirectional"] is True


def test_save_roots_preserves_relations(isolated_registry):
    """D-020 sharedDocs 보존 회귀와 같은 패턴 — relations도 roots만 저장할 때
    같이 사라지면 안 됨."""
    isolated_registry.write_text(
        json.dumps({
            "roots": [],
            "relations": [{"fromPath": "C:\\x", "toPath": "C:\\y", "reason": "보존 확인용"}],
        }),
        encoding="utf-8",
    )
    m._LAST_KNOWN_HASH = m._hash_bytes(isolated_registry.read_bytes())
    m.save_roots([{"label": "a", "path": "C:\\a"}])
    payload = json.loads(isolated_registry.read_text(encoding="utf-8"))
    assert payload["relations"] == [{"fromPath": "C:\\x", "toPath": "C:\\y", "reason": "보존 확인용"}]


def test_populate_roots_adds_drive_section_without_crashing_reveal(isolated_registry, isolated_qsettings):
    """구분선(경로데이터 없음)이 섞여도 reveal_path가 안 죽는지 — D-028 도입
    중 실제로 발견해서 고친 버그의 회귀 테스트."""
    win = m.SSOTExplorer()
    try:
        # 등록된 루트 0개 + 구분선 1개 + 드라이브 N개가 최상위에 있어야 함
        assert win.tree.topLevelItemCount() >= 2
        # 존재하지 않는 경로라 실제로 못 찾지만, 예외 없이 조용히 리턴돼야 함
        win.reveal_path("C:\\definitely-does-not-exist-xyz")
    finally:
        win.close()


def test_update_relations_panel_shows_and_hides(isolated_registry, isolated_qsettings, monkeypatch):
    monkeypatch.setattr(
        m, "load_relations",
        lambda: [{"fromPath": "C:\\x", "toPath": "C:\\y", "reason": "패널 테스트", "bidirectional": True}],
    )
    win = m.SSOTExplorer()
    win.show()  # isVisible()은 실제로 show()된 창이어야 의미 있게 반영됨
    try:
        win.update_relations_panel(Path("C:\\x\\sub"))
        assert win.relations_list.isVisible()
        assert win.relations_list.count() == 1
        assert win.relations_list.item(0).data(Qt.UserRole) == "C:\\y"

        win.update_relations_panel(Path("C:\\completely\\unrelated"))
        assert not win.relations_list.isVisible()
        assert win.relations_list.count() == 0
    finally:
        win.close()


# --------------------------------------------------- D-029: 새 문서 저장(라우터)

def _run_classification_sync(dlg):
    """D-051(H-008) — run_classification()이 이제 QThread 배경작업(D-013
    SearchWorker와 같은 패턴)이라, 테스트에서는 워커가 끝나길 기다린 뒤
    큐잉된 result_ready 신호를 processEvents()로 직접 배달해야 dlg.
    candidates에 결과가 반영된다(그래야 기존 동기 호출 시절과 같은
    어서션을 그대로 쓸 수 있음)."""
    dlg.run_classification()
    dlg.worker.wait()
    QApplication.processEvents()


def test_save_document_dialog_run_classification_populates_candidates(tmp_path):
    root_dir = tmp_path / "flutter_App"
    root_dir.mkdir()
    roots = [{"label": "flutter_App", "path": str(root_dir), "scope": "플러터 앱 개발", "referenceCondition": ""}]
    dlg = m.SaveDocumentDialog(roots)
    try:
        dlg.content_edit.setPlainText("플러터 앱 개발 관련 메모")
        _run_classification_sync(dlg)
        assert dlg.candidates_list.count() == 1
        assert dlg.candidates[0]["rootLabel"] == "flutter_App"
    finally:
        dlg.close()


def test_run_classification_does_not_block_ui_thread(tmp_path):
    """D-051(H-008) 핵심 회귀 — run_classification() 호출 직후(워커가 아직
    안 끝났을 시점)엔 결과가 비어있고 버튼이 비활성화 상태여야 진짜로
    배경 스레드에서 도는 것. 이 어서션이 없으면 실수로 다시 동기 호출로
    되돌려도(H-008 재발) 다른 테스트들은 processEvents()가 어차피 결과를
    채워줘서 못 잡는다."""
    root_dir = tmp_path / "flutter_App"
    root_dir.mkdir()
    roots = [{"label": "flutter_App", "path": str(root_dir), "scope": "플러터 앱 개발", "referenceCondition": ""}]
    dlg = m.SaveDocumentDialog(roots)
    try:
        dlg.content_edit.setPlainText("플러터 앱 개발 관련 메모")
        dlg.run_classification()
        assert dlg.worker is not None
        assert dlg.candidates == []  # 워커가 아직 결과를 emit 안 함
        assert dlg.classify_btn.isEnabled() is False
        assert "분류 중" in dlg.status_label.text()

        dlg.worker.wait()
        QApplication.processEvents()
        assert dlg.candidates_list.count() == 1
        assert dlg.classify_btn.isEnabled() is True
    finally:
        dlg.close()


def test_reject_while_classification_running_does_not_crash(tmp_path):
    """워커가 아직 도는 중에 다이얼로그를 닫아도(X버튼/취소) 이미 파괴된
    위젯에 신호가 배달되며 죽지 않아야 한다 — _stop_worker()가 신호를
    먼저 끊고 기다리는지 실측."""
    root_dir = tmp_path / "flutter_App"
    root_dir.mkdir()
    roots = [{"label": "flutter_App", "path": str(root_dir), "scope": "플러터 앱 개발", "referenceCondition": ""}]
    dlg = m.SaveDocumentDialog(roots)
    dlg.content_edit.setPlainText("플러터 앱 개발 관련 메모")
    dlg.run_classification()
    dlg.reject()  # 워커가 아직 도는 중일 가능성 높음(kiwipiepy 콜드인잇 ~1.4초)
    assert dlg.worker.isRunning() is False  # _stop_worker()가 끝날 때까지 기다렸어야 함


def test_save_document_dialog_no_candidates_shows_hint(tmp_path):
    root_dir = tmp_path / "x"
    root_dir.mkdir()
    roots = [{"label": "x", "path": str(root_dir), "scope": "전혀다른주제", "referenceCondition": ""}]
    dlg = m.SaveDocumentDialog(roots)
    try:
        # D-033/D-034: 명사가 4개 이상은 있어야 needs_clarification(너무
        # 짧음) 분기로 안 새고, 등록 루트와는 진짜 무관한 실제 단어 문장.
        dlg.content_edit.setPlainText("고양이와 강아지와 물고기와 새와 토끼 이야기")
        _run_classification_sync(dlg)
        assert dlg.candidates_list.count() == 0
        assert "후보가 없습니다" in dlg.status_label.text()
    finally:
        dlg.close()


def test_save_document_dialog_save_writes_file_and_records_approved(tmp_path, monkeypatch):
    # QMessageBox.information은 실제로 부르면 모달로 블로킹된다 — mock 필수
    # (D-025에서 이미 겪은 것과 같은 함정, 여기서도 빠뜨렸다가 테스트가
    # 멈춰서 발견하고 고침).
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    root_dir = tmp_path / "flutter_App"
    root_dir.mkdir()
    roots = [{"label": "flutter_App", "path": str(root_dir), "scope": "플러터 앱 개발", "referenceCondition": ""}]
    dlg = m.SaveDocumentDialog(roots)
    try:
        dlg.content_edit.setPlainText("플러터 앱 개발 메모 내용")
        _run_classification_sync(dlg)
        dlg.candidates_list.setCurrentRow(0)
        dlg.filename_edit.setText("메모.md")
        dlg.save_to_selected()

        saved_file = root_dir / "메모.md"
        assert saved_file.exists()
        assert saved_file.read_text(encoding="utf-8") == "플러터 앱 개발 메모 내용"

        proposals = router_proposals.load_proposals()
        assert len(proposals) == 1
        assert proposals[0]["decision"] == "approved"
        assert proposals[0]["rootLabel"] == "flutter_App"
    finally:
        dlg.close()


def test_save_document_dialog_save_uses_live_text_after_edit(tmp_path, monkeypatch):
    """D-043(code-review 발견) — 분류 제안을 본 뒤 내용을 더 고치면, 저장은
    화면에 지금 보이는 내용을 써야 한다(예전엔 분류 시점 스냅샷을 써서
    수정분이 조용히 사라졌음)."""
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    root_dir = tmp_path / "flutter_App"
    root_dir.mkdir()
    roots = [{"label": "flutter_App", "path": str(root_dir), "scope": "플러터 앱 개발", "referenceCondition": ""}]
    dlg = m.SaveDocumentDialog(roots)
    try:
        dlg.content_edit.setPlainText("플러터 앱 개발 메모 초안")
        _run_classification_sync(dlg)
        dlg.candidates_list.setCurrentRow(0)
        dlg.content_edit.setPlainText("플러터 앱 개발 메모 — 수정된 최종본")  # 분류 후 추가 편집
        dlg.filename_edit.setText("메모.md")
        dlg.save_to_selected()

        saved_file = root_dir / "메모.md"
        assert saved_file.read_text(encoding="utf-8") == "플러터 앱 개발 메모 — 수정된 최종본"
    finally:
        dlg.close()


def test_save_document_dialog_rejects_path_traversal_filename(tmp_path):
    """D-043(code-review 발견) — 파일명에 '..'나 절대경로가 섞이면 등록된
    루트 밖에 쓰기가 새는 결함이었음(Path(root)/filename이 절대경로 우변을
    그대로 채택). 지금은 거절하고 아무것도 안 써야 한다."""
    root_dir = tmp_path / "flutter_App"
    root_dir.mkdir()
    outside_target = tmp_path / "evil.md"
    roots = [{"label": "flutter_App", "path": str(root_dir), "scope": "플러터 앱 개발", "referenceCondition": ""}]
    dlg = m.SaveDocumentDialog(roots)
    try:
        dlg.content_edit.setPlainText("플러터 앱 개발 메모")
        _run_classification_sync(dlg)
        dlg.candidates_list.setCurrentRow(0)

        dlg.filename_edit.setText("../evil.md")
        dlg.save_to_selected()
        assert not outside_target.exists()
        assert "루트" in dlg.status_label.text() or "절대경로" in dlg.status_label.text()

        dlg.filename_edit.setText(str(outside_target))  # 절대경로 자체
        dlg.save_to_selected()
        assert not outside_target.exists()
    finally:
        dlg.close()


def test_save_document_dialog_save_without_selection_shows_warning(tmp_path):
    roots = [{"label": "x", "path": str(tmp_path), "scope": "", "referenceCondition": ""}]
    dlg = m.SaveDocumentDialog(roots)
    try:
        dlg.save_to_selected()
        assert "먼저" in dlg.status_label.text()
        assert router_proposals.load_proposals() == []
    finally:
        dlg.close()


def test_save_document_dialog_cancel_after_classification_records_cancelled(tmp_path):
    root_dir = tmp_path / "flutter_App"
    root_dir.mkdir()
    roots = [{"label": "flutter_App", "path": str(root_dir), "scope": "플러터 앱 개발", "referenceCondition": ""}]
    dlg = m.SaveDocumentDialog(roots)
    dlg.content_edit.setPlainText("플러터 앱 개발 메모")
    _run_classification_sync(dlg)
    dlg.cancel_and_close()  # reject() 호출 — 다이얼로그는 이 시점에 이미 닫힘

    proposals = router_proposals.load_proposals()
    assert len(proposals) == 1
    assert proposals[0]["decision"] == "cancelled"
    assert (root_dir / "메모.md").exists() is False  # 파일은 절대 안 써짐


def test_save_document_dialog_cancel_without_classification_records_nothing():
    roots = [{"label": "x", "path": "C:\\x", "scope": "", "referenceCondition": ""}]
    dlg = m.SaveDocumentDialog(roots)
    dlg.cancel_and_close()
    assert router_proposals.load_proposals() == []


def test_toolbar_has_save_document_action(isolated_qsettings):
    win = m.SSOTExplorer()
    try:
        assert hasattr(win, "open_save_document_dialog")
        toolbar_actions = [a for tb in win.findChildren(m.QToolBar) for a in tb.actions()]
        assert any(a.text() == "새 문서 저장" for a in toolbar_actions)
    finally:
        win.close()


# --------------------------------------------------- D-031: 루트 자동 init

def _wait_for_root_init(win):
    """H-009 — _ensure_all_roots_initialized()가 이제 RootInitWorker
    (QThread) 배경작업이라(run_classification과 동일 패턴, D-051 참고),
    __init__ 직후엔 아직 파일이 안 써져 있을 수 있다. 워커가 끝나길
    기다린 뒤 큐잉된 done 신호를 processEvents()로 배달해야 기존 동기
    호출 시절과 같은 어서션을 그대로 쓸 수 있다."""
    win.root_init_worker.wait()
    QApplication.processEvents()


def test_ensure_all_roots_initialized_creates_missing_claude_md(tmp_path, isolated_registry, isolated_qsettings):
    root_dir = tmp_path / "missing_init_root"
    root_dir.mkdir()
    m.save_roots([{"label": "missing_init_root", "path": str(root_dir), "referenceCondition": ""}])

    win = m.SSOTExplorer()  # __init__이 _ensure_all_roots_initialized()를 호출
    try:
        _wait_for_root_init(win)
        claude_path = root_dir / "CLAUDE.md"
        assert claude_path.exists()
        assert m.SYNC_MARKER in claude_path.read_text(encoding="utf-8")
    finally:
        win.close()


def test_ensure_all_roots_initialized_does_not_touch_existing_file(tmp_path, isolated_registry, isolated_qsettings):
    root_dir = tmp_path / "already_has_init"
    root_dir.mkdir()
    existing_content = "# 손으로 쓴 내용 — 절대 안 건드려야 함"
    (root_dir / "CLAUDE.md").write_text(existing_content, encoding="utf-8")
    m.save_roots([{"label": "already_has_init", "path": str(root_dir), "referenceCondition": ""}])

    win = m.SSOTExplorer()
    try:
        _wait_for_root_init(win)
        assert (root_dir / "CLAUDE.md").read_text(encoding="utf-8") == existing_content
    finally:
        win.close()


def test_ensure_all_roots_initialized_skips_nonexistent_path(isolated_registry, isolated_qsettings):
    m.save_roots([{"label": "gone", "path": "C:\\definitely-does-not-exist-xyz", "referenceCondition": ""}])
    win = m.SSOTExplorer()  # 예외 없이 조용히 건너뛰어야 함
    _wait_for_root_init(win)
    win.close()


def test_ensure_all_roots_initialized_does_not_block_ui_thread(tmp_path, isolated_registry, isolated_qsettings):
    """H-009 핵심 회귀 — __init__ 반환 직후(워커가 아직 안 끝났을 수 있는
    시점)엔 root_init_worker가 QThread 인스턴스로 존재해야 진짜로 배경
    스레드에서 도는 것(H-008의 run_classification 회귀 테스트와 동일한
    발상). 이 어서션이 없으면 실수로 다시 동기 호출로 되돌려도 다른
    테스트들은 processEvents()가 어차피 결과를 채워줘서 못 잡는다."""
    root_dir = tmp_path / "missing_init_root"
    root_dir.mkdir()
    m.save_roots([{"label": "missing_init_root", "path": str(root_dir), "referenceCondition": ""}])

    win = m.SSOTExplorer()
    try:
        assert isinstance(win.root_init_worker, m.RootInitWorker)
        _wait_for_root_init(win)
        assert (root_dir / "CLAUDE.md").exists()
    finally:
        win.close()

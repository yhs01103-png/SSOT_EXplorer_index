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


# ---------------------------------------------------------- 기타 순수 로직 함수

def test_review_age_days_handles_missing_and_bad_format():
    assert m.review_age_days({}) is None
    assert m.review_age_days({"lastReviewed": "not-a-date"}) is None
    assert m.review_age_days({"lastReviewed": "2020-01-01"}) is not None


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

def test_save_document_dialog_run_classification_populates_candidates(tmp_path):
    root_dir = tmp_path / "flutter_App"
    root_dir.mkdir()
    roots = [{"label": "flutter_App", "path": str(root_dir), "scope": "플러터 앱 개발", "referenceCondition": ""}]
    dlg = m.SaveDocumentDialog(roots)
    try:
        dlg.content_edit.setPlainText("플러터 앱 개발 관련 메모")
        dlg.run_classification()
        assert dlg.candidates_list.count() == 1
        assert dlg.candidates[0]["rootLabel"] == "flutter_App"
    finally:
        dlg.close()


def test_save_document_dialog_no_candidates_shows_hint(tmp_path):
    root_dir = tmp_path / "x"
    root_dir.mkdir()
    roots = [{"label": "x", "path": str(root_dir), "scope": "전혀다른주제", "referenceCondition": ""}]
    dlg = m.SaveDocumentDialog(roots)
    try:
        # D-033: "내용"이 불용어라 짧은 문구엔 못 씀(needs_clarification
        # 분기로 새서 테스트 의도가 흐려짐) — 충분히 길고 구체적인, 그러나
        # 등록 루트와는 진짜 무관한 문장으로 바꿈.
        dlg.content_edit.setPlainText("겹치지 않는 완전히 별개인 임의의 낯선 주제입니다")
        dlg.run_classification()
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
        dlg.run_classification()
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
    dlg.run_classification()
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

def test_ensure_all_roots_initialized_creates_missing_claude_md(tmp_path, isolated_registry, isolated_qsettings):
    root_dir = tmp_path / "missing_init_root"
    root_dir.mkdir()
    m.save_roots([{"label": "missing_init_root", "path": str(root_dir), "referenceCondition": ""}])

    win = m.SSOTExplorer()  # __init__이 _ensure_all_roots_initialized()를 호출
    try:
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
        assert (root_dir / "CLAUDE.md").read_text(encoding="utf-8") == existing_content
    finally:
        win.close()


def test_ensure_all_roots_initialized_skips_nonexistent_path(isolated_registry, isolated_qsettings):
    m.save_roots([{"label": "gone", "path": "C:\\definitely-does-not-exist-xyz", "referenceCondition": ""}])
    win = m.SSOTExplorer()  # 예외 없이 조용히 건너뛰어야 함
    win.close()

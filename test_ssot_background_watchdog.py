"""D-088 — ssot_background_watchdog.py 테스트. GUI/mcp 어느 쪽 픽스처도
필요 없다(PySide6/mcp SDK 둘 다 안 씀) — tmp_path 격리 레지스트리로 순수하게
검증."""
from __future__ import annotations

import pytest

import router_registry as rr
import ssot_background_watchdog as watchdog


@pytest.fixture(autouse=True)
def isolated_folder_snapshot(tmp_path, monkeypatch):
    """2026-09-04 — `_scan()`이 루트마다 매번 router_registry.
    save_folder_snapshot()을 호출한다(D-0XX, 하위 폴더 README 추적).
    실제 사용자 파일(~/.claude/scripts/ssot_folder_snapshots.json)을 절대
    안 건드리게 이 파일의 모든 테스트에 기본 격리 — 개별 테스트가 다시
    patch해도 같은 tmp_path 기반이라 무해하다."""
    monkeypatch.setattr(rr, "FOLDER_SNAPSHOT_PATH", tmp_path / "folder-snapshots.json")


def test_scan_and_queue_flags_missing_root_path(tmp_path):
    registry_path = tmp_path / "ssot-roots.json"
    rr.add_root({"label": "a", "path": str(tmp_path / "does-not-exist")}, registry_path)

    notices = watchdog.scan_and_queue(registry_path)

    assert len(notices) == 1
    assert "a" in notices[0]
    pending = rr.load_pending_actions(registry_path)
    assert pending[0]["targetType"] == "root"
    assert pending[0]["targetLabel"] == "a"
    assert pending[0]["actionType"] == "fix_path"


def test_scan_and_queue_flags_root_missing_readme(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    registry_path = tmp_path / "ssot-roots.json"
    rr.add_root({"label": "a", "path": str(root)}, registry_path)

    watchdog.scan_and_queue(registry_path)

    pending = rr.load_pending_actions(registry_path)
    assert pending[0]["actionType"] == "create_readme"


def test_scan_and_queue_flags_stale_root_readme(tmp_path):
    import os
    import time

    root = tmp_path / "root"
    root.mkdir()
    readme = root / "README.md"
    readme.write_text("old", encoding="utf-8")
    other = root / "other.txt"
    other.write_text("new", encoding="utf-8")
    old_time = time.time() - 40 * 86400
    os.utime(readme, (old_time, old_time))
    registry_path = tmp_path / "ssot-roots.json"
    rr.add_root({"label": "a", "path": str(root)}, registry_path)

    watchdog.scan_and_queue(registry_path)

    pending = rr.load_pending_actions(registry_path)
    assert pending[0]["actionType"] == "modify_readme"


def test_scan_and_queue_fresh_root_queues_nothing(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    # 2026-09-03 — roots[]도 SSOT-LABEL 마커까지 검사하도록 확장됐으므로
    # (labeledFolders[]와 동일 검사), "아무 문제도 없는" fixture는 마커도
    # 라벨과 일치해야 한다.
    (root / "README.md").write_text("<!-- SSOT-LABEL: a -->\n\nfresh", encoding="utf-8")
    registry_path = tmp_path / "ssot-roots.json"
    rr.add_root({"label": "a", "path": str(root)}, registry_path)

    notices = watchdog.scan_and_queue(registry_path)

    assert notices == []
    assert rr.load_pending_actions(registry_path) == []


def test_scan_and_queue_root_label_marker_mismatch_queues_modify_readme(tmp_path):
    """roots[]도 labeledFolders[]와 동일하게 SSOT-LABEL 마커 불일치를
    잡아야 한다(2026-09-03 확장) — README가 "수정"돼 다른 라벨을 자기선언
    하게 된 경우의 재현."""
    root = tmp_path / "root"
    root.mkdir()
    (root / "README.md").write_text("<!-- SSOT-LABEL: wrong-label -->\n\nbody", encoding="utf-8")
    registry_path = tmp_path / "ssot-roots.json"
    rr.add_root({"label": "a", "path": str(root)}, registry_path)

    notices = watchdog.scan_and_queue(registry_path)

    assert len(notices) == 1
    assert "SSOT-LABEL" in notices[0]
    pending = rr.load_pending_actions(registry_path)
    assert len(pending) == 1
    assert pending[0]["targetType"] == "root"
    assert pending[0]["actionType"] == "modify_readme"


def test_scan_and_queue_flags_labeled_folder_missing_path(tmp_path):
    registry_path = tmp_path / "ssot-roots.json"
    rr.add_labeled_folder({"label": "b", "path": str(tmp_path / "gone")}, registry_path)

    watchdog.scan_and_queue(registry_path)

    pending = rr.load_pending_actions(registry_path)
    assert pending[0]["targetType"] == "labeledFolder"
    assert pending[0]["actionType"] == "fix_path"


def test_scan_and_queue_flags_labeled_folder_missing_readme(tmp_path):
    folder = tmp_path / "folder"
    folder.mkdir()
    registry_path = tmp_path / "ssot-roots.json"
    rr.add_labeled_folder({"label": "b", "path": str(folder)}, registry_path)

    watchdog.scan_and_queue(registry_path)

    pending = rr.load_pending_actions(registry_path)
    assert pending[0]["actionType"] == "create_readme"


def test_scan_and_queue_flags_labeled_folder_marker_mismatch(tmp_path):
    folder = tmp_path / "folder"
    folder.mkdir()
    (folder / "README.md").write_text("<!-- SSOT-LABEL: wrong -->\n", encoding="utf-8")
    registry_path = tmp_path / "ssot-roots.json"
    rr.add_labeled_folder({"label": "b", "path": str(folder)}, registry_path)

    watchdog.scan_and_queue(registry_path)

    pending = rr.load_pending_actions(registry_path)
    assert pending[0]["actionType"] == "modify_readme"
    assert "wrong" in pending[0]["note"]


def test_scan_and_queue_matching_marker_queues_nothing(tmp_path):
    folder = tmp_path / "folder"
    folder.mkdir()
    (folder / "README.md").write_text("<!-- SSOT-LABEL: b -->\n", encoding="utf-8")
    registry_path = tmp_path / "ssot-roots.json"
    rr.add_labeled_folder({"label": "b", "path": str(folder)}, registry_path)

    notices = watchdog.scan_and_queue(registry_path)

    assert notices == []


def test_scan_and_queue_does_not_duplicate_already_queued_request(tmp_path):
    registry_path = tmp_path / "ssot-roots.json"
    rr.add_root({"label": "a", "path": str(tmp_path / "gone")}, registry_path)

    first = watchdog.scan_and_queue(registry_path)
    second = watchdog.scan_and_queue(registry_path)

    assert len(first) == 1
    assert second == []  # 이미 큐에 있으니 두 번째 스캔은 새로 안 쌓음
    assert len(rr.load_pending_actions(registry_path)) == 1


def test_scan_and_queue_skips_when_developer_mode_off(tmp_path):
    import router_proposals as rp

    registry_path = tmp_path / "ssot-roots.json"
    rr.add_root({"label": "a", "path": str(tmp_path / "gone")}, registry_path)
    rp.set_developer_mode(False, registry_path)

    notices = watchdog.scan_and_queue(registry_path)

    assert notices == []
    assert rr.load_pending_actions(registry_path) == []


def test_send_toast_raises_clear_error_when_win11toast_missing(monkeypatch):
    """win11toast는 선택적 의존성 - 미설치 환경(이 테스트 환경 포함)에서
    ImportError를 감춰서 명확한 예외로 재던지는지 확인(EmbeddingProvider
    NotConfigured와 동일한 스켈레톤 패턴)."""
    try:
        import win11toast  # noqa: F401
    except ImportError:
        pass
    else:
        pytest.skip("win11toast가 설치돼 있어 이 회귀 테스트 대상이 아님")
    try:
        watchdog.send_toast("t", "b")
        raise AssertionError("should have raised")
    except watchdog.ToastProviderNotConfigured:
        pass


def test_main_skips_toast_gracefully_when_nothing_found(tmp_path, monkeypatch):
    """main()이 새로 발견된 문제가 없을 때 토스트 시도 자체를 안 하는지 —
    빈 레지스트리(등록된 것 없음)로 스모크."""
    registry_path = tmp_path / "ssot-roots.json"
    log_path = tmp_path / "ssot_watchdog_log.json"
    monkeypatch.setenv("SSOT_REGISTRY_PATH", str(registry_path))
    monkeypatch.setattr(watchdog, "WATCHDOG_LOG_PATH", log_path)
    watchdog.main()  # 예외 없이 종료되면 통과


# --------------------------------------------------- 근거(evidence) + 실행 로그

def test_scan_records_evidence_for_missing_path(tmp_path):
    registry_path = tmp_path / "ssot-roots.json"
    missing = tmp_path / "gone"
    rr.add_root({"label": "a", "path": str(missing)}, registry_path)

    findings = watchdog._scan(registry_path)

    assert findings[0]["evidence"] == {"checkedPath": str(missing)}
    assert findings[0]["requestId"]  # add_pending_action이 실제로 발급한 id


def test_scan_records_evidence_for_stale_readme(tmp_path):
    import os
    import time

    root = tmp_path / "root"
    root.mkdir()
    readme = root / "README.md"
    readme.write_text("old", encoding="utf-8")
    (root / "other.txt").write_text("new", encoding="utf-8")
    old_time = time.time() - 40 * 86400
    os.utime(readme, (old_time, old_time))
    registry_path = tmp_path / "ssot-roots.json"
    rr.add_root({"label": "a", "path": str(root)}, registry_path)

    findings = watchdog._scan(registry_path)

    ev = findings[0]["evidence"]
    assert ev["staleThresholdDays"] == watchdog.README_STALE_DAYS
    assert ev["gapDays"] > watchdog.README_STALE_DAYS
    assert ev["readmePath"] == str(readme)


def test_scan_records_evidence_for_marker_mismatch(tmp_path):
    folder = tmp_path / "folder"
    folder.mkdir()
    (folder / "README.md").write_text("<!-- SSOT-LABEL: wrong -->\n", encoding="utf-8")
    registry_path = tmp_path / "ssot-roots.json"
    rr.add_labeled_folder({"label": "b", "path": str(folder)}, registry_path)

    findings = watchdog._scan(registry_path)

    ev = findings[0]["evidence"]
    assert ev == {
        "readmePath": str(folder / "README.md"),
        "expectedLabel": "b",
        "markerFound": "wrong",
    }


def test_scan_and_queue_does_not_write_watchdog_log(tmp_path, monkeypatch):
    """scan_and_queue()는 요약 문자열만 반환 — 로그는 main() 경로에서만
    쌓인다(단독 호출/테스트마다 로그 파일이 안 늘어나야 함)."""
    log_path = tmp_path / "ssot_watchdog_log.json"
    monkeypatch.setattr(watchdog, "WATCHDOG_LOG_PATH", log_path)
    registry_path = tmp_path / "ssot-roots.json"
    rr.add_root({"label": "a", "path": str(tmp_path / "gone")}, registry_path)

    watchdog.scan_and_queue(registry_path)

    assert not log_path.exists()


def test_main_logs_run_with_findings_and_evidence(tmp_path, monkeypatch):
    """send_toast 자체를 몽키패치해서(no-op) 실제 OS 토스트가 안 뜨게 하고,
    toastFired=True가 로그에 정확히 기록되는지 확인 — 이 테스트 환경에
    win11toast가 실제로 설치돼 있는지 여부와 무관하게 결정적이어야 함."""
    registry_path = tmp_path / "ssot-roots.json"
    log_path = tmp_path / "ssot_watchdog_log.json"
    missing = tmp_path / "gone"
    rr.add_root({"label": "a", "path": str(missing)}, registry_path)
    monkeypatch.setenv("SSOT_REGISTRY_PATH", str(registry_path))
    monkeypatch.setattr(watchdog, "WATCHDOG_LOG_PATH", log_path)
    monkeypatch.setattr(watchdog, "send_toast", lambda title, body: None)

    watchdog.main()

    runs = watchdog.load_watchdog_log(log_path)
    assert len(runs) == 1
    run = runs[0]
    assert run["checkedRoots"] == 1
    assert run["checkedLabeledFolders"] == 0
    assert run["newFindingsCount"] == 1
    assert run["findings"][0]["evidence"] == {"checkedPath": str(missing)}
    assert run["toastFired"] is True


def test_main_logs_toast_fired_false_when_toast_provider_missing(tmp_path, monkeypatch):
    registry_path = tmp_path / "ssot-roots.json"
    log_path = tmp_path / "ssot_watchdog_log.json"
    rr.add_root({"label": "a", "path": str(tmp_path / "gone")}, registry_path)
    monkeypatch.setenv("SSOT_REGISTRY_PATH", str(registry_path))
    monkeypatch.setattr(watchdog, "WATCHDOG_LOG_PATH", log_path)

    def _raise(title, body):
        raise watchdog.ToastProviderNotConfigured("test")

    monkeypatch.setattr(watchdog, "send_toast", _raise)

    watchdog.main()

    runs = watchdog.load_watchdog_log(log_path)
    assert runs[0]["toastFired"] is False
    assert runs[0]["newFindingsCount"] == 1


def test_main_logs_run_even_when_nothing_found(tmp_path, monkeypatch):
    """알림이 안 뜨는 조용한 실행도 로그에는 남아야 한다 — "워치독이 최근에
    실제로 돌긴 했다"를 확인할 유일한 방법."""
    registry_path = tmp_path / "ssot-roots.json"
    log_path = tmp_path / "ssot_watchdog_log.json"
    monkeypatch.setenv("SSOT_REGISTRY_PATH", str(registry_path))
    monkeypatch.setattr(watchdog, "WATCHDOG_LOG_PATH", log_path)

    watchdog.main()

    runs = watchdog.load_watchdog_log(log_path)
    assert len(runs) == 1
    assert runs[0]["findings"] == []
    assert runs[0]["toastFired"] is False


def test_load_watchdog_log_empty_when_missing_file(tmp_path):
    assert watchdog.load_watchdog_log(tmp_path / "no-such-file.json") == []


# ------------------------------------- 하위 폴더 README 추적(2026-09-04, D-0XX)

def test_scan_and_queue_flags_subfolder_missing_readme(tmp_path, monkeypatch):
    snapshot_path = tmp_path / "snapshots.json"
    monkeypatch.setattr(rr, "FOLDER_SNAPSHOT_PATH", snapshot_path)
    root = tmp_path / "root"
    (root / "sub").mkdir(parents=True)
    (root / "README.md").write_text("<!-- SSOT-LABEL: a -->\n", encoding="utf-8")
    registry_path = tmp_path / "ssot-roots.json"
    rr.add_root({"label": "a", "path": str(root)}, registry_path)

    notices = watchdog.scan_and_queue(registry_path)

    pending = rr.load_pending_actions(registry_path)
    subfolder_actions = [p for p in pending if p["targetType"] == "subfolder"]
    assert len(subfolder_actions) == 1
    assert subfolder_actions[0]["targetLabel"] == "a:sub"
    assert subfolder_actions[0]["actionType"] == "create_readme"
    assert any("sub" in n for n in notices)


def test_scan_and_queue_flags_subfolder_readme_deleted(tmp_path, monkeypatch):
    snapshot_path = tmp_path / "snapshots.json"
    monkeypatch.setattr(rr, "FOLDER_SNAPSHOT_PATH", snapshot_path)
    root = tmp_path / "root"
    (root / "sub").mkdir(parents=True)
    (root / "sub" / "README.md").write_text("x", encoding="utf-8")
    (root / "README.md").write_text("<!-- SSOT-LABEL: a -->\n", encoding="utf-8")
    registry_path = tmp_path / "ssot-roots.json"
    rr.add_root({"label": "a", "path": str(root)}, registry_path)

    # 첫 스캔 — 정상, 스냅샷에 sub=True로 기록됨
    first = watchdog.scan_and_queue(registry_path)
    assert first == []

    # sub의 README가 사라짐
    (root / "sub" / "README.md").unlink()
    second = watchdog.scan_and_queue(registry_path)

    pending = rr.load_pending_actions(registry_path)
    subfolder_actions = [p for p in pending if p["targetType"] == "subfolder"]
    assert len(subfolder_actions) == 1
    assert subfolder_actions[0]["actionType"] == "readme_deleted"
    assert any("사라짐" in n for n in second)


def test_scan_and_queue_subfolder_with_readme_queues_nothing(tmp_path, monkeypatch):
    snapshot_path = tmp_path / "snapshots.json"
    monkeypatch.setattr(rr, "FOLDER_SNAPSHOT_PATH", snapshot_path)
    root = tmp_path / "root"
    (root / "sub").mkdir(parents=True)
    (root / "sub" / "README.md").write_text("x", encoding="utf-8")
    (root / "README.md").write_text("<!-- SSOT-LABEL: a -->\n", encoding="utf-8")
    registry_path = tmp_path / "ssot-roots.json"
    rr.add_root({"label": "a", "path": str(root)}, registry_path)

    notices = watchdog.scan_and_queue(registry_path)

    assert notices == []


def test_scan_and_queue_updates_snapshot_after_scan(tmp_path, monkeypatch):
    snapshot_path = tmp_path / "snapshots.json"
    monkeypatch.setattr(rr, "FOLDER_SNAPSHOT_PATH", snapshot_path)
    root = tmp_path / "root"
    (root / "sub").mkdir(parents=True)
    (root / "README.md").write_text("<!-- SSOT-LABEL: a -->\n", encoding="utf-8")
    registry_path = tmp_path / "ssot-roots.json"
    rr.add_root({"label": "a", "path": str(root)}, registry_path)

    watchdog.scan_and_queue(registry_path)

    assert rr.load_folder_snapshot("a", snapshot_path) == {"sub": False}

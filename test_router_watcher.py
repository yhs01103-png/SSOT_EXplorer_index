"""router_watcher.py 전용 테스트 — D-029(스켈레톤) → D-042(경량 폴링 구현).
예전엔 "아직 구현 안 됐다"는 사실 자체를 확인하는 테스트였는데(그 문서화된
의도대로) 실제 구현이 들어오면서 자연스럽게 깨졌음 — 이 파일이 그 신호를
받아 전면 교체한 결과."""
from __future__ import annotations

from pathlib import Path

import pytest

import router_watcher as rw
from router_watcher import InboxWatcher


@pytest.fixture(autouse=True)
def isolated_watcher_log(tmp_path, monkeypatch):
    """실제 사용자 로그(~/.claude/scripts/ssot_watcher_log.json)를 안 건드리게."""
    monkeypatch.setattr(rw, "WATCHER_LOG_PATH", tmp_path / "watcher-log.json")
    yield


# --------------------------------------------------------------- 순수 함수

def test_snapshot_dir_lists_top_level_files_only(tmp_path):
    (tmp_path / "a.md").write_text("x", encoding="utf-8")
    (tmp_path / "b.txt").write_text("x", encoding="utf-8")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "c.md").write_text("x", encoding="utf-8")  # 비재귀 — 안 잡혀야 함
    assert rw.snapshot_dir(tmp_path) == {"a.md", "b.txt"}


def test_snapshot_dir_missing_folder_returns_empty_set(tmp_path):
    assert rw.snapshot_dir(tmp_path / "no-such") == set()


def test_diff_new_files_only_reports_additions():
    before = {"a.md", "b.md"}
    after = {"a.md", "c.md"}  # b.md는 없어짐(관심사 아님), c.md만 새로 생김
    assert rw.diff_new_files(before, after) == ["c.md"]


# ------------------------------------------------------------------ 로그

def test_record_new_file_event_appends_and_persists(tmp_path):
    rw.record_new_file_event(tmp_path, "a.md")
    rw.record_new_file_event(tmp_path, "b.md")
    events = rw.load_watcher_log()
    assert [e["fileName"] for e in events] == ["a.md", "b.md"]
    assert all(e["watchDir"] == str(tmp_path) for e in events)


def test_load_watcher_log_missing_file_returns_empty():
    assert rw.load_watcher_log() == []


def test_record_new_file_event_leaves_no_tmp_file(tmp_path):
    rw.record_new_file_event(tmp_path, "a.md")
    leftovers = list(rw.WATCHER_LOG_PATH.parent.glob(rw.WATCHER_LOG_PATH.name + ".tmp*"))
    assert leftovers == []


# ------------------------------------------------------------- InboxWatcher

def test_inbox_watcher_ignores_files_present_at_construction(tmp_path):
    (tmp_path / "existing.md").write_text("x", encoding="utf-8")
    seen = []
    watcher = InboxWatcher(tmp_path, on_new_file=seen.append)
    assert watcher.poll_once() == []  # 시작 시점에 이미 있던 파일은 "새 파일" 아님
    assert seen == []


def test_inbox_watcher_poll_once_detects_new_file_and_calls_callback(tmp_path):
    seen = []
    watcher = InboxWatcher(tmp_path, on_new_file=seen.append)
    (tmp_path / "new.md").write_text("x", encoding="utf-8")
    new_names = watcher.poll_once()
    assert new_names == ["new.md"]
    assert seen == ["new.md"]


def test_inbox_watcher_poll_once_is_idempotent_after_first_detection(tmp_path):
    watcher = InboxWatcher(tmp_path, on_new_file=lambda name: None)
    (tmp_path / "new.md").write_text("x", encoding="utf-8")
    assert watcher.poll_once() == ["new.md"]
    assert watcher.poll_once() == []  # 두 번째 폴링에선 이미 알려진 파일 — 재알림 없음


def test_inbox_watcher_stop_sets_running_false_without_error():
    watcher = InboxWatcher(Path("C:\\inbox"), on_new_file=lambda name: None)
    watcher.stop()  # start() 호출 전에 stop()해도 예외 없어야 함
    assert watcher._running is False


def test_inbox_watcher_stop_before_start_prevents_loop_from_ever_running(tmp_path):
    """2026-08-21(D-072) — 실제 QThread 타이밍 경쟁(QThread.start() 호출과
    OS 스레드가 실제로 run()에 진입하는 시점 사이의 지연) 재현: toggle_
    inbox_watcher()를 딜레이 없이 두 번 연속 호출하면 stop()이 start()의
    "진짜 스레드 진입"보다 먼저 실행될 수 있다. 그 경쟁을 스레드 없이도
    결정적으로 재현 — stop()을 먼저 호출한 뒤 start()를 부르면, 예전
    구현(`self._running = True`를 무조건 첫 줄에서 재설정)은 이 정지
    신호를 지우고 루프에 진입해서 poll_interval마다 영원히 깨어났다(실제
    로컬 테스트 실행에서 pytest 프로세스가 무한 hang으로 재현·확인된
    버그). poll_interval을 0으로 줘서, 고쳐지지 않았다면 이 테스트 자체가
    타임아웃 없이 CPU를 100% 쓰며 절대 안 끝나는 방식으로 회귀를 잡는다."""
    watcher = InboxWatcher(tmp_path, on_new_file=lambda name: None, poll_interval=0)
    watcher.stop()  # start()보다 먼저 — 실제 QThread 타이밍 경쟁 재현
    watcher.start()  # 고쳐졌다면 즉시 반환, 안 고쳐졌다면 이 줄에서 영원히 안 돌아옴
    assert watcher._running is False

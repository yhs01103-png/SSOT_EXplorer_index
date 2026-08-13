"""router_watcher.py 전용 테스트 — D-029. 이 모듈은 의도적으로 스켈레톤만
있어서(틀만 구축, 실제 감시는 미구현) 테스트도 "약속대로 아직 구현 안 됐다"
는 사실 자체를 확인한다 — 나중에 실제로 구현하면 이 테스트가 자연스럽게
깨지면서 "이제 채워야 한다"는 신호가 된다."""
from __future__ import annotations

from pathlib import Path

import pytest

from router_watcher import InboxWatcher


def test_start_raises_not_implemented():
    watcher = InboxWatcher(Path("C:\\inbox"), on_new_file=lambda p: None)
    with pytest.raises(NotImplementedError):
        watcher.start()


def test_stop_sets_running_false_without_error():
    watcher = InboxWatcher(Path("C:\\inbox"), on_new_file=lambda p: None)
    watcher.stop()  # 예외 없어야 함(start 안 한 상태에서 stop해도 안전)
    assert watcher._running is False

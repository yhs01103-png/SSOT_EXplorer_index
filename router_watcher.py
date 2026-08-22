"""SSOT_Explorer 라우터 — 파일 감시자(2026-08-13 D-029 스켈레톤 →
2026-08-14 D-042 경량 구현).

**경량화 결정(D-042)**: O-006 원래 비전("새 파일 생기면 자동으로 분류 제안
까지")은 여전히 보류(재논의 조건 그대로 — router_proposals.acceptance_rate()
로 휴리스틱 분류기 정확도가 실사용 데이터로 검증될 때까지). 사용자가 이번엔
그 절반만 떼어서 요청: **"새 파일 자동감지 → 로그 쌓이듯 알려주기"** —
classify_content()/router_proposals와는 아예 연결하지 않는다. 감지된 파일이
누구 손도 안 타고 그대로 남는다 — 순수 알림/기록 기능.

**의존성 없음**: watchdog 같은 새 패키지를 추가하는 대신 폴링만으로 구현
(개인용 도구 규모에서 충분, D-029 스켈레톤 메모의 우려였던 "디바운스"도
poll_interval 자체가 자연스럽게 흡수 — 짧은 시간에 같은 파일이 여러 번
바뀌어도 다음 폴링 시점에 한 번만 관찰됨).

**감시 범위**: 지정된 폴더 1개, **비재귀**(바로 밑 파일만) — D-029 스켈레톤
메모의 "전체 드라이브 감시는 노이즈가 너무 크다" 원칙 그대로 유지.

**Qt 미의존**: router_classifier.py/router_proposals.py와 같은 원칙 — 이
파일은 순수 로직만 갖고 있고, `InboxWatcher.start()`는 블로킹 폴링 루프라
GUI에서는 반드시 별도 스레드(main.py의 QThread 래퍼)에서 돌려야 한다.
`poll_once()`로 한 번의 스캔 단위를 분리해둬서 sleep 없이도 단위 테스트
가능.
"""
from __future__ import annotations

import json
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from router_proposals import atomic_write_json

WATCHER_LOG_PATH = Path.home() / ".claude" / "scripts" / "ssot_watcher_log.json"
DEFAULT_POLL_INTERVAL = 2.0  # 초


def snapshot_dir(folder: Path) -> set[str]:
    """폴더 바로 밑(비재귀) 파일 이름 집합. 하위 폴더는 안 봄 — 감시 범위를
    좁게 유지하는 게 노이즈를 줄이는 핵심(위 모듈 docstring 참고)."""
    if not folder.is_dir():
        return set()
    try:
        return {entry.name for entry in folder.iterdir() if entry.is_file()}
    except (PermissionError, OSError):
        return set()


def diff_new_files(before: set[str], after: set[str]) -> list[str]:
    """before에는 없고 after에만 있는 파일 이름(정렬됨) — 삭제/이름변경은
    무시(그건 이 기능의 관심사가 아님, "새 파일 감지"만)."""
    return sorted(after - before)


def load_watcher_log(log_path: Path | None = None) -> list[dict]:
    path = log_path or WATCHER_LOG_PATH
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return []


def record_new_file_event(watch_dir: Path, file_name: str, log_path: Path | None = None) -> dict:
    """감지된 파일 하나를 로그에 원자적으로 추가(D-021/D-032와 같은
    atomic_write_json 재사용) — "로그 쌓이듯" 계속 append. 분류 제안이나
    승인 절차와는 무관, 순수 기록."""
    path = log_path or WATCHER_LOG_PATH
    event = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "watchDir": str(watch_dir),
        "fileName": file_name,
    }
    events = load_watcher_log(path)
    events.append(event)
    atomic_write_json(path, events)
    return event


class InboxWatcher:
    """지정 폴더를 폴링으로 감시하다 새 파일이 보이면 on_new_file(파일명)을
    호출한다. 시작 시점에 이미 있던 파일은 "새 파일"로 안 잡음(기준 스냅샷을
    __init__에서 먼저 떠 둠) — 앱 켤 때마다 기존 파일들이 전부 알림으로
    쏟아지는 걸 방지."""

    def __init__(
        self,
        watch_dir: Path,
        on_new_file: Callable[[str], None],
        poll_interval: float = DEFAULT_POLL_INTERVAL,
    ):
        self.watch_dir = watch_dir
        self.on_new_file = on_new_file
        self.poll_interval = poll_interval
        self._running = False
        # 2026-08-21(D-072) — start()보다 stop()이 먼저 불리는 경쟁을 별도
        # 플래그로 기억(아래 start()/stop() 주석 참고).
        self._stop_requested = False
        self._known = snapshot_dir(watch_dir)

    def poll_once(self) -> list[str]:
        """한 번 스캔 — 새 파일 이름 목록을 반환하고 콜백도 각각 호출한다.
        sleep 없이 즉시 실행되므로 이 메서드만 따로 단위 테스트 가능."""
        current = snapshot_dir(self.watch_dir)
        new_names = diff_new_files(self._known, current)
        for name in new_names:
            self.on_new_file(name)
        self._known = current
        return new_names

    def start(self) -> None:
        """블로킹 폴링 루프 — GUI에서는 반드시 QThread 등 별도 스레드에서
        호출해야 Qt 이벤트 루프를 안 막는다(SearchWorker와 같은 원칙).

        2026-08-21(D-072, 실측 발견) — 예전엔 이 메서드 첫 줄이 무조건
        `self._running = True`였다. QThread.start()는 실제 OS 스레드가
        이 메서드에 진입하는 시점을 보장 안 하므로, 호출 쪽(toggle_inbox_
        watcher 등)이 시작 직후 곧바로 stop()을 부르면(테스트에서 딜레이
        없이 두 번 연속 토글하는 경우 등) `stop()`이 먼저 실행돼
        `_running=False`를 세팅해놔도, 뒤늦게 진짜로 시작된 이 스레드가
        그 값을 다시 `True`로 덮어써버려 정지 신호가 통째로 사라지고
        폴링 루프가 영원히 도는 경쟁조건이 있었다(로컬 테스트에서 실제로
        무한 hang으로 재현·확인). `_stop_requested`를 먼저 확인해서,
        start() 진입 전에 이미 stop()이 불렸으면 루프에 아예 안 들어간다."""
        if self._stop_requested:
            return
        self._running = True
        while self._running:
            time.sleep(self.poll_interval)
            if not self._running:
                break
            self.poll_once()

    def stop(self) -> None:
        self._stop_requested = True
        self._running = False

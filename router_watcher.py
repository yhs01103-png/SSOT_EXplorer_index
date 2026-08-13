"""SSOT_Explorer 라우터 — 파일 감시자 스켈레톤(2026-08-13 D-029, 틀만).

"새 파일이 생기면 추적해서 자동으로 분류 제안" 요구의 3단계 부분. 이번
라운드는 사용자가 명시적으로 "앱 내장 API는 틀만 구축"을 요청했고, 이
감시자는 그 요청이 가장 크게 걸리는 조각이라 실제 백그라운드 감시는
아직 안 붙였다 — 인터페이스만 먼저 고정해서, 다음 라운드에 내부만
채우면 되게 해둔다.

의도한 흐름(다음 라운드 구현 예정): InboxWatcher가 감시 대상 폴더에 새
파일이 생기면 on_new_file 콜백을 부르고, 그 콜백이
router_classifier.classify_content()로 제안을 만들어
router_proposals에 "pending" 상태로 쌓는다 — GUI가 그 대기열을 보여주고
사용자가 승인/취소를 누르면 router_proposals.record_decision()으로 넘어간다.

실제로 붙일 때 고려할 것(설계만 미리 적어둠 — O-007 참고):
- 감시 대상은 "전체 드라이브"가 아니라 지정된 Inbox 폴더 1~2개로 한정해야
  함 — 전체 파일시스템 감시는 노이즈가 너무 큼(다운로드/빌드산출물/
  임시파일까지 전부 걸림).
- watchdog 패키지가 신규 의존성으로 필요(requirements.txt에 아직 없음).
- Qt 이벤트루프를 막지 않도록 별도 스레드(QThread, SearchWorker와 같은
  패턴)나 별도 프로세스로 돌아야 함.
- 디바운스 필요(파일 하나가 저장 중 여러 번 변경 이벤트를 낼 수 있음 —
  에디터가 임시파일→원본파일 순으로 쓰는 경우 등).
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable


class InboxWatcher:
    """스켈레톤 — start()/stop() 인터페이스만 정의, 실제 파일시스템 감시는
    아직 구현 안 됨(NotImplementedError). 호출부(main.py)가 이 클래스를
    미리 가정하고 짜여도 되게, 나중에 내부만 채우면 되는 모양으로 고정."""

    def __init__(self, watch_dir: Path, on_new_file: Callable[[Path], None]):
        self.watch_dir = watch_dir
        self.on_new_file = on_new_file
        self._running = False

    def start(self) -> None:
        raise NotImplementedError(
            "D-029 — 아직 틀만 구축된 상태. 실제 감시(watchdog 등)는 "
            "다음 라운드 과제(O-007 참고)."
        )

    def stop(self) -> None:
        self._running = False

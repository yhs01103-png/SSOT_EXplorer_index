"""SSOT_Explorer — QThread 워커 모음(2026-09-04, D-104, O-021 Stage 4-2).

레이어 분리 방침 대비 main.py 분석(O-021)의 "UX/UI 미분리" 갭 해소, Stage
4의 두 번째 조각. main.py에 흩어져 있던 4개 QThread 워커(느린 I/O를 배경
스레드로 분리해 Qt 이벤트 루프를 안 막는 "SearchWorker(D-013) 패턴"의
반복 적용)를 여기로 이관 — 전부 소규모, 서로 독립적, 생성자 인자로 필요한
값을 다 받는다.

**RootInitWorker만 생성자에 `registry_path`를 추가로 받는다**: 원래
main.py의 모듈 전역 `REGISTRY_PATH`(→ `generate_init_claude_md()` 경유)를
암묵적으로 참조했는데, 이 파일이 main.py 밖으로 나오면서 그 전역을 bare
name으로 참조할 방법이 없다(순환참조 문제, Stage 4 계획 문서 참고). 값을
직접 주입받는 게 REGISTRY_PATH를 이 파일에 별도로 캐싱하는 것보다 안전
— 테스트가 여러 모듈의 REGISTRY_PATH 사본을 동기화해서 patch할 필요가
없어진다. 이 클래스를 생성하는 곳(main.py의 SSOTExplorer 한 곳뿐, 테스트가
직접 생성하지 않음 — 실측 확인)만 호출부를 바꾸면 된다.
"""
from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QThread, Signal

import router_orchestrator
import router_sync
import router_watcher

# ---------------------------------------------------------------- Inbox 감시
#
# 2026-08-14(D-042) — O-006 경량화(자동분류 연결 없이 감지+로그+알림만).
# router_watcher.InboxWatcher.start()는 블로킹 폴링 루프라 SearchWorker와
# 같은 이유로 QThread에서 돌린다(Qt 이벤트 루프를 안 막기 위해).

class InboxWatcherThread(QThread):
    new_file_detected = Signal(str, str)  # (watch_dir, file_name)

    def __init__(self, watch_dir: Path):
        super().__init__()
        self.watch_dir = watch_dir
        self._watcher = router_watcher.InboxWatcher(watch_dir, on_new_file=self._on_new_file)

    def _on_new_file(self, file_name: str):
        router_watcher.record_new_file_event(self.watch_dir, file_name)
        self.new_file_detected.emit(str(self.watch_dir), file_name)

    def run(self):
        self._watcher.start()

    def stop(self):
        self._watcher.stop()


# --------------------------------------------------------------------- 검색
#
# 2026-08-13: 재귀 스캔(os.walk)을 QThread로 분리 — 등록된 루트가 크면
# 원래는 다이얼로그를 만드는 동안 UI 전체가 멈췄다(모달이라 더 체감됨).
# 이제 "검색 중..." 표시만 먼저 뜨고, 스캔은 백그라운드에서 돌다가 끝나면
# 신호로 결과를 채운다.

class SearchWorker(QThread):
    result_ready = Signal(list)

    def __init__(self, roots: list[dict], query: str):
        super().__init__()
        self.roots = roots
        self.query = query
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        q = self.query.lower()
        matches = []
        for r in self.roots:
            if self._cancelled:
                return
            root_path = Path(r["path"])
            if not root_path.exists():
                continue
            for dirpath, dirnames, filenames in os.walk(root_path):
                if self._cancelled:
                    return
                dirnames[:] = [d for d in dirnames if not d.startswith(".")]
                for name in dirnames + filenames:
                    if q in name.lower():
                        matches.append(str(Path(dirpath) / name))
                if len(matches) >= 300:
                    break
            if len(matches) >= 300:
                break
        if not self._cancelled:
            self.result_ready.emit(matches)


# ------------------------------------------------------- 라우터(D-029) — 저장

class ClassificationWorker(QThread):
    """SaveDocumentDialog.run_classification()의 router_orchestrator.
    orchestrate() 호출을 배경 스레드로 분리(D-051, H-008) — SearchWorker
    (D-013)와 같은 "느린 작업은 QThread로" 패턴."""
    result_ready = Signal(dict)

    def __init__(self, text: str, roots: list[dict]):
        super().__init__()
        self.text = text
        self.roots = roots

    def run(self):
        result = router_orchestrator.orchestrate(self.text, self.roots)
        self.result_ready.emit(result)


class RootInitWorker(QThread):
    """_ensure_all_roots_initialized()의 존재확인+init 생성 루프를 배경
    스레드로 분리(H-009) — 루트 개수만큼 순차 is_dir()/exists()/쓰기를
    UI 스레드(__init__)에서 돌리던 걸, SearchWorker(D-013)/
    ClassificationWorker(D-051)와 같은 "느린 I/O는 QThread로" 패턴으로
    옮겼다. 현재 등록 루트(로컬/OneDrive 5개)에서는 체감 지연이 실측된
    적 없지만, 네트워크 드라이브나 오프라인 경로가 섞이는 시나리오까지
    감안해 재현 전에 선제 적용."""
    done = Signal(list)

    def __init__(self, roots: list[dict], registry_path: Path):
        super().__init__()
        self.roots = roots
        self.registry_path = registry_path

    def run(self):
        created = []
        for entry in self.roots:
            root_path = Path(entry["path"])
            if not root_path.is_dir():
                continue  # 경로 자체가 없으면(다른 기기 전용 등) 건너뜀
            claude_path = router_sync.resolve_claude_md_target(root_path)
            if claude_path.exists():
                continue
            try:
                claude_path.write_text(
                    router_sync.generate_init_claude_md(entry, self.registry_path), encoding="utf-8",
                )
                created.append(entry["label"])
            except OSError:
                pass  # 권한 문제 등 — 조용히 건너뜀, 앱 시작을 막을 이유 없음
        self.done.emit(created)

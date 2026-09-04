"""SSOT_Explorer — 검색 다이얼로그(2026-09-04, D-105, O-021 Stage 4-3, 1/3).

레이어 분리 방침 대비 main.py 분석(O-021)의 "UX/UI 미분리" 갭 해소, Stage
4-3 첫 조각 — "트리거 하나 = 컴포넌트 하나" 원칙에 맞춰 main.py에 있던
`SearchDialog`를 독립 파일로 이관. REGISTRY_PATH를 전혀 안 쓰는 가장 단순한
케이스(main_workers.SearchWorker만 있으면 됨)라 순환참조/모듈별 캐싱 문제가
없다.
"""
from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QListWidget, QVBoxLayout

from main_workers import SearchWorker


class SearchDialog(QDialog):
    """루트들 밑을 재귀적으로 훑어 이름에 쿼리가 포함된 폴더/파일을 나열."""

    def __init__(self, roots: list[dict], query: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"검색: {query}")
        self.resize(700, 400)
        self.result_path: str | None = None

        self.listw = QListWidget()
        self.listw.addItem("🔎 검색 중...")
        self.listw.itemDoubleClicked.connect(self.accept_selection)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept_selection)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.listw)
        layout.addWidget(buttons)

        self.worker = SearchWorker(roots, query)
        self.worker.result_ready.connect(self._on_results)
        self.worker.start()

    def _on_results(self, matches: list[str]):
        self.listw.clear()
        self.listw.addItems(matches if matches else ["(결과 없음)"])

    def accept_selection(self):
        items = self.listw.selectedItems()
        if items and items[0].text() not in ("(결과 없음)", "🔎 검색 중..."):
            self.result_path = items[0].text()
            self._stop_worker()
            self.accept()

    def _stop_worker(self):
        """2026-08-21(D-072, GitHub Actions ubuntu-latest 실측 발견) — 예전엔
        `wait(300)`(고정 타임아웃)이었다. cancel()이 os.walk 루프 중간
        체크포인트에서만 반영되므로, 느리거나 부하가 큰 환경(CI 등)에선
        300ms 안에 실제로 안 끝날 수 있다 — 타임아웃이 지나면 `_stop_
        worker`는 그냥 반환해버려서, 다이얼로그/윈도우는 파괴됐는데
        스레드는 백그라운드에서 계속 도는 상태가 남는다. 그 상태로 프로세스
        가 종료되면 Qt가 "QThread: Destroyed while thread '' is still
        running"로 abort(core dumped)한다 — 개별 테스트는 전부 성공으로
        리포트된 뒤 pytest 프로세스 자체가 죽는 형태라 원인 추적이 어려움.
        인자 없는 `wait()`는 스레드가 실제로 끝날 때까지 블로킹 — 검색은
        300개 매치 제한이 있어 무한히 안 끝날 일이 없으므로 안전하다."""
        if self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait()

    def reject(self):
        self._stop_worker()
        super().reject()

    def closeEvent(self, event):
        self._stop_worker()
        super().closeEvent(event)

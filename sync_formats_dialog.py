"""SSOT_Explorer — AI 툴별 동기화 다이얼로그(2026-09-04, D-106, O-021 Stage
4-3, 2/3).

레이어 분리 방침 대비 main.py 분석(O-021)의 "UX/UI 미분리" 갭 해소, Stage
4-3의 두 번째 조각 — `SyncFormatsDialog`를 독립 파일로 이관.

**REGISTRY_PATH를 이 파일이 직접 캐싱한다(중요, 순환참조 설계 결정)**:
`_sync()`/`mark_reviewed()`가 `main_pipeline.sync_formats()`/
`mark_root_reviewed()`를 호출할 때 registry_path가 실제로 필요하다(단순
주입으로 못 피하는 케이스 — main_workers.RootInitWorker와 다름, 이 다이얼로그
는 테스트가 `SyncFormatsDialog(root_path, entry)`로 registry_path 없이 직접
생성하기 때문에 생성자 인자로 강제할 수 없다). main.py를 import해서
`main.REGISTRY_PATH`를 참조하면 "main.py가 이 파일을 import + 이 파일이
main.py를 import"하는 순환참조가 된다 — 그 대신 `ssot_mcp_server.py`가
이미 쓰는 패턴(여러 최상위 모듈이 REGISTRY_PATH를 각자 독립적으로 캐싱,
테스트가 관련된 모듈 전부를 같은 값으로 patch)을 그대로 재사용한다.
test_main.py의 `isolated_registry` autouse fixture가 `m.REGISTRY_PATH`와
`sync_formats_dialog.REGISTRY_PATH`를 같은 값으로 함께 patch한다.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QDialog, QLabel, QMessageBox, QPushButton, QVBoxLayout

import main_pipeline
import router_sync
from main_view import review_age_days
from router_proposals import resolve_registry_path
from router_sync import FORMAT_TARGETS

REGISTRY_PATH = resolve_registry_path()


class SyncFormatsDialog(QDialog):
    """레지스트리 참조조건 하나에서 CLAUDE.md/AGENTS.md/Cursor(.cursor/rules)/
    Windsurf(.windsurf/rules) — 그리고 이미 있는 레거시 .cursorrules/
    .windsurfrules까지 — 툴별로 골라서(또는 한 번에) 동기화한다. 포맷마다
    독립적으로 SYNC_MARKER 안전장치가 걸린다 — 손으로 쓴 파일은 확인 없이 안
    덮어씀. 레거시 포맷(legacy=True)은 신규 생성은 안 하고 이미 있을 때만
    갱신(H-006, D-036 — Cursor/Windsurf가 실제로 폐기한 포맷이라 새로 안 만듦)."""

    def __init__(self, root_path: Path, entry: dict, parent=None):
        super().__init__(parent)
        self.root_path = root_path
        self.entry = entry
        self.setWindowTitle(f"{entry['label']} — AI 툴별 동기화")
        self.resize(440, 300)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"'{entry['label']}' 루트 — 같은 참조조건을 어느 포맷으로 쓸까요?"))
        layout.addWidget(QLabel("(내용은 전부 동일, 파일명/포맷만 다름 — 손편집 파일은 확인 후에만 덮어씀)"))

        # 2026-08-13(O-001, Lazzy_App_OS_Monorepo 이식): primarySource가
        # "web"이면 로컬 referenceCondition은 정본이 아니라 참고용 스냅샷일
        # 뿐이라, 동기화 자체는 막지 않되(오프라인 참고용으로는 여전히
        # 쓸모 있음) 그 사실을 눈에 띄게 경고한다.
        if entry.get("primarySource") == "web":
            web_url = (entry.get("webArtifactUrl") or "").strip()
            warn = QLabel(
                f"⚠️ 이 루트는 웹 아티팩트가 정본입니다({web_url or 'URL 미등록'}) — "
                "아래로 동기화해도 참고용 스냅샷일 뿐, 최신 정본을 대체하지 않습니다."
            )
            warn.setWordWrap(True)
            warn.setStyleSheet("color: #b45309; font-weight: bold;")
            layout.addWidget(warn)

        for fmt, info in FORMAT_TARGETS.items():
            btn = QPushButton(f"{fmt} 동기화 — {info['tool']}")
            btn.clicked.connect(lambda checked=False, f=fmt: self.sync_one(f))
            layout.addWidget(btn)

        all_btn = QPushButton(f"전체 ({len(FORMAT_TARGETS)}개 포맷 한 번에)")
        all_btn.clicked.connect(self.sync_all)
        layout.addWidget(all_btn)

        age = review_age_days(entry)
        age_text = "기록 없음" if age is None else f"{entry.get('lastReviewed')} ({age}일 전)"
        review_btn = QPushButton(f"✓ 리뷰 완료로 표시 (현재: {age_text})")
        review_btn.clicked.connect(self.mark_reviewed)
        layout.addWidget(review_btn)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        close_btn = QPushButton("닫기")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def _sync(self, formats: list[str]):
        """1차 시도(main_pipeline.sync_formats)를 부르고, "needs-confirmation"
        이 나온 포맷만 이 자리에서 QMessageBox로 물어본 뒤 확인된 것만
        main_pipeline.confirm_sync_formats로 재시도한다(D-068 — 실제 쓰기
        판단/생성 로직은 router_sync에 있고, 여기는 "어떻게 확인받을지"만
        안다 — GUI만의 책임. 2026-09-04 D-102, O-021 Stage 3에서 두 호출
        사이의 조립 로직을 main_pipeline.py로 이관)."""
        first = main_pipeline.sync_formats(self.root_path, self.entry, REGISTRY_PATH, formats)
        needs_confirm = [f for f, r in first.items() if r == "needs-confirmation"]
        confirmed = []
        for fmt in needs_confirm:
            target = router_sync.resolve_format_target(self.root_path, fmt)
            resp = QMessageBox.question(
                self, "덮어쓰기 확인",
                f"{target}\n\n이미 있고 자동생성 표식이 없습니다 — 손으로 쓴 "
                "내용일 수 있습니다. 그래도 덮어쓸까요?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if resp == QMessageBox.Yes:
                confirmed.append(fmt)
        return main_pipeline.confirm_sync_formats(
            self.root_path, self.entry, REGISTRY_PATH, first, needs_confirm, confirmed,
        )

    def sync_one(self, format_name: str):
        results = self._sync([format_name])
        target = router_sync.resolve_format_target(self.root_path, format_name)
        result = results[format_name]
        self.status_label.setText(f"{router_sync.RESULT_ICONS[result]} {format_name}: {result} → {target}")

    def sync_all(self):
        results = self._sync(list(FORMAT_TARGETS))
        lines = [f"{fmt}: {router_sync.RESULT_ICONS[result]}" for fmt, result in results.items()]
        self.status_label.setText("\n".join(lines))

    def mark_reviewed(self):
        """2026-09-04(D-102, O-021 Stage 3) — 저장 로직은 main_pipeline.
        mark_root_reviewed()로 이관, 이 메서드는 결과 표시만 담당한다."""
        result = main_pipeline.mark_root_reviewed(self.entry["label"], REGISTRY_PATH)
        if result["status"] == "not_found":
            self.status_label.setText("❌ 레지스트리에서 항목을 못 찾음")
            return
        if result["status"] == "conflict":
            self.status_label.setText(f"⚠️ {result['error']}")
            return
        self.entry["lastReviewed"] = result["reviewedAt"]
        self.status_label.setText(f"✅ 리뷰 완료로 표시: {result['reviewedAt']}")

"""SSOT_Explorer — 새 문서 저장 다이얼로그(2026-09-04, D-107, O-021 Stage
4-3, 3/3).

레이어 분리 방침 대비 main.py 분석(O-021)의 "UX/UI 미분리" 갭 해소, Stage
4-3의 마지막 조각 — `SaveDocumentDialog`를 독립 파일로 이관. REGISTRY_PATH를
전혀 안 쓴다(main_pipeline.save_new_document()가 이미 registry_path 없이도
동작하도록 D-100에서 설계됨) — 순환참조/모듈별 캐싱 문제가 없는 가장 단순한
케이스.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

import main_pipeline
from main_workers import ClassificationWorker


class SaveDocumentDialog(QDialog):
    """"저장하면 알아서 맞는 프로젝트 폴더로" 워크플로우의 1단계(수동 캡처
    + 분류 제안 + 사용자 승인, 2026-08-13 D-029). router_classifier로
    등록 루트 중 후보를 순위매겨 보여주고, 사용자가 후보를 골라 "저장"을
    눌러야만 실제로 파일을 쓴다 — 이 다이얼로그가 SSOT_Explorer 전체에서
    새 파일을 실제로 쓰는 유일한 지점이다. P-01(파일쓰기 자동화 금지)의
    조건부 예외: 매번 사용자가 명시적으로 승인 버튼을 눌러야만 실행되고,
    승인/취소 둘 다 router_proposals에 기록돼 나중에 제안 정밀도를 높이는
    재료가 된다(사용자 요청사항)."""

    def __init__(self, roots: list[dict], parent=None):
        super().__init__(parent)
        self.roots = roots
        self.setWindowTitle("새 문서 저장 — 분류 제안")
        self.resize(600, 520)
        self.candidates: list[dict] = []
        self.classified_text = ""
        self.worker: ClassificationWorker | None = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("저장할 내용을 붙여넣으세요:"))
        self.content_edit = QTextEdit()
        self.content_edit.setPlaceholderText("여기에 텍스트를 붙여넣거나 입력...")
        layout.addWidget(self.content_edit)

        self.classify_btn = QPushButton("🔍 분류 제안 보기")
        self.classify_btn.clicked.connect(self.run_classification)
        layout.addWidget(self.classify_btn)

        layout.addWidget(QLabel("제안된 저장 위치(점수 높은 순 — 등록 루트 label/scope/참조조건과 겹치는 키워드 기준):"))
        self.candidates_list = QListWidget()
        layout.addWidget(self.candidates_list)

        filename_row = QHBoxLayout()
        filename_row.addWidget(QLabel("파일명:"))
        self.filename_edit = QLineEdit()
        self.filename_edit.setPlaceholderText("예: 회의메모.md")
        filename_row.addWidget(self.filename_edit)
        layout.addLayout(filename_row)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("✅ 여기에 저장")
        save_btn.clicked.connect(self.save_to_selected)
        cancel_btn = QPushButton("취소")
        cancel_btn.clicked.connect(self.cancel_and_close)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def run_classification(self):
        """D-032 — router_classifier 단독 대신 router_orchestrator를 통해
        3단계(구조화 신호 + README 실시간 프로즈검색 + 신뢰폐루프 주석)를
        전부 거친 결과를 쓴다 — CLI와 정확히 같은 결과(같은 함수 호출)라
        GUI/세션 어느 쪽으로 물어도 답이 갈리지 않는다.

        2026-08-17(D-051, H-008) — orchestrate()를 동기 호출하면 kiwipiepy
        Kiwi() 콜드인잇(~1.4초, D-034)+전체 등록 루트 README 읽기가 전부 UI
        스레드에서 돌아 그동안 창이 멈춘 것처럼 보였다(D-043 코드리뷰 발견).
        SearchWorker(D-013)와 같은 패턴으로 QThread + Signal로 분리."""
        text = self.content_edit.toPlainText()
        if not text.strip():
            self.status_label.setText("⚠️ 내용을 먼저 입력하세요.")
            return
        self.classified_text = text
        self.classify_btn.setEnabled(False)
        self.candidates_list.clear()
        self.status_label.setText("⏳ 분류 중...")
        self.worker = ClassificationWorker(text, self.roots)
        self.worker.result_ready.connect(self._on_classification_result)
        self.worker.start()

    def _on_classification_result(self, result: dict):
        self.classify_btn.setEnabled(True)
        self.candidates = result["candidates"]
        self.candidates_list.clear()
        if not self.candidates:
            # D-030: "물어보기 원칙" 이식 — 진짜 무관해서 후보가 없는 건지,
            # 내용 자체가 너무 짧아서/지시대명사 위주라 판단 근거가 부족한
            # 건지 구분해서 알려준다.
            if result["needsClarification"]:
                self.status_label.setText(
                    "🤔 내용이 너무 짧거나 무엇을 가리키는지 애매해서 판단이 "
                    "어렵습니다 — 조금 더 구체적으로 적어서 다시 시도하세요."
                )
            else:
                self.status_label.setText(
                    "😕 겹치는 키워드/scope/README 내용이 없어 제안할 후보가 "
                    "없습니다 — 이 버전(v1, 휴리스틱)은 자동제안 실패 시 대안이 "
                    "없습니다. 파일명을 직접 정하고 폴더는 트리에서 직접 관리하세요."
                )
            return
        for c in self.candidates:
            trust_badge = " ✅신뢰됨" if c.get("trusted") else ""
            item = QListWidgetItem(f"{c['rootLabel']}{trust_badge}  (점수 {c['score']})\n   {c['reason']}")
            item.setData(Qt.UserRole, c)
            self.candidates_list.addItem(item)
        self.status_label.setText(f"✅ 후보 {len(self.candidates)}개 — 하나를 선택하고 파일명을 입력한 뒤 저장하세요.")

    def save_to_selected(self):
        """2026-08-14(D-043, code-review 발견 반영) — 예전엔 run_classification()
        시점에 캡처한 self.classified_text를 그대로 썼는데, "분류 제안 보기"를
        누른 뒤 내용을 더 고쳤다면 화면엔 새 내용이 보이는데 저장은 옛 내용으로
        조용히 되는 버그였음 — 저장은 항상 지금 이 순간의 텍스트박스 내용을
        읽는다.

        2026-09-04(D-100, O-021 Stage 3) — 경로검증/쓰기/record_decision은
        main_pipeline.save_new_document()로 이관, 이 메서드는 그 결과를
        받아 UX(상태 메시지/확인 다이얼로그)만 담당한다."""
        items = self.candidates_list.selectedItems()
        if not items:
            self.status_label.setText("⚠️ 먼저 후보 목록에서 하나를 선택하세요.")
            return
        candidate = items[0].data(Qt.UserRole)
        raw_filename = self.filename_edit.text().strip()
        if not raw_filename:
            self.status_label.setText("⚠️ 파일명을 입력하세요.")
            return
        content = self.content_edit.toPlainText()
        result = main_pipeline.save_new_document(candidate, raw_filename, content)
        if result["status"] == "invalid_filename":
            self.status_label.setText("⚠️ 파일명에 절대경로나 '..'는 쓸 수 없습니다.")
            return
        if result["status"] == "outside_root":
            self.status_label.setText("⚠️ 파일명이 등록된 루트 밖을 가리킵니다.")
            return
        if result["status"] == "needs_confirmation":
            resp = QMessageBox.question(
                self, "덮어쓰기 확인",
                f"{result['targetPath']}\n\n이미 존재합니다. 덮어쓸까요?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if resp != QMessageBox.Yes:
                return
            result = main_pipeline.save_new_document(candidate, raw_filename, content, overwrite=True)
        if result["status"] == "write_failed":
            self.status_label.setText(f"❌ 저장 실패: {result['error']}")
            return
        QMessageBox.information(self, "저장 완료", f"저장됨: {result['targetPath']}")
        self.accept()

    def cancel_and_close(self):
        if self.candidates:
            # 후보를 봤는데(=제안을 받았는데) 저장 안 하고 취소 — 1순위
            # 후보 기준으로 "취소" 기록(제안 정밀도 데이터 누적, 사용자
            # 요청사항). 아예 분류를 안 돌려본 채 닫으면 기록 안 함 —
            # 판단할 제안 자체가 없었으니까.
            main_pipeline.record_save_cancelled(self.candidates[0], self.classified_text)
        self.reject()

    def _stop_worker(self):
        """SearchDialog(D-013)와 같은 이유 — 다이얼로그가 닫히는 동안 백그
        라운드 스레드가 끝나서 이미 파괴된 위젯에 신호를 쏘는 걸 막는다.
        orchestrate()는 SearchWorker처럼 중간에 끊을 체크포인트가 없는
        단일 호출이라(취소 플래그 대신) 신호만 먼저 끊고 끝날 때까지
        기다린다.

        2026-08-21(D-072, GitHub Actions ubuntu-latest 실측 발견) — 예전엔
        `wait(2000)`(고정 2초 타임아웃, "kiwipiepy 콜드인잇 포함 실측
        ~1.4초라 충분한 여유"라는 로컬 Windows 실측 기준)이었다. 부하가 더
        큰/공유된 CI 러너에서는 콜드인잇이 2초를 넘을 수 있고, 타임아웃이
        지나면 `_stop_worker`는 그냥 반환해버려서 다이얼로그는 파괴됐는데
        스레드는 백그라운드에서 계속 도는 상태가 남는다 — 프로세스 종료
        시점에 Qt가 "QThread: Destroyed while thread '' is still
        running"로 abort(core dumped)하는 원인이었음(개별 테스트는 전부
        성공으로 리포트된 뒤 pytest 프로세스 자체가 죽는 형태라 원인
        추적이 어려웠음). 인자 없는 `wait()`는 실제로 끝날 때까지 블로킹
        — orchestrate()는 유한 호출(무한루프 아님)이라 안전하다."""
        if self.worker is not None and self.worker.isRunning():
            try:
                self.worker.result_ready.disconnect(self._on_classification_result)
            except (RuntimeError, TypeError):
                pass
            self.worker.wait()

    def reject(self):
        self._stop_worker()
        super().reject()

    def closeEvent(self, event):
        self._stop_worker()
        super().closeEvent(event)

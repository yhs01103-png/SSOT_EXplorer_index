"""SSOT_Explorer — 개발자 탭(2026-09-04, D-108, O-021 Stage 4-4, 계획 마지막
조각).

레이어 분리 방침 대비 main.py 분석(O-021)의 "UX/UI 미분리" 갭 해소, Stage
4의 마지막 조각 — `ManagementPanel`(개발자 탭)을 독립 파일로 이관.

**REGISTRY_PATH를 이 파일이 직접 캐싱한다(중요, 순환참조 설계 결정,
sync_formats_dialog.py와 동일 이유)**: `refresh()`/`run_benchmark()`가
`load_roots`/`load_shared_docs`/`load_registry_raw`를 필요로 하는데, 이
3개는 main.py의 모듈 전역 REGISTRY_PATH를 참조한다. main.py를 import해서
`main.REGISTRY_PATH`를 참조하면 순환참조가 되므로, `ssot_mcp_server.py`가
이미 쓰는 패턴(여러 최상위 모듈이 REGISTRY_PATH를 각자 독립적으로 캐싱)을
재사용 — `load_roots`/`load_shared_docs`/`load_registry_raw`를 이 파일
안에서 자체 REGISTRY_PATH로 다시 구현한다(각각 한두 줄짜리 순수 파일
읽기라 복제 비용이 낮음 — `load_roots()`처럼 main.py 쪽이 이미 zero-arg
공개 계약으로 test_main.py에 13곳 넘게 물려 있어 시그니처를 못 바꾼다).
test_main.py의 `isolated_registry` autouse fixture가 `m.REGISTRY_PATH`/
`sync_formats_dialog.REGISTRY_PATH`/`management_panel.REGISTRY_PATH`를
같은 값으로 함께 patch한다.
"""
from __future__ import annotations

import json
from datetime import datetime

from PySide6.QtCore import QProcess
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

import router_keyword_registry
import router_orchestrator
import router_proposals
import router_registry
import router_watcher
import ssot_background_watchdog
from main_view import (
    find_python_interpreter,
    format_orchestration_log_text,
    format_proposals_text,
    format_registry_text,
    format_schema_validation_text,
    format_session_context_log_text,
    format_shared_docs_text,
    format_watchdog_log_text,
    format_watcher_log_text,
    load_session_context_log,
    validate_registry,
)
from main_workers import ClassificationWorker
from router_paths import DRIFT_LOG_PATH, DRIFT_SCRIPT_PATH
from router_proposals import resolve_registry_path

REGISTRY_PATH = resolve_registry_path()


def _load_roots() -> list[dict]:
    return router_registry.load_roots(REGISTRY_PATH)


def _load_shared_docs() -> list[dict]:
    """공용 컨벤션 문서 목록 — 여러 루트가 참조할 수 있는 문서(해시 추적 대상).
    이 문서가 바뀌면 dependsOnDocs에 그 label을 걸어둔 루트들에 드리프트
    스크립트가 '반영 필요'를 표시한다."""
    if not REGISTRY_PATH.exists():
        return []
    try:
        data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return []
    return data.get("sharedDocs", [])


def _load_registry_raw() -> dict:
    """검증용 — _load_roots()와 달리 setdefault로 필드를 채우지 않은 원본
    그대로 반환한다(스키마가 "빠진 필드"까지 정확히 봐야 하므로)."""
    if not REGISTRY_PATH.exists():
        return {}
    try:
        return json.loads(REGISTRY_PATH.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}


class ManagementPanel(QWidget):
    """레지스트리(JSON)+스키마검증+Inbox감시로그+키워드레지스트리+세션
    컨텍스트로그+드리프트 로그를 보여주고, 드리프트 체크를 즉시 실행할 수
    있게 한다. 전부 앱 자신의 제어 파일이라 P-01(읽기전용 원칙) 범위 밖 —
    프로젝트 파일 자체는 여전히 안 건드린다.

    2026-08-14(D-047) — 모달 QDialog였다가(D-038 최초 도입 당시 이름
    ManagementDialog) 사용자 요청으로 메인 창의 상시 탭("개발자")으로
    승격 — Lazzy_App_OS_Monorepo의 사이드바 "개발자" 대분류와 같은 발상
    (D-046 로컬 웹콘솔의 "환경 세팅 전 임시 대안"). QDialog 전용 기능
    (.exec() 모달)을 안 쓰므로 QWidget으로 베이스를 바꿨을 뿐 내부 로직은
    전부 그대로."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process: QProcess | None = None
        self.classification_worker: ClassificationWorker | None = None

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("루트 레지스트리 (ssot-roots.json) — 읽기 전용, 추가/삭제/참조조건 수정은 다른 경로로"))
        self.registry_view = QTextBrowser()
        self.registry_view.setMaximumHeight(160)
        layout.addWidget(self.registry_view)

        # 2026-08-14(D-038) — 필드 오타/타입 오류를 앱이 조용히 무시하지 않고
        # 여기서 눈에 띄게 보여준다(Backstage catalog-info.yaml 스키마 검증
        # 대비 격차를 좁히는 낮은 비용 항목).
        layout.addWidget(QLabel("스키마 검증"))
        self.schema_view = QTextBrowser()
        self.schema_view.setMaximumHeight(90)
        layout.addWidget(self.schema_view)

        # 2026-08-14(D-042) — Inbox 감시 로그(경량 O-006, 감지+기록만).
        layout.addWidget(QLabel("Inbox 감시 로그 (최근 20건)"))
        self.watcher_log_view = QTextBrowser()
        self.watcher_log_view.setMaximumHeight(90)
        layout.addWidget(self.watcher_log_view)

        # 2026-08-14(D-044) — 키워드 레지스트리(맥락형 인덱싱 1단계, Lazzy
        # keyword_registry.py 경량 이식) — 반복 관측된 키워드가 active로
        # 승급되면 다음 분류부터 점수 보너스를 받는다.
        layout.addWidget(QLabel("키워드 레지스트리 (반복 관측→자동 승급)"))
        self.keyword_registry_view = QTextBrowser()
        self.keyword_registry_view.setMaximumHeight(90)
        layout.addWidget(self.keyword_registry_view)

        # 2026-08-14(D-045) — SessionStart 훅(이 레포 밖)이 쌓는 로그. 이
        # 앱은 읽기만("어떤 루트가 실제로 세션에서 쓰였는지" 가시화).
        layout.addWidget(QLabel("세션 컨텍스트 로그 (최근 20건 — SessionStart 훅)"))
        self.session_context_log_view = QTextBrowser()
        self.session_context_log_view.setMaximumHeight(90)
        layout.addWidget(self.session_context_log_view)

        # 2026-08-23(D-076) — 분류 파이프라인 벤치마크. 드리프트체크(아래)가
        # 이미 "버튼 눌러서 실제 스크립트 실행+실시간 출력" 패턴을 갖고
        # 있지만, classify_content는 무거운 서브프로세스가 아니라 순수
        # 파이썬 함수 호출(빠름)이라 QProcess 대신 이미 있는 ClassificationWorker
        # (D-051/H-008, SaveDocumentDialog가 쓰던 QThread 래퍼)를 그대로
        # 재사용한다 — "샌드박스"를 따로 안 만든 이유: classify_content는
        # 애초에 P-01(읽기전용) 설계라 실제 등록 데이터로 바로 돌려도
        # 안전하고, 자체 로그(ssot_orchestrator_log.json)에만 기록을 남긴다.
        layout.addWidget(QLabel("분류 파이프라인 벤치마크 (실제 코드 실행 — router_orchestrator.orchestrate())"))
        bench_row = QHBoxLayout()
        self.bench_input = QLineEdit()
        self.bench_input.setPlaceholderText("분류해볼 텍스트를 입력...")
        self.bench_run_btn = QPushButton("지금 실행")
        self.bench_run_btn.clicked.connect(self.run_benchmark)
        bench_row.addWidget(self.bench_input, 1)
        bench_row.addWidget(self.bench_run_btn)
        layout.addLayout(bench_row)
        self.bench_result_view = QTextBrowser()
        self.bench_result_view.setMaximumHeight(110)
        self.bench_result_view.setPlainText("(아직 실행 안 함)")
        layout.addWidget(self.bench_result_view)

        layout.addWidget(QLabel("오케스트레이션 로그 (최근 20건 — classify가 GUI/CLI/MCP 어디서 불렸든 전부 쌓임)"))
        self.orchestration_log_view = QTextBrowser()
        self.orchestration_log_view.setMaximumHeight(110)
        layout.addWidget(self.orchestration_log_view)

        # 2026-09-04(D-093, O-012) — 분류 피드백 원장(D-029부터 쌓여왔지만
        # 뷰가 없었던 데이터). GUI 승인/취소 버튼 + MCP record_classification_
        # feedback tool(D-092) 양쪽이 같은 파일에 쓰므로 뷰도 하나로 합친다.
        layout.addWidget(QLabel("분류 피드백 이력 (승인/취소 원장 — GUI 버튼 + MCP record_classification_feedback 공통)"))
        self.proposals_view = QTextBrowser()
        self.proposals_view.setMaximumHeight(110)
        layout.addWidget(self.proposals_view)

        # 2026-08-28(D-088 후속) — 워치독은 GUI 프로세스 밖(작업 스케줄러)
        # 에서 도니까, 이 앱이 그 실행 이력을 사후에 읽어서 보여주는 것뿐
        # (다른 로그뷰와 동일 원칙 — 이 앱은 워치독을 실행하지 않는다).
        layout.addWidget(QLabel("워치독 로그 (최근 20건 — 세션 없이 도는 백그라운드 감지, 근거 포함)"))
        self.watchdog_log_view = QTextBrowser()
        self.watchdog_log_view.setMaximumHeight(130)
        layout.addWidget(self.watchdog_log_view)

        layout.addWidget(QLabel("드리프트 진행상황(실시간) / 로그"))
        self.log_view = QTextBrowser()
        layout.addWidget(self.log_view)

        btn_row = QHBoxLayout()
        self.run_btn = QPushButton("지금 드리프트 체크 실행")
        self.run_btn.clicked.connect(self.run_drift_check)
        refresh_btn = QPushButton("저장된 로그 새로고침")
        refresh_btn.clicked.connect(self.refresh)
        btn_row.addWidget(self.run_btn)
        btn_row.addWidget(refresh_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        self.refresh()

    def refresh(self):
        docs_text = format_shared_docs_text(_load_shared_docs())
        roots_text = format_registry_text(_load_roots())
        self.registry_view.setPlainText(f"[공용문서(sharedDocs)]\n{docs_text}\n\n[루트]\n{roots_text}")
        errors = validate_registry(_load_registry_raw())
        self.schema_view.setPlainText(format_schema_validation_text(errors))
        self.watcher_log_view.setPlainText(format_watcher_log_text(router_watcher.load_watcher_log()))
        self.keyword_registry_view.setPlainText(
            router_keyword_registry.format_keyword_registry_text(router_keyword_registry.load_keyword_registry())
        )
        self.session_context_log_view.setPlainText(
            format_session_context_log_text(load_session_context_log())
        )
        self.orchestration_log_view.setPlainText(
            format_orchestration_log_text(router_orchestrator.load_orchestration_log())
        )
        self.proposals_view.setPlainText(
            format_proposals_text(router_proposals.load_proposals(), router_proposals.load_trust_state())
        )
        self.watchdog_log_view.setPlainText(
            format_watchdog_log_text(ssot_background_watchdog.load_watchdog_log())
        )
        if DRIFT_LOG_PATH.exists():
            text = DRIFT_LOG_PATH.read_text(encoding="utf-8", errors="replace")
            self.log_view.setPlainText(text[-5000:])
        else:
            self.log_view.setPlainText("(로그 없음 — 아직 드리프트 감지 안 됨)")

    def run_drift_check(self):
        if not DRIFT_SCRIPT_PATH.exists():
            QMessageBox.warning(self, "실행 실패", f"스크립트 없음: {DRIFT_SCRIPT_PATH}")
            return
        self.run_btn.setEnabled(False)
        self.status_label.setText("⏳ 실행 중...")
        self.log_view.setPlainText("")  # 실시간 출력으로 대체 — 끝나면 저장된 로그로 새로고침 가능

        self.process = QProcess(self)
        self.process.setProgram(find_python_interpreter())
        self.process.setArguments([str(DRIFT_SCRIPT_PATH)])
        self.process.readyReadStandardOutput.connect(self._on_process_output)
        self.process.readyReadStandardError.connect(self._on_process_output)
        self.process.finished.connect(self._on_process_finished)
        self.process.errorOccurred.connect(self._on_process_error)
        self.process.start()

    def _on_process_output(self):
        if not self.process:
            return
        out = bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace")
        err = bytes(self.process.readAllStandardError()).decode("utf-8", errors="replace")
        if out:
            self.log_view.append(out.rstrip("\n"))
        if err:
            self.log_view.append(err.rstrip("\n"))

    def _on_process_finished(self, exit_code, _exit_status):
        self.run_btn.setEnabled(True)
        if exit_code == 0:
            self.status_label.setText(f"✅ 완료 ({datetime.now().strftime('%H:%M:%S')})")
        else:
            self.status_label.setText(f"❌ 종료 코드 {exit_code}")
        self.process = None
        self.refresh()

    def _on_process_error(self, _error):
        self.status_label.setText("❌ 실행 실패")
        self.run_btn.setEnabled(True)
        self.process = None

    def run_benchmark(self):
        """2026-08-23(D-076) — orchestrate()를 실제 등록 레지스트리로 배경
        스레드에서 실행(ClassificationWorker, D-051/H-008 재사용). 결과가
        오면 스테이지별 소요시간을 보여주고, 이 실행 자체가 이미
        ssot_orchestrator_log.json에 자동으로 쌓였으니 로그 뷰도 새로고침."""
        text = self.bench_input.text().strip()
        if not text:
            self.bench_result_view.setPlainText("(텍스트를 입력하세요)")
            return
        self.bench_run_btn.setEnabled(False)
        self.bench_result_view.setPlainText("⏳ 실행 중...")
        self.classification_worker = ClassificationWorker(text, _load_roots())
        self.classification_worker.result_ready.connect(self._on_benchmark_result)
        self.classification_worker.start()

    def _on_benchmark_result(self, result: dict):
        self.bench_run_btn.setEnabled(True)
        lines = [f"총 {result.get('totalElapsedMs', '?')}ms"]
        for step in result["steps"]:
            extra = " (skipped)" if step.get("skipped") else ""
            lines.append(f"  {step['stage']:<16} {step.get('elapsedMs', '?')}ms{extra}")
        top3 = result["candidates"][:3]
        if top3:
            lines.append("후보: " + ", ".join(f"{c['rootLabel']}({c['score']})" for c in top3))
        else:
            lines.append("후보 없음")
        self.bench_result_view.setPlainText("\n".join(lines))
        self.classification_worker = None
        self.refresh()  # 오케스트레이션 로그 뷰에 이번 실행이 바로 반영되게

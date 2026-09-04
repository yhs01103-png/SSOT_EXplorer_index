"""SSOT Explorer — SSOT 인덱싱 트리 전용 탐색기 대체 뷰어 (v2)

좌측: 레지스트리(~/.claude/ssot-roots.json)에 등록된 SSOT 루트들을 트리로
      보여줌(폴더+파일, 지연 로딩). CLAUDE.md/README.md가 있는 폴더는 굵게 표시.
우측: 선택한 폴더의 CLAUDE.md/README.md 내용을 그대로 보여줌.
상단: 루트 추가/삭제, 검색.
더블클릭: 폴더는 Windows 탐색기로, 파일은 기본 프로그램으로 엶.
우클릭: 탐색기로 열기 / VS Code로 열기 / 터미널 열기 / 경로 복사.

루트 목록은 이 파일에 하드코딩하지 않는다 — 레지스트리(ssot-roots.json)가 SSOT
(드리프트 스크립트/훅 스크립트와 공유). 여기서 추가/삭제하면 그 파일이 바로
갱신되고, 다른 스크립트들도 다음 실행 때 즉시 반영해서 읽는다.

레지스트리 위치는 2026-08-13부로 flutter_App\\.claude\\ 밑으로 이동함(사용자가
가장 자주 여는 루트라 세션 열 때 바로 보이는 게 편해서) — 예전엔 ~/.claude/ 밑
전역 위치였음.
"""
import json
import logging
import os
import subprocess
import sys
import traceback
import webbrowser
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QAction, QColor, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QSplitter,
    QStyle,
    QTabWidget,
    QTextBrowser,
    QToolBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

import main_pipeline
import router_proposals
import router_registry

# 2026-09-04(D-103, O-021 Stage 4-1) — Qt/REGISTRY_PATH 어느 쪽도 안 건드리는
# 순수 뷰 포맷터/조회 함수는 main_view.py로 이관(레이어 분리 방침의
# "UX/UI 미분리" 갭 해소 시작). 여기서는 재노출만 — bare name 그대로라
# 기존 테스트(m.format_registry_text 등 직접 호출)가 안 깨진다. 2026-09-04
# (D-108, O-021 Stage 4-4) — ManagementPanel이 management_panel.py로
# 옮겨가며 아래 대부분이 이 파일 안에서 직접은 안 불리게 됐지만, 각각
# test_main.py가 m.<이름>로 재노출 여부 자체를 검증하는 공개 별칭이라 유지
# (format_shared_docs_text만 그런 테스트가 없어 제거).
from main_view import (  # noqa: E402
    _is_or_under,  # noqa: F401
    find_relations_for_path,
    format_orchestration_log_text,  # noqa: F401
    format_proposals_text,  # noqa: F401
    format_registry_text,  # noqa: F401
    format_schema_validation_text,  # noqa: F401
    format_session_context_log_text,  # noqa: F401
    format_watchdog_log_text,  # noqa: F401
    format_watcher_log_text,  # noqa: F401
    get_available_drives,  # noqa: F401
    load_session_context_log,  # noqa: F401
    review_age_days,  # noqa: F401
    validate_registry,  # noqa: F401
)

# 2026-09-04(D-104, O-021 Stage 4-2) — QThread 워커 4종은 main_workers.py로
# 이관(레이어 분리 방침의 "UX/UI 미분리" 갭 해소, Stage 4-1 다음 조각).
# 여기서는 재노출만 — bare name 그대로라 기존 테스트가 안 깨진다.
# ClassificationWorker는 D-108(SaveDocumentDialog/ManagementPanel 둘 다
# 옮겨감)로 이 파일 안에서 더 이상 안 쓰여 재노출 목록에서 제거(재노출
# 여부를 검증하는 테스트 없음, 실측 확인 후 정리).
from main_workers import (  # noqa: E402
    InboxWatcherThread,
    RootInitWorker,
)

# 2026-09-04(D-108, O-021 Stage 4-4) — ManagementPanel(개발자 탭)도 독립
# 파일로 이관. 여기서는 재노출만.
from management_panel import ManagementPanel  # noqa: E402

# 2026-09-04(D-098, O-021 Stage 1) — 경로 상수는 router_paths.py로 이관(레이어
# 분리 방침의 "경로" 레이어 신설). 여기서는 재노출만 — bare name 그대로라
# 기존 monkeypatch 기반 테스트(예: monkeypatch.setattr(m, "LOG_PATH", ...))는
# 안 깨진다. DRIFT_LOG_PATH/DRIFT_SCRIPT_PATH는 D-108로 ManagementPanel이
# 옮겨가며 이 파일 안에서 더 이상 안 쓰여 제거(재노출 검증 테스트 없음).
from router_paths import (  # noqa: E402
    LOG_PATH,
    SCRIPTS_DIR,
)

# 2026-09-04(D-107, O-021 Stage 4-3) — SaveDocumentDialog도 독립 파일로 이관.
# 여기서는 재노출만.
from save_document_dialog import SaveDocumentDialog  # noqa: E402

# 2026-09-04(D-105, O-021 Stage 4-3) — SearchDialog는 독립 파일로 이관(레이어
# 분리 방침의 "트리거 하나 = 컴포넌트 하나" 원칙). 여기서는 재노출만.
from search_dialog import SearchDialog  # noqa: E402

# 2026-09-04(D-106, O-021 Stage 4-3) — SyncFormatsDialog도 독립 파일로 이관.
# 여기서는 재노출만.
from sync_formats_dialog import SyncFormatsDialog  # noqa: E402

# --------------------------------------------------------------------- 로깅
#
# 2026-08-13(D-025) — Lazzy_App_OS_Monorepo/server/core/log/jarvis_log.py
# 이식. 그쪽이 print()에서 logging으로 바꾼 이유: Windows 콘솔(cp949 등)이
# 이모지/em-dash를 못 만나면 print()는 UnicodeEncodeError로 프로세스 자체를
# 죽였다(2026-07-29 실측 사고 — DB연결실패 로그를 찍다가 앱 기동이 죽음).
# logging.StreamHandler.emit()은 쓰기 실패를 내부에서 삼켜(handleError())
# 예외를 다시 안 던지므로 같은 상황에서도 죽지 않는다. SSOT_Explorer는 원래
# print()/logging이 아예 없었다 — --windowed exe(콘솔 없음)라 뭔가 터지면
# 사용자 눈엔 그냥 조용히 멈추거나 사라지는 것처럼 보이는 게 더 큰 문제였다.
# (LOG_PATH는 router_paths.py에서 이관된 값 — 위 import 참고)


def _setup_logger() -> logging.Logger:
    logger = logging.getLogger("ssot_explorer")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(stream_handler)
        try:
            SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
            file_handler.setFormatter(
                logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
            )
            logger.addHandler(file_handler)
        except OSError:
            pass  # 파일 로그 없어도 콘솔 로그는 유지 — 로깅 실패가 앱을 막으면 안 됨
    return logger


log = _setup_logger()


def _install_crash_logging() -> None:
    """미처리 예외를 파일 로그 + 다이얼로그로 남긴다. PySide6은 슬롯(버튼
    클릭 등 콜백) 안에서 터진 예외를 잡아 Qt C++ 스택으로는 못 풀고
    sys.excepthook으로 넘긴다 — 기본 excepthook(콘솔에 traceback만 출력)은
    --windowed exe에서 아무 흔적도 안 남는다. 여기서 커스텀 excepthook을
    깔아서 (1) 로그 파일에 남기고 (2) 사용자에게 다이얼로그로 알리고
    (3) 원래 excepthook도 그대로 호출(개발 중 콘솔 확인용)한다 — 슬롯 안
    예외는 이렇게 해도 이벤트 루프 자체는 계속 돈다(앱이 안 죽음)."""
    def excepthook(exc_type, exc_value, exc_tb):
        formatted = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        log.error("미처리 예외:\n%s", formatted)
        QMessageBox.critical(
            None, "SSOT Explorer 오류",
            f"예상치 못한 오류가 발생했습니다.\n\n{exc_value}\n\n"
            f"자세한 내용은 로그 파일에 남았습니다:\n{LOG_PATH}",
        )
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = excepthook


# (find_python_interpreter는 main_view.py로 이관됨 — D-108, O-021 Stage
# 4-4, 상단 import 참고)

# 2026-08-14(공개 준비, D-039) — 레지스트리 경로를 개인 폴더 하드코딩에서
# 환경변수로. `SSOT_REGISTRY_PATH`가 있으면 그걸 쓰고, 없으면 범용 기본값
# (`~/.claude/ssot-roots.json`, D-014 이전 전역 위치)으로 폴백 — README
# "레지스트리 위치" 참고. 실제 로직은 router_proposals.resolve_registry_path()
# 로 옮겨서(D-043, code-review 발견 — 이 함수와 router_classifier.py의
# `_default_registry_path()`가 로직을 각자 중복으로 들고 있었음) 이젠 위임만
# 한다. 함수 이름/시그니처는 기존 호출부·테스트와의 호환을 위해 유지.
def resolve_registry_path() -> Path:
    return router_proposals.resolve_registry_path()


REGISTRY_PATH = resolve_registry_path()
# find_index_files/pick_canonical_index_file/INDEX_FILENAMES/CANONICAL_INDEX_NAMES는
# router_registry.py로 이관됨(D-071, O-010 해소) — 아래는 기존 호출부를 안
# 고치기 위한 얇은 별칭.
INDEX_FILENAMES = router_registry.INDEX_FILENAMES


# ---------------------------------------------------------------- 레지스트리
#
# v2 (2026-08-13): 각 루트 항목이 referenceCondition(참조조건, 프로즈 텍스트)을
# 갖는다. 이게 이제 그 루트의 실질적 규칙 SSOT다 — 각 루트의 CLAUDE.md는 이
# 레지스트리에서 "동기화"로 생성되는 init 파일일 뿐(P-04 갱신: "구조화 데이터는
# 단순 목록에만" 원칙을 여기서 의도적으로 확장 — CLAUDE.md가 손으로 직접 관리하는
# 프로즈가 아니라 레지스트리에서 매번 재생성 가능한 산출물이 되므로, 재생성 시
# 항상 레지스트리와 일치해서 이중관리 위험이 원래 우려와 달리 발생하지 않음).
# referenceCondition은 앱 UI가 아니라 Claude Code가 대화 중에 직접 채운다.

# 레지스트리 로드/저장(RegistryConflictError, load_roots, save_roots)은
# router_registry.py로 이관됨(D-069, router_sync.py/D-068과 같은 이유 —
# "메인은 오케스트레이션 호출만"). 아래는 기존 호출부(`load_roots()`,
# `save_roots(roots)`, `RegistryConflictError`)를 안 고치기 위한 얇은 별칭.
RegistryConflictError = router_registry.RegistryConflictError


def load_roots() -> list[dict]:
    return router_registry.load_roots(REGISTRY_PATH)


def load_labeled_folders() -> list[dict]:
    return router_registry.load_labeled_folders(REGISTRY_PATH)


# (load_shared_docs는 main.py 안에서 더 이상 안 쓰임 — ManagementPanel이
# management_panel.py로 옮겨가며 자체 REGISTRY_PATH로 다시 구현함, D-108.
# 재노출 안 함 — 이걸 검증하는 테스트 없음, 실측 확인 후 정리.)


# ------------------------------------------------------------------ 관계
#
# 2026-08-13(D-028) — Lazzy_App_OS_Monorepo의 "능동적 인덱싱" 이식. 그쪽
# CLAUDE.md들은 그냥 폴더 목록이 아니라 각 항목에 "언제/왜 여는지" 조건이
# 붙은 표+양방향 역참조 프로즈다. 지금까지 SSOT_Explorer 레지스트리는 이
# 정보를 각 루트 referenceCondition 프로즈 안에 통째로 묻어놓기만 해서
# 앱이 그 관계를 몰랐다 — 트리에서 폴더 하나를 클릭해도 "이게 뭐랑 왜
# 연관되는지"는 안 보여줬다. relations를 별도 구조화 데이터로 승격해서
# 트리 어느 폴더를 클릭하든(등록된 루트든 아니든) 관련 폴더+이유를 역조회
# 할 수 있게 한다. dependsOnDocs(안1: 자동스캔 대신 명시적 선언)와 같은
# 원칙 — 프로즈 관계는 자동 추출이 신뢰할 수 없어(D-020 판단 그대로) 사람이
# (Claude Code가 대화 중) 직접 선언한다.

def load_relations() -> list[dict]:
    """폴더 대 폴더 관계 선언 목록. 각 항목: fromPath/toPath/reason/
    bidirectional(기본 True — 두 경로 중 어느 쪽을 클릭해도 관계가 보임)."""
    if not REGISTRY_PATH.exists():
        return []
    try:
        data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return []
    relations = data.get("relations", [])
    for r in relations:
        r.setdefault("bidirectional", True)
    return relations


# (_is_or_under/find_relations_for_path/REVIEW_STALE_DAYS/review_age_days는
# main_view.py로 이관됨(D-103, O-021 Stage 4-1) — 상단 import 참고)


# ------------------------------------------------------------ 스키마 검증
#
# (REGISTRY_SCHEMA/validate_registry/format_schema_validation_text는
# main_view.py로 이관됨(D-103, O-021 Stage 4-1) — 상단 import 참고)


def load_registry_raw() -> dict:
    """검증용 — load_roots()와 달리 setdefault로 필드를 채우지 않은 원본
    그대로 반환한다(스키마가 "빠진 필드"까지 정확히 봐야 하므로). load_
    shared_docs/load_relations과 같은 파일 읽기 규칙(존재/파싱 실패 시
    빈 dict)을 공유."""
    if not REGISTRY_PATH.exists():
        return {}
    try:
        return json.loads(REGISTRY_PATH.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_roots(roots: list[dict]) -> None:
    router_registry.save_roots(roots, REGISTRY_PATH)


# AI 툴별 규칙 파일 동기화(FORMAT_TARGETS/generate_*/SYNC_MARKER 등)는
# router_sync.py로 이관됨(D-068, "메인은 오케스트레이션 호출만" 원칙 —
# router_orchestrator.py가 classify 쪽에서 이미 하던 분리를 sync 쪽에도
# 적용). 이 파일에서 GUI가 필요로 하는 이름들은 아래에서 재노출만 한다
# (호출부를 전부 안 고치기 위한 얇은 별칭 — 새 코드는 router_sync를 직접
# 쓸 것). 2026-09-04(D-106, O-021 Stage 4-3) — SyncFormatsDialog가
# sync_formats_dialog.py로 옮겨가며 이 파일 안에서 직접 부르는 곳은 없어졌지만,
# 아래 3개 전부 test_main.py가 m.<이름>로 재노출 여부 자체를 검증하는 공개
# 별칭이라 유지.
from router_sync import (  # noqa: E402
    FORMAT_TARGETS,  # noqa: F401 — 위 설명과 동일 이유로 유지.
    SYNC_MARKER,  # noqa: F401 — 위 설명과 동일 이유로 유지.
    resolve_format_target,  # noqa: F401 — 위 설명과 동일 이유로 유지.
)

# (resolve_claude_md_target/generate_init_claude_md는 main.py 안에서 더 이상
# 안 쓰임 — RootInitWorker가 main_workers.py로 옮겨가며 router_sync를 직접
# 씀, D-104. add_root_entry()도 D-101부터 이미 router_sync 직접 호출. 재노출
# 안 함 — 이걸 검증하는 테스트 없음, 실측 확인 후 정리.)


# (format_registry_text/format_shared_docs_text/_format_recent_log_text+5
# 로그 포맷터/load_session_context_log/get_available_drives는 main_view.py로
# 이관됨(D-103, O-021 Stage 4-1) — 상단 import 참고)


# find_index_files/pick_canonical_index_file/CANONICAL_INDEX_NAMES(D-041,
# H-003 대소문자 중복 방지)는 router_registry.py로 이관됨(D-071, O-010
# 해소 — ssot_mcp_server.py가 이 순수 함수들 때문에 main.py를 통째로
# 임포트해서 PySide6까지 끌려왔음). 아래는 기존 호출부를 안 고치기 위한
# 얇은 별칭.
CANONICAL_INDEX_NAMES = router_registry.CANONICAL_INDEX_NAMES


def pick_canonical_index_file(key: str, paths: list[Path]) -> Path:
    return router_registry.pick_canonical_index_file(key, paths)


def find_index_files(folder: Path) -> dict:
    return router_registry.find_index_files(folder)


# (InboxWatcherThread/SearchWorker는 main_workers.py로 이관됨 — D-104,
# O-021 Stage 4-2, 상단 import 참고)


# (SearchDialog는 search_dialog.py로 이관됨 — D-105, O-021 Stage 4-3,
# 상단 import 참고)


# -------------------------------------------------------------------- 관리

# (ManagementPanel은 management_panel.py로 이관됨 — D-108, O-021
# Stage 4-4, 상단 import 참고. 자기만의 REGISTRY_PATH 캐싱 — 그 파일
# docstring 참고)


# ------------------------------------------------------- AI 툴별 동기화 다이얼로그

# (SyncFormatsDialog는 sync_formats_dialog.py로 이관됨 — D-106, O-021
# Stage 4-3, 상단 import 참고. 자기만의 REGISTRY_PATH 캐싱 — 그 파일
# docstring 참고)


# ------------------------------------------------------- 라우터(D-029) — 저장
#
# (ClassificationWorker는 main_workers.py로 이관됨 — D-104, O-021 Stage 4-2,
# 상단 import 참고)

# (SaveDocumentDialog는 save_document_dialog.py로 이관됨 — D-107, O-021
# Stage 4-3, 상단 import 참고)


# (RootInitWorker는 main_workers.py로 이관됨 — D-104, O-021 Stage 4-2,
# 상단 import 참고. 생성자가 registry_path를 추가로 받게 됐으므로 아래
# _ensure_all_roots_initialized()의 호출부도 같이 바뀜)


# ---------------------------------------------------------------------- 앱

class SSOTExplorer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SSOT Explorer")
        self.resize(1200, 750)

        self.roots = load_roots()
        self.labeled_folders = load_labeled_folders()
        # 2026-08-17(D-057) — 개발자 모드: 레지스트리 최상위 developerMode
        # 필드(기본 True, "이 앱을 쓴다는 건 이미 개발자"). 꺼지면 개발자
        # 탭이 숨겨지고 MCP 서버(ssot_mcp_server.py)의 3개 tool도 전부
        # 비활성 응답을 준다(같은 플래그를 두 프로세스가 같은 레지스트리
        # 파일에서 읽어 공유 — O-010이 "웹서빙 2단계"로 계획했던 걸
        # 사용자가 재논의: MCP가 이미 "IDE가 어디서든 조회"를 해결하므로
        # 별도 웹서버는 불필요, 대신 이 토글이 필요하다는 판단).
        self.developer_mode = router_proposals.is_developer_mode(REGISTRY_PATH)
        self.current_folder: Path | None = None
        self.inbox_watcher_thread: InboxWatcherThread | None = None
        self.root_init_worker: RootInitWorker | None = None
        # 2026-08-13: 창 크기/스플리터 비율/마지막 선택 위치 기억(QSettings,
        # Windows에서는 레지스트리 HKCU\Software\SSOT_Explorer\SSOT_Explorer에
        # 저장 — 별도 설정파일 없음).
        self.settings = QSettings("SSOT_Explorer", "SSOT_Explorer")

        self._build_toolbar()
        self.statusBar().showMessage("준비됨", 2000)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["SSOT 인덱싱 트리 (굵게 = CLAUDE.md/README.md 있음)"])
        self.tree.itemExpanded.connect(self.on_item_expanded)
        self.tree.itemSelectionChanged.connect(self.on_selection_changed)
        self.tree.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.on_context_menu)

        self.viewer = QTextBrowser()

        tree_font = self.tree.font()
        tree_font.setPointSize(13)
        self.tree.setFont(tree_font)
        self.tree.setStyleSheet("QTreeWidget::item { padding: 5px 2px; }")

        viewer_font = self.viewer.font()
        viewer_font.setPointSize(13)
        self.viewer.setFont(viewer_font)

        # 2026-08-13(D-028) — 관계 패널: 선택한 폴더가 relations 목록에
        # 걸리면(등록된 루트든 아니든) "관련 폴더 + 이유"를 뷰어 위에 보여준다.
        # 관계가 없는 폴더 선택 시엔 라벨/리스트 둘 다 숨김(불필요한 빈 패널
        # 안 뜨게).
        self.relations_label = QLabel("🔗 연관된 인덱싱 폴더 (더블클릭 시 이동)")
        self.relations_list = QListWidget()
        self.relations_list.setMaximumHeight(110)
        self.relations_list.itemDoubleClicked.connect(self.on_relation_double_clicked)
        self.relations_label.setVisible(False)
        self.relations_list.setVisible(False)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(self.relations_label)
        right_layout.addWidget(self.relations_list)
        right_layout.addWidget(self.viewer)

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(self.tree)
        self.splitter.addWidget(right_panel)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 2)

        # 2026-08-14(D-047) — 상단 "탐색기"/"개발자" 대분류 탭(Lazzy
        # 사이드바의 사용자/개발자 대분류와 같은 발상, 사용자 요청 —
        # "일단은 클라이언트에 개발자탭 추가해서 거기서 보여지고, 나머지
        # 환경(D-046 로컬 웹콘솔의 포트/보안/exe패키징, O-010)이 세팅되면
        # HTML 서빙으로 바꿔줘"). 관리자 패널이 모달 다이얼로그였다가
        # 상시 탭으로 승격 — 항상 최신 상태를 보여주려고 탭이 활성화될
        # 때마다 refresh().
        # 2026-08-17(D-057) — 개발자 모드가 꺼져 있으면 탭 자체를 안 붙인다
        # (인스턴스는 그대로 만들어둠 — 나중에 토글로 다시 켜면 상태 안
        # 잃고 재부착만 하면 되도록, _apply_developer_mode_visibility 참고).
        self.management_panel = ManagementPanel(self)
        self.tabs = QTabWidget()
        self.tabs.addTab(self.splitter, "탐색기")
        if self.developer_mode:
            self.tabs.addTab(self.management_panel, "개발자")
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.setCentralWidget(self.tabs)

        self._build_shortcuts()
        self.populate_roots()
        self._restore_state()
        self._ensure_all_roots_initialized()

    # -------------------------------------------------------- 창 상태 기억

    def _restore_state(self):
        geo = self.settings.value("windowGeometry")
        if geo is not None:
            self.restoreGeometry(geo)
        splitter_state = self.settings.value("splitterState")
        if splitter_state is not None:
            self.splitter.restoreState(splitter_state)
        last_path = self.settings.value("lastSelectedPath")
        if last_path:
            self.reveal_path(last_path)

    def closeEvent(self, event):
        self.settings.setValue("windowGeometry", self.saveGeometry())
        self.settings.setValue("splitterState", self.splitter.saveState())
        selected = self.tree.selectedItems()
        if selected:
            self.settings.setValue("lastSelectedPath", selected[0].data(0, Qt.UserRole))
        if self.inbox_watcher_thread is not None:
            self.inbox_watcher_thread.stop()
            self.inbox_watcher_thread.wait()
        # 2026-08-21(D-072, GitHub Actions ubuntu-latest 실측 발견) — 예전엔
        # wait(3000)이었다. RootInitWorker.run()은 self.roots 개수만큼
        # is_dir()/exists()/쓰기를 순차 실행하는 유한 루프라 무한히 안
        # 끝날 일이 없다 — 고정 타임아웃 대신 실제로 끝날 때까지 블로킹해서,
        # 느린 CI 환경에서 타임아웃이 지나 스레드가 백그라운드에 남는 것을
        # 원천 차단한다(그 상태로 프로세스가 종료되면 Qt가 "QThread:
        # Destroyed while thread '' is still running"로 abort함).
        if self.root_init_worker is not None and self.root_init_worker.isRunning():
            self.root_init_worker.wait()
        super().closeEvent(event)

    # ------------------------------------------------------------ 툴바

    def _build_toolbar(self):
        # 2026-08-13: 아이콘 추가(QStyle 표준 아이콘 — 자산 파일 없이 동작,
        # PyInstaller 패키징에 영향 없음) + 기능별 그룹으로 재배치 + 새로고침
        # 버튼 신설(예전엔 외부 변경사항을 보려면 앱을 재시작해야 했음).
        bar = QToolBar("도구")
        bar.setMovable(False)
        self.addToolBar(bar)
        style = self.style()

        add_action = QAction(style.standardIcon(QStyle.SP_FileDialogNewFolder), "루트 추가", self)
        add_action.setToolTip("새 폴더를 SSOT 루트로 등록")
        add_action.triggered.connect(self.add_root)
        bar.addAction(add_action)

        remove_action = QAction(style.standardIcon(QStyle.SP_TrashIcon), "루트 삭제", self)
        remove_action.setToolTip("등록 해제(파일은 그대로 둠) — 트리에서 루트 선택 후 Delete 키도 가능")
        remove_action.triggered.connect(self.remove_root)
        bar.addAction(remove_action)

        refresh_action = QAction(style.standardIcon(QStyle.SP_BrowserReload), "새로고침", self)
        refresh_action.setShortcut(QKeySequence(Qt.Key_F5))
        refresh_action.setToolTip("레지스트리 + 트리 다시 읽기 (F5)")
        refresh_action.triggered.connect(self.refresh_tree)
        bar.addAction(refresh_action)

        bar.addSeparator()

        sync_action = QAction(style.standardIcon(QStyle.SP_DialogApplyButton), "AI 툴별 동기화", self)
        sync_action.setToolTip("선택한 루트를 CLAUDE.md/AGENTS.md/Cursor/Windsurf 등으로 동기화")
        sync_action.triggered.connect(self.open_sync_dialog)
        bar.addAction(sync_action)

        export_action = QAction(style.standardIcon(QStyle.SP_DriveFDIcon), "전체 내보내기", self)
        export_action.setToolTip("등록된 모든 루트를 앱/레지스트리 없이도 동작하는 완전판으로 내보내기")
        export_action.triggered.connect(self.export_all_roots)
        bar.addAction(export_action)

        bar.addSeparator()

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("이름 검색 후 Enter (Ctrl+F로 포커스)")
        self.search_box.setMaximumWidth(320)
        self.search_box.returnPressed.connect(self.run_search)
        bar.addWidget(self.search_box)

        bar.addSeparator()

        self.manage_action = QAction(style.standardIcon(QStyle.SP_FileDialogDetailedView), "개발자 탭으로", self)
        self.manage_action.setToolTip("개발자 탭으로 전환(레지스트리/스키마검증/로그 뷰 + 드리프트 체크)")
        self.manage_action.setEnabled(self.developer_mode)
        self.manage_action.triggered.connect(self.open_management)
        bar.addAction(self.manage_action)

        # 2026-08-17(D-057) — 개발자 모드 토글: 꺼지면 개발자 탭이 숨겨지고
        # MCP 서버 tool 3개도 전부 비활성 응답을 준다(register_proposals.
        # is_developer_mode()를 두 프로세스가 공유). 이 버튼 자체는
        # 항상(탭 상태와 무관하게) 툴바에 있어서, 실수로 껐어도 되돌릴
        # 경로가 항상 보인다.
        self.dev_mode_action = QAction(style.standardIcon(QStyle.SP_ComputerIcon), "개발자 모드", self)
        self.dev_mode_action.setCheckable(True)
        self.dev_mode_action.setChecked(self.developer_mode)
        self.dev_mode_action.setToolTip(
            "끄면 개발자 탭이 숨겨지고 MCP 서버(ssot_mcp_server.py) 기능도 "
            "전부 비활성화됩니다 — 언제든 이 버튼으로 다시 켤 수 있습니다."
        )
        self.dev_mode_action.toggled.connect(self.on_developer_mode_toggled)
        bar.addAction(self.dev_mode_action)

        save_doc_action = QAction(style.standardIcon(QStyle.SP_FileIcon), "새 문서 저장", self)
        save_doc_action.setToolTip(
            "텍스트를 붙여넣으면 등록된 루트 중 맞는 곳을 제안 — 승인해야만 "
            "실제 저장(D-029, 항상 사용자 확인 필요)"
        )
        save_doc_action.triggered.connect(self.open_save_document_dialog)
        bar.addAction(save_doc_action)

        # 2026-08-14(D-042) — Inbox 감시(경량 O-006): 자동분류 없이 감지+알림만.
        self.inbox_watch_action = QAction(
            style.standardIcon(QStyle.SP_MediaPlay), "Inbox 감시 시작", self
        )
        self.inbox_watch_action.setToolTip(
            "폴더 하나를 골라 새 파일이 생기면 상태바 알림 + 로그 기록"
            "(자동 분류/저장 없음, 순수 감지)"
        )
        self.inbox_watch_action.triggered.connect(self.toggle_inbox_watcher)
        bar.addAction(self.inbox_watch_action)

    def _build_shortcuts(self):
        """전역 단축키. Ctrl+F는 창 어디서든(WindowShortcut, 기본값), Delete는
        트리가 포커스 있을 때만(WidgetShortcut) — 검색창에서 텍스트 지울 때
        루트가 삭제되는 사고를 막는다."""
        focus_search = QAction(self)
        focus_search.setShortcut(QKeySequence("Ctrl+F"))
        focus_search.triggered.connect(self._focus_search)
        self.addAction(focus_search)

        delete_root_action = QAction(self)
        delete_root_action.setShortcut(QKeySequence(Qt.Key_Delete))
        delete_root_action.setShortcutContext(Qt.WidgetShortcut)
        delete_root_action.triggered.connect(self.on_delete_key)
        self.tree.addAction(delete_root_action)

    def _focus_search(self):
        self.search_box.setFocus()
        self.search_box.selectAll()

    def _on_tab_changed(self, index: int):
        """개발자 탭으로 전환할 때마다 최신 상태로(D-047) — 뒤에서 Inbox
        감시/라우터가 계속 데이터를 쌓고 있을 수 있어, 탭 자체를 볼 때마다
        새로고침해야 방금 쌓인 걸 놓치지 않는다."""
        if self.tabs.widget(index) is self.management_panel:
            self.management_panel.refresh()

    def open_management(self):
        """툴바 버튼 하위호환 — 이제 모달 대신 상시 탭(D-047)이라 그
        탭으로 전환만 한다."""
        self.tabs.setCurrentWidget(self.management_panel)

    def on_developer_mode_toggled(self, checked: bool):
        """D-057 — 개발자 모드 토글. 레지스트리에 기록해서 MCP 서버
        (별도 프로세스)도 같은 값을 보게 하고, 이 세션의 탭/버튼 상태도
        즉시 반영한다."""
        self.developer_mode = checked
        main_pipeline.set_developer_mode(checked, REGISTRY_PATH)
        self._apply_developer_mode_visibility()
        self.manage_action.setEnabled(checked)
        self.statusBar().showMessage(
            "🛠 개발자 모드 켜짐 — 개발자 탭 표시, MCP 서버 기능 활성화" if checked
            else "🛠 개발자 모드 꺼짐 — 개발자 탭 숨김, MCP 서버 기능 비활성화",
            5000,
        )

    def _apply_developer_mode_visibility(self):
        """개발자 탭을 탈부착 — ManagementPanel 인스턴스 자체는 항상
        살아있으니(D-057, __init__ 참고) 껐다 켜도 레지스트리 뷰 등 상태를
        다시 잃지 않는다."""
        idx = self.tabs.indexOf(self.management_panel)
        if self.developer_mode and idx == -1:
            self.tabs.insertTab(1, self.management_panel, "개발자")
        elif not self.developer_mode and idx != -1:
            self.tabs.removeTab(idx)

    def open_save_document_dialog(self):
        dlg = SaveDocumentDialog(self.roots, self)
        if dlg.exec() == QDialog.Accepted:
            self.refresh_tree()
            self.statusBar().showMessage("📥 새 문서 저장됨 — 트리 새로고침함", 4000)

    def toggle_inbox_watcher(self):
        """D-042 — 감시 중이 아니면 폴더를 골라 시작, 감시 중이면 중지.
        자동 분류/저장은 전혀 안 함 — 새 파일이 보이면 상태바 알림 +
        ssot_watcher_log.json에 기록만 한다(router_watcher.py 참고)."""
        if self.inbox_watcher_thread is not None:
            self.inbox_watcher_thread.stop()
            # 2026-08-21(D-072, GitHub Actions ubuntu-latest 실측 발견) —
            # 예전엔 wait(3000)이었다. 이 메서드는 closeEvent와 별개 경로
            # (토글로 직접 켰다 끌 때)라 closeEvent 쪽만 고쳐서는 이 경로가
            # 안 고쳐진다 — 실제로 이게 진짜 leak의 원인이었다: wait(3000)이
            # 타임아웃돼도 바로 다음 줄에서 `self.inbox_watcher_thread =
            # None`으로 참조를 놓아버려서, 그 이후로는 누구도 다시 stop()을
            # 호출할 방법이 없어 폴링 스레드가 프로세스 종료 때까지 무한히
            # 계속 돎(poll_interval마다 깨어나 확인하는 루프라 멈출 방법이
            # 완전히 사라짐) — 프로세스 종료 시점에 Qt가 "QThread:
            # Destroyed while thread '' is still running"로 abort. 인자
            # 없는 wait()는 stop()이 실제로 반영될 때까지(최대 poll_
            # interval, 기본 2초) 블로킹 — 무한루프가 아니라 안전하다.
            self.inbox_watcher_thread.wait()
            self.inbox_watcher_thread = None
            self.inbox_watch_action.setText("Inbox 감시 시작")
            self.inbox_watch_action.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
            self.statusBar().showMessage("⏹ Inbox 감시 중지됨", 3000)
            return
        folder = QFileDialog.getExistingDirectory(self, "감시할 Inbox 폴더 선택")
        if not folder:
            return
        self.inbox_watcher_thread = InboxWatcherThread(Path(folder))
        self.inbox_watcher_thread.new_file_detected.connect(self._on_inbox_file_detected)
        self.inbox_watcher_thread.start()
        self.inbox_watch_action.setText("Inbox 감시 중지")
        self.inbox_watch_action.setIcon(self.style().standardIcon(QStyle.SP_MediaStop))
        self.statusBar().showMessage(f"📥 Inbox 감시 시작: {folder}", 4000)

    def _on_inbox_file_detected(self, watch_dir: str, file_name: str):
        self.statusBar().showMessage(f"🔔 새 파일 감지: {file_name} ({watch_dir})", 8000)

    def refresh_tree(self):
        """레지스트리+파일시스템을 다시 읽어 트리를 재구성한다(F5). 예전엔
        외부에서(탐색기 등) 폴더/파일이 바뀌어도 앱을 재시작해야 보였음."""
        self.roots = load_roots()
        self.labeled_folders = load_labeled_folders()
        self.tree.clear()
        self.populate_roots()
        self.statusBar().showMessage("🔄 새로고침 완료", 3000)

    def _ensure_all_roots_initialized(self):
        """D-031 — "앱을 켜놓으면 등록된 인덱싱 폴더를 전부 init 상태로
        유지해달라"는 요청. 등록된 루트 중 CLAUDE.md(또는 .claude\\CLAUDE.md)
        가 아예 없는 것만 골라 init 포인터를 자동 생성 — add_root()가 신규
        루트 하나에 대해 하던 걸 앱 시작 시 전체 루트로 확장한 것. 기존
        파일이 있으면(손편집이든 이미 동기화된 것이든) 절대 손 안 댐 —
        "없는 것만 채운다"라 SYNC_MARKER 확인조차 필요 없다(덮어쓸 대상이
        없으므로). 조용히 처리하고 상태바에 몇 개 채웠는지만 알림.

        2026-08-17(H-009) — 실제 파일 존재확인+쓰기 루프는 RootInitWorker
        (QThread)로 옮겨 __init__이 이 작업이 끝나길 기다리지 않고 바로
        반환한다(SearchWorker/ClassificationWorker와 동일 패턴). self에
        참조를 들고 있어야 워커가 가비지컬렉트 안 됨.

        2026-09-04(D-104, O-021 Stage 4-2) — RootInitWorker가 main_workers.py
        로 옮겨가며 생성자가 registry_path를 명시로 받게 됐다(그 파일
        안에서는 main.py의 모듈 전역 REGISTRY_PATH를 bare name으로 참조할
        수 없어서, 이 파일이 생성 시점에 직접 주입)."""
        self.root_init_worker = RootInitWorker(self.roots, REGISTRY_PATH)
        self.root_init_worker.done.connect(self._on_roots_initialized)
        self.root_init_worker.start()

    def _on_roots_initialized(self, created: list[str]):
        if created:
            self.tree.clear()
            self.populate_roots()
            self.statusBar().showMessage(
                f"📌 init 파일 없던 루트 {len(created)}개 자동 생성: {', '.join(created)}", 6000
            )

    def add_root(self):
        """2026-09-04(D-101, O-021 Stage 3) — 중첩루트 검사(find_nested_roots)
        와 실제 등록 시퀀스(add_root_entry)는 main_pipeline.py로 이관, 이
        메서드는 다이얼로그 순서(폴더 선택 → 경고 확인 → 이름 입력 →
        등록)와 결과 표시만 담당한다."""
        folder = QFileDialog.getExistingDirectory(self, "SSOT 루트로 등록할 폴더 선택")
        if not folder:
            return

        # 2026-09-03 — 이 폴더를 등록하면 그 밑에 이미 등록된 하위 루트를
        # "삼키는" 셈이 된다(SSOT_Coding_File이 flutter_App/Local_APP보다
        # 배열에서 앞에 있으면 하위 세션들이 전부 더 넓은 이 루트로
        # 잘못 매치되던 실제 사고, SSOT_Coding_File/README.md "레지스트리
        # 배열 순서" 절 참고) — 지금까진 이걸 사람이 등록 시점에 알아챌
        # 방법이 전혀 없었다. 등록 전에 미리 보여주고 확인받는다.
        new_root = Path(folder).resolve()
        covered = main_pipeline.find_nested_roots(new_root, self.roots)
        if covered:
            preview = "\n".join(f"  · {r['label']} ({r['path']})" for r in covered[:20])
            if len(covered) > 20:
                preview += f"\n  ...외 {len(covered) - 20}개"
            resp = QMessageBox.question(
                self,
                "하위 루트 발견",
                f"이 폴더 밑에 이미 등록된 루트가 {len(covered)}개 있습니다:\n\n{preview}\n\n"
                "이 폴더를 새 루트로 등록하면, 등록 순서에 따라 저 하위 루트들의 "
                "세션이 이 더 넓은 루트로 잘못 매치될 수 있습니다(먼저 매치되는 "
                "항목 하나만 적용됨). 그래도 등록할까요?\n"
                "(등록 후 ssot-roots.json에서 이 항목이 하위 루트들보다 "
                "뒤에 오는지 반드시 확인하세요.)",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if resp != QMessageBox.Yes:
                return

        label, ok = QInputDialog.getText(self, "루트 이름", "표시할 이름:", text=Path(folder).name)
        if not ok or not label.strip():
            return

        result = main_pipeline.add_root_entry(folder, label, self.roots, REGISTRY_PATH)
        self.roots = result["roots"]
        if result["status"] == "conflict":
            QMessageBox.warning(self, "루트 추가 실패", f"{result['error']}\n(레지스트리를 새로고침했습니다 — 다시 시도하세요.)")
            self.tree.clear()
            self.populate_roots()
            return
        if result.get("initFileError"):
            QMessageBox.warning(self, "init 생성 실패", result["initFileError"])

        self.tree.clear()
        self.populate_roots()
        self.statusBar().showMessage(f"✅ 루트 추가됨: {result['entry']['label']}", 4000)

    def remove_root(self):
        if not self.roots:
            QMessageBox.information(self, "루트 삭제", "등록된 루트가 없습니다.")
            return
        labels = [f"{r['label']} ({r['path']})" for r in self.roots]
        choice, ok = QInputDialog.getItem(self, "루트 삭제", "삭제할 루트:", labels, editable=False)
        if not ok:
            return
        self._remove_root_at(labels.index(choice))

    def _remove_root_at(self, idx: int):
        """실제 삭제 로직 — 툴바 버튼과 Delete 단축키가 공유(중복 제거).
        2026-09-04(D-101, O-021 Stage 3) — save_roots 시퀀스는 main_pipeline.
        remove_root_entry()로 이관, 이 메서드는 결과 표시만 담당한다."""
        result = main_pipeline.remove_root_entry(idx, self.roots, REGISTRY_PATH)
        self.roots = result["roots"]
        if result["status"] == "conflict":
            QMessageBox.warning(self, "루트 삭제 실패", f"{result['error']}\n(레지스트리를 새로고침했습니다 — 다시 시도하세요.)")
            self.tree.clear()
            self.populate_roots()
            return
        self.tree.clear()
        self.populate_roots()
        self.statusBar().showMessage(f"🗑 삭제됨: {result['removed']['label']} (파일은 그대로 둠, 레지스트리에서만 제외)", 5000)

    def on_delete_key(self):
        """트리에서 최상위(루트) 항목이 선택된 상태로 Delete를 누르면 삭제
        확인창. 하위 폴더/파일 선택 시엔(파일시스템 삭제가 아니므로) 아무
        일도 안 하고 안내만 — 오조작 방지."""
        items = self.tree.selectedItems()
        if not items or items[0].parent() is not None:
            self.statusBar().showMessage("⚠️ Delete는 트리 최상위(등록된 루트) 선택 시에만 동작합니다", 3000)
            return
        target = Path(items[0].data(0, Qt.UserRole))
        idx = next((i for i, r in enumerate(self.roots) if Path(r["path"]) == target), None)
        if idx is None:
            return
        label = self.roots[idx]["label"]
        resp = QMessageBox.question(
            self, "루트 삭제",
            f"'{label}' 루트를 레지스트리에서 삭제할까요?\n(파일은 그대로 둠, 레지스트리에서만 제외)",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if resp != QMessageBox.Yes:
            return
        self._remove_root_at(idx)

    def open_sync_dialog(self):
        items = self.tree.selectedItems()
        if not items:
            QMessageBox.information(self, "동기화", "먼저 트리에서 루트를 선택하세요.")
            return
        target = Path(items[0].data(0, Qt.UserRole))
        entry = next((r for r in self.roots if Path(r["path"]) == target), None)
        if not entry:
            QMessageBox.information(
                self, "동기화", "루트 항목(레지스트리에 등록된 최상위 폴더)만 동기화할 수 있습니다."
            )
            return
        dlg = SyncFormatsDialog(target, entry, self)
        dlg.exec()
        # 다이얼로그 안 status_label은 창이 닫히면 같이 사라지니, 마지막 결과를
        # 메인 창 상태바에도 남겨서 "동기화했는데 결과가 뭐였는지" 안 잃게 함.
        last_status = dlg.status_label.text().strip()
        if last_status:
            self.statusBar().showMessage(last_status.splitlines()[0], 6000)
        self.style_item(items[0], target)
        self.on_selection_changed()

    def export_all_roots(self):
        """레지스트리 전체를 완전판 CLAUDE.md로 내보낸다(앱/레지스트리를 더
        이상 안 쓰게 될 때를 위한 스냅샷) — 동기화 마커 없는(=손편집) 파일은
        건너뛰고 보고만 한다, 절대 안 건드림. 2026-09-04(D-102, O-021
        Stage 3) — 순회+쓰기 로직은 main_pipeline.export_all_roots_to_files()
        로 이관, 이 메서드는 확인 다이얼로그+결과 표시만 담당한다."""
        if not self.roots:
            QMessageBox.information(self, "전체 내보내기", "등록된 루트가 없습니다.")
            return
        resp = QMessageBox.question(
            self, "전체 내보내기 확인",
            f"등록된 루트 {len(self.roots)}개의 CLAUDE.md를 레지스트리 전체 내용으로 "
            "채워 넣습니다(레지스트리 없이도 동작하는 완전판). 손으로 쓴 CLAUDE.md가 "
            "있는 루트는 건너뜁니다. 계속할까요?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if resp != QMessageBox.Yes:
            return

        result = main_pipeline.export_all_roots_to_files(self.roots)
        exported, skipped, failed = result["exported"], result["skipped"], result["failed"]
        msg = f"내보냄: {len(exported)}개\n건너뜀(손편집 보호): {len(skipped)}개"
        if skipped:
            msg += "\n  - " + ", ".join(skipped)
        if failed:
            msg += f"\n실패: {', '.join(failed)}"
        QMessageBox.information(self, "전체 내보내기 완료", msg)
        self.tree.clear()
        self.populate_roots()

    def run_search(self):
        query = self.search_box.text().strip()
        if not query:
            return
        dlg = SearchDialog(self.roots, query, self)
        if dlg.exec() == QDialog.Accepted and dlg.result_path:
            self.reveal_path(dlg.result_path)

    def reveal_path(self, target: str):
        """루트부터 target까지 트리를 순차적으로 펼치며 내려가서 선택한다.
        2026-08-13(D-028): 최상위에 구분선(전체 드라이브 라벨, 경로 데이터
        없음)이 섞여 있어 건너뛴다 — 안 그러면 Path(None)에서 죽는다."""
        target_path = Path(target)
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            top_data = top.data(0, Qt.UserRole)
            if not top_data:
                continue
            root_path = Path(top_data)
            try:
                rel = target_path.relative_to(root_path)
            except ValueError:
                continue
            current = top
            accumulated = root_path
            for part in rel.parts:
                self.tree.expandItem(current)
                self.on_item_expanded(current)  # 지연로딩 강제 트리거
                found = None
                for c in range(current.childCount()):
                    child = current.child(c)
                    if child.text(0) == part:
                        found = child
                        break
                if not found:
                    return
                current = found
                accumulated = accumulated / part
            self.tree.setCurrentItem(current)
            self.tree.scrollToItem(current)
            return

    # ------------------------------------------------------------ 트리

    def populate_roots(self):
        for r in self.roots:
            root_path = Path(r["path"])
            item = QTreeWidgetItem([r["label"]])
            item.setData(0, Qt.UserRole, str(root_path))
            self.style_item(item, root_path)
            self.tree.addTopLevelItem(item)
            self.add_children_placeholder(item, root_path)

        self.populate_labeled_folders()

        # 2026-08-13(D-028) — 등록된 루트 밑에 전체 드라이브도 추가로 노출.
        # "앱을 켜면 어느 드라이브든 탐색기 전체가 들어온다" 요구 — 내용을
        # 미리 스캔하지 않고(느림+대부분 무관) 기존 지연로딩(on_item_expanded)
        # 그대로 재사용해서 드라이브 문자만 최상위에 추가한다. 구분선은
        # NoItemFlags라 선택/펼치기 불가(순수 라벨).
        separator = QTreeWidgetItem(["── 전체 드라이브 (등록 안 된 폴더 탐색용) ──"])
        separator.setFlags(Qt.NoItemFlags)
        sep_font = separator.font(0)
        sep_font.setItalic(True)
        separator.setFont(0, sep_font)
        self.tree.addTopLevelItem(separator)

        for drive in get_available_drives():
            drive_path = Path(drive)
            item = QTreeWidgetItem([drive])
            item.setData(0, Qt.UserRole, str(drive_path))
            self.tree.addTopLevelItem(item)
            self.add_children_placeholder(item, drive_path)

    def populate_labeled_folders(self):
        """2026-08-22(D-073 후속, 유기적 확장) — labeledFolders[]는 지금까지
        CLI/MCP/훅만 알고 GUI 트리엔 안 보였다(별도 top-level 순회가 없었기
        때문). roots[]와 똑같은 무게로 취급하지 않는다 — 동기화/삭제 다이얼로그
        는 여전히 roots 전용, 여기선 "보인다 + 감사 상태를 한눈에 안다"만
        채운다(경량 배열이라는 설계 의도 그대로 유지)."""
        if not self.labeled_folders:
            return
        separator = QTreeWidgetItem(["── 라벨 폴더 (경량 등록, O-018(b)) ──"])
        separator.setFlags(Qt.NoItemFlags)
        sep_font = separator.font(0)
        sep_font.setItalic(True)
        separator.setFont(0, sep_font)
        self.tree.addTopLevelItem(separator)

        today = datetime.now().date()
        for f in self.labeled_folders:
            folder_path = Path(f["path"])
            audit = router_registry.labeled_folder_audit_status(f, today)
            item = QTreeWidgetItem([f["label"]])
            item.setData(0, Qt.UserRole, str(folder_path))
            if folder_path.is_dir():
                self.style_item(item, folder_path)
                self.add_children_placeholder(item, folder_path)
            if audit["status"] in ("never_audited", "due"):
                item.setForeground(0, QColor("#C6631A"))
                tip = "⚠️ 감사 이력 없음" if audit["status"] == "never_audited" else "⚠️ 30일 감사 주기 도달"
            else:
                tip = f"감사까지 {audit['daysRemaining']}일 남음"
            if not folder_path.is_dir():
                tip += " / ⚠️ 경로가 존재하지 않음(이동·삭제됐을 수 있음)"
            existing_tip = item.toolTip(0)
            item.setToolTip(0, f"{existing_tip}\n{tip}" if existing_tip else tip)
            self.tree.addTopLevelItem(item)

    def style_item(self, item: QTreeWidgetItem, folder: Path):
        idx = find_index_files(folder)
        if idx:
            f = item.font(0)
            f.setBold(True)
            item.setFont(0, f)
            names = "+".join(sorted(idx.keys()))
            item.setToolTip(0, f"인덱스 파일: {names}")

    def add_children_placeholder(self, item: QTreeWidgetItem, folder: Path):
        try:
            has_children = any(True for _ in folder.iterdir())
        except (PermissionError, OSError):
            has_children = False
        if has_children:
            item.addChild(QTreeWidgetItem(["..."]))

    def on_item_expanded(self, item: QTreeWidgetItem):
        if item.childCount() == 1 and item.child(0).text(0) == "...":
            item.takeChildren()
            folder = Path(item.data(0, Qt.UserRole))
            try:
                entries = sorted(
                    (
                        p for p in folder.iterdir()
                        if p.name == ".claude" or not p.name.startswith(".")
                    ),
                    key=lambda p: (p.is_file(), p.name.lower()),
                )
            except (PermissionError, OSError):
                entries = []
            for entry in entries:
                child = QTreeWidgetItem([entry.name])
                child.setData(0, Qt.UserRole, str(entry))
                if entry.is_dir():
                    self.style_item(child, entry)
                    self.add_children_placeholder(child, entry)
                item.addChild(child)

    def update_relations_panel(self, target: Path):
        """D-028 — target이 relations 목록에 걸리면(등록된 루트든 임의
        폴더든) 패널을 채우고, 없으면 숨긴다. 파일/폴더 어느 쪽을 선택해도
        동작(관계는 폴더 단위 prefix 매치라 파일이면 그 부모까지 안 봄 —
        의도적으로 단순하게: 파일 자체에 관계를 걸 일은 거의 없음)."""
        relations = find_relations_for_path(target, load_relations())
        self.relations_list.clear()
        if not relations:
            self.relations_label.setVisible(False)
            self.relations_list.setVisible(False)
            return
        for rel in relations:
            arrow = "↔" if rel.get("bidirectional", True) else "→"
            list_item = QListWidgetItem(f"{arrow} {rel['otherPath']}\n   {rel['reason']}")
            list_item.setData(Qt.UserRole, rel["otherPath"])
            self.relations_list.addItem(list_item)
        self.relations_label.setVisible(True)
        self.relations_list.setVisible(True)

    def on_relation_double_clicked(self, item):
        other_path = item.data(Qt.UserRole)
        if other_path:
            self.reveal_path(other_path)

    def on_selection_changed(self):
        items = self.tree.selectedItems()
        if not items:
            return
        target = Path(items[0].data(0, Qt.UserRole))
        self.update_relations_panel(target)
        if target.is_file():
            self.current_folder = None
            self.viewer.setPlainText(f"[파일] {target}\n\n더블클릭하면 기본 프로그램으로 엽니다.")
            return
        self.current_folder = target
        idx = find_index_files(target)
        if not idx:
            is_root = any(Path(r["path"]) == target for r in self.roots)
            is_labeled_folder = any(Path(f["path"]) == target for f in self.labeled_folders)
            if is_root:
                hint = (
                    "이 폴더는 등록된 루트입니다 — 툴바의 \"선택 루트 CLAUDE.md 동기화\"로 "
                    "레지스트리 참조조건 기반 init 파일을 만들 수 있습니다."
                )
            elif is_labeled_folder:
                hint = (
                    "이 폴더는 라벨 폴더로 등록돼 있습니다(labeledFolders[], 경량 등록) — "
                    "README.md가 아직 없다면 직접 작성하고 맨 위에 "
                    "<!-- SSOT-LABEL: 라벨명 --> 마커를 추가하세요(동기화 대상 아님)."
                )
            else:
                hint = (
                    "일괄/자동 생성은 등록된 루트에만 적용됩니다. 이 폴더 자체에 만들려면 "
                    "직접 작성하거나 Claude Code에게 요청하세요."
                )
            self.viewer.setPlainText(f"[{target}]\n\n이 폴더엔 CLAUDE.md/README.md가 없습니다.\n\n{hint}")
            return
        parts = []
        for name in ("claude.md", "readme.md"):
            if name in idx:
                p = idx[name]
                try:
                    text = p.read_text(encoding="utf-8", errors="replace")
                except OSError as e:
                    text = f"(읽기 실패: {e})"
                # 2026-08-13: 순수 텍스트 대신 마크다운으로 렌더링 — 파일 라벨은
                # 헤더(#)로 안 쓰고 굵게만(**) 처리해서 파일 자체의 # 제목
                # 레벨과 안 겹치게 한다.
                parts.append(f"**📄 {p.name}**\n\n{text}")
        self.viewer.setMarkdown("\n\n---\n\n".join(parts))

    def on_item_double_clicked(self, item: QTreeWidgetItem, _column: int):
        target = item.data(0, Qt.UserRole)
        if target and os.path.exists(target):
            os.startfile(target)

    # -------------------------------------------------------- 컨텍스트메뉴

    def on_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item:
            return
        target = item.data(0, Qt.UserRole)
        if not target:
            return
        menu = QMenu(self)

        act_explorer = menu.addAction("탐색기로 열기")
        act_vscode = menu.addAction("VS Code로 열기")
        act_terminal = menu.addAction("여기서 터미널 열기")
        # 2026-08-13(O-002, Lazzy_App_OS_Monorepo/Skirpt 런처 이식): cd 후
        # claude CLI까지 한 번에 실행 — Lazzy의 Claude_Code_CLC_play.cmd와
        # 같은 패턴(cmd /K "cd /d ... && claude").
        act_claude = menu.addAction("여기서 Claude Code 실행")
        act_copy = menu.addAction("경로 복사")

        root_entry = next((r for r in self.roots if Path(r["path"]) == Path(target)), None)
        web_url = (root_entry.get("webArtifactUrl") or "").strip() if root_entry else ""
        act_web = menu.addAction("웹 아티팩트 열기") if web_url else None

        chosen = menu.exec(self.tree.viewport().mapToGlobal(pos))
        folder = target if os.path.isdir(target) else str(Path(target).parent)

        if chosen == act_explorer:
            os.startfile(folder)
        elif chosen == act_vscode:
            # shell=True는 의도적 — Windows에서 `code`는 실제 .exe가 아니라
            # .cmd 셔임이라, shell 없이 CreateProcess로 직접 실행하면
            # PATHEXT 해석이 안 돼 FileNotFoundError가 난다. folder는
            # 외부 입력이 아니라 이 앱이 이미 탐색한 로컬 파일시스템 경로뿐
            # (사용자가 트리에서 고른 폴더) — 인젝션 대상이 아님.
            subprocess.Popen(["code", folder], shell=True)  # nosec B602
        elif chosen == act_terminal:
            subprocess.Popen(["cmd.exe", "/K", f"cd /d {folder}"])
        elif chosen == act_claude:
            subprocess.Popen(["cmd.exe", "/K", f"cd /d {folder} && claude"])
        elif chosen == act_copy:
            QApplication.clipboard().setText(target)
            self.statusBar().showMessage(f"📋 경로 복사됨: {target}", 3000)
        elif act_web is not None and chosen == act_web:
            webbrowser.open(web_url)


def main():
    app = QApplication(sys.argv)
    _install_crash_logging()
    default_font = app.font()
    default_font.setPointSize(12)
    app.setFont(default_font)
    win = SSOTExplorer()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

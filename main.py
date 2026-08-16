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
import sys
import os
import shutil
import webbrowser
import json
import hashlib
import logging
import subprocess
import traceback
from collections import Counter
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTreeWidget, QTreeWidgetItem, QSplitter,
    QTextBrowser, QTextEdit, QToolBar, QLineEdit, QInputDialog, QFileDialog,
    QMessageBox, QMenu, QListWidget, QListWidgetItem, QDialog, QVBoxLayout,
    QDialogButtonBox, QWidget, QPushButton, QLabel, QHBoxLayout, QStyle,
    QTabWidget,
)
from PySide6.QtCore import Qt, QProcess, QThread, Signal, QSettings
from PySide6.QtGui import QAction, QFont, QKeySequence

import router_classifier
import router_keyword_registry
import router_orchestrator
import router_proposals
import router_watcher

# 2026-08-14(D-038, H-005 다음 항목) — 레지스트리 스키마 검증. jsonschema는
# 진단용 부가기능이라 kiwipiepy(D-034)와 같은 선택적 의존성 원칙 — 미설치
# 환경에서도 앱 자체는 그대로 동작하고, 검증만 "건너뜀"으로 표시한다.
try:
    import jsonschema
    _JSONSCHEMA_AVAILABLE = True
except ImportError:
    _JSONSCHEMA_AVAILABLE = False

SCRIPTS_DIR = Path.home() / ".claude" / "scripts"
DRIFT_LOG_PATH = SCRIPTS_DIR / "ssot-index-drift.log"
# 2026-08-13: 순수 Python으로 교체(크로스플랫폼) — PS1 버전은 레거시 보존만.
DRIFT_SCRIPT_PATH = SCRIPTS_DIR / "ssot_index_drift_check.py"
# 2026-08-14(D-045) — ~/.claude/hooks/ssot_session_context.py(이 레포 밖,
# SessionStart 훅)가 쌓는 로그. 이 앱은 읽기만 함(관리자 패널 뷰).
SESSION_CONTEXT_LOG_PATH = SCRIPTS_DIR / "ssot_session_context_log.json"

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
LOG_PATH = SCRIPTS_DIR / "ssot_explorer.log"


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


def find_python_interpreter() -> str:
    """드리프트 스크립트를 실행할 python 인터프리터 경로를 찾는다.
    sys.executable은 exe로 패키징(PyInstaller)된 상태에서는 SSOT_Explorer.exe
    자기 자신을 가리켜서 못 쓴다 — 그럴 때만 PATH에서 진짜 python을 찾는다."""
    if not getattr(sys, "frozen", False):
        return sys.executable
    found = shutil.which("python") or shutil.which("python3")
    return found or "python"

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
INDEX_FILENAMES = {"claude.md", "readme.md"}


# ---------------------------------------------------------------- 레지스트리
#
# v2 (2026-08-13): 각 루트 항목이 referenceCondition(참조조건, 프로즈 텍스트)을
# 갖는다. 이게 이제 그 루트의 실질적 규칙 SSOT다 — 각 루트의 CLAUDE.md는 이
# 레지스트리에서 "동기화"로 생성되는 init 파일일 뿐(P-04 갱신: "구조화 데이터는
# 단순 목록에만" 원칙을 여기서 의도적으로 확장 — CLAUDE.md가 손으로 직접 관리하는
# 프로즈가 아니라 레지스트리에서 매번 재생성 가능한 산출물이 되므로, 재생성 시
# 항상 레지스트리와 일치해서 이중관리 위험이 원래 우려와 달리 발생하지 않음).
# referenceCondition은 앱 UI가 아니라 Claude Code가 대화 중에 직접 채운다.

class RegistryConflictError(Exception):
    """save_roots()가 쓰기 직전 재확인한 디스크 해시가, 마지막으로 읽은 시점의
    해시(_LAST_KNOWN_HASH)와 다를 때. OneDrive로 여러 기기에 동기화되는
    레지스트리라 이 세션이 모르는 사이 다른 기기/세션이 먼저 저장했을 수
    있다는 뜻 — 조용히 덮어쓰지 않고 여기서 멈춘다(낙관적 동시성 제어,
    2026-08-13. 락 대신 캐시: 이 앱은 단일 프로세스·단일 스레드라 프로세스
    내부 경합은 없고, 진짜 위험은 외부(다른 기기)라 매번 잠그기보다
    '마지막으로 확인한 값'을 기억해뒀다가 쓰기 직전에만 비교하는 쪽이 더
    맞는 해법)."""


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _current_registry_hash() -> str:
    if not REGISTRY_PATH.exists():
        return ""
    try:
        return _hash_bytes(REGISTRY_PATH.read_bytes())
    except OSError:
        return ""


_LAST_KNOWN_HASH: str = ""  # load_roots/save_roots가 성공할 때마다 갱신하는 기준선


def load_roots() -> list[dict]:
    global _LAST_KNOWN_HASH
    if not REGISTRY_PATH.exists():
        _LAST_KNOWN_HASH = ""
        return []
    try:
        raw = REGISTRY_PATH.read_bytes()
    except OSError:
        return []
    _LAST_KNOWN_HASH = _hash_bytes(raw)
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return []
    roots = data.get("roots", [])
    for r in roots:
        r.setdefault("referenceCondition", "")
        r.setdefault("readmeReferenceCondition", "")
        r.setdefault("webArtifactUrl", "")
        # 2026-08-13: 프로즈+경량 스키마 하이브리드(Backstage catalog-info.yaml
        # 방식) — 도구가 검증 가능한 필드만 얇게. 나머지(referenceCondition 등)는
        # 계속 자유 프로즈.
        r.setdefault("owner", "")
        r.setdefault("lastReviewed", "")
        r.setdefault("scope", "")
        # 2026-08-13: 영향범위 전파(안1 — 명시적 의존성 선언). 이 루트가 실제로
        # 구조적으로 의존하는 sharedDocs label 목록.
        r.setdefault("dependsOnDocs", [])
        # 2026-08-13: Lazzy_App_OS_Monorepo 이식(O-001) — 참조조건이 로컬
        # referenceCondition이 아니라 webArtifactUrl 자체인 루트 표시.
        # "local"(기본) = 지금처럼 로컬이 메인, "web" = 로컬은 참고용
        # 스냅샷일 뿐 웹 아티팩트가 유일한 정본(Lazzy가 결정이력 문서 2개를
        # 이 방식으로 전환한 사례 — 문서가 너무 커지거나/가독성이 떨어질 때).
        r.setdefault("primarySource", "local")
    return roots


def load_shared_docs() -> list[dict]:
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


def _is_or_under(target: Path, base: Path) -> bool:
    """target이 base 자신이거나 base의 하위 경로인지 — relative_to는 같은
    경로일 때도 Path('.')를 반환하며 성공하므로 두 케이스를 한 번에 잡는다."""
    try:
        target.relative_to(base)
        return True
    except ValueError:
        return False


def find_relations_for_path(target: Path, relations: list[dict]) -> list[dict]:
    """target 폴더(또는 그 하위)에 걸리는 관계만 골라, 클릭한 쪽 기준으로
    "반대쪽" 경로/이유를 붙여 돌려준다. bidirectional=False면 fromPath
    쪽에서 클릭했을 때만 보여준다(단방향 선언)."""
    matches = []
    for rel in relations:
        from_p = Path(rel["fromPath"])
        to_p = Path(rel["toPath"])
        if _is_or_under(target, from_p):
            matches.append({**rel, "otherPath": rel["toPath"], "direction": "from"})
        elif rel.get("bidirectional", True) and _is_or_under(target, to_p):
            matches.append({**rel, "otherPath": rel["fromPath"], "direction": "to"})
    return matches


REVIEW_STALE_DAYS = 180  # 이보다 오래 리뷰 안 되면 관리자 패널에서 경고 표시


def review_age_days(entry: dict) -> int | None:
    """lastReviewed로부터 오늘까지 며칠 지났는지. 값이 없거나 형식이 깨지면 None."""
    raw = (entry.get("lastReviewed") or "").strip()
    if not raw:
        return None
    try:
        last = datetime.strptime(raw, "%Y-%m-%d")
    except ValueError:
        return None
    return (datetime.now() - last).days


# ------------------------------------------------------------ 스키마 검증
#
# 2026-08-14(D-038) — 상용비교분석(D-027/D-037)이 지적한 격차 중 하나:
# Backstage의 catalog-info.yaml은 정식 스키마+검증이 있는데 이 레지스트리는
# `.setdefault()`로 필드 오타/타입 오류를 조용히 무시했다. 전부 강제하진
# 않는다 — D-018의 "프로즈+경량스키마 하이브리드" 원칙 그대로, 타입/필수
# 필드만 검증하고 scope 등 자유 프로즈 값은 여전히 자유(엄격한 enum 강제는
# 실제 값이 늘어날 때마다 오탐을 만들 위험이 더 큼). additionalProperties를
# 전부 허용하는 것도 의도적 — 실측(matchToken 필드, main.py는 안 읽지만
# 외부 훅 스크립트가 채워 쓰는 것으로 확인)처럼 이 코드가 모르는 필드를
# 다른 스크립트가 협조적으로 더 쓸 수 있다는 걸 이미 알고 있어서, 스키마가
# 이유 없이 그걸 막지 않게 한다.
REGISTRY_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "SSOT Explorer Registry",
    "type": "object",
    "additionalProperties": True,
    "properties": {
        "roots": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["label", "path"],
                "additionalProperties": True,
                "properties": {
                    "label": {"type": "string", "minLength": 1},
                    "path": {"type": "string", "minLength": 1},
                    "referenceCondition": {"type": "string"},
                    "readmeReferenceCondition": {"type": "string"},
                    "webArtifactUrl": {"type": "string"},
                    "primarySource": {"type": "string", "enum": ["local", "web"]},
                    "owner": {"type": "string"},
                    "scope": {"type": "string"},
                    "lastReviewed": {"type": "string", "pattern": r"^$|^\d{4}-\d{2}-\d{2}$"},
                    "dependsOnDocs": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        "sharedDocs": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["label", "path"],
                "additionalProperties": True,
                "properties": {
                    "label": {"type": "string", "minLength": 1},
                    "path": {"type": "string", "minLength": 1},
                },
            },
        },
        "relations": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["fromPath", "toPath"],
                "additionalProperties": True,
                "properties": {
                    "fromPath": {"type": "string", "minLength": 1},
                    "toPath": {"type": "string", "minLength": 1},
                    "reason": {"type": "string"},
                    "bidirectional": {"type": "boolean"},
                },
            },
        },
    },
}


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


def validate_registry(data: dict) -> list[str]:
    """레지스트리 원본 JSON(dict)을 스키마와 대조해 사람이 읽을 문제 목록을
    반환한다(빈 리스트 = 문제 없음). jsonschema 미설치 시에도 앱은 그대로
    동작해야 하므로 그 경우 안내 문구 1줄만 반환(예외로 앱을 막지 않음)."""
    if not _JSONSCHEMA_AVAILABLE:
        return ["jsonschema 패키지가 설치돼 있지 않아 검증을 건너뜁니다 (pip install jsonschema)"]
    validator = jsonschema.Draft7Validator(REGISTRY_SCHEMA)
    errors = []
    for err in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
        loc = "/".join(str(p) for p in err.path) or "(최상위)"
        errors.append(f"{loc}: {err.message}")
    # 2026-08-14(D-043, code-review 발견) — "배열 안에서 label이 유일해야
    # 한다"는 JSON Schema로 표현하기 어려운 제약이라 별도 체크로 보강.
    # router_orchestrator.orchestrate()/classify_content() 등 여러 곳이
    # label을 암묵적 딕셔너리 키로 쓰고 있어서, 중복되면 한쪽 루트가 결과에서
    # 조용히 사라지는 실제 버그로 이어짐 — 방어선을 여기 하나로 모아둔다.
    label_counts = Counter(
        r.get("label") for r in data.get("roots", []) if isinstance(r, dict) and r.get("label")
    )
    for label, count in label_counts.items():
        if count > 1:
            errors.append(
                f"roots: label '{label}'이(가) {count}번 중복됨 — 등록 루트의 "
                "label은 유일해야 함(중복되면 분류 결과에서 한쪽이 사라짐)"
            )
    return errors


def format_schema_validation_text(errors: list[str]) -> str:
    if not errors:
        return "✅ 스키마 검증 통과 — 문제 없음"
    lines = [f"⚠️ 스키마 문제 {len(errors)}건:"]
    lines += [f"  - {e}" for e in errors]
    return "\n".join(lines)


def save_roots(roots: list[dict]) -> None:
    """roots만 갱신 — sharedDocs/$comment 등 다른 최상위 키는 기존 파일에서
    그대로 보존한다(병합 저장, 2026-08-13 수정 — 예전엔 통째로 덮어써서
    sharedDocs가 저장할 때마다 사라지는 버그가 있었음).

    2026-08-13 추가 — 원자적 쓰기 + 낙관적 동시성 제어(레지스트리가
    OneDrive로 여러 기기에 동기화되는 걸 감안):
    - 원자적 쓰기: 같은 폴더의 임시파일에 먼저 쓰고 os.replace()로 치환.
      os.replace()는 Windows/POSIX 둘 다 원자적이라, 쓰다가 죽어도(정전,
      OneDrive 충돌 등) 절반만 쓰인 JSON이 실제 파일명으로 남는 일이 없다.
    - 낙관적 동시성 제어: 쓰기 직전 디스크의 '현재' 해시를 다시 재서
      _LAST_KNOWN_HASH(마지막으로 load_roots/save_roots가 확인한 값)와
      비교한다. 다르면 그 사이 다른 기기/세션이 먼저 저장한 것 —
      RegistryConflictError를 던져서 그 위에 조용히 덮어쓰는 걸 막는다.
      (OS 파일락은 안 씀 — 이 앱은 단일 프로세스라 프로세스 내부 경합은
      없고, 진짜 리스크는 프로세스 밖/기기 밖이라 락보다 이 비교가 맞다.)
    """
    global _LAST_KNOWN_HASH
    current_hash = _current_registry_hash()
    if _LAST_KNOWN_HASH and current_hash != _LAST_KNOWN_HASH:
        raise RegistryConflictError(
            "레지스트리가 마지막으로 읽은 이후 다른 곳에서 바뀌었습니다. "
            "덮어쓰지 않고 중단합니다 — 새로고침 후 다시 시도하세요."
        )

    payload = {}
    if REGISTRY_PATH.exists():
        try:
            payload = json.loads(REGISTRY_PATH.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            payload = {}
    payload.setdefault(
        "$comment",
        "SSOT 인덱싱 루트 레지스트리 — 단일 소스. main.py(SSOT Explorer), "
        "ssot_index_drift_check.py, ssot_index_reminder.py가 전부 이 파일을 "
        "읽는다. referenceCondition은 각 루트 CLAUDE.md(init)로 동기화되는 "
        "실제 규칙 텍스트, dependsOnDocs는 sharedDocs 의존관계(영향범위 전파) "
        "— 전부 Claude Code가 대화 중 직접 채운다.",
    )
    payload.setdefault("sharedDocs", [])
    payload.setdefault("relations", [])  # D-028 — 병합 보존(sharedDocs와 동일 이유)
    payload["roots"] = roots

    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    tmp_path = REGISTRY_PATH.with_name(REGISTRY_PATH.name + f".tmp{os.getpid()}")
    try:
        tmp_path.write_bytes(raw)
        os.replace(tmp_path, REGISTRY_PATH)  # 원자적 치환
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
    _LAST_KNOWN_HASH = _hash_bytes(raw)


SYNC_MARKER = "SSOT Explorer가 동기화"  # 두 생성 모드(포인터/전체복제) 공통 마커


def resolve_claude_md_target(folder: Path) -> Path:
    """이 폴더의 CLAUDE.md를 어디에 쓰거나 읽어야 하는지 결정한다 — 이미
    `.claude\\CLAUDE.md`(flutter_App 등의 컨벤션)가 있으면 그쪽, 아니면
    플랫 루트(새 루트는 기본이 플랫). find_index_files와 같은 두 위치를
    본다 — 여기서 어긋나면 엉뚱한 곳에 새 파일이 생기고 기존 파일은 안 지켜짐."""
    nested = folder / ".claude" / "CLAUDE.md"
    if nested.exists():
        return nested
    return folder / "CLAUDE.md"


# --------------------------------------------------------- AI 툴 포맷 어댑터
#
# 2026-08-13: CLAUDE.md 전용이던 걸 여러 AI 코딩 툴 포맷으로 확장. 같은
# referenceCondition(레지스트리, 단일 소스)에서 툴별 규칙 파일을 각각 생성 —
# "여러 AI 툴을 섞어 쓰는데 지침 파일이 서로 어긋난다"는 문제를 정면으로 겨냥.
#
# 2026-08-14(D-036, H-006): `.cursorrules`/`.windsurfrules`(플랫 단일파일)가
# 실제로는 이미 폐기된 레거시 포맷임을 상용비교분석(D-027) 중 발견 — Cursor는
# `.cursor/rules/*.mdc`(디렉토리, MDC 프론트매터), Windsurf는
# `.windsurf/rules/*.md`(디렉토리)로 이전됨. 신규 생성은 디렉토리 포맷을
# 우선하고, 레거시 플랫 파일은 "이미 있을 때만" 계속 동기화(legacy=True) —
# 새로 만들지는 않되 과거에 만들어둔 파일이 낡은 채로 방치되지도 않게.
# AGENTS.md는 30개+ 툴이 네이티브 지원하는 1차 공용 포맷으로 재포지셔닝.
# 포맷을 추가하려면 FORMAT_TARGETS에 한 줄만 추가하면 됨(파일명 + 경로 함수).

FORMAT_TARGETS: dict[str, dict] = {
    "CLAUDE.md": {
        "tool": "Claude Code",
        "resolver": lambda root: resolve_claude_md_target(root),
    },
    "AGENTS.md": {
        "tool": "범용(AGENTS.md 표준 — 30개+ 툴 네이티브 지원)",
        "resolver": lambda root: root / "AGENTS.md",
    },
    ".cursor/rules/ssot-index.mdc": {
        "tool": "Cursor",
        "resolver": lambda root: root / ".cursor" / "rules" / "ssot-index.mdc",
        "frontmatter": "---\ndescription: SSOT 인덱스 포인터\nalwaysApply: true\n---\n\n",
    },
    ".windsurf/rules/ssot-index.md": {
        "tool": "Windsurf",
        "resolver": lambda root: root / ".windsurf" / "rules" / "ssot-index.md",
        "frontmatter": "---\ntrigger: always_on\n---\n\n",
    },
    ".cursorrules": {
        "tool": "Cursor(레거시 — 이미 있을 때만 동기화, 신규 생성 안 함)",
        "resolver": lambda root: root / ".cursorrules",
        "legacy": True,
    },
    ".windsurfrules": {
        "tool": "Windsurf(레거시 — 이미 있을 때만 동기화, 신규 생성 안 함)",
        "resolver": lambda root: root / ".windsurfrules",
        "legacy": True,
    },
}

_RESULT_ICONS = {
    "ok": "✅",
    "skip": "⏭ 건너뜀(손편집 보호)",
    "skip-legacy": "⏭ 건너뜀(레거시, 신규생성 안 함)",
    "fail": "❌ 실패",
}


def resolve_format_target(root: Path, format_name: str) -> Path:
    return FORMAT_TARGETS[format_name]["resolver"](root)


def generate_init_pointer(entry: dict, format_name: str) -> str:
    """평소 모드 — 순수 포인터. 어떤 포맷(CLAUDE.md/AGENTS.md/Cursor/Windsurf 등)
    이든 내용은 동일 — 파일명만 다르다. 레지스트리가 곧 SSOT라 내용을 여기
    박아넣지 않는다(중복 없음)."""
    today = datetime.now().strftime("%Y-%m-%d")
    has_readme_cond = bool((entry.get("readmeReferenceCondition") or "").strip())
    readme_line = (
        "\nREADME.md도 있다면 그 참고조건도 같은 항목에 있다.\n"
        if has_readme_cond else ""
    )
    web_url = (entry.get("webArtifactUrl") or "").strip()
    is_web_primary = entry.get("primarySource") == "web"
    # 2026-08-13(O-001): "정본"이라는 단어는 실제로 웹이 유일한 정본일 때만
    # 붙인다 — 예전엔 webArtifactUrl만 있으면 무조건 "정본"이라 적어서, 로컬
    # referenceCondition이 여전히 메인인 경우까지 오해를 줄 수 있었다.
    if web_url and is_web_primary:
        web_line = (
            f"⚠️ 이 루트는 웹 아티팩트가 유일한 정본이다(로컬 참조조건은 참고용): "
            f"{web_url}\n"
        )
    elif web_url:
        web_line = f"웹 아티팩트(참고, 정본 아님): {web_url}\n"
    else:
        web_line = ""
    return (
        f"# {entry['label']} — SSOT 인덱스 ({format_name} init — {SYNC_MARKER}, "
        "손으로 고치지 말 것)\n\n"
        "이 폴더는 SSOT 레지스트리에 등록되어 있다. 실제 참조조건/인덱싱 규칙은 "
        "항상 아래 레지스트리 파일에서 확인한다 — 이 파일은 포인터일 뿐, 내용을 "
        "여기 복붙하지 않는다. CLAUDE.md/AGENTS.md/Cursor/Windsurf 등 여러 AI 툴 "
        "포맷 전부 같은 레지스트리 항목에서 나온 동일 내용이다 — 툴마다 따로 안 "
        "써도 됨.\n\n"
        f"레지스트리: `{REGISTRY_PATH}`\n"
        f"이 폴더의 항목: label == \"{entry['label']}\"\n"
        f"{web_line}"
        f"{readme_line}\n"
        "---\n"
        f"동기화: {today} (SSOT Explorer)\n"
    )


def generate_full_export_pointer(entry: dict, format_name: str) -> str:
    """전체 내보내기 모드 — 참조조건 전문을 그대로 박아넣는다(레지스트리/앱
    없이도 그 AI 툴이 그대로 읽을 수 있게). 포맷 무관 동일 내용."""
    today = datetime.now().strftime("%Y-%m-%d")
    condition = (entry.get("referenceCondition") or "").strip() or "(비어있음)"
    readme_condition = (entry.get("readmeReferenceCondition") or "").strip()
    readme_section = (
        f"\n## README.md 참고 조건\n\n{readme_condition}\n" if readme_condition else ""
    )
    web_url = (entry.get("webArtifactUrl") or "").strip()
    is_web_primary = entry.get("primarySource") == "web"
    web_section = ""
    web_warning = ""
    if web_url and is_web_primary:
        web_section = f"\n## 웹 아티팩트\n\n**유일한 정본**: {web_url}\n"
        # O-001: 로컬이 정본이 아닌데 "완전판"으로 내보내면 스냅샷이 금방
        # 낡아 오해를 줄 수 있어 경고를 맨 앞에 박아둔다.
        web_warning = (
            "⚠️ 이 루트는 웹 아티팩트가 정본입니다 — 아래 참조 조건은 내보내기 "
            f"시점({today}) 로컬 스냅샷일 뿐이며 최신이 아닐 수 있습니다. 최신 "
            f"내용은 반드시 위 URL에서 확인하세요.\n\n"
        )
    elif web_url:
        web_section = f"\n## 웹 아티팩트\n\n참고(정본 아님): {web_url}\n"
    return (
        f"# {entry['label']} — SSOT 인덱스 ({format_name} 전체 내보내기 — "
        f"{SYNC_MARKER}, 손으로 고치지 말 것)\n\n"
        "이 파일은 SSOT 레지스트리에서 전체 내보내기(export)로 생성됐다 — 레지스트리나 "
        "SSOT Explorer 없이도 이 파일 하나만으로 완결된다.\n\n"
        f"{web_warning}"
        "## 참조 조건\n\n"
        f"{condition}\n"
        f"{readme_section}"
        f"{web_section}\n"
        "---\n"
        f"내보내기: {today} (SSOT Explorer)\n"
    )


def generate_init_claude_md(entry: dict) -> str:
    """하위호환 wrapper — CLAUDE.md는 generate_init_pointer의 특수 케이스."""
    return generate_init_pointer(entry, "CLAUDE.md")


def generate_init_readme_md(entry: dict) -> str:
    """README도 평소엔 순수 포인터 — README 참고조건은 레지스트리에 있다."""
    today = datetime.now().strftime("%Y-%m-%d")
    return (
        f"# {entry['label']} (init — {SYNC_MARKER}, 손으로 고치지 말 것)\n\n"
        "이 폴더의 README 참고조건은 SSOT 레지스트리(`readmeReferenceCondition`)에 "
        "있다 — 여기 복붙하지 않는다.\n\n"
        f"레지스트리: `{REGISTRY_PATH}`\n"
        f"이 폴더의 항목: label == \"{entry['label']}\"\n\n"
        "---\n"
        f"동기화: {today} (SSOT Explorer)\n"
    )


def generate_full_export_readme_md(entry: dict) -> str:
    """전체 내보내기 모드의 README — readmeReferenceCondition 전체를 그대로 박아넣는다."""
    today = datetime.now().strftime("%Y-%m-%d")
    condition = (entry.get("readmeReferenceCondition") or "").strip() or "(비어있음)"
    return (
        f"# {entry['label']} (전체 내보내기 — {SYNC_MARKER}, 손으로 고치지 말 것)\n\n"
        f"{condition}\n\n"
        "---\n"
        f"내보내기: {today} (SSOT Explorer)\n"
    )


def generate_full_export_claude_md(entry: dict) -> str:
    """하위호환 wrapper — CLAUDE.md는 generate_full_export_pointer의 특수 케이스."""
    return generate_full_export_pointer(entry, "CLAUDE.md")


def format_registry_text(roots: list[dict]) -> str:
    """레지스트리를 raw JSON이 아니라 루트별로 정리된 텍스트로 보여준다."""
    if not roots:
        return "(등록된 루트 없음)"
    blocks = []
    for r in roots:
        cond = (r.get("referenceCondition") or "").strip() or "(비어있음)"
        readme_cond = (r.get("readmeReferenceCondition") or "").strip()
        age = review_age_days(r)
        if age is None:
            review_line = "  리뷰: 기록 없음 ⚠️"
        elif age > REVIEW_STALE_DAYS:
            review_line = f"  리뷰: {r.get('lastReviewed')} ({age}일 전) ⚠️ 리뷰 필요"
        else:
            review_line = f"  리뷰: {r.get('lastReviewed')} ({age}일 전)"
        web_primary_tag = " 🌐웹정본" if r.get("primarySource") == "web" else ""
        block = (
            f"■ {r['label']}{web_primary_tag}"
            f" [owner={r.get('owner') or '?'}, scope={r.get('scope') or '?'}]\n"
            f"{review_line}\n"
            f"  경로: {r['path']}\n"
            f"  참조조건: {cond}"
        )
        if readme_cond:
            block += f"\n  README 참고: {readme_cond}"
        web_url = (r.get("webArtifactUrl") or "").strip()
        if web_url:
            block += f"\n  웹 아티팩트: {web_url}"
        depends = r.get("dependsOnDocs") or []
        if depends:
            block += f"\n  공용문서 의존: {', '.join(depends)}"
        blocks.append(block)
    return "\n\n".join(blocks)


def format_shared_docs_text(shared_docs: list[dict]) -> str:
    """sharedDocs를 정리된 텍스트로 — 이 문서들이 바뀌면 dependsOnDocs에 건
    루트들에 드리프트체크가 '반영 필요'를 표시한다."""
    if not shared_docs:
        return "(등록된 공용문서 없음)"
    lines = []
    for d in shared_docs:
        exists = Path(d["path"]).exists()
        lines.append(f"■ {d['label']}{'' if exists else ' ⚠️ 파일 없음'}\n  경로: {d['path']}")
    return "\n\n".join(lines)


def format_watcher_log_text(events: list[dict], limit: int = 20) -> str:
    """D-042 — Inbox 감시 로그를 관리자 패널에 보여줄 텍스트로. 최신 항목이
    위로 오게(다른 로그뷰들과 통일된 관례) 최근 limit개만."""
    if not events:
        return "(로그 없음 — 아직 감지된 파일 없음, Inbox 감시를 시작하면 쌓임)"
    recent = events[-limit:]
    lines = [f"{e['timestamp']}  {e['fileName']}  ({e['watchDir']})" for e in recent]
    return "\n".join(reversed(lines))


def load_session_context_log(path: Path | None = None) -> list[dict]:
    """D-045 — SessionStart 훅이 쌓는 "어떤 루트가 언제 매치됐는지" 로그를
    읽기만 한다(이 앱은 안 씀, 훅 스크립트 전용 쓰기)."""
    p = path or SESSION_CONTEXT_LOG_PATH
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return []


def format_session_context_log_text(entries: list[dict], limit: int = 20) -> str:
    """관리자 패널용 — 최신이 위로, 최근 limit개만."""
    if not entries:
        return "(로그 없음 — 등록 루트 안에서 Claude Code 세션을 열면 쌓임)"
    recent = entries[-limit:]
    lines = [
        f"{e['timestamp']}  {e['matchedLabel']}  (관련폴더 {e['relatedCount']}개, 다른루트 {e['otherRootsCount']}개)"
        for e in recent
    ]
    return "\n".join(reversed(lines))


def get_available_drives() -> list[str]:
    """존재하는 Windows 드라이브 문자 목록(C:\\, D:\\ 등) — 외부 의존성 없이
    알파벳을 순회하며 확인한다. 2026-08-13(D-028) — "앱을 켜면 전체 탐색기가
    다 들어온다" 요구를 위한 최상위 진입점. 실제 내용은 여기서 안 읽는다
    (존재 여부만 stat) — 각 드라이브 밑은 트리가 펼칠 때만(지연 로딩) 읽음,
    그래서 드라이브가 몇 개든 이 함수 자체는 즉시 끝난다."""
    import string
    drives = []
    for letter in string.ascii_uppercase:
        drive = f"{letter}:\\"
        if Path(drive).exists():
            drives.append(drive)
    return drives


# 2026-08-14(D-041, H-003) — 대소문자만 다른 CLAUDE.md/claude.md가 한 폴더에
# 동시에 존재하는 경우의 방어 코드. Windows는 파일시스템이 대소문자를 구분 안
# 해서 이 상황 자체가 발생 안 하지만, 이 프로젝트는 크로스플랫폼을 표방하고
# (D-019 순수 Python 스크립트, D-039 경로 이식성) 대소문자 구분 파일시스템
# (Linux 등)에서는 실제로 둘 다 존재할 수 있음 — 실사용에서 재현된 적은
# 없지만(H-003 원 결정문 그대로), 재현을 기다리지 않고 이번 라운드에서 미리
# 방어. CANONICAL_INDEX_NAMES를 우선 채택, 그래도 안 갈리면(둘 다 비표준
# 표기) 이름 사전순 — 실행마다 같은 선택이 나오게(OS 디렉토리 순회 순서에
# 의존하던 기존 setdefault 방식은 결정적이지 않았음).
CANONICAL_INDEX_NAMES = {"claude.md": "CLAUDE.md", "readme.md": "README.md"}


def pick_canonical_index_file(key: str, paths: list[Path]) -> Path:
    """같은 폴더에 대소문자만 다른 인덱스 파일이 여러 개일 때 어느 걸 쓸지
    결정적으로 고른다 — find_index_files에서 분리한 순수 함수(디스크 접근
    없이 테스트 가능, 실제 케이스-센서티브 파일시스템 없이도 회귀 검증)."""
    canonical = CANONICAL_INDEX_NAMES.get(key)
    chosen = next((p for p in paths if p.name == canonical), None)
    return chosen if chosen is not None else sorted(paths, key=lambda p: p.name)[0]


def find_index_files(folder: Path) -> dict:
    """folder 바로 밑, 그리고 folder\\.claude 밑 양쪽에서 CLAUDE.md/README.md를
    찾는다 — 플랫 컨벤션과 `.claude` 하위 컨벤션 둘 다 지원. 바로 밑 파일이
    있으면 그쪽을 우선한다."""
    found = {}
    if not folder.is_dir():
        return found
    candidates = [folder]
    claude_sub = folder / ".claude"
    if claude_sub.is_dir():
        candidates.append(claude_sub)
    for base in candidates:
        try:
            matches: dict[str, list[Path]] = {}
            for entry in base.iterdir():
                if entry.is_file() and entry.name.lower() in INDEX_FILENAMES:
                    matches.setdefault(entry.name.lower(), []).append(entry)
        except (PermissionError, OSError):
            continue
        for key, paths in matches.items():
            if key in found:
                continue  # 상위 base(폴더 바로 밑)가 이미 채웠으면 유지 — 기존 우선순위
            if len(paths) == 1:
                found[key] = paths[0]
                continue
            chosen = pick_canonical_index_file(key, paths)
            found[key] = chosen
            others = ", ".join(p.name for p in paths if p != chosen)
            log.warning(
                f"{base}에 대소문자만 다른 인덱스 파일 {len(paths)}개 발견 — "
                f"'{chosen.name}' 사용, 무시됨: {others}"
            )
    return found


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
            self.accept()

    def _stop_worker(self):
        if self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait(300)

    def reject(self):
        self._stop_worker()
        super().reject()

    def closeEvent(self, event):
        self._stop_worker()
        super().closeEvent(event)


# -------------------------------------------------------------------- 관리

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
        docs_text = format_shared_docs_text(load_shared_docs())
        roots_text = format_registry_text(load_roots())
        self.registry_view.setPlainText(f"[공용문서(sharedDocs)]\n{docs_text}\n\n[루트]\n{roots_text}")
        errors = validate_registry(load_registry_raw())
        self.schema_view.setPlainText(format_schema_validation_text(errors))
        self.watcher_log_view.setPlainText(format_watcher_log_text(router_watcher.load_watcher_log()))
        self.keyword_registry_view.setPlainText(
            router_keyword_registry.format_keyword_registry_text(router_keyword_registry.load_keyword_registry())
        )
        self.session_context_log_view.setPlainText(
            format_session_context_log_text(load_session_context_log())
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


# ------------------------------------------------------- AI 툴별 동기화 다이얼로그

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

    def _write_one(self, format_name: str, force: bool) -> str:
        info = FORMAT_TARGETS[format_name]
        target = info["resolver"](self.root_path)
        if info.get("legacy") and not target.exists():
            return "skip-legacy"  # 레거시 포맷은 이미 있을 때만 갱신, 신규 생성 안 함
        if target.exists() and not force:
            existing = target.read_text(encoding="utf-8", errors="replace")
            if SYNC_MARKER not in existing:
                return "skip"
        try:
            target.parent.mkdir(parents=True, exist_ok=True)  # .cursor/rules 등 신규 디렉토리
            body = info.get("frontmatter", "") + generate_init_pointer(self.entry, format_name)
            target.write_text(body, encoding="utf-8")
            return "ok"
        except OSError:
            return "fail"

    def sync_one(self, format_name: str):
        target = resolve_format_target(self.root_path, format_name)
        force = False
        if target.exists():
            existing = target.read_text(encoding="utf-8", errors="replace")
            if SYNC_MARKER not in existing:
                resp = QMessageBox.question(
                    self, "덮어쓰기 확인",
                    f"{target}\n\n이미 있고 자동생성 표식이 없습니다 — 손으로 쓴 "
                    "내용일 수 있습니다. 그래도 덮어쓸까요?",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
                )
                if resp != QMessageBox.Yes:
                    self.status_label.setText(f"{format_name}: 건너뜀(취소)")
                    return
                force = True
        result = self._write_one(format_name, force)
        self.status_label.setText(f"{_RESULT_ICONS[result]} {format_name}: {result} → {target}")

    def sync_all(self):
        lines = []
        for fmt in FORMAT_TARGETS:
            result = self._write_one(fmt, force=False)
            lines.append(f"{fmt}: {_RESULT_ICONS[result]}")
        self.status_label.setText("\n".join(lines))

    def mark_reviewed(self):
        today = datetime.now().strftime("%Y-%m-%d")
        roots = load_roots()
        target_entry = next((r for r in roots if r["label"] == self.entry["label"]), None)
        if not target_entry:
            self.status_label.setText("❌ 레지스트리에서 항목을 못 찾음")
            return
        target_entry["lastReviewed"] = today
        try:
            save_roots(roots)
        except RegistryConflictError as e:
            self.status_label.setText(f"⚠️ {e}")
            return
        self.entry["lastReviewed"] = today
        self.status_label.setText(f"✅ 리뷰 완료로 표시: {today}")


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
        읽는다."""
        items = self.candidates_list.selectedItems()
        if not items:
            self.status_label.setText("⚠️ 먼저 후보 목록에서 하나를 선택하세요.")
            return
        candidate = items[0].data(Qt.UserRole)
        raw_filename = self.filename_edit.text().strip()
        if not raw_filename:
            self.status_label.setText("⚠️ 파일명을 입력하세요.")
            return
        # 절대경로나 '..'가 섞인 파일명이면 등록된 루트 밖으로 쓰기가 샐 수
        # 있음(code-review 발견) — 두 단계로 막는다: (1) 파츠 검사로 명백한
        # 케이스 즉시 거절 (2) resolve() 기반으로 최종 목적지가 실제로 루트
        # 밑인지 재확인(심볼릭 링크 등 우회까지 방어).
        name_path = Path(raw_filename)
        root_path = Path(candidate["rootPath"])
        if name_path.is_absolute() or ".." in name_path.parts:
            self.status_label.setText("⚠️ 파일명에 절대경로나 '..'는 쓸 수 없습니다.")
            return
        target = root_path / name_path
        try:
            target.resolve().relative_to(root_path.resolve())
        except ValueError:
            self.status_label.setText("⚠️ 파일명이 등록된 루트 밖을 가리킵니다.")
            return
        if target.exists():
            resp = QMessageBox.question(
                self, "덮어쓰기 확인",
                f"{target}\n\n이미 존재합니다. 덮어쓸까요?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if resp != QMessageBox.Yes:
                return
        content = self.content_edit.toPlainText()
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        except OSError as e:
            self.status_label.setText(f"❌ 저장 실패: {e}")
            return
        router_proposals.record_decision(candidate, content, "approved")
        QMessageBox.information(self, "저장 완료", f"저장됨: {target}")
        self.accept()

    def cancel_and_close(self):
        if self.candidates:
            # 후보를 봤는데(=제안을 받았는데) 저장 안 하고 취소 — 1순위
            # 후보 기준으로 "취소" 기록(제안 정밀도 데이터 누적, 사용자
            # 요청사항). 아예 분류를 안 돌려본 채 닫으면 기록 안 함 —
            # 판단할 제안 자체가 없었으니까.
            router_proposals.record_decision(self.candidates[0], self.classified_text, "cancelled")
        self.reject()

    def _stop_worker(self):
        """SearchDialog(D-013)와 같은 이유 — 다이얼로그가 닫히는 동안 백그
        라운드 스레드가 끝나서 이미 파괴된 위젯에 신호를 쏘는 걸 막는다.
        orchestrate()는 SearchWorker처럼 중간에 끊을 체크포인트가 없는
        단일 호출이라(취소 플래그 대신) 신호만 먼저 끊고 최대 2초 기다린다
        — kiwipiepy 콜드인잇 포함 실측 ~1.4초(D-034)라 충분한 여유."""
        if self.worker is not None and self.worker.isRunning():
            try:
                self.worker.result_ready.disconnect(self._on_classification_result)
            except (RuntimeError, TypeError):
                pass
            self.worker.wait(2000)

    def reject(self):
        self._stop_worker()
        super().reject()

    def closeEvent(self, event):
        self._stop_worker()
        super().closeEvent(event)


# ---------------------------------------------------------------------- 앱

class SSOTExplorer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SSOT Explorer")
        self.resize(1200, 750)

        self.roots = load_roots()
        self.current_folder: Path | None = None
        self.inbox_watcher_thread: InboxWatcherThread | None = None
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
        self.management_panel = ManagementPanel(self)
        self.tabs = QTabWidget()
        self.tabs.addTab(self.splitter, "탐색기")
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
            self.inbox_watcher_thread.wait(3000)
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

        manage_action = QAction(style.standardIcon(QStyle.SP_FileDialogDetailedView), "개발자 탭으로", self)
        manage_action.setToolTip("개발자 탭으로 전환(레지스트리/스키마검증/로그 뷰 + 드리프트 체크)")
        manage_action.triggered.connect(self.open_management)
        bar.addAction(manage_action)

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
            self.inbox_watcher_thread.wait(3000)
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
        없으므로). 조용히 처리하고 상태바에 몇 개 채웠는지만 알림."""
        created = []
        for entry in self.roots:
            root_path = Path(entry["path"])
            if not root_path.is_dir():
                continue  # 경로 자체가 없으면(다른 기기 전용 등) 건너뜀
            claude_path = resolve_claude_md_target(root_path)
            if claude_path.exists():
                continue
            try:
                claude_path.write_text(generate_init_claude_md(entry), encoding="utf-8")
                created.append(entry["label"])
            except OSError:
                pass  # 권한 문제 등 — 조용히 건너뜀, 앱 시작을 막을 이유 없음
        if created:
            self.tree.clear()
            self.populate_roots()
            self.statusBar().showMessage(
                f"📌 init 파일 없던 루트 {len(created)}개 자동 생성: {', '.join(created)}", 6000
            )

    def add_root(self):
        folder = QFileDialog.getExistingDirectory(self, "SSOT 루트로 등록할 폴더 선택")
        if not folder:
            return
        label, ok = QInputDialog.getText(self, "루트 이름", "표시할 이름:", text=Path(folder).name)
        if not ok or not label.strip():
            return
        entry = {"label": label.strip(), "path": folder, "referenceCondition": ""}
        self.roots.append(entry)
        try:
            save_roots(self.roots)
        except RegistryConflictError as e:
            self.roots.pop()  # 실패했으니 메모리 상태도 되돌림
            self.roots = load_roots()  # 최신 디스크 상태로 다시 맞춤
            QMessageBox.warning(self, "루트 추가 실패", f"{e}\n(레지스트리를 새로고침했습니다 — 다시 시도하세요.)")
            self.tree.clear()
            self.populate_roots()
            return

        # 새 루트는 기존 내용이 없으니 안전하게 init CLAUDE.md를 바로 생성
        claude_path = resolve_claude_md_target(Path(folder))
        if not claude_path.exists():
            try:
                claude_path.write_text(generate_init_claude_md(entry), encoding="utf-8")
            except OSError as e:
                QMessageBox.warning(self, "init 생성 실패", str(e))

        self.tree.clear()
        self.populate_roots()
        self.statusBar().showMessage(f"✅ 루트 추가됨: {entry['label']}", 4000)

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
        """실제 삭제 로직 — 툴바 버튼과 Delete 단축키가 공유(중복 제거)."""
        removed = self.roots.pop(idx)
        try:
            save_roots(self.roots)
        except RegistryConflictError as e:
            self.roots.insert(idx, removed)  # 실패했으니 메모리 상태도 되돌림
            self.roots = load_roots()  # 최신 디스크 상태로 다시 맞춤
            QMessageBox.warning(self, "루트 삭제 실패", f"{e}\n(레지스트리를 새로고침했습니다 — 다시 시도하세요.)")
            self.tree.clear()
            self.populate_roots()
            return
        self.tree.clear()
        self.populate_roots()
        self.statusBar().showMessage(f"🗑 삭제됨: {removed['label']} (파일은 그대로 둠, 레지스트리에서만 제외)", 5000)

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
        건너뛰고 보고만 한다, 절대 안 건드림."""
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

        exported, skipped, failed = [], [], []
        for entry in self.roots:
            root_path = Path(entry["path"])
            claude_path = resolve_claude_md_target(root_path)
            if claude_path.exists():
                existing = claude_path.read_text(encoding="utf-8", errors="replace")
                if SYNC_MARKER not in existing:
                    skipped.append(entry["label"])
                    continue
            try:
                claude_path.write_text(generate_full_export_claude_md(entry), encoding="utf-8")
                exported.append(entry["label"])
            except OSError:
                failed.append(entry["label"])
                continue

            if (entry.get("readmeReferenceCondition") or "").strip():
                readme_path = root_path / "README.md"
                if readme_path.exists():
                    existing_readme = readme_path.read_text(encoding="utf-8", errors="replace")
                    if SYNC_MARKER not in existing_readme:
                        continue  # README는 손편집 보호, CLAUDE.md만 내보내고 건너뜀
                try:
                    readme_path.write_text(generate_full_export_readme_md(entry), encoding="utf-8")
                except OSError:
                    pass

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
            hint = (
                "이 폴더는 등록된 루트입니다 — 툴바의 \"선택 루트 CLAUDE.md 동기화\"로 "
                "레지스트리 참조조건 기반 init 파일을 만들 수 있습니다."
                if is_root else
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
            subprocess.Popen(["code", folder], shell=True)
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

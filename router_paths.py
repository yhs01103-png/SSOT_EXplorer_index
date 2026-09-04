"""SSOT_Explorer — 경로(path) 레이어(2026-09-04, D-098, O-021 Stage 1).

레이어 분리 방침(Plug_In_Global\\.claude\\레이어_분리_방침.md)의 "경로" 레이어를
실제로 신설한다 — 지금까지 SCRIPTS_DIR/각종 *_LOG_PATH가 8개 파일(main.py,
router_orchestrator.py, router_proposals.py, router_keyword_registry.py,
router_registry.py, router_watcher.py, ssot_background_watchdog.py,
dev_console_server.py)에 각자 흩어져 선언돼 있었다 — 방침의 "모든 경로/설정값은
이 레이어에서만 선언" 원칙과 안 맞는다는 게 상용 비교 분석(O-021)에서 지적됨.

`REGISTRY_PATH`(`router_proposals.resolve_registry_path()`)는 이관 대상 밖 —
이미 그 함수 하나로 중앙화돼 있고, 리스크 최소화를 위해 이번 스테이지는 "새
상수 이관만"으로 범위를 좁힌다(기존 계약은 안 건드림).

**테스트 호환 계약(중요)**: 이 모듈은 상수만 선언하고 아무것도 import하지
않는다(경로 레이어는 "전 레이어가 참조하되 아무것도 호출 안 함" 원칙, 방침
문서 그대로). 각 소비 모듈은 `from router_paths import XXX_PATH`로 재노출해서
기존 monkeypatch 기반 테스트(각 모듈 자신의 속성을 패치하는 방식 —
`router_sync.FORMAT_TARGETS`/`SYNC_MARKER`를 main.py가 재노출하는 것과 동일
기법, D-068)가 안 깨지게 유지한다.
"""
from __future__ import annotations

from pathlib import Path

SCRIPTS_DIR = Path.home() / ".claude" / "scripts"

# ---------------------------------------------------------------- main.py 전용
DRIFT_LOG_PATH = SCRIPTS_DIR / "ssot-index-drift.log"
# 2026-08-13: 순수 Python으로 교체(크로스플랫폼) — PS1 버전은 레거시 보존만.
DRIFT_SCRIPT_PATH = SCRIPTS_DIR / "ssot_index_drift_check.py"
# 2026-08-14(D-045) — ~/.claude/hooks/ssot_session_context.py(이 레포 밖,
# SessionStart 훅)가 쌓는 로그. main.py는 읽기만 함(관리자 패널 뷰).
SESSION_CONTEXT_LOG_PATH = SCRIPTS_DIR / "ssot_session_context_log.json"
# 2026-08-13(D-025) — Lazzy_App_OS_Monorepo/server/core/log/jarvis_log.py
# 이식. Windows 콘솔(cp949 등)이 이모지/em-dash를 못 만나면 print()는
# UnicodeEncodeError로 프로세스 자체를 죽였다(2026-07-29 실측 사고). main.py의
# _setup_logger()가 이 경로에 FileHandler를 건다.
LOG_PATH = SCRIPTS_DIR / "ssot_explorer.log"

# --------------------------------------------------------- router_orchestrator.py
ORCHESTRATION_LOG_PATH = SCRIPTS_DIR / "ssot_orchestrator_log.json"

# ------------------------------------------------------------- router_proposals.py
PROPOSALS_LOG_PATH = SCRIPTS_DIR / "ssot_router_proposals.json"
TRUST_STATE_PATH = SCRIPTS_DIR / "ssot_router_trust.json"

# ----------------------------------------------------- router_keyword_registry.py
KEYWORD_REGISTRY_PATH = SCRIPTS_DIR / "ssot_keyword_registry.json"

# --------------------------------------------------------------- router_registry.py
# 2026-09-04 — 하위 폴더 README 재귀 추적(D-090)의 스냅샷 기준점. 레지스트리
# 본체(ssot-roots.json)와 별개 파일이라 RegistryConflictError 동시성 제어
# 대상이 아니다.
FOLDER_SNAPSHOT_PATH = SCRIPTS_DIR / "ssot_folder_snapshots.json"

# ---------------------------------------------------------------- router_watcher.py
WATCHER_LOG_PATH = SCRIPTS_DIR / "ssot_watcher_log.json"

# --------------------------------------------------------- ssot_background_watchdog.py
WATCHDOG_LOG_PATH = SCRIPTS_DIR / "ssot_watchdog_log.json"

# ------------------------------------------------------------- dev_console_server.py
# 정적 자산 경로 — 런타임 로그와 성격은 다르지만("이 레이어에서만 선언"이라는
# 본질은 같음). router_paths.py도 SSOT_Explorer/ 밑에 있어 dev_console_static/
# 상대 위치는 동일하게 계산된다.
STATIC_DIR = Path(__file__).resolve().parent / "dev_console_static"
PAGE_PATH = STATIC_DIR / "dev_console.html"

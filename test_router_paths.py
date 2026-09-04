"""router_paths.py 전용 테스트 — D-098, O-021 Stage 1(레이어 분리 방침의
"경로" 레이어 신설). 이 모듈은 상수만 선언하므로 검증할 로직은 사실상 없다 —
대신 (1) 모든 상수가 SCRIPTS_DIR 밑에 있는지(dev_console_server의 정적 자산
경로만 예외) (2) 각 소비 모듈이 재노출한 이름이 실제로 이 모듈의 값과 동일한
객체인지를 확인해, "재노출을 깜빡해서 두 값이 갈라지는" 회귀를 방지한다."""
from __future__ import annotations

from pathlib import Path

import router_paths as rp


def test_scripts_dir_based_constants_live_under_scripts_dir():
    scripts_based = [
        rp.DRIFT_LOG_PATH, rp.DRIFT_SCRIPT_PATH, rp.SESSION_CONTEXT_LOG_PATH,
        rp.LOG_PATH, rp.ORCHESTRATION_LOG_PATH, rp.PROPOSALS_LOG_PATH,
        rp.TRUST_STATE_PATH, rp.KEYWORD_REGISTRY_PATH, rp.FOLDER_SNAPSHOT_PATH,
        rp.WATCHER_LOG_PATH, rp.WATCHDOG_LOG_PATH,
    ]
    for path in scripts_based:
        assert path.parent == rp.SCRIPTS_DIR


def test_static_asset_paths_live_next_to_this_module():
    assert rp.STATIC_DIR == Path(__file__).resolve().parent / "dev_console_static"
    assert rp.PAGE_PATH == rp.STATIC_DIR / "dev_console.html"


def test_main_reexports_match_router_paths():
    import main as m
    assert m.DRIFT_LOG_PATH is rp.DRIFT_LOG_PATH
    assert m.DRIFT_SCRIPT_PATH is rp.DRIFT_SCRIPT_PATH
    assert m.SESSION_CONTEXT_LOG_PATH is rp.SESSION_CONTEXT_LOG_PATH
    assert m.LOG_PATH is rp.LOG_PATH
    assert m.SCRIPTS_DIR is rp.SCRIPTS_DIR


def test_router_orchestrator_reexports_match_router_paths():
    import router_orchestrator as ro
    assert ro.ORCHESTRATION_LOG_PATH is rp.ORCHESTRATION_LOG_PATH


def test_router_proposals_reexports_match_router_paths():
    import router_proposals as proposals
    assert proposals.PROPOSALS_LOG_PATH is rp.PROPOSALS_LOG_PATH
    assert proposals.TRUST_STATE_PATH is rp.TRUST_STATE_PATH


def test_router_keyword_registry_reexports_match_router_paths():
    import router_keyword_registry as kr
    assert kr.KEYWORD_REGISTRY_PATH is rp.KEYWORD_REGISTRY_PATH


def test_router_registry_reexports_match_router_paths():
    import router_registry as rr
    assert rr.FOLDER_SNAPSHOT_PATH is rp.FOLDER_SNAPSHOT_PATH


def test_router_watcher_reexports_match_router_paths():
    import router_watcher as rw
    assert rw.WATCHER_LOG_PATH is rp.WATCHER_LOG_PATH


def test_ssot_background_watchdog_reexports_match_router_paths():
    import ssot_background_watchdog as watchdog
    assert watchdog.WATCHDOG_LOG_PATH is rp.WATCHDOG_LOG_PATH


def test_dev_console_server_reexports_match_router_paths():
    import dev_console_server as dcs
    assert dcs.PAGE_PATH is rp.PAGE_PATH

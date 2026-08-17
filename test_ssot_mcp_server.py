"""ssot_mcp_server.py 전용 테스트 — D-048. tool 함수(@server.tool()로 감싼
함수도 원본 그대로 직접 호출 가능, MCPServer가 데코레이터에서 원본을
반환함을 실측 확인함)를 프로토콜 계층 없이 직접 부른다 — dev_console_server
테스트(D-046)가 실제 소켓까지 왕복하는 것과 달리, 여기는 mtime 계산 로직이
핵심이라 순수 함수 호출로 충분(과한 인프라 안 씀). conftest.py 없이 파일
하나로(D-024 관례) — 실제 사용자 레지스트리는 절대 안 건드리게 이 파일
안에서 monkeypatch."""
from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

import main as m
import router_keyword_registry as kr
import router_orchestrator as ro
import router_proposals as rp
import ssot_mcp_server as mcp_srv


@pytest.fixture(autouse=True)
def isolated_registry(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "REGISTRY_PATH", tmp_path / "ssot-roots.json")
    m._LAST_KNOWN_HASH = ""
    yield


@pytest.fixture(autouse=True)
def isolated_orchestrator_state(tmp_path, monkeypatch):
    """classify_content()가 내부적으로 router_orchestrator.orchestrate()를
    부르는데, 이게 오케스트레이션 로그/키워드 레지스트리/신뢰상태 전부를
    기본(실제 사용자) 경로에 쓴다 — test_router_orchestrator.py와 같은
    이유로 셋 다 격리(D-044 이후 정립된 관례)."""
    monkeypatch.setattr(ro, "ORCHESTRATION_LOG_PATH", tmp_path / "orch-log.json")
    monkeypatch.setattr(kr, "KEYWORD_REGISTRY_PATH", tmp_path / "keywords.json")
    monkeypatch.setattr(rp, "PROPOSALS_LOG_PATH", tmp_path / "proposals.json")
    monkeypatch.setattr(rp, "TRUST_STATE_PATH", tmp_path / "trust.json")
    yield


def _touch(path: Path, mtime_offset_days: float, content: str = "x"):
    """path에 content를 쓰고 mtime을 '지금 - mtime_offset_days일'로 강제
    설정 — 오래된 파일/최신 파일 시나리오를 결정적으로 재현하기 위함."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    target = time.time() - mtime_offset_days * 86400
    os.utime(path, (target, target))


def _register_root(label: str, path: Path):
    m.save_roots([{"label": label, "path": str(path)}])


# --------------------------------------------------------------- list_ssot_roots

def test_list_ssot_roots_returns_registered_entries():
    m.save_roots([
        {"label": "a", "path": "C:\\a", "scope": "workspace", "referenceCondition": "조건A"},
        {"label": "b", "path": "C:\\b"},
    ])
    result = mcp_srv.list_ssot_roots()
    assert [r["label"] for r in result] == ["a", "b"]
    assert result[0]["referenceCondition"] == "조건A"
    assert result[1]["referenceCondition"] == ""  # 없으면 빈 문자열(None 아님)


def test_list_ssot_roots_empty_when_no_registry():
    assert mcp_srv.list_ssot_roots() == []


def test_list_ssot_roots_reports_path_exists(tmp_path):
    """D-052 — 폴더 삭제/이동 신호(pathExists)가 MCP로도 나가는지."""
    missing = tmp_path / "does-not-exist"
    m.save_roots([
        {"label": "here", "path": str(tmp_path)},
        {"label": "gone", "path": str(missing)},
    ])
    result = mcp_srv.list_ssot_roots()
    by_label = {r["label"]: r["pathExists"] for r in result}
    assert by_label == {"here": True, "gone": False}


# ------------------------------------------------------- check_readme_freshness

def test_readme_freshness_root_missing_on_disk(tmp_path):
    _register_root("gone", tmp_path / "does-not-exist")
    result = mcp_srv.check_readme_freshness()
    assert result == [{"label": "gone", "path": str(tmp_path / "does-not-exist"), "status": "root_missing"}]


def test_readme_freshness_no_readme(tmp_path):
    root = tmp_path / "root"
    _touch(root / "main.py", 0)
    _register_root("noreadme", root)
    result = mcp_srv.check_readme_freshness()
    assert result[0]["status"] == "no_readme"


def test_readme_freshness_fresh_when_readme_is_newest(tmp_path):
    root = tmp_path / "root"
    _touch(root / "old_code.py", 10)
    _touch(root / "README.md", 0)  # 방금 갱신
    _register_root("fresh-root", root)
    result = mcp_srv.check_readme_freshness()
    assert result[0]["status"] == "fresh"
    assert "readmePath" in result[0]
    assert "gapDays" not in result[0]  # README가 최신이면 격차 자체가 없음


def test_readme_freshness_stale_when_gap_exceeds_threshold(tmp_path):
    root = tmp_path / "root"
    _touch(root / "README.md", 60)  # 60일 전
    _touch(root / "new_code.py", 0)  # 방금 수정 — 60일 격차
    _register_root("stale-root", root)
    result = mcp_srv.check_readme_freshness(stale_days=30)
    assert result[0]["status"] == "stale"
    assert result[0]["gapDays"] == pytest.approx(60, abs=1)


def test_readme_freshness_small_gap_stays_fresh(tmp_path):
    root = tmp_path / "root"
    _touch(root / "README.md", 10)
    _touch(root / "new_code.py", 0)  # 10일 격차
    _register_root("small-gap-root", root)
    result = mcp_srv.check_readme_freshness(stale_days=30)
    assert result[0]["status"] == "fresh"
    assert result[0]["gapDays"] == pytest.approx(10, abs=1)  # 격차는 보여주되 임계값 안 넘으면 fresh


def test_readme_freshness_ignores_dot_folders(tmp_path):
    """SearchWorker(D-013)와 같은 관례 — .git 등 dot-폴더 안 파일은 신선도
    판단에서 제외돼야 한다(안 그러면 .git 내부 잦은 갱신 때문에 항상
    stale로 오판할 수 있음)."""
    root = tmp_path / "root"
    _touch(root / "README.md", 60)
    _touch(root / ".git" / "index", 0)  # dot-폴더 안 최신 파일 — 무시돼야 함
    _register_root("dotfolder-root", root)
    result = mcp_srv.check_readme_freshness(stale_days=30)
    assert result[0]["status"] == "fresh"
    assert "gapDays" not in result[0]


def test_readme_freshness_filters_by_label(tmp_path):
    root_a = tmp_path / "a"
    root_b = tmp_path / "b"
    _touch(root_a / "README.md", 0)
    _touch(root_b / "README.md", 0)
    m.save_roots([{"label": "a", "path": str(root_a)}, {"label": "b", "path": str(root_b)}])
    result = mcp_srv.check_readme_freshness(root_label="b")
    assert len(result) == 1
    assert result[0]["label"] == "b"


def test_readme_freshness_unknown_label():
    result = mcp_srv.check_readme_freshness(root_label="no-such-label")
    assert result == [{"status": "label_not_found", "label": "no-such-label"}]


def test_readme_freshness_empty_registry_returns_empty_list():
    assert mcp_srv.check_readme_freshness() == []


# ---------------------------------------------------------------- classify_content

def test_classify_content_ranks_matching_root_first(tmp_path):
    """referenceCondition에 실제 사전 단어("보안")를 써서 구조화 신호가
    확실히 나게 함 — test_router_orchestrator.py와 같은 실측 패턴(D-034,
    kiwipiepy가 미등록 조어를 걸러내는 문제 회피)."""
    root = tmp_path / "root"
    root.mkdir()
    m.save_roots([
        {"label": "match", "path": str(root), "referenceCondition": "보안 관련 문서"},
        {"label": "nomatch", "path": str(root), "referenceCondition": "요리 레시피"},
    ])
    result = mcp_srv.classify_content("보안 정책을 정리해줘")
    assert result["candidates"]
    assert result["candidates"][0]["rootLabel"] == "match"


def test_classify_content_empty_registry_returns_no_candidates():
    result = mcp_srv.classify_content("아무 내용")
    assert result["candidates"] == []


def test_classify_content_result_is_json_serializable(tmp_path):
    """MCP는 반환값을 JSON으로 직렬화한다 — Path 등 비직렬화 객체가 섞여
    들어가는 회귀를 여기서 잡는다."""
    import json

    root = tmp_path / "root"
    root.mkdir()
    (root / "README.md").write_text("보안 정책 문서", encoding="utf-8")
    m.save_roots([{"label": "root", "path": str(root), "referenceCondition": "보안"}])
    result = mcp_srv.classify_content("보안 관련 요청")
    json.dumps(result)  # 예외 없이 직렬화되면 통과


def test_classify_content_records_orchestration_log(tmp_path):
    """D-044부터 있던 동작(내부 로그 축적)이 MCP 경유로도 그대로 유지되는지
    — docstring에 명시한 "새로 생긴 부작용 아님"을 실측으로 뒷받침."""
    m.save_roots([{"label": "a", "path": "C:\\a"}])
    mcp_srv.classify_content("아무 텍스트")
    assert len(ro.load_orchestration_log()) == 1


# --------------------------------------------------------- D-057: 개발자 모드 게이팅

def test_list_ssot_roots_gated_when_developer_mode_off(tmp_path):
    m.save_roots([{"label": "a", "path": "C:\\a"}])
    rp.set_developer_mode(False, m.REGISTRY_PATH)
    result = mcp_srv.list_ssot_roots()
    assert result == [mcp_srv._DEV_MODE_OFF]


def test_check_readme_freshness_gated_when_developer_mode_off(tmp_path):
    _register_root("a", tmp_path)
    rp.set_developer_mode(False, m.REGISTRY_PATH)
    result = mcp_srv.check_readme_freshness()
    assert result == [mcp_srv._DEV_MODE_OFF]


def test_classify_content_gated_when_developer_mode_off(tmp_path):
    m.save_roots([{"label": "a", "path": "C:\\a", "referenceCondition": "보안"}])
    rp.set_developer_mode(False, m.REGISTRY_PATH)
    result = mcp_srv.classify_content("보안 관련 요청")
    assert result == mcp_srv._DEV_MODE_OFF


def test_tools_work_normally_when_developer_mode_explicitly_true(tmp_path):
    """기본값(필드 없음)뿐 아니라 명시적 True에서도 정상 동작하는지 —
    False만 잠그고 True는 그냥 통과시키는지 확인."""
    m.save_roots([{"label": "a", "path": "C:\\a"}])
    rp.set_developer_mode(True, m.REGISTRY_PATH)
    result = mcp_srv.list_ssot_roots()
    assert result != [mcp_srv._DEV_MODE_OFF]
    assert result[0]["label"] == "a"


# ------------------------------------------------------------ tool 등록 확인

def test_tools_are_registered_on_server():
    """데코레이터가 원본 함수를 그대로 반환하면서(직접 호출 가능) 동시에
    MCPServer에도 등록됐는지 — list_tools()가 비동기라 asyncio로 부름."""
    import asyncio

    tools = asyncio.run(mcp_srv.server.list_tools())
    names = {t.name for t in tools}
    assert "list_ssot_roots" in names
    assert "check_readme_freshness" in names
    assert "classify_content" in names

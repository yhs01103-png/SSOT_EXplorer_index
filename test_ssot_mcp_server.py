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
import ssot_mcp_server as mcp_srv


@pytest.fixture(autouse=True)
def isolated_registry(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "REGISTRY_PATH", tmp_path / "ssot-roots.json")
    m._LAST_KNOWN_HASH = ""
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


# ------------------------------------------------------------ tool 등록 확인

def test_tools_are_registered_on_server():
    """데코레이터가 원본 함수를 그대로 반환하면서(직접 호출 가능) 동시에
    MCPServer에도 등록됐는지 — list_tools()가 비동기라 asyncio로 부름."""
    import asyncio

    tools = asyncio.run(mcp_srv.server.list_tools())
    names = {t.name for t in tools}
    assert "list_ssot_roots" in names
    assert "check_readme_freshness" in names

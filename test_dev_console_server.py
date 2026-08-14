"""dev_console_server.py 전용 테스트 — D-046. 실제로 로컬 HTTP 서버를
띄우고(ephemeral 포트, 0) 진짜 HTTP 요청으로 검증한다 — 라우팅 딕셔너리를
직접 들여다보는 대신 실제 소켓 왕복까지 거치게(Lazzy의 test_dev_track_
gating.py가 TestClient로 실제 배선을 검증한 것과 같은 이유 — 이 파일도
"라우팅이 실제로 동작하는지"를 직접 확인한다). conftest.py 없이 파일
하나로(D-024 관례) — main.py/router_*.py의 실제 사용자 파일을 안 건드리게
전부 이 파일 안에서 monkeypatch."""
from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

import dev_console_server as dcs
import main as m
import router_keyword_registry as kr
import router_watcher as rw


@pytest.fixture(autouse=True)
def isolated_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "REGISTRY_PATH", tmp_path / "ssot-roots.json")
    monkeypatch.setattr(m, "SESSION_CONTEXT_LOG_PATH", tmp_path / "session-log.json")
    monkeypatch.setattr(rw, "WATCHER_LOG_PATH", tmp_path / "watcher-log.json")
    monkeypatch.setattr(kr, "KEYWORD_REGISTRY_PATH", tmp_path / "keywords.json")
    m._LAST_KNOWN_HASH = ""
    yield


@pytest.fixture
def server_url():
    server = dcs.start(host="127.0.0.1", port=0)  # 0 = OS가 빈 포트 배정(테스트 충돌 방지)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _get(url: str):
    with urllib.request.urlopen(url, timeout=5) as resp:
        return resp.status, resp.read().decode("utf-8")


def _get_json(url: str):
    status, body = _get(url)
    return status, json.loads(body)


def test_root_serves_html_page(server_url):
    status, body = _get(server_url + "/")
    assert status == 200
    assert "개발자 콘솔" in body
    for label in ["스키마 검증", "Inbox 감시 로그", "키워드 레지스트리", "세션 컨텍스트 로그"]:
        assert label in body


def test_dev_console_alias_path_serves_same_page(server_url):
    status, body = _get(server_url + "/dev-console")
    assert status == 200
    assert "개발자 콘솔" in body


def test_unknown_path_returns_404(server_url):
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        _get(server_url + "/no-such-route")
    assert exc_info.value.code == 404


def test_html_page_references_all_api_routes(server_url):
    """새 뷰를 추가하고 dev_console.html에 fetch() 경로를 안 넣는 실수를
    잡는 회귀 테스트 — main.py에 뷰를 추가하고 배선을 깜빡하는 것과 같은
    부류의 실수(D-042/D-044/D-045에서 반복된 패턴)를 여기서도 미리 막는다."""
    _, body = _get(server_url + "/")
    for path in dcs._ROUTES:
        assert path in body


def test_schema_endpoint_returns_empty_errors_when_registry_missing(server_url):
    status, data = _get_json(server_url + "/api/schema")
    assert status == 200
    assert data == {"errors": []}


def test_schema_endpoint_reports_duplicate_labels(server_url):
    m.save_roots([{"label": "dup", "path": "C:\\a"}, {"label": "dup", "path": "C:\\b"}])
    status, data = _get_json(server_url + "/api/schema")
    assert status == 200
    assert any("dup" in e and "중복" in e for e in data["errors"])


def test_watcher_log_endpoint_returns_recorded_events(server_url):
    rw.record_new_file_event(Path("C:\\inbox"), "new.md")
    status, data = _get_json(server_url + "/api/watcher-log")
    assert status == 200
    assert data["events"][-1]["fileName"] == "new.md"


def test_keyword_registry_endpoint_returns_recorded_keywords(server_url):
    kr.record_keyword_hits(["보안"])
    status, data = _get_json(server_url + "/api/keyword-registry")
    assert status == 200
    assert data["keywords"]["보안"]["hitCount"] == 1


def test_session_log_endpoint_returns_empty_list_when_missing(server_url):
    status, data = _get_json(server_url + "/api/session-log")
    assert status == 200
    assert data == {"entries": []}

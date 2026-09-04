"""SSOT_Explorer 개발자 콘솔 — 로컬 HTTP 서버 스켈레톤(2026-08-14, D-046).

Lazzy_App_OS_Monorepo의 개발자 콘솔(D-SERVER-092, server/api/static/
dev_console.html + api/routes/dev_console_router.py)과 같은 발상 — 이미
관리자 패널(main.py의 ManagementDialog)이 보여주는 4개 데이터(스키마 검증/
Inbox 감시 로그/키워드 레지스트리/세션 컨텍스트 로그)를 웹페이지로도 볼 수
있게 한다.

**이번 라운드는 "임포트만 하면 서빙되는" 코드만** — `from dev_console_server
import start; start()`(또는 CLI로 `python dev_console_server.py`) 하면 바로
동작하지만, main.py UI에 시작/중지를 트리거하는 버튼은 아직 안 붙였다.
남은 항목은 실행규격서/결정이력에 O-010으로 기록(설계 문서 참고) — 포트/
바인드 주소/exe 패키징 등 결정이 아직 안 끝났다는 뜻이지, 이 파일 자체가
안 돌아간다는 뜻이 아니다.

Lazzy와 다른 점: 이건 로컬 전용(같은 기기, 또는 같은 Wi-Fi에서 IP로 접근)
이지 Railway 같은 공개 배포가 없다. 그래서 토큰 인증 없이 시작한다 — 외부
인터넷에 노출된 적이 없는 한 위협 모델 자체가 Lazzy(공인 도메인 + 여러
기기/사용자)와 다르다. 기본 바인드 주소를 `127.0.0.1`(이 기기에서만 접근
가능)로 잡아둔 것도 같은 이유 — LAN의 폰/태블릿에서도 열고 싶어지면
`start(host="0.0.0.0")`로 바꾸면 되지만, 그 순간부터는 같은 Wi-Fi에 있는
아무나 이 데이터를 볼 수 있다는 뜻이라 인증을 다시 고려해야 한다(O-010).

새 의존성 없음 — stdlib `http.server`만 사용(Flask/FastAPI 등 도입 안 함,
이 프로젝트의 "필요할 때만 무거운 의존성을 들인다" 원칙 그대로, D-034
kiwipiepy 때와 동일한 판단 기준).

**알려진 절충**: 아래 import가 `main.py`를 가져와서, 이 스크립트를 단독
실행해도 PySide6(GUI 프레임워크)까지 같이 로드된다 — `load_registry_raw`/
`validate_registry`가 지금 main.py에만 있어서다. 완전히 헤드리스하게(Qt
없이) 쓰고 싶어지면 그 두 함수 + REGISTRY_SCHEMA를 D-043 때처럼 Qt 미의존
모듈로 옮기는 리팩터가 필요 — 지금은 "일단 동작하는 스켈레톤"이 우선이라
미룸(O-010)."""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import router_keyword_registry
import router_watcher
from main import load_registry_raw, load_session_context_log, validate_registry
from router_paths import (
    PAGE_PATH,  # D-098, O-021 Stage 1 — 경로 레이어로 이관, 재노출만
)

DEFAULT_HOST = "127.0.0.1"  # 로컬 전용 기본값 — 위 모듈 docstring 참고
DEFAULT_PORT = 8765

# 경로 → 데이터 함수. 새 뷰를 추가하려면 여기 한 줄 + dev_console.html에
# 탭 하나만 추가하면 된다(main.py 관리자 패널에 새 로그뷰를 추가할 때와
# 같은 "한 곳에 한 줄" 확장 패턴).
_ROUTES = {
    "/api/schema": lambda: {"errors": validate_registry(load_registry_raw())},
    "/api/watcher-log": lambda: {"events": router_watcher.load_watcher_log()},
    "/api/keyword-registry": lambda: {"keywords": router_keyword_registry.load_keyword_registry()},
    "/api/session-log": lambda: {"entries": load_session_context_log()},
}


class DevConsoleHandler(BaseHTTPRequestHandler):
    """`/`(또는 `/dev-console`)는 정적 페이지, `/api/*`는 JSON — Lazzy
    쪽처럼 서버가 프록시 로직을 갖지 않고 이미 있는 로더 함수를 그대로
    JSON으로 감싸기만 한다."""

    def log_message(self, format, *args):  # noqa: A002 — stdlib 시그니처 그대로
        pass  # 로컬 전용 도구라 매 요청마다 콘솔에 찍을 필요 없음(조용히)

    def do_GET(self):
        if self.path in ("/", "/dev-console"):
            self._serve_page()
        elif self.path in _ROUTES:
            self._serve_json(_ROUTES[self.path]())
        else:
            self.send_error(404, "Not Found")

    def _serve_page(self):
        try:
            body = PAGE_PATH.read_bytes()
        except OSError:
            self.send_error(500, "정적 페이지 파일을 못 찾음")
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_json(self, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def start(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> ThreadingHTTPServer:
    """서버 인스턴스만 만들어서 반환 — serve_forever()는 호출부 책임(별도
    스레드에서 돌리거나, 테스트처럼 handle_request()를 한 번만 부르거나).
    main.py UI에서 나중에 "콘솔 시작" 버튼을 붙일 때 이 함수를 QThread
    안에서 부르면 된다(InboxWatcherThread, D-042와 같은 패턴)."""
    return ThreadingHTTPServer((host, port), DevConsoleHandler)


def serve_forever(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    """블로킹 — `python dev_console_server.py`로 바로 실행할 때 씀."""
    server = start(host, port)
    print(f"SSOT_Explorer 개발자 콘솔: http://{host}:{port}/")
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    serve_forever()

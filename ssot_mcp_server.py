"""SSOT_Explorer MCP 서버(2026-08-16, D-048) — "범용 IDE 플러그인" 방향의 첫
실현체.

**방향 전환 배경**: 지금까지 SSOT_Explorer의 자동화(드리프트 감지, 리뷰
신선도, InboxWatcher, 라우터)는 전부 "이 앱(PySide6 GUI) 또는 Claude Code
전용 SessionStart 훅" 안에서만 동작했다 — 둘 다 이 앱/Claude Code에 종속.
사용자가 명시한 방향은 다르다: **파일 수정/삭제/생성은 항상 IDE(또는 그 안의
AI 에이전트)가 하고, 이 프로젝트는 "신호"만 준다** — 그리고 그 신호를
Claude Code뿐 아니라 Cursor/Windsurf 등 MCP를 지원하는 어떤 IDE/에이전트에서도
받을 수 있어야 "범용"이다. Claude Code 훅(PreToolUse 등)은 Claude Code
전용이라 이 목표에 안 맞고, MCP(Model Context Protocol)가 지금 시점에 여러
AI 코딩 툴이 공통으로 지원하는 사실상 유일한 프로토콜이라 이걸 그릇으로
택했다.

**이번 라운드 범위 — README 신선도 체크 1개 tool만(스켈레톤, D-046
개발자콘솔과 같은 "일단 동작하는 것부터" 판단)**:
`check_readme_freshness` — 등록된 루트의 README.md가 그 폴더 안 다른
파일들의 최신 수정 시각(mtime) 대비 얼마나 뒤처졌는지 확인한다. git 커밋
이력 기반이 아니라 **mtime 기반**인 이유: 등록된 5개 루트 전부 git 저장소가
아님(실측 확인, 2026-08-16) — OneDrive로 동기화되는 일반 폴더라 git log를
쓸 수 없다. `lastReviewed`(D-018, 사람이 "리뷰했음"을 수동으로 기록, 180일
기준)와는 다른 신호다 — 이쪽은 "실제로 파일이 그만큼 안 낡았는지"를 자동
계산하는 교차검증용.

**읽기 전용(P-01) 그대로 유지** — 이 서버는 파일을 절대 쓰지 않는다. 결과를
받은 IDE/에이전트가 알아서 판단해서 (필요하면) 자기 도구로 직접 고친다.

**알려진 절충**(dev_console_server.py의 D-046 절충과 동일 계열): 아래
`from main import ...`가 PySide6까지 로드한다 — `load_roots`/
`find_index_files`가 지금 main.py에만 있어서다. 완전히 헤드리스하게 쓰고
싶어지면 그 함수들을 Qt 미의존 모듈로 옮기는 리팩터가 필요(O-010이 이미
같은 부채를 기록해뒀음 — 이제 두 파일이 공유하는 부채라 다음 라운드
우선순위가 자연히 올라감).

사용법(단독 실행, stdio transport):
    python ssot_mcp_server.py
IDE 쪽 mcp 설정(예: Claude Code `.mcp.json`)에 이 파일을 커맨드로 등록하면
붙는다 — 이번 라운드는 서버 코드 자체까지만, 실제 등록 설정은 별도(O-011로
기록).
"""
from __future__ import annotations

import os
from pathlib import Path

from mcp.server import MCPServer

# mtime 기반이라 사람 리뷰 주기(REVIEW_STALE_DAYS=180, D-018)보다 훨씬
# 짧게 잡는다 — 이건 "실제 파일 변경 대비 문서가 며칠 뒤처졌는지"라, 활발히
# 바뀌는 폴더라면 한 달만 밀려도 신호로 볼 가치가 있다고 판단(실측 데이터
# 없음 — H-009와 같은 "재현/사용 후 조정" 대상, 기본값일 뿐).
README_STALE_DAYS = 30

server = MCPServer(
    "ssot-explorer",
    version="1.0.0",
    instructions=(
        "SSOT_Explorer 레지스트리에 등록된 여러 프로젝트 루트에 대한 읽기 전용 "
        "신호를 제공한다. 파일을 직접 쓰거나 지우지 않는다 — 결과를 보고 실제 "
        "조치는 호출한 에이전트가 한다."
    ),
)


def _max_other_mtime(root_path: Path, exclude: Path) -> float | None:
    """root_path 밑(dot-폴더 제외, 기존 SearchWorker(D-013)와 같은 관례)
    exclude를 뺀 모든 파일 중 가장 최근 수정 시각. 파일이 하나도 없거나
    전부 stat 실패면 None."""
    latest: float | None = None
    for dirpath, dirnames, filenames in os.walk(root_path):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for name in filenames:
            p = Path(dirpath) / name
            if p == exclude:
                continue
            try:
                mtime = p.stat().st_mtime
            except OSError:
                continue
            if latest is None or mtime > latest:
                latest = mtime
    return latest


def _check_one_root(entry: dict, stale_days: int) -> dict:
    from main import find_index_files  # 지연 import, 순환참조 회피(dev_console_server.py와 동일 사유)

    label = entry.get("label", "")
    path_str = entry.get("path", "")
    root_path = Path(path_str)
    if not root_path.is_dir():
        return {"label": label, "path": path_str, "status": "root_missing"}

    index = find_index_files(root_path)
    readme_path = index.get("readme.md")
    if readme_path is None:
        return {"label": label, "path": path_str, "status": "no_readme"}

    try:
        readme_mtime = readme_path.stat().st_mtime
    except OSError:
        return {"label": label, "path": path_str, "status": "readme_unreadable"}

    latest_other = _max_other_mtime(root_path, readme_path)
    if latest_other is None or latest_other <= readme_mtime:
        return {
            "label": label, "path": path_str, "status": "fresh",
            "readmePath": str(readme_path),
        }

    gap_days = round((latest_other - readme_mtime) / 86400, 1)
    status = "stale" if gap_days > stale_days else "fresh"
    return {
        "label": label, "path": path_str, "status": status,
        "readmePath": str(readme_path), "gapDays": gap_days,
    }


@server.tool()
def list_ssot_roots() -> list[dict]:
    """등록된 SSOT 루트 목록을 반환한다(label/path/scope/참조조건 요약) —
    다른 tool을 부르기 전에 어떤 루트가 있는지 확인하는 용도."""
    from main import load_roots

    return [
        {
            "label": r.get("label", ""),
            "path": r.get("path", ""),
            "scope": r.get("scope"),
            "referenceCondition": (r.get("referenceCondition") or "")[:200],
        }
        for r in load_roots()
    ]


@server.tool()
def check_readme_freshness(
    root_label: str | None = None, stale_days: int = README_STALE_DAYS
) -> list[dict]:
    """등록된 루트(들)의 README.md가 그 폴더 안 다른 파일들의 최신 수정
    시각(mtime) 대비 며칠이나 뒤처졌는지 확인한다. root_label을 주면 그
    루트 하나만, 안 주면 등록된 전체를 확인한다. 파일을 절대 고치지 않는다
    — status가 "stale"이면 호출한 에이전트/사람이 README를 검토할지
    판단한다."""
    from main import load_roots

    roots = load_roots()
    if root_label is not None:
        roots = [r for r in roots if r.get("label") == root_label]
        if not roots:
            return [{"status": "label_not_found", "label": root_label}]
    return [_check_one_root(r, stale_days) for r in roots]


if __name__ == "__main__":
    server.run(transport="stdio")

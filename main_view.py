"""SSOT_Explorer — 뷰(View) 지원 레이어(2026-09-04, D-103, O-021 Stage 4-1).

레이어 분리 방침(Plug_In_Global\\.claude\\레이어_분리_방침.md) 대비 main.py
분석(O-021)의 마지막 남은 갭 "UX/UI 미분리"를 해소하는 Stage 4의 첫 조각.
main.py에 섞여 있던 함수 중 **Qt를 전혀 안 쓰고 REGISTRY_PATH도 전혀 안
건드리는**(순수하게 dict/list를 받아 dict/list/str을 돌려주는) 것만 여기로
이관한다 — 스키마 검증, 레지스트리/로그 텍스트 포맷터, 관계 조회, 드라이브
목록.

**왜 REGISTRY_PATH 의존 함수는 안 옮겼나(중요)**: `load_roots`/`save_roots`/
`load_shared_docs`/`load_relations`/`load_registry_raw`처럼 main.py의 모듈
전역 `REGISTRY_PATH`를 참조하는 함수는 이 스테이지에서 의도적으로 제외했다.
이 프로젝트에는 이미 "여러 최상위 모듈이 REGISTRY_PATH를 각자 독립적으로
캐싱하고, 테스트가 관련된 모듈 전부를 따로 patch"하는 패턴이 있다
(`ssot_mcp_server.py`가 자기만의 REGISTRY_PATH를 갖고, test_ssot_mcp_server.py
가 `m.REGISTRY_PATH`/`mcp_srv.REGISTRY_PATH` 둘 다 patch) — 하지만
`test_main.py`에는 `m.REGISTRY_PATH`/이 함수들에 대한 직접 참조가 73곳
있어서, 그 전부를 한 번에 새 모듈로 옮기고 테스트 fixture까지 안전하게
갱신하는 건 이번 조각의 범위를 넘는 리스크(실수하면 테스트가 실제 사용자
레지스트리 파일을 건드릴 수 있음)로 판단해 별도로 신중하게 다룬다.

Qt는 물론이고 router_registry.py/router_proposals.py 외의 어떤
REGISTRY_PATH도 이 모듈은 모른다 — `validate_registry()`는 데이터를 인자로
받고, `load_session_context_log()`는 REGISTRY_PATH가 아니라
router_paths.SESSION_CONTEXT_LOG_PATH(별개 경로, 훅 전용 로그)만 쓴다.
"""
from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from router_paths import SESSION_CONTEXT_LOG_PATH

# 2026-08-14(D-038, H-005 다음 항목) — 레지스트리 스키마 검증. jsonschema는
# 진단용 부가기능이라 kiwipiepy(D-034)와 같은 선택적 의존성 원칙 — 미설치
# 환경에서도 앱 자체는 그대로 동작하고, 검증만 "건너뜀"으로 표시한다.
try:
    import jsonschema
    _JSONSCHEMA_AVAILABLE = True
except ImportError:
    _JSONSCHEMA_AVAILABLE = False


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
                    # 2026-08-28(D-087, O-020 확장) — labeledFolders의 3자
                    # 일치 감사(D-073)를 roots[]에도 적용하기 위한 짝 필드.
                    # lastReviewed(180일, "내용을 사람이 검토했나")와는 별개
                    # 신호 — "라벨↔폴더↔README 마커가 구조적으로 일치하나"를
                    # 본다(30일 문턱값 재사용).
                    "lastAudited": {"type": "string", "pattern": r"^$|^\d{4}-\d{2}-\d{2}$"},
                    "previousLabels": {"type": "array", "items": {"type": "string", "minLength": 1}},
                    "dependsOnDocs": {"type": "array", "items": {"type": "string"}},
                    # 2026-08-17(D-058, O-013) — 액션 레지스트리. trigger는
                    # fnmatch 글롭(예: "*/productized/*"), policy는 호출한
                    # 에이전트가 자동 실행할지 사용자 승인을 받을지 판단하는
                    # 힌트(이 앱은 강제 안 함). scriptPath(실행 스크립트
                    # 경로)/prompt(순수 자연어 규칙, 실행 파일 없음) 중
                    # 최소 하나는 있어야 함(D-061) — 둘 다 없으면 호출한
                    # 에이전트가 뭘 해야 할지 알 수 없는 빈 액션이라 무의미.
                    "actions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["trigger", "policy"],
                            "anyOf": [
                                {"required": ["scriptPath"]},
                                {"required": ["prompt"]},
                            ],
                            "additionalProperties": True,
                            "properties": {
                                "trigger": {"type": "string", "minLength": 1},
                                "scriptPath": {"type": "string", "minLength": 1},
                                "prompt": {"type": "string", "minLength": 1},
                                "policy": {"type": "string", "enum": ["auto", "approve"]},
                                "description": {"type": "string"},
                            },
                        },
                    },
                },
            },
        },
        "developerMode": {"type": "boolean"},
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
        # 2026-08-22(D-073, O-018(b)) — roots[]와 분리한 경량 배열. referenceCondition
        # 동기화/actions 같은 무거운 필드가 없다 — README가 있거나 필요한
        # 하위 폴더를 최소 필드로만 추적한다.
        "labeledFolders": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["label", "path"],
                "additionalProperties": True,
                "properties": {
                    "label": {"type": "string", "minLength": 1},
                    "path": {"type": "string", "minLength": 1},
                    "parentLabel": {"type": ["string", "null"]},
                    "lastAudited": {"type": "string", "pattern": r"^$|^\d{4}-\d{2}-\d{2}$"},
                    # 2026-08-28(D-086, O-020) — 이 폴더가 실제로 리네임된 적
                    # 있으면 옛 label(들)을 여기 쌓아둔다. 3자 일치 감사(라벨↔
                    # 폴더↔자기 README)는 폴더가 "자기 자신과 일치하는가"만
                    # 보고, "다른 문서가 이 폴더를 옛 이름으로 부르고 있진
                    # 않은가"는 못 본다 — 이 필드가 그 검색의 출발점(무엇을
                    # 찾아야 하는지)이 된다.
                    "previousLabels": {"type": "array", "items": {"type": "string", "minLength": 1}},
                },
            },
        },
        # 2026-08-28(D-087) — GUI(main.py)와 Claude Code 세션 사이의 유일한
        # 접점인 이 레지스트리 파일에, GUI가 "README 등록/경로 수정/은퇴"
        # 버튼으로 남기는 구조화된 요청 큐. GUI는 이 배열에 항목만 추가하고
        # (P-01, "GUI는 신호만"), 실제 파일 작업은 다음 Claude Code 세션이
        # 이 큐를 보고 사용자 승인을 받은 뒤 수행 — 처리 완료되면 그 항목을
        # 큐에서 지운다(이력 남기지 않음, router_registry.resolve_pending_
        # action 참고).
        "pendingActions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["requestId", "targetType", "targetLabel", "actionType", "requestedAt"],
                "additionalProperties": True,
                "properties": {
                    "requestId": {"type": "string", "minLength": 1},
                    "targetType": {"type": "string", "enum": ["root", "labeledFolder", "subfolder"]},
                    "targetLabel": {"type": "string", "minLength": 1},
                    "actionType": {
                        "type": "string",
                        "enum": ["create_readme", "modify_readme", "fix_path", "retire", "readme_deleted"],
                    },
                    "requestedAt": {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$"},
                    "note": {"type": "string"},
                },
            },
        },
    },
}


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
    # 2026-08-22(D-073) — labeledFolders도 add_labeled_folder가 쓰기 시점엔
    # 중복을 막지만, 수동 편집으로 우회될 수 있어 roots와 동일하게 보강.
    labeled_folder_label_counts = Counter(
        f.get("label") for f in data.get("labeledFolders", []) if isinstance(f, dict) and f.get("label")
    )
    for label, count in labeled_folder_label_counts.items():
        if count > 1:
            errors.append(
                f"labeledFolders: label '{label}'이(가) {count}번 중복됨 — "
                "라벨 폴더의 label도 유일해야 함"
            )
    return errors


def format_schema_validation_text(errors: list[str]) -> str:
    if not errors:
        return "✅ 스키마 검증 통과 — 문제 없음"
    lines = [f"⚠️ 스키마 문제 {len(errors)}건:"]
    lines += [f"  - {e}" for e in errors]
    return "\n".join(lines)


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
        # 2026-08-17(D-052) — 폴더가 삭제/이동됐는데 레지스트리엔 그대로
        # 남아있는 경우를 한눈에 보이게. 자동 등록해제는 안 함(감지→알림만,
        # 이 프로젝트 일관 원칙) — 사람이 여기 보고 직접 "루트 삭제" 버튼을
        # 누를지 판단.
        missing_tag = " ⚠️경로없음" if not Path(r["path"]).is_dir() else ""
        block = (
            f"■ {r['label']}{web_primary_tag}{missing_tag}"
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


def _format_recent_log_text(
    entries: list[dict],
    limit: int,
    empty_message: str,
    render_entry: Callable[[dict], list[str]],
) -> str:
    """2026-09-04(D-099, H-012 해소, O-021 Stage 2) — 개발자 탭 로그뷰
    포맷터 5종(format_watcher_log_text 등)이 전부 같은 골격("최근 limit개만,
    최신이 위로")을 각자 복붙하고 있던 걸 하나로 모은다. 항목 하나가 줄
    1개(대부분)든 여러 개(format_watchdog_log_text처럼 요약+실패사유+근거
    줄을 같이 내는 경우)든 상관없이 render_entry가 그 항목의 줄 목록만
    돌려주면 된다 — reversed(recent)로 최신 항목부터 순회하며 그대로
    이어붙이므로, 항목 내부의 줄 순서(예: 요약 줄이 근거 줄보다 먼저)는
    항상 보존된다(줄 단위로 통째로 뒤집는 방식이었다면 이게 깨졌을 것)."""
    if not entries:
        return empty_message
    recent = entries[-limit:]
    lines: list[str] = []
    for entry in reversed(recent):
        lines.extend(render_entry(entry))
    return "\n".join(lines)


def format_watcher_log_text(events: list[dict], limit: int = 20) -> str:
    """D-042 — Inbox 감시 로그를 관리자 패널에 보여줄 텍스트로. 최신 항목이
    위로 오게(다른 로그뷰들과 통일된 관례) 최근 limit개만."""
    return _format_recent_log_text(
        events, limit,
        "(로그 없음 — 아직 감지된 파일 없음, Inbox 감시를 시작하면 쌓임)",
        lambda e: [f"{e['timestamp']}  {e['fileName']}  ({e['watchDir']})"],
    )


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
    return _format_recent_log_text(
        entries, limit,
        "(로그 없음 — 등록 루트 안에서 Claude Code 세션을 열면 쌓임)",
        lambda e: [
            f"{e['timestamp']}  {e['matchedLabel']}  (관련폴더 {e['relatedCount']}개, 다른루트 {e['otherRootsCount']}개)"
        ],
    )


def format_orchestration_log_text(runs: list[dict], limit: int = 20) -> str:
    """2026-08-23(D-076) — 개발자 탭 벤치마크 뷰용. classify_content가 실행될
    때마다(GUI/CLI/MCP 어느 경로로 불렸든) router_orchestrator._log_run이
    이미 쌓아둔 ssot_orchestrator_log.json을 그대로 읽어서, 각 실행의 전체
    소요시간(totalElapsedMs)+최상위 후보를 한 줄로 보여준다. 다른 로그뷰와
    동일 관례(최신이 위, 최근 limit개만)."""
    def render(r: dict) -> list[str]:
        top = r.get("topCandidate")
        top_text = f"{top['rootLabel']}({top['score']})" if top else "(후보 없음)"
        total_ms = r.get("totalElapsedMs")
        ms_text = f"{total_ms}ms" if total_ms is not None else "?"
        preview = (r.get("queryPreview") or "").replace("\n", " ")[:40]
        return [f"{r['ranAt']}  {ms_text:>9}  1위:{top_text}  \"{preview}\""]

    return _format_recent_log_text(
        runs, limit, "(로그 없음 — classify를 한 번이라도 실행하면 쌓임)", render,
    )


def format_watchdog_log_text(runs: list[dict], limit: int = 20) -> str:
    """2026-08-28 — 개발자 탭 워치독 로그 뷰용. ssot_background_watchdog.
    main()이 실행될 때마다(작업 스케줄러 경유든 수동 실행이든) 쌓아둔
    ssot_watchdog_log.json을 그대로 읽어서, 각 실행이 뭘 검사했고 뭘
    찾았으며(근거 포함) 토스트를 실제로 띄웠는지 보여준다 — "무슨 파일을
    무슨 근거로 판단했는지"가 알림 요약이 아니라 여기 그대로 남는다."""
    def render(r: dict) -> list[str]:
        toast_text = "🔔" if r.get("toastFired") else "-"
        lines = [
            f"{r['ranAt']}  검사 루트{r.get('checkedRoots', 0)}+라벨폴더{r.get('checkedLabeledFolders', 0)}"
            f"  발견 {r.get('newFindingsCount', 0)}건  토스트{toast_text}"
        ]
        # 2026-09-04(D-096) — 스캔 도중 예외가 나면(레지스트리 쓰기 충돌 등)
        # findings/toast는 비어있어도 이 줄만으로 "그날 실패했다"가 보여야
        # 한다 — 예전엔 이 경우 로그 자체가 안 남아 무인 실행 실패가 완전히
        # 조용히 사라졌다.
        if r.get("error"):
            lines.append(f"    ❌ 실패: {r['error']}")
        for f in r.get("findings", []):
            evidence = ", ".join(f"{k}={v}" for k, v in (f.get("evidence") or {}).items())
            lines.append(f"    [{f['targetType']}/{f['targetLabel']}] {f['actionType']}: {f['note']} ({evidence})")
        return lines

    return _format_recent_log_text(runs, limit, "(로그 없음 — 워치독이 아직 한 번도 안 돌았음)", render)


def format_proposals_text(proposals: list[dict], trust_state: dict, limit: int = 20) -> str:
    """2026-09-04(D-093, O-012 해소) — 분류 피드백 원장(ssot_router_proposals.
    json, D-029)을 개발자 탭에 보여준다. 이 데이터 자체는 D-029부터
    SaveDocumentDialog 승인/취소 버튼이 쌓아왔지만 지금까지 뷰가 아예 없었다
    (grep으로 확인 — 다른 로그 5종은 다 있는데 이것만 빠져 있었음). D-092로
    MCP `record_classification_feedback` tool이 추가되면서 GUI/MCP 양쪽
    피드백이 같은 파일에 합쳐지므로, 이 뷰 하나가 두 경로 전부를 보여준다.
    각 줄에 그 루트의 현재 신뢰 상태(연속 5승인 시 ✅, D-030)도 같이 표시.
    다른 로그뷰와 동일 관례(최신이 위, 최근 limit개만)."""
    def render(p: dict) -> list[str]:
        label = p.get("rootLabel") or "?"
        badge = " ✅신뢰됨" if trust_state.get(label, {}).get("trusted") else ""
        mark = "✔승인" if p.get("decision") == "approved" else "✘취소"
        preview = (p.get("contentPreview") or "").replace("\n", " ")[:40]
        return [f"{p.get('decidedAt', '?')}  {mark}  {label}({p.get('score', '?')}){badge}  \"{preview}\""]

    return _format_recent_log_text(
        proposals, limit,
        "(기록 없음 — SaveDocumentDialog 승인/취소 또는 MCP record_classification_feedback 호출 시 쌓임)",
        render,
    )


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

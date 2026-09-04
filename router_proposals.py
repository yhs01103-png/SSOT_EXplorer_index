"""SSOT_Explorer 라우터 — 제안 이력 + 신뢰 폐루프(2026-08-13 D-029,
2026-08-13 D-030에서 신뢰승급/강등 실제 이식).

자동분류 제안을 사용자가 승인/취소한 기록을 남긴다. 처음(D-029)엔 원장부만
쌓았는데, 사용자가 "Lazzy의 confidence_calibrator.py를 실제로 읽어보라"고
요청해서 코드를 직접 확인한 결과 — 그쪽은 승인/거부 결과를 그냥 로그로만
남기지 않고 (kind, action) 조합별로 **연속 승인 스트릭을 추적해 신뢰
승급/강등**까지 한다(5연속 approved → trusted 승급, 단 한 번이라도 거부되면
즉시 스트릭 0 + 이미 승급했어도 강등 — 보수적). D-030이 그 핵심 메커니즘을
포팅한 버전: `_update_trust()`가 root_label별로 같은 계산을 한다.

**주의**: trusted==True가 돼도 이 파일이나 SaveDocumentDialog가 승인 절차를
자동으로 생략하지는 않는다 — 사용자가 명시적으로 "항상 사람 확인 후 승인/
취소, 절대 자동실행 안 함"이라고 확정했으므로(D-029), trusted 여부는 UI에
"✅ 신뢰됨" 배지로만 노출되고 실제 저장은 여전히 매번 버튼 클릭이 필요하다.
Lazzy 원본은 trusted면 리뷰 자체를 생략(mark_trusted_auto)하지만, 그 부분은
사용자 결정과 배치돼 의도적으로 이식 안 함.

**D-094(결정 번복) — trusted가 실제 분류 점수에도 반영됨**: D-029/D-030
당시엔 "과거 승인 이력이 자동으로 우선순위를 좌우하게 하지 않는다"는 게
명시적 결정이었다(trusted는 참고용 배지일 뿐, router_orchestrator.orchestrate()
5단계는 순위를 절대 안 바꿨음). 그런데 그 결과 "피드백 루프"라는 이름이
실제로는 아무 것도 학습하지 않는 스트릭 카운터에 불과하다는 이름-실체
괴리가 상용 비교 분석에서 지적됐다 — 결정을 번복해 TRUST_MATCH_BONUS를
새로 도입하고, orchestrate()가 다른 additive 신호(SCOPE_MATCH_BONUS/
ACTIVE_KEYWORD_BONUS/EMBEDDING_MATCH_BONUS)와 같은 모양으로 trusted 후보의
점수에 실제로 가점을 준다. "항상 사람 확인 후 승인"이라는 D-029의 별개
원칙(자동 저장 금지)은 이번에도 그대로 유지 — 바뀌는 건 순위/점수뿐, 저장은
여전히 매번 버튼 클릭이 필요하다.

router_classifier.py와 마찬가지로 Qt를 import하지 않는 순수 모듈 — 나중에
서버 프로세스로 떼어내도 그대로 재사용 가능.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

PROPOSALS_LOG_PATH = Path.home() / ".claude" / "scripts" / "ssot_router_proposals.json"
TRUST_STATE_PATH = Path.home() / ".claude" / "scripts" / "ssot_router_trust.json"
TRUST_PROMOTION_STREAK = 5  # Lazzy confidence_calibrator.py의 _REVIEW_PROMOTION_THRESHOLD와 동일 값
# D-094 — trusted 후보가 router_orchestrator.orchestrate()에서 실제로 받는
# additive 가점. ACTIVE_KEYWORD_BONUS(0.15)보다 작게 잡음 — "과거 이 루트가
# 자주 맞았다"는 메타 신호일 뿐이라, 이번 요청의 실제 내용 겹침(구조화/
# 프로즈/시맨틱)보다 약하게 취급해야 한 번 신뢰를 얻은 루트가 이후 무관한
# 요청에서도 계속 상위권을 차지하는 자기강화 편향을 억제할 수 있다.
# TRUST_PROMOTION_STREAK의 "단 한 번의 거부로 즉시 스트릭 0 + 강등"이라는
# 보수성이 그 편향의 1차 방어선이고, 이 상수의 작은 크기가 2차 방어선.
TRUST_MATCH_BONUS = 0.1


def resolve_registry_path() -> Path:
    """레지스트리(ssot-roots.json) 위치 — main.py와 router_classifier.py 둘 다
    같은 로직이 필요해서(D-039) 각자 따로 갖고 있었는데(code-review 발견,
    D-043) 여기 하나로 모았다. `SSOT_REGISTRY_PATH` 환경변수 우선, 없으면
    범용 기본값(`~/.claude/ssot-roots.json`, D-014 이전에 실제로 쓰던 전역
    위치). 이 파일은 Qt를 import하지 않아서(모듈 docstring 참고) main.py/
    router_classifier.py 양쪽에서 안전하게 재사용 가능."""
    return Path(
        os.environ.get("SSOT_REGISTRY_PATH")
        or (Path.home() / ".claude" / "ssot-roots.json")
    )


def is_developer_mode(registry_path: Path | None = None) -> bool:
    """레지스트리 최상위 `developerMode` 필드(D-057) — 기본값 True("이
    앱을 쓴다는 건 이미 개발자"라는 사용자 명시 전제, O-010 재논의 결과).
    main.py가 개발자 탭 표시 여부를 판단할 때, ssot_mcp_server.py가 각
    tool 호출을 게이팅할 때 둘 다 이 하나의 플래그를 같은 레지스트리
    파일에서 읽는다 — router_proposals.py는 Qt 미의존이라 ssot_mcp_
    server.py가 이 체크 하나 때문에 추가로 PySide6를 로드할 일은 없다
    (2026-08-21, D-071 — `load_roots`/`find_index_files`도 router_registry.py로
    옮겨서 ssot_mcp_server.py는 이제 어떤 이유로도 main.py를 안 거친다).

    registry_path를 생략하면 resolve_registry_path()(기본 위치) — main.py
    는 자기 REGISTRY_PATH를 명시로 넘겨서 테스트 격리와 일관되게 맞춘다
    (router_orchestrator.orchestrate()의 log_path 패턴과 동일)."""
    path = registry_path or resolve_registry_path()
    if not path.exists():
        return True
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return True
    return bool(data.get("developerMode", True))


def set_developer_mode(enabled: bool, registry_path: Path | None = None) -> None:
    """developerMode 필드만 갱신 — roots/sharedDocs/relations 등 나머지는
    디스크에서 읽은 그대로 보존한다(D-020 sharedDocs 보존과 동일 원칙,
    save_roots()가 매번 디스크를 먼저 읽는 것과 같은 이유). save_roots()
    (main.py)와 달리 낙관적 동시성 검사는 생략 — 이 플래그는 단일 세션
    UI 토글용이라 여러 기기 동시편집 충돌 위험이 roots보다 훨씬 낮다고
    판단(필요해지면 같은 패턴으로 승격 가능, H-009식 "재현 후 대응")."""
    path = registry_path or resolve_registry_path()
    payload = {}
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            payload = {}
    payload["developerMode"] = enabled
    atomic_write_json(path, payload)


def load_proposals() -> list[dict]:
    if not PROPOSALS_LOG_PATH.exists():
        return []
    try:
        return json.loads(PROPOSALS_LOG_PATH.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return []


def atomic_write_json(path: Path, data) -> bytes:
    """D-021과 같은 원자적 쓰기(temp+os.replace) 패턴 — proposals 로그와
    trust 상태 둘 다 이걸로 쓴다. 둘 다 단일 기기·단일 프로세스 전용이라
    (OneDrive로 여러 기기에 공유되는 레지스트리와 다름) 낙관적 동시성
    검사는 생략하고 원자성만 챙긴다.

    2026-08-17(D-055, H-011) — 실제로 쓴 바이트를 반환하도록 확장(기존
    호출부는 반환값을 안 써서 영향 없음). main.py의 save_roots()가 이
    저수준 부분(temp 쓰기+replace)만 여기로 위임하고, 그 위에 얹힌
    낙관적 동시성 검사(RegistryConflictError)는 save_roots() 쪽에만
    유지한 채 _LAST_KNOWN_HASH 갱신에 이 반환값을 그대로 재사용한다 —
    같은 payload를 두 번 json.dumps()하지 않기 위함."""
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    tmp_path = path.with_name(path.name + f".tmp{os.getpid()}")
    try:
        tmp_path.write_bytes(raw)
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
    return raw


def _save_proposals(proposals: list[dict]) -> None:
    atomic_write_json(PROPOSALS_LOG_PATH, proposals)


def record_decision(candidate: dict, content_preview: str, decision: str) -> dict:
    """decision은 "approved" | "cancelled"만 허용. 승인된 것만 실제 파일
    쓰기로 이어진다(main.py의 SaveDocumentDialog가 처리) — 이 함수는
    기록만 하고 파일시스템은 건드리지 않는다. 기록 직후 _update_trust로
    신뢰 스트릭도 같이 갱신한다."""
    if decision not in ("approved", "cancelled"):
        raise ValueError(f"알 수 없는 decision: {decision!r}")
    proposals = load_proposals()
    entry = {
        "id": len(proposals) + 1,
        "decidedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "rootLabel": candidate.get("rootLabel"),
        "rootPath": candidate.get("rootPath"),
        "score": candidate.get("score"),
        "reason": candidate.get("reason"),
        "contentPreview": (content_preview or "")[:200],
        "decision": decision,
    }
    proposals.append(entry)
    _save_proposals(proposals)
    root_label = candidate.get("rootLabel")
    if root_label:
        _update_trust(root_label, decision)
    return entry


def acceptance_rate(root_label: str | None = None) -> float | None:
    """지금까지 기록된 제안 중 승인 비율 — root_label 지정 시 그 루트만.
    데이터 0건이면 None(계산 불가 — 0%와 구분해야 함, 아직 아무 신호도
    없는 상태를 "전부 틀렸다"로 오독하면 안 됨)."""
    proposals = load_proposals()
    if root_label:
        proposals = [p for p in proposals if p.get("rootLabel") == root_label]
    if not proposals:
        return None
    approved = sum(1 for p in proposals if p["decision"] == "approved")
    return round(approved / len(proposals), 3)


# --------------------------------------------------- D-030: 신뢰 폐루프(승급/강등)
#
# Lazzy_App_OS_Monorepo/server/core/orchestrators/confidence_calibrator.py를
# 실제로 읽고 이식(2026-08-13) — 원본은 (kind, action) 조합별 AutoApplyTrust
# DB 테이블 + ConfidenceJudgment 판정마다 outcome 역참조라는 훨씬 정교한
# 구조지만, 핵심 메커니즘(연속 승인 스트릭 → 승급, 단 한 번의 거부로 즉시
# 리셋+강등)만 root_label 단위로 축소 이식.

def load_trust_state() -> dict:
    """{rootLabel: {"trusted": bool, "streak": int}}"""
    if not TRUST_STATE_PATH.exists():
        return {}
    try:
        return json.loads(TRUST_STATE_PATH.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}


def is_trusted(root_label: str) -> bool:
    """UI 배지 표시용 — trusted==True여도 실제 저장 승인 절차를 자동으로
    생략하지 않는다(D-029에서 사용자가 확정한 "항상 사람 확인" 원칙 유지).
    Lazzy 원본의 mark_trusted_auto(신뢰되면 리뷰 자체 생략)는 의도적으로
    이식 안 함."""
    return load_trust_state().get(root_label, {}).get("trusted", False)


def _update_trust(root_label: str, decision: str) -> None:
    state = load_trust_state()
    entry = state.get(root_label, {"trusted": False, "streak": 0})
    if decision == "approved":
        entry["streak"] += 1
        if entry["streak"] >= TRUST_PROMOTION_STREAK:
            entry["trusted"] = True
    else:  # cancelled — 단 한 번이라도 나오면 즉시 리셋+강등(보수적, Lazzy와 동일)
        entry["streak"] = 0
        entry["trusted"] = False
    state[root_label] = entry
    atomic_write_json(TRUST_STATE_PATH, state)

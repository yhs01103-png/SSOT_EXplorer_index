"""SSOT_Explorer 라우터 — 키워드/태그 자동 승급 레지스트리(2026-08-14, D-044).

Lazzy_App_OS_Monorepo/server/core/orchestrators/keyword_registry.py를 실제로
읽고 이식(사용자 요청 — "맥락형 인덱싱으로 발전"의 1단계). 원본은 SQLAlchemy
DB 테이블(KeywordRegistry) + 비동기 교차조회까지 갖춘 훨씬 큰 구조지만, 이
프로젝트 규모(등록 루트 5개, DB 없음)에 맞게 핵심 메커니즘만 축소 이식:

**candidate → active → dormant 3단계 수명주기.** 라우터가 실제로 분류에 쓴
키워드(=classify_content()/orchestrate()의 matchedKeywords — "아무 단어나"가
아니라 "실제로 판단에 쓰인 단어"만)가 처음 보이면 candidate로 등록되고,
**hit_count≥5 AND 관측 기간(첫~마지막 관측일)≥3일**을 동시에 넘기면 active로
자동 승급된다(원본과 동일 임계값). active 키워드는 이후 분류 점수에 보너스를
받는다(router_orchestrator.py 참고) — "여러 번, 여러 날에 걸쳐 반복된 단어일수록
더 믿는다"는 게 이 메커니즘의 핵심. 14일 넘게 안 보인 candidate는 dormant로
전환(삭제 아님, 원본과 동일 원칙 — "참조 안 하는 보관함").

router_proposals.py와 마찬가지로 Qt를 import하지 않는 순수 모듈, atomic_write_json
재사용(원자적 쓰기 로직 중복 방지, D-043에서 이미 지적된 패턴).

원본과 의도적으로 다르게 이식 안 한 것: DB 테이블/비동기/dev_alert 로깅
(SSOT_Explorer엔 그런 인프라 자체가 없음), TOCTOU 동시성 방어(단일 프로세스
개인용 도구라 원본이 우려하는 "동시 요청 경쟁" 자체가 성립 안 함 — D-021의
낙관적 동시성 제어가 다루는 레지스트리 파일과 달리, 이 파일은 앱 프로세스
1개만 건드림)."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from router_paths import (
    KEYWORD_REGISTRY_PATH,  # D-098, O-021 Stage 1 — 경로 레이어로 이관, 재노출만
)
from router_proposals import atomic_write_json

# keyword_registry.py(D-SERVER-054/D-SERVER-062)와 동일 임계값.
PROMOTION_HIT_THRESHOLD = 5
PROMOTION_MIN_SPAN_DAYS = 3
STALE_CANDIDATE_DAYS = 14  # 이보다 오래 안 보인 candidate는 dormant로

ACTIVE_KEYWORD_BONUS = 0.15  # router_orchestrator.py에서 쓰는 점수 보너스


def load_keyword_registry(path: Path | None = None) -> dict[str, dict]:
    """{keyword: {"status", "hitCount", "firstSeenAt", "lastSeenAt"}}"""
    p = path or KEYWORD_REGISTRY_PATH
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save(registry: dict[str, dict], path: Path | None = None) -> None:
    atomic_write_json(path or KEYWORD_REGISTRY_PATH, registry)


def record_keyword_hits(keywords: list[str], path: Path | None = None) -> list[str]:
    """실제로 분류에 쓰인 키워드들(matchedKeywords)을 관측 기록에 반영.
    없으면 candidate로 신설(hitCount=1), candidate면 hitCount+1/lastSeenAt
    갱신, active/dormant는 안 건드림(원본과 동일 — 승격 완료·휴면 상태는
    이 함수 책임 밖). 반환값: 이번 호출로 실제 터치된 키워드 목록
    (try_promote 재확인 대상)."""
    if not keywords:
        return []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    registry = load_keyword_registry(path)
    touched = []
    for kw in keywords:
        entry = registry.get(kw)
        if entry is None:
            registry[kw] = {
                "status": "candidate",
                "hitCount": 1,
                "firstSeenAt": now,
                "lastSeenAt": now,
            }
            touched.append(kw)
        elif entry["status"] == "candidate":
            entry["hitCount"] += 1
            entry["lastSeenAt"] = now
            touched.append(kw)
        # active/dormant는 그대로 둠
    if touched:
        _save(registry, path)
    return touched


def try_promote(keyword: str, path: Path | None = None) -> bool:
    """candidate인 keyword의 hitCount/관측기간이 임계값을 넘었으면 active로
    승급. 넘지 못했거나 candidate가 아니면(이미 active/dormant, 또는 존재
    안 함) 아무 것도 안 하고 False."""
    registry = load_keyword_registry(path)
    entry = registry.get(keyword)
    if entry is None or entry["status"] != "candidate":
        return False
    first = datetime.strptime(entry["firstSeenAt"], "%Y-%m-%d %H:%M:%S")
    last = datetime.strptime(entry["lastSeenAt"], "%Y-%m-%d %H:%M:%S")
    span_days = (last.date() - first.date()).days
    if entry["hitCount"] < PROMOTION_HIT_THRESHOLD or span_days < PROMOTION_MIN_SPAN_DAYS:
        return False
    entry["status"] = "active"
    _save(registry, path)
    return True


def sweep_stale_candidates(path: Path | None = None) -> int:
    """lastSeenAt이 STALE_CANDIDATE_DAYS 넘게 지난 candidate를 dormant로.
    삭제 안 함. 반환값: 전환된 키워드 수. 원본은 일일 배치 스케줄러가
    호출하지만, 이 프로젝트 규모에선 별도 스케줄러 없이 router_orchestrator.
    orchestrate() 호출마다 opportunistic하게 불러도 비용이 무시할 만큼
    작다(작은 dict 순회+날짜 비교뿐)."""
    now = datetime.now()
    registry = load_keyword_registry(path)
    cutoff = now - timedelta(days=STALE_CANDIDATE_DAYS)
    count = 0
    for entry in registry.values():
        if entry["status"] != "candidate":
            continue
        last = datetime.strptime(entry["lastSeenAt"], "%Y-%m-%d %H:%M:%S")
        if last < cutoff:
            entry["status"] = "dormant"
            count += 1
    if count:
        _save(registry, path)
    return count


def active_keywords(path: Path | None = None) -> set[str]:
    """router_orchestrator.py가 점수 보너스를 줄 때 참조하는 집합."""
    registry = load_keyword_registry(path)
    return {kw for kw, entry in registry.items() if entry["status"] == "active"}


def format_keyword_registry_text(registry: dict[str, dict] | None = None, path: Path | None = None) -> str:
    """관리자 패널용 정리 텍스트 — active 먼저, 그다음 candidate(hitCount
    내림차순), dormant는 개수만 요약(공간 아낌)."""
    data = registry if registry is not None else load_keyword_registry(path)
    if not data:
        return "(등록된 키워드 없음 — 라우터를 쓰면서 자동으로 쌓임)"
    active = sorted((k for k, v in data.items() if v["status"] == "active"))
    candidates = sorted(
        ((k, v["hitCount"]) for k, v in data.items() if v["status"] == "candidate"),
        key=lambda kv: kv[1], reverse=True,
    )
    dormant_count = sum(1 for v in data.values() if v["status"] == "dormant")
    lines = []
    if active:
        lines.append("✅ 활성(점수 보너스 적용): " + ", ".join(active))
    if candidates:
        lines.append("⏳ 관찰중: " + ", ".join(f"{k}({n})" for k, n in candidates[:20]))
    if dormant_count:
        lines.append(f"💤 휴면: {dormant_count}개(14일 이상 안 보임)")
    return "\n".join(lines) if lines else "(등록된 키워드 없음)"

"""SSOT_Explorer 라우터 — 제안 이력(2026-08-13 D-029).

자동분류 제안을 사용자가 승인/취소한 기록을 남긴다 — "지금은 제안만 하고
자세히 설명하되, 사용자가 승인/취소 버튼을 누르면 그걸 기록해서 나중에
로그로 정밀도를 높이는 재료로 쓴다"는 요청의 저장소 부분. 지금은 그
정밀도 계산(점수 재조정 등)까지는 안 하고 원장부만 쌓는다 — 실제
재조정 로직은 데이터가 어느 정도 쌓인 뒤 별도 라운드 과제(O-007).

Lazzy_App_OS_Monorepo의 ConfidenceJudgment/confidence_calibrator 패턴
(판정마다 근거를 남기고, 사후 정확도를 추적해 다음 판단에 반영하는 폐루프)
과 방향이 같다 — 다만 이건 그 축소판(원장부만, 자동 재조정은 아직 없음).

router_classifier.py와 마찬가지로 Qt를 import하지 않는 순수 모듈 — 나중에
서버 프로세스로 떼어내도 그대로 재사용 가능.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

PROPOSALS_LOG_PATH = Path.home() / ".claude" / "scripts" / "ssot_router_proposals.json"


def load_proposals() -> list[dict]:
    if not PROPOSALS_LOG_PATH.exists():
        return []
    try:
        return json.loads(PROPOSALS_LOG_PATH.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return []


def _save_proposals(proposals: list[dict]) -> None:
    """D-021과 같은 원자적 쓰기(temp+os.replace) 패턴 재사용 — 이 로그는
    단일 기기·단일 프로세스 전용이라(OneDrive로 여러 기기에 공유되는
    레지스트리와 다름) 낙관적 동시성 검사는 생략하고 원자성만 챙긴다."""
    PROPOSALS_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(proposals, ensure_ascii=False, indent=2).encode("utf-8")
    tmp_path = PROPOSALS_LOG_PATH.with_name(PROPOSALS_LOG_PATH.name + f".tmp{os.getpid()}")
    try:
        tmp_path.write_bytes(raw)
        os.replace(tmp_path, PROPOSALS_LOG_PATH)
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def record_decision(candidate: dict, content_preview: str, decision: str) -> dict:
    """decision은 "approved" | "cancelled"만 허용. 승인된 것만 실제 파일
    쓰기로 이어진다(main.py의 SaveDocumentDialog가 처리) — 이 함수는
    기록만 하고 파일시스템은 건드리지 않는다."""
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
    return entry


def acceptance_rate(root_label: str | None = None) -> float | None:
    """지금까지 기록된 제안 중 승인 비율 — root_label 지정 시 그 루트만.
    데이터 0건이면 None(계산 불가 — 0%와 구분해야 함, 아직 아무 신호도
    없는 상태를 "전부 틀렸다"로 오독하면 안 됨). "정밀도 높여지는 방향"의
    첫 단계 지표 — 실제 분류 점수에 반영하는 건 이후 라운드 과제."""
    proposals = load_proposals()
    if root_label:
        proposals = [p for p in proposals if p.get("rootLabel") == root_label]
    if not proposals:
        return None
    approved = sum(1 for p in proposals if p["decision"] == "approved")
    return round(approved / len(proposals), 3)

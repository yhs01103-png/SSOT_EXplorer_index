"""router_proposals.py 전용 테스트 — D-029, D-030(신뢰 폐루프 추가).
PROPOSALS_LOG_PATH/TRUST_STATE_PATH를 임시 경로로 격리해서 실제 사용자
로그(~/.claude/scripts/ssot_router_proposals.json, ssot_router_trust.json)
를 절대 안 건드린다."""
from __future__ import annotations

import pytest

import router_proposals as rp


@pytest.fixture(autouse=True)
def isolated_proposals_log(tmp_path, monkeypatch):
    monkeypatch.setattr(rp, "PROPOSALS_LOG_PATH", tmp_path / "proposals.json")
    monkeypatch.setattr(rp, "TRUST_STATE_PATH", tmp_path / "trust.json")
    yield


def test_load_proposals_missing_file_returns_empty():
    assert rp.load_proposals() == []


# --------------------------------------------- D-043: 공유 레지스트리 경로 해석

def test_resolve_registry_path_env_var_and_fallback(monkeypatch, tmp_path):
    """D-043(code-review 발견) — main.py/router_classifier.py가 각자 들고
    있던 동일 로직을 여기 하나로 모음. 두 파일 다 이 함수로 위임하는지는
    test_main.py의 D-039 테스트가 계속 커버."""
    custom = tmp_path / "custom-roots.json"
    monkeypatch.setenv("SSOT_REGISTRY_PATH", str(custom))
    assert rp.resolve_registry_path() == custom

    monkeypatch.delenv("SSOT_REGISTRY_PATH", raising=False)
    from pathlib import Path
    assert rp.resolve_registry_path() == Path.home() / ".claude" / "ssot-roots.json"


def test_record_decision_appends_and_persists():
    candidate = {"rootLabel": "a", "rootPath": "C:\\a", "score": 0.5, "reason": "테스트"}
    entry = rp.record_decision(candidate, "내용 미리보기", "approved")
    assert entry["decision"] == "approved"
    assert entry["rootLabel"] == "a"
    loaded = rp.load_proposals()
    assert len(loaded) == 1
    assert loaded[0]["id"] == entry["id"]


def test_record_decision_rejects_invalid_decision():
    candidate = {"rootLabel": "a", "rootPath": "C:\\a", "score": 0.5, "reason": "테스트"}
    with pytest.raises(ValueError):
        rp.record_decision(candidate, "x", "maybe")


def test_record_decision_truncates_long_preview():
    candidate = {"rootLabel": "a", "rootPath": "C:\\a", "score": 0.5, "reason": "테스트"}
    entry = rp.record_decision(candidate, "x" * 500, "approved")
    assert len(entry["contentPreview"]) == 200


def test_save_proposals_leaves_no_tmp_file(tmp_path):
    candidate = {"rootLabel": "a", "rootPath": "C:\\a", "score": 0.5, "reason": "테스트"}
    rp.record_decision(candidate, "x", "approved")
    leftovers = list(rp.PROPOSALS_LOG_PATH.parent.glob(rp.PROPOSALS_LOG_PATH.name + ".tmp*"))
    assert leftovers == []


def test_acceptance_rate_none_when_no_data():
    assert rp.acceptance_rate() is None
    assert rp.acceptance_rate("아무거나") is None


def test_acceptance_rate_computes_correctly():
    candidate = {"rootLabel": "a", "rootPath": "C:\\a", "score": 0.5, "reason": "테스트"}
    rp.record_decision(candidate, "x", "approved")
    rp.record_decision(candidate, "y", "approved")
    rp.record_decision(candidate, "z", "cancelled")
    assert rp.acceptance_rate() == pytest.approx(2 / 3, rel=1e-3)


def test_acceptance_rate_filters_by_root_label():
    cand_a = {"rootLabel": "a", "rootPath": "C:\\a", "score": 0.5, "reason": "테스트"}
    cand_b = {"rootLabel": "b", "rootPath": "C:\\b", "score": 0.5, "reason": "테스트"}
    rp.record_decision(cand_a, "x", "approved")
    rp.record_decision(cand_b, "y", "cancelled")
    assert rp.acceptance_rate("a") == 1.0
    assert rp.acceptance_rate("b") == 0.0


# ------------------------------------------- D-030: 신뢰 폐루프(승급/강등)

def test_is_trusted_false_when_no_history():
    assert rp.is_trusted("never-seen") is False


def test_trust_promotes_after_streak_of_approvals():
    candidate = {"rootLabel": "a", "rootPath": "C:\\a", "score": 0.5, "reason": "테스트"}
    for _ in range(rp.TRUST_PROMOTION_STREAK - 1):
        rp.record_decision(candidate, "x", "approved")
    assert rp.is_trusted("a") is False  # 아직 스트릭 미달
    rp.record_decision(candidate, "x", "approved")  # 마지막 1번 채움
    assert rp.is_trusted("a") is True


def test_trust_resets_and_demotes_on_single_cancellation():
    candidate = {"rootLabel": "a", "rootPath": "C:\\a", "score": 0.5, "reason": "테스트"}
    for _ in range(rp.TRUST_PROMOTION_STREAK):
        rp.record_decision(candidate, "x", "approved")
    assert rp.is_trusted("a") is True

    rp.record_decision(candidate, "x", "cancelled")  # 단 한 번의 거부
    assert rp.is_trusted("a") is False  # 이미 승급했어도 즉시 강등

    state = rp.load_trust_state()
    assert state["a"]["streak"] == 0  # 스트릭도 0으로 리셋


def test_trust_is_tracked_independently_per_root_label():
    cand_a = {"rootLabel": "a", "rootPath": "C:\\a", "score": 0.5, "reason": "테스트"}
    cand_b = {"rootLabel": "b", "rootPath": "C:\\b", "score": 0.5, "reason": "테스트"}
    for _ in range(rp.TRUST_PROMOTION_STREAK):
        rp.record_decision(cand_a, "x", "approved")
    assert rp.is_trusted("a") is True
    assert rp.is_trusted("b") is False  # b는 아직 이력 없음


def test_save_trust_state_leaves_no_tmp_file():
    candidate = {"rootLabel": "a", "rootPath": "C:\\a", "score": 0.5, "reason": "테스트"}
    rp.record_decision(candidate, "x", "approved")
    leftovers = list(rp.TRUST_STATE_PATH.parent.glob(rp.TRUST_STATE_PATH.name + ".tmp*"))
    assert leftovers == []

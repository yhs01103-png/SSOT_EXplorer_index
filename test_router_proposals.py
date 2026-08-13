"""router_proposals.py 전용 테스트 — D-029. PROPOSALS_LOG_PATH를 임시
경로로 격리해서 실제 사용자 로그(~/.claude/scripts/ssot_router_proposals.json)
를 절대 안 건드린다."""
from __future__ import annotations

import pytest

import router_proposals as rp


@pytest.fixture(autouse=True)
def isolated_proposals_log(tmp_path, monkeypatch):
    monkeypatch.setattr(rp, "PROPOSALS_LOG_PATH", tmp_path / "proposals.json")
    yield


def test_load_proposals_missing_file_returns_empty():
    assert rp.load_proposals() == []


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

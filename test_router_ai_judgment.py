"""router_ai_judgment.py 전용 테스트 — D-063(틀만, O-014). judge_candidates는
아직 프로바이더 미연결이라 예외를 던지는 게 "정상 동작" — 그 사실 자체를
확인한다(test_router_embeddings.py와 동일 취지 — 나중에 프로바이더가 실제로
붙으면 이 테스트가 자연스럽게 깨지면서 "이제 채워야 한다"는 신호가 된다)."""
from __future__ import annotations

import pytest

import router_ai_judgment as aj


def test_judge_candidates_raises_not_configured():
    with pytest.raises(aj.AIJudgeProviderNotConfigured):
        aj.judge_candidates("아무 텍스트", [{"rootLabel": "x", "score": 0.5}])


def test_judge_candidates_raises_even_with_empty_candidates():
    with pytest.raises(aj.AIJudgeProviderNotConfigured):
        aj.judge_candidates("아무 텍스트", [])

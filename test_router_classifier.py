"""router_classifier.py 전용 테스트 — D-029, D-030(다중신호+CLI 업그레이드).
모듈이 Qt를 안 쓰는 순수 함수라 test_main.py의 qapp 픽스처 없이도 독립적
으로 돈다."""
from __future__ import annotations

import json
import subprocess
import sys

import pytest

import router_classifier as rc


def test_tokenize_lowercases_and_filters_short_tokens():
    words = rc.tokenize("Hello 안 a AI 프로젝트")
    assert "hello" in words
    assert "프로젝트" in words
    assert "a" not in words  # 1글자는 버림
    assert "ai" in words  # 2글자는 유지


def test_tokenize_empty_or_none_returns_empty_set():
    assert rc.tokenize("") == set()
    assert rc.tokenize(None) == set()


def test_classify_content_empty_text_returns_empty():
    roots = [{"label": "a", "path": "C:\\a", "scope": "테스트"}]
    assert rc.classify_content("", roots) == []


def test_classify_content_no_overlap_returns_empty():
    roots = [{"label": "a", "path": "C:\\a", "scope": "완전히다른주제", "referenceCondition": ""}]
    assert rc.classify_content("전혀 겹치지 않는 별개의 내용입니다", roots) == []


def test_classify_content_ranks_by_overlap_score():
    roots = [
        {"label": "flutter_App", "path": "C:\\flutter", "scope": "플러터 앱 개발", "referenceCondition": ""},
        {"label": "coding_admin", "path": "C:\\admin", "scope": "보안 정보", "referenceCondition": ""},
    ]
    text = "플러터 앱 개발 관련 메모 — UI 레이아웃 정리"
    results = rc.classify_content(text, roots)
    assert len(results) == 1
    assert results[0]["rootLabel"] == "flutter_App"
    assert results[0]["score"] > 0
    assert "rootPath" in results[0]
    assert "reason" in results[0]


def test_classify_content_sorts_descending_by_score():
    """referenceCondition으로 키워드겹침 신호를 차등 발생시킨다 — scope는
    신호1(키워드겹침) 해시태그에서 빠졌으므로(D-030) scope만으로는 이 테스트가
    차등 순위를 만들 수 없다."""
    roots = [
        {"label": "low", "path": "C:\\low", "scope": "", "referenceCondition": "코딩"},
        {"label": "high", "path": "C:\\high", "scope": "", "referenceCondition": "코딩 프로젝트 개발 문서 정리"},
    ]
    text = "코딩 프로젝트 개발 문서 정리 작업"
    results = rc.classify_content(text, roots)
    assert len(results) == 2
    assert results[0]["rootLabel"] == "high"
    assert results[0]["score"] >= results[1]["score"]


# ------------------------------------------ D-033: IDF 가중치, floor→additive

def test_compute_idf_downweights_terms_common_across_roots():
    """"코드"가 모든 문서에 나오고 "특이어"는 하나에만 나오면, 후자가 훨씬
    높은 가중치를 받아야 한다 — IDF의 핵심 성질."""
    corpora = {
        "a": "코드 프로젝트 규칙",
        "b": "코드 프로젝트 정리",
        "c": "코드 특이어 문서",
    }
    idf = rc.compute_idf(corpora)
    assert idf["특이어"] > idf["코드"]


def test_classify_content_idf_differentiates_generic_vs_specific_match():
    """D-032 실측 문제의 재현+회귀 테스트 — "코드"/"프로젝트"/"규칙"처럼
    거의 모든 루트에 흔한 단어만 걸린 루트보다, 그 단어들에 더해 특이
    단어까지 겹친 루트가 확실히 더 높은 점수를 받아야 한다(예전엔 둘 다
    scope 신호면 강제로 0.5 동점이었음)."""
    roots = [
        {"label": "generic_only", "path": "C:\\g", "scope": "", "referenceCondition": "코드 프로젝트 규칙 정리"},
        {"label": "generic_plus_specific", "path": "C:\\gs", "scope": "", "referenceCondition": "코드 프로젝트 규칙 정리 범용규칙모음집"},
        {"label": "unrelated", "path": "C:\\u", "scope": "", "referenceCondition": "완전히 다른 주제 내용"},
    ]
    text = "코드 프로젝트 규칙 정리 범용규칙모음집 작업"
    results = rc.classify_content(text, roots)
    by_label = {c["rootLabel"]: c for c in results}
    assert by_label["generic_plus_specific"]["score"] > by_label["generic_only"]["score"]
    assert "unrelated" not in by_label


# ---------------------------------------------- D-030: 다중신호(union) 구조

def test_classify_content_scope_literal_signal_alone_is_enough():
    """키워드 겹침이 0이어도 scope 문구가 텍스트에 그대로 있으면 신호2만
    으로 채택돼야 함(union 원칙 — 신호 하나만 걸려도 후보). D-033: floor가
    아니라 additive라 점수는 SCOPE_MATCH_BONUS 그 자체(0.3) — 0.5가 아님."""
    roots = [{"label": "x", "path": "C:\\x", "scope": "보안금고특수키워드", "referenceCondition": ""}]
    results = rc.classify_content("이건 보안금고특수키워드 관련 새 메모다", roots)
    assert len(results) == 1
    assert "scope일치" in results[0]["signals"]
    assert results[0]["score"] == pytest.approx(rc.SCOPE_MATCH_BONUS)


def test_classify_content_both_signals_rank_above_single_signal():
    roots = [
        {"label": "single", "path": "C:\\s", "scope": "특수키워드", "referenceCondition": ""},
        {"label": "both", "path": "C:\\b", "scope": "특수키워드", "referenceCondition": "특수키워드 관련 메모 정리"},
    ]
    text = "특수키워드 관련 메모 정리"
    results = rc.classify_content(text, roots)
    assert results[0]["rootLabel"] == "both"
    assert len(results[0]["signals"]) == 2
    assert len(results[1]["signals"]) == 1


# --------------------------------------------------------- D-030: 물어보기 원칙

def test_needs_clarification_true_for_short_text():
    assert rc.needs_clarification("이거") is True
    assert rc.needs_clarification("그거 저장해줘") is True  # 3토큰 이하


def test_needs_clarification_false_for_specific_text():
    assert rc.needs_clarification("플러터 앱 개발 관련 회의록 정리 문서") is False


def test_needs_clarification_false_for_empty_text():
    assert rc.needs_clarification("") is False


# --------------------------------------------------------------- D-030: CLI

def test_cli_returns_candidates_as_json(tmp_path):
    root_dir = tmp_path / "flutter_App"
    root_dir.mkdir()
    registry = tmp_path / "ssot-roots.json"
    registry.write_text(json.dumps({
        "roots": [{"label": "flutter_App", "path": str(root_dir), "scope": "플러터 앱 개발", "referenceCondition": ""}],
    }), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, rc.__file__, "--text", "플러터 앱 개발 메모", "--registry", str(registry)],
        capture_output=True, text=True, encoding="utf-8", timeout=15,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["needsClarification"] is False
    assert len(payload["candidates"]) == 1
    assert payload["candidates"][0]["rootLabel"] == "flutter_App"


def test_cli_reports_needs_clarification_for_vague_text(tmp_path):
    registry = tmp_path / "ssot-roots.json"
    registry.write_text(json.dumps({"roots": []}), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, rc.__file__, "--text", "이거", "--registry", str(registry)],
        capture_output=True, text=True, encoding="utf-8", timeout=15,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["needsClarification"] is True
    assert payload["candidates"] == []

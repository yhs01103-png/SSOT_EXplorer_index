"""router_classifier.py 전용 테스트 — D-029. 모듈이 Qt를 안 쓰는 순수
함수라 test_main.py의 qapp 픽스처 없이도 독립적으로 돈다."""
from __future__ import annotations

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
    roots = [
        {"label": "low", "path": "C:\\low", "scope": "코딩", "referenceCondition": ""},
        {"label": "high", "path": "C:\\high", "scope": "코딩 프로젝트 개발 문서 정리", "referenceCondition": ""},
    ]
    text = "코딩 프로젝트 개발 문서 정리 작업"
    results = rc.classify_content(text, roots)
    assert len(results) == 2
    assert results[0]["rootLabel"] == "high"
    assert results[0]["score"] >= results[1]["score"]

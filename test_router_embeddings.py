"""router_embeddings.py 전용 테스트 — D-044(틀만, O-009). embed_text/
embed_query_text는 아직 프로바이더 미연결이라 예외를 던지는 게 "정상 동작"
— 그 사실 자체를 확인한다(D-029 InboxWatcher 스켈레톤 테스트와 같은 취지,
나중에 프로바이더가 실제로 붙으면 이 두 테스트가 자연스럽게 깨지면서
"이제 채워야 한다"는 신호가 된다). cosine_similarity/rank_by_similarity는
프로바이더 없이도 완성된 순수 로직이라 지금 바로 검증."""
from __future__ import annotations

import pytest

import router_embeddings as re_


def test_embed_text_raises_not_configured():
    with pytest.raises(re_.EmbeddingProviderNotConfigured):
        re_.embed_text("아무 텍스트")


def test_embed_query_text_raises_not_configured():
    with pytest.raises(re_.EmbeddingProviderNotConfigured):
        re_.embed_query_text("아무 질의")


def test_cosine_similarity_identical_vectors_is_one():
    assert re_.cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)


def test_cosine_similarity_orthogonal_vectors_is_zero():
    assert re_.cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_cosine_similarity_mismatched_length_returns_zero():
    assert re_.cosine_similarity([1.0, 0.0], [1.0, 0.0, 0.0]) == 0.0


def test_cosine_similarity_empty_vector_returns_zero():
    assert re_.cosine_similarity([], [1.0]) == 0.0


def test_rank_by_similarity_filters_and_sorts():
    query = [1.0, 0.0]
    items = [
        {"label": "same", "embedding": [1.0, 0.0]},       # sim = 1.0
        {"label": "orthogonal", "embedding": [0.0, 1.0]},  # sim = 0.0 (below default min)
        {"label": "close", "embedding": [0.9, 0.1]},
    ]
    ranked = re_.rank_by_similarity(query, items, top_k=5, min_similarity=0.5)
    labels = [item["label"] for item in ranked]
    assert labels[0] == "same"
    assert "orthogonal" not in labels


def test_rank_by_similarity_skips_items_without_embedding():
    items = [{"label": "no-embedding"}]
    assert re_.rank_by_similarity([1.0, 0.0], items) == []


def test_rank_by_similarity_respects_top_k():
    query = [1.0, 0.0]
    items = [{"label": str(i), "embedding": [1.0, 0.0]} for i in range(10)]
    assert len(re_.rank_by_similarity(query, items, top_k=3, min_similarity=0.0)) == 3

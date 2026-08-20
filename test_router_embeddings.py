"""router_embeddings.py 전용 테스트.

embed_text/embed_query_text는 D-067부로 실제 로컬 모델(fastembed)에
연결됐다 — 하지만 매 테스트마다 실제 ONNX 모델을 로드/추론하면 느리고
최초 가중치 다운로드(네트워크)에 의존해 이 프로젝트의 결정적 테스트
원칙(D-024)과 안 맞는다. 그래서 _get_model()이 반환하는 모델 객체를
가짜로 교체해 이 모듈의 계약(프리픽스 없음, 벡터 반환, 지연 로딩+캐싱,
미설치 시 예외 변환)만 검증한다 — fastembed/모델 자체가 의미상 올바른
벡터를 내놓는지는 이 테스트의 책임이 아니다(그건 fastembed/모델의 신뢰
영역, 실제 유사도 스팟체크는 D-067 결정이력에 실측으로 남겨둠).

cosine_similarity/rank_by_similarity는 순수 로직이라 원래대로 실제 값으로
검증(D-044부터 있던 테스트 그대로, 변화 없음)."""
from __future__ import annotations

import sys
from types import ModuleType

import pytest

import router_embeddings as re_


class _FakeVector:
    def __init__(self, values):
        self._values = values

    def tolist(self):
        return self._values


class _FakeModel:
    def __init__(self):
        self.calls: list[str] = []

    def embed(self, texts):
        self.calls.append(texts[0])
        return [_FakeVector([float(len(texts[0])), 0.0])]


@pytest.fixture(autouse=True)
def _reset_model_cache():
    """_model은 모듈 전역 캐시라 테스트 간 서로 오염되지 않게 매번 리셋."""
    re_._model = None
    yield
    re_._model = None


def test_embed_text_returns_list_of_floats(monkeypatch):
    fake = _FakeModel()
    monkeypatch.setattr(re_, "_get_model", lambda: fake)
    result = re_.embed_text("아무 텍스트")
    assert isinstance(result, list)
    assert all(isinstance(x, float) for x in result)


def test_embed_text_passes_text_unchanged_no_prefix(monkeypatch):
    """D-067 — 현재 모델(MiniLM)은 E5식 프리픽스가 없다."""
    fake = _FakeModel()
    monkeypatch.setattr(re_, "_get_model", lambda: fake)
    re_.embed_text("원문 그대로")
    assert fake.calls == ["원문 그대로"]


def test_embed_query_text_passes_text_unchanged_no_prefix(monkeypatch):
    fake = _FakeModel()
    monkeypatch.setattr(re_, "_get_model", lambda: fake)
    re_.embed_query_text("질의 그대로")
    assert fake.calls == ["질의 그대로"]


def test_get_model_raises_not_configured_when_fastembed_missing(monkeypatch):
    """fastembed import 실패 시 EmbeddingProviderNotConfigured로 변환돼야
    orchestrator의 기존 except 절(D-044 계약)이 하위호환으로 계속 동작."""
    import builtins

    real_import = builtins.__import__

    def _blocked_import(name, *args, **kwargs):
        if name == "fastembed":
            raise ImportError("no fastembed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _blocked_import)
    with pytest.raises(re_.EmbeddingProviderNotConfigured):
        re_._get_model()


def test_get_model_caches_across_calls(monkeypatch):
    """모델 로드는 1회만 — 두 번째 호출부턴 캐시된 인스턴스를 재사용해야
    호출마다 수백MB 모델을 다시 안 띄운다."""
    created = []

    class _CountingFakeTextEmbedding:
        def __init__(self, model_name):
            created.append(model_name)

        def embed(self, texts):
            return [_FakeVector([0.0])]

    fake_module = ModuleType("fastembed")
    fake_module.TextEmbedding = _CountingFakeTextEmbedding
    monkeypatch.setitem(sys.modules, "fastembed", fake_module)

    re_.embed_text("a")
    re_.embed_text("b")
    assert len(created) == 1
    assert created[0] == re_._MODEL_NAME


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

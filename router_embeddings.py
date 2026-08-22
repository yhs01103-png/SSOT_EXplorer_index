"""SSOT_Explorer 라우터 — 임베딩 기반 시맨틱 매칭(2026-08-14 D-044 틀만 →
2026-08-21 D-067 실제 연결, O-009 확정).

D-067: 사용자가 AskUserQuestion으로 "로컬 모델(추천)/Gemini API/OpenAI API/
보류" 중 로컬 모델을 명시적으로 선택 — 이 프로젝트가 D-034부터 지켜온 완전
오프라인 원칙을 깨지 않는 유일한 선택지였다. `fastembed`(Qdrant, ONNX
런타임 — torch 의존성 없음, onnxruntime만)로 로컬 실행. API 키/네트워크
호출/비용/외부 텍스트 전송 전부 없음 — 최초 실행 시 모델 가중치를
로컬 캐시에 받는 것만 유일한 네트워크 의존(그 이후는 완전 오프라인 추론).

**모델 선정 — 계획을 실측으로 바꾼 지점**: 애초 `intfloat/multilingual-e5-
small`(E5 계열, query/passage 프리픽스로 질의·색인을 구분해 학습된 모델이라
embed_text/embed_query_text 분리와 정확히 들어맞을 것으로 기대)을 쓰려
했으나, `TextEmbedding.list_supported_models()`로 fastembed 자체 레지스트리를
실측 확인하니 small 버전은 없고 `multilingual-e5-large`(2.24GB)뿐이었다 —
PyInstaller 배포 크기(현재 exe 161MB)를 감안하면 부적합. 대신
`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`(0.22GB, 50+
언어·한국어 포함)로 교체. 이 모델은 E5식 프리픽스 관례가 없어 embed_text/
embed_query_text 둘 다 원문을 그대로 임베딩한다 — "task_type 분리가
정확도를 올린다"는 Lazzy(Gemini) 실측이 이 모델 아키텍처엔 직접 적용되지
않는다는 뜻이다. 인터페이스는 향후 E5류 모델로 교체할 가능성을 위해 그대로
분리 유지.

모델 로딩은 지연 초기화(첫 호출 시 1회) + 락으로 스레드 세이프하게 캐시.
`fastembed`가 설치 안 돼 있으면(선택적 의존성) `EmbeddingProviderNotConfigured`
로 안내 — orchestrator는 이 경우도 여전히 skipped로만 기록하고 결과에
영향 없음(D-044 계약 유지, 하위호환).

**MIN_SIMILARITY 재보정(O-016) — 실측 2쌍**: "flutter_App은 Flutter 앱들을
모아둔 프로젝트다"(passage) 대비 "플러터 앱 관련 작업"(관련 query)
0.6782, "오늘 점심 메뉴 추천"(무관 query) 0.1468. Lazzy(Gemini) 실측을
그대로 가져온 옛 기본값 0.7은 이 모델에서는 **관련 쌍마저 걸러낼 만큼
안 맞아** 0.5로 낮췄다 — 다만 표본이 2쌍뿐이라 잠정값이다(이 프로젝트의
LOW_SAMPLE_THRESHOLD 관례와 같은 정신으로, 실사용 쿼리가 쌓이면 재조정
필요, O-016에 표시).

fastembed 0.8.0에서 이 모델이 "이제 CLS 대신 mean pooling을 쓴다"는
런타임 경고가 뜬다(라이브러리 쪽 변경, 우리 코드 아님) — 향후 fastembed
버전이 다시 바뀌면 벡터 분포가 조용히 달라질 수 있어 requirements.txt에
`fastembed==0.8.0`으로 버전을 고정했다.
"""
from __future__ import annotations

import math
import threading

_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

_model = None
_model_lock = threading.Lock()


class EmbeddingProviderNotConfigured(Exception):
    """embed_text()/embed_query_text()를 실제로 호출했는데 fastembed가
    설치돼 있지 않을 때(선택적 의존성, D-067). 정상 설치 환경에서는
    발생하지 않는다."""


def _get_model():
    """지연 초기화 — 첫 호출 시에만 모델을 로드(가중치 다운로드/디스크
    읽기가 임포트 시점이 아니라 실제 사용 시점에 일어나게). double-checked
    locking으로 동시 호출 시 중복 로드 방지."""
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                try:
                    from fastembed import TextEmbedding
                except ImportError as exc:
                    raise EmbeddingProviderNotConfigured(
                        "fastembed가 설치되지 않았습니다. `pip install fastembed`로 "
                        "설치하세요(D-067 — 로컬 모델로 확정, requirements.txt 참고)."
                    ) from exc
                _model = TextEmbedding(model_name=_MODEL_NAME)
    return _model


def embed_text(text: str) -> list[float]:
    """색인(저장) 대상 텍스트를 임베딩. MiniLM은 E5류 프리픽스 관례가 없어
    원문을 그대로 넘긴다 — embed_query_text와 지금은 동일 동작이지만,
    인터페이스는 향후 프리픽스 기반 모델로 교체할 가능성을 위해 분리
    유지(D-067)."""
    model = _get_model()
    (vector,) = model.embed([text])
    return vector.tolist()


def embed_query_text(text: str) -> list[float]:
    """검색 질의 전용 임베딩. 현재 모델(MiniLM)에서는 embed_text와 동일
    동작 — D-067 참고."""
    model = _get_model()
    (vector,) = model.embed([text])
    return vector.tolist()


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """순수 Python(numpy 없음) — Lazzy embeddings.py와 동일 계약. 프로바이더
    연결 전에도 미리 완성해둘 수 있는 부분이라 지금 구현."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# D-067 실측 재보정값(표본 2쌍, 잠정 — O-016). 모듈 docstring 참고.
DEFAULT_MIN_SIMILARITY = 0.5
DEFAULT_TOP_K = 5


def rank_by_similarity(
    query_embedding: list[float],
    items: list[dict],
    embedding_key: str = "embedding",
    top_k: int = DEFAULT_TOP_K,
    min_similarity: float = DEFAULT_MIN_SIMILARITY,
) -> list[dict]:
    """items(각 dict가 embedding_key에 벡터를 담고 있다고 가정)를 query_
    embedding과의 코사인 유사도로 랭킹 — min_similarity 이상만, 내림차순
    top_k개. 임베딩이 없는 항목은 건너뜀. 프로바이더 연결 전에도 이 함수
    자체는 순수 계산이라 지금 테스트 가능(가짜 벡터로)."""
    scored: list[tuple[float, dict]] = []
    for item in items:
        vec = item.get(embedding_key)
        if not vec:
            continue
        similarity = cosine_similarity(query_embedding, vec)
        if similarity >= min_similarity:
            scored.append((similarity, item))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in scored[:top_k]]

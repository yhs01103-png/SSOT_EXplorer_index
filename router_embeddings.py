"""SSOT_Explorer 라우터 — 임베딩 기반 시맨틱 매칭 스켈레톤(2026-08-14, D-044,
O-009로 재논의 조건 기록).

Lazzy_App_OS_Monorepo/server/core/embeddings.py를 확인 후, **틀만** 이식하기로
결정(사용자 요청 — "API를 나중에 붙일 경우 대비"). 순수 로직(코사인 유사도,
랭킹)은 원본과 동일 계약으로 지금 구현하지만, 실제 임베딩 생성(`embed_text`)은
Gemini 등 외부 API 키+네트워크 호출+비용이 필요해서 아직 안 붙인다 — 지금
붙이면 이 프로젝트가 D-034(kiwipiepy 채택 이유가 "로컬/오프라인/무료")부터
지켜온 완전 오프라인 원칙을 처음으로 깨는 결정이라, 사용자가 명시적으로
"연결해줘"라고 할 때까지는 `EmbeddingProviderNotConfigured`만 던진다
(D-029 InboxWatcher 스켈레톤의 NotImplementedError와 같은 패턴 — 인터페이스만
먼저 고정해서, 다음 라운드에 provider 구현만 채우면 되게).

실제로 붙일 때 고려할 것(O-009 참고):
- provider 선택 필요(Gemini/OpenAI/로컬 모델 등) — API 키 관리, 비용, 폴더
  내용을 외부 서버로 보내는 것에 대한 사용자 동의가 먼저.
- Lazzy 실측(embeddings.py 주석): 무관한 문장 쌍도 코사인 유사도 0.55~0.6대가
  나오는 경향 — MIN_SIMILARITY 기본값 0.7은 그 실측을 그대로 가져온 참고값
  (프로바이더가 바뀌면 재보정 필요, 다른 임베딩 모델은 분포가 다를 수 있음).
- 색인용 임베딩과 질의용 임베딩을 다른 task_type으로 구분해야 정확도가
  올라간다는 Lazzy의 발견(embed_text vs embed_query_text)도 인터페이스에
  이미 반영해둠 — provider 구현 시 실제로 구분해서 호출할 것.
"""
from __future__ import annotations

import math


class EmbeddingProviderNotConfigured(Exception):
    """embed_text()/embed_query_text()를 실제로 호출하면 이 예외 — 아직
    프로바이더가 안 붙어 있다는 뜻(O-009, 틀만 구축 단계)."""


def embed_text(text: str) -> list[float]:
    """색인(저장) 대상 텍스트를 임베딩 — 아직 프로바이더 미연결."""
    raise EmbeddingProviderNotConfigured(
        "임베딩 API가 아직 연결되지 않았습니다(D-044 — 틀만 구축, O-009 참고). "
        "실제로 쓰려면 프로바이더(Gemini 등) 선택 + API 키 설정이 먼저 필요합니다."
    )


def embed_query_text(text: str) -> list[float]:
    """검색 질의 전용 임베딩 — Lazzy 실측(embeddings.py)상 색인용과 다른
    task_type으로 임베딩해야 짧은 키워드형 질의가 부당하게 낮은 유사도로
    나오는 문제가 줄어든다는 근거가 있어, 인터페이스를 처음부터 분리해둠."""
    raise EmbeddingProviderNotConfigured(
        "임베딩 API가 아직 연결되지 않았습니다(D-044 — 틀만 구축, O-009 참고)."
    )


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """순수 Python(numpy 없음) — Lazzy embeddings.py와 동일 계약. 프로바이더
    연결 전에도 미리 완성해둘 수 있는 부분이라 지금 구현."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# Lazzy 실측(embeddings.py) 그대로 가져온 참고값 — 실제 프로바이더가 붙으면
# 그 모델의 분포로 재보정 필요(주석 참고).
DEFAULT_MIN_SIMILARITY = 0.7
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

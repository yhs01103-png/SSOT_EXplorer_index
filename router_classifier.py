"""SSOT_Explorer 라우터 — 분류기 ("서버" 쪽 두뇌, 2026-08-13 D-029).

새 문서/파일이 어느 등록 루트에 속하는지 후보를 순위매겨 제안한다 —
사용자가 요청한 "저장하면 알아서 맞는 프로젝트 폴더로" 워크플로우의 핵심.
지금 당장 동작하는 v1은 휴리스틱(키워드 겹침) 기반, AI 없음. 나중에
Claude API 등으로 교체해도 classify_content()의 반환 shape만 유지하면
호출부(main.py)는 안 건드려도 되게 설계했다 — "앱 자체에 API를 내장하되
이번 라운드는 틀만 구축해달라"는 요청의 핵심 부분.

main.py(GUI, "클라이언트")가 아니라 별도 파일로 분리한 이유: 분류 로직을
나중에 실제 서버 프로세스로 떼어내기 쉽게(server/client 분리) 지금부터
독립 모듈로 둔다. 그래서 이 모듈은 자기 상태를 안 갖고(클래스 없음),
Qt를 import하지 않고, 순수 함수로만 구성 — 프로세스 경계를 넘어(HTTP API
등) 호출해도 그대로 재사용 가능하게.

한국어 토크나이저는 지금 단순 정규식 분리뿐이라 정확도가 낮다 —
Lazzy_App_OS_Monorepo가 뉘앙스 톤 자동조절에 쓰는 kiwipiepy(형태소
분석기, D-SERVER-063)를 이식하면 정확도가 오를 다음 후보(O-007 참고).
"""
from __future__ import annotations

import re

_STOPWORD_LEN_MIN = 2  # 이보다 짧은 토큰(조사/1글자 등)은 노이즈로 버림


def tokenize(text: str) -> set[str]:
    """아주 단순한 토크나이저 — 영숫자+한글 연속 구간을 단어로 취급."""
    words = re.findall(r"[\w가-힣]+", (text or "").lower())
    return {w for w in words if len(w) >= _STOPWORD_LEN_MIN}


def classify_content(text: str, roots: list[dict]) -> list[dict]:
    """text가 각 등록 루트(label/scope/referenceCondition)와 얼마나
    겹치는지로 순위를 매긴다. 점수 0(겹치는 단어 없음)인 후보는 제외 —
    빈 리스트도 정상 결과다(사용자가 수동으로 골라야 함을 뜻함).

    반환: [{rootLabel, rootPath, score, matchedKeywords, reason}, ...]
    score 내림차순 정렬. 이 shape은 계약이다 — 분류 로직 내부를 AI로
    바꿔도 이 shape만 지키면 호출부(SaveDocumentDialog 등)는 안 바뀐다.
    """
    text_words = tokenize(text)
    if not text_words:
        return []
    candidates = []
    for r in roots:
        haystack = " ".join([
            r.get("label", "") or "",
            r.get("scope", "") or "",
            r.get("referenceCondition", "") or "",
        ])
        haystack_words = tokenize(haystack)
        overlap = text_words & haystack_words
        if not overlap:
            continue
        score = len(overlap) / len(text_words)
        matched = sorted(overlap)
        preview = ", ".join(matched[:5]) + ("..." if len(matched) > 5 else "")
        candidates.append({
            "rootLabel": r["label"],
            "rootPath": r["path"],
            "score": round(score, 3),
            "matchedKeywords": matched,
            "reason": (
                f"내용 단어 {len(text_words)}개 중 {len(overlap)}개가 이 루트의 "
                f"label/scope/참조조건과 겹침: {preview}"
            ),
        })
    candidates.sort(key=lambda c: c["score"], reverse=True)
    return candidates

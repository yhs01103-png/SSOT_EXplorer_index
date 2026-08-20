"""SSOT_Explorer 라우터 — 실제 AI 판단 연결 스켈레톤(2026-08-19, D-063,
O-014로 재논의 조건 기록).

O-007/O-008("언급 vs 소유" 혼동)의 근본 해결책 중 하나 — router_classifier의
휴리스틱 후보 목록을 실제 LLM(Gemini/Claude API 등)에 넘겨 최종 판단을
맡기는 경로. router_embeddings.py(O-009)와 완전히 같은 이유로 **틀만**
만든다: API 키 관리+네트워크 호출+비용이 필요하고, 이 프로젝트가 D-034부터
지켜온 완전 오프라인 원칙을 처음으로 깨는 결정이라 사용자의 명시적 승인
없이는 `AIJudgeProviderNotConfigured`만 던진다(D-029 InboxWatcher/D-044
임베딩 스켈레톤과 동일 패턴).

router_orchestrator.orchestrate()는 이 함수를 이미 호출하되 예외를 잡아
skipped로만 기록한다(semantic 단계와 동일 처리) — 실제 판단 결과는 결과에
전혀 영향을 주지 않는다.

**이 경로와 tag_word_roles()(같은 D-063, router_classifier.py)의 차이**:
tag_word_roles는 오프라인 원칙 안에서 휴리스틱을 한 겹 더한 것뿐이고,
이 모듈은 원칙을 의도적으로 깨는 별도 결정이 필요한 경로다 — 둘을 섞지
않는다(AskUserQuestion으로 사용자가 명시적으로 "1번은 지금, 2번은 틀만"
이라고 갈랐음, 2026-08-19).

실제로 붙일 때 고려할 것(O-014):
- provider 선택(Gemini/Claude API 등) — API 키 관리, 비용, 후보 목록+원문
  텍스트를 외부로 보내는 것에 대한 사용자 동의가 먼저.
- 입력은 router_classifier.classify_content()가 이미 만든 candidates
  (rootLabel/score/reason/matchedKeywordRoles 포함) + 원문 text — 새로
  루트 텍스트를 통째로 다시 보낼 필요 없이, 이미 압축된 신호만 보내면
  충분할 가능성이 높음(비용 절감 관점에서 우선 검토).
- 반환 shape은 classify_content()와 동일하게 유지 — orchestrator가 이미
  그 shape을 병합하는 코드를 갖고 있어서, 이 계약만 지키면 병합 로직을
  새로 안 짜도 됨.
"""
from __future__ import annotations


class AIJudgeProviderNotConfigured(Exception):
    """judge_candidates()를 실제로 호출하면 이 예외 — 아직 프로바이더가
    안 붙어 있다는 뜻(D-063, O-014, 틀만 구축 단계)."""


def judge_candidates(text: str, candidates: list[dict]) -> list[dict]:
    """원문 text + router_classifier.classify_content()가 이미 만든
    candidates를 실제 AI 판단에 넘겨 재순위/재점수화 — 아직 프로바이더
    미연결."""
    raise AIJudgeProviderNotConfigured(
        "AI 판단 API가 아직 연결되지 않았습니다(D-063 — 틀만 구축, O-014 "
        "참고). 실제로 쓰려면 프로바이더(Gemini/Claude API 등) 선택 + API 키 "
        "설정 + 오프라인 원칙을 깨는 것에 대한 명시적 승인이 먼저 필요합니다."
    )

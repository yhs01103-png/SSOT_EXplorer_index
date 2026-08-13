"""SSOT_Explorer 라우터 — 분류기 ("서버" 쪽 두뇌, 2026-08-13 D-029, 2026-08-13
다중신호 구조로 업그레이드 D-030).

새 문서/파일이 어느 등록 루트에 속하는지 후보를 순위매겨 제안한다.

**구조는 Lazzy_App_OS_Monorepo/server/core/orchestrators/user_info_indexer.py
에서 실제 코드로 확인 후 이식**(D-030, 2026-08-13) — 그쪽은 대화기억(user_
info) 인덱싱이라 도메인은 완전히 다르지만, "여러 개의 독립적인 신호를 각각
따로 구해서 id 기준으로 합집합(가중합 아님 — 신호 하나만 걸려도 채택)"하는
구조 자체는 도메인 무관하게 재사용 가능했다. 원본은 3신호(임베딩 유사도
top-K + 리터럴 키워드 매치 + 카테고리/서브카테고리 패턴 매치) — 여기서는
임베딩(신규 의존성+API 필요)만 빼고 2신호로 시작:
  신호1: 텍스트와 루트 label/scope/referenceCondition의 키워드 겹침
  신호2: 루트 scope 문구가 텍스트에 리터럴로 그대로 등장(카테고리 매치의
         축소판 — Lazzy의 category_patterns.json 서브카테고리 정규화매치와
         같은 발상, 다만 SSOT_Explorer는 카테고리 사전이 없어 scope 필드
         자체를 그 역할로 씀)
둘 중 하나만 걸려도 후보 채택(union) — 신호 2개 다 걸리면 더 위로.

"물어보기 원칙"(user_info_indexer.py 34~39행, 8단계 스펙 6단계)도 이식 —
매치가 없을 때 무조건 "후보 없음"으로 끝내지 않고, 텍스트 자체가 너무
짧거나 지시대명사 위주라 판단이 애초에 불가능해 보이면 needs_clarification()
로 구분해서 알려준다.

CLI 진입점(D-030) — 이게 이번 업그레이드의 핵심 동기: 분류 로직이 GUI
버튼 뒤에만 있으면 Claude Code가 세션 중에 "이 대화 내용 범용규칙으로
만들어줘" 같은 요청을 받아도 호출할 방법이 없었다. `python
router_classifier.py --text "..."`로 아무 세션에서나 직접 불러서 JSON으로
후보를 받을 수 있게 열었다 — GUI(SaveDocumentDialog)도 같은 함수를 내부적
으로 쓰므로 결과가 항상 일치한다.

나중에 Claude API 등으로 신호를 하나 더 얹어도(임베딩 유사도 등) 이
union 구조 자체는 안 바뀐다 — classify_content()의 반환 shape이 계약이다.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

_STOPWORD_LEN_MIN = 2  # 이보다 짧은 토큰(조사/1글자 등)은 노이즈로 버림
_REFERENCE_PRONOUNS = {
    "이거", "그거", "저거", "이것", "그것", "저것", "이런거", "그런거", "이걸", "그걸",
}


def tokenize(text: str) -> set[str]:
    """아주 단순한 토크나이저 — 영숫자+한글 연속 구간을 단어로 취급."""
    words = re.findall(r"[\w가-힣]+", (text or "").lower())
    return {w for w in words if len(w) >= _STOPWORD_LEN_MIN}


def needs_clarification(text: str) -> bool:
    """user_info_indexer.py의 "물어보기 원칙" 이식 — 후보가 하나도 없을 때
    무조건 "관련 없음"으로 단정하지 않고, 텍스트 자체가 짧거나 지시대명사
    위주라 애초에 판단 근거가 부족해 보이면 True. 호출부(GUI/CLI)가 이걸로
    "후보 없음(진짜 무관)" vs "정보 부족(되물어야 함)" 메시지를 구분한다."""
    words = tokenize(text)
    if not words:
        return False
    has_pronoun = bool(words & _REFERENCE_PRONOUNS)
    is_short = len(words) <= 3
    return has_pronoun or is_short


def _keyword_signal(text_words: set[str], root: dict) -> set[str] | None:
    """신호1 — label/referenceCondition과의 키워드 겹침. 안 걸리면 None.
    2026-08-13(D-030) 수정: scope는 여기 안 넣는다 — scope 필드는 신호2
    (scope 리터럴 매치) 전용으로 남겨야 두 신호가 진짜 독립적이다. 처음
    버전은 scope를 여기에도 같이 넣어서, scope가 매치되면 사실상 항상
    신호1도 같이 걸려버려(같은 haystack에서 나온 거니까) "union"이 무의미
    했던 걸 테스트 작성 중 발견하고 고쳤다."""
    haystack = " ".join([
        root.get("label", "") or "",
        root.get("referenceCondition", "") or "",
    ])
    overlap = text_words & tokenize(haystack)
    return overlap or None


def _scope_literal_signal(text_lower: str, root: dict) -> str | None:
    """신호2 — scope 문구가 텍스트에 리터럴로 그대로 등장. Lazzy의 카테고리/
    서브카테고리 패턴 매치(category_patterns.json 키워드가 질의 원문에
    그대로 있으면 채택)와 같은 발상 — 여기선 카테고리 사전 대신 이미 있는
    scope 필드를 그 자리에 쓴다."""
    scope = (root.get("scope") or "").strip()
    if scope and scope.lower() in text_lower:
        return scope
    return None


def classify_content(text: str, roots: list[dict]) -> list[dict]:
    """신호1(키워드겹침)과 신호2(scope리터럴매치)를 독립적으로 구해 합집합—
    하나만 걸려도 채택, 둘 다 걸리면 순위가 위로 간다. 점수 산정: 키워드
    겹침 비율이 기본, scope 신호가 단독으로만 걸렸을 때도 무시 못 할 최소
    점수(0.5)를 보장한다(그 신호 하나만으로도 "관련 있다"고 판단할 근거가
    되므로 — union 원칙).

    반환: [{rootLabel, rootPath, score, matchedKeywords, reason, signals}, ...]
    score 내림차순, 동점이면 signals 개수 많은 쪽이 위(신호 2개 다 걸린
    후보 우대). 이 shape은 계약 — 나중에 신호를 더 추가해도 유지."""
    text_words = tokenize(text)
    text_lower = (text or "").lower()
    if not text_words:
        return []

    candidates = []
    for r in roots:
        keyword_overlap = _keyword_signal(text_words, r)
        scope_hit = _scope_literal_signal(text_lower, r)
        if keyword_overlap is None and scope_hit is None:
            continue  # 두 신호 다 없으면 후보 제외

        signals = []
        reasons = []
        matched = sorted(keyword_overlap) if keyword_overlap else []
        score = len(matched) / len(text_words) if matched else 0.0

        if keyword_overlap:
            signals.append("키워드겹침")
            preview = ", ".join(matched[:5]) + ("..." if len(matched) > 5 else "")
            reasons.append(f"키워드 겹침 {len(matched)}개: {preview}")
        if scope_hit:
            signals.append("scope일치")
            reasons.append(f"scope 문구 '{scope_hit}'가 내용에 그대로 등장")
            score = max(score, 0.5)  # 신호 단독으로도 무시 못 할 최소 점수

        candidates.append({
            "rootLabel": r["label"],
            "rootPath": r["path"],
            "score": round(score, 3),
            "matchedKeywords": matched,
            "reason": " / ".join(reasons),
            "signals": signals,
        })

    candidates.sort(key=lambda c: (len(c["signals"]), c["score"]), reverse=True)
    return candidates


# --------------------------------------------------------------------- CLI
#
# D-030 — Claude Code(세션 중 저 자신)가 아무 프로젝트에서나 바로 이 분류
# 로직을 호출할 수 있게. GUI(SaveDocumentDialog)를 열 필요 없음.

def _default_registry_path() -> Path:
    return (
        Path.home() / "OneDrive" / "Desktop" / "SSOT" / "SSOT_Coding_File"
        / "flutter_App" / ".claude" / "ssot-roots.json"
    )


def _run_cli() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="텍스트가 어느 SSOT 등록 루트와 관련 있는지 분류 제안(JSON 출력)"
    )
    parser.add_argument("--text", required=True, help="분류할 내용. '-'면 stdin에서 읽음")
    parser.add_argument("--registry", default=None, help="ssot-roots.json 경로(생략 시 기본 위치)")
    args = parser.parse_args()

    text = sys.stdin.read() if args.text == "-" else args.text
    registry_path = Path(args.registry) if args.registry else _default_registry_path()

    try:
        data = json.loads(registry_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        return 1

    roots = data.get("roots", [])
    candidates = classify_content(text, roots)
    result = {
        "needsClarification": not candidates and needs_clarification(text),
        "candidates": candidates,
    }
    # ensure_ascii=True(기본값) — Windows에서 subprocess로 이 stdout을 읽는
    # 쪽(pytest, 또는 Claude Code의 Bash 도구)이 콘솔 코드페이지 때문에
    # UTF-8을 오독하는 사고를 겪은 적 있어서(이 프로젝트에서 반복된 패턴),
    # 사람이 읽는 용도가 아니라 기계가 파싱하는 용도라 \uXXXX 이스케이프로
    # 인코딩 문제 자체를 원천봉쇄한다.
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(_run_cli())

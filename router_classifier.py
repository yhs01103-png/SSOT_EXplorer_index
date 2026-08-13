"""SSOT_Explorer 라우터 — 분류기 ("서버" 쪽 두뇌, 2026-08-13 D-029, 2026-08-13
다중신호 구조로 업그레이드 D-030, 2026-08-14 IDF 가중치로 정밀도 개선 D-033).

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

**D-033(2026-08-14) — IDF 가중치, floor→additive 전환**: 실사용 중(D-032
오케스트레이터로 실제 질의를 돌려봄) "코드"/"프로젝트"/"규칙"처럼 거의
모든 루트 텍스트에 등장하는 흔한 단어가 걸리기만 하면 scope 신호가 무조건
`score = max(score, 0.5)`로 고정돼서, 서로 다른 루트 4개가 전부 정확히
0.5점 동점이 되는 문제가 실측으로 확인됐다(User: "정밀하게 할 수 있는
방법?"). 원인은 토크나이저가 아니라 "점수를 고정값으로 뭉개는 방식" —
IDF(역문서빈도, 여러 루트에 흔한 단어는 가중치를 낮추고 소수 루트에만
있는 특이 단어는 가중치를 높이는 표준 정보검색 기법)로 교체하고, floor
(고정값 보정)를 additive(더하는 보너스)로 바꿔서 얼마나 구체적으로
겹쳤는지가 점수에 그대로 반영되게 했다.

**D-034(2026-08-14) — kiwipiepy(한국어 형태소 분석기) 이식**: O-007에서
"아직 문제로 확인 안 된 걸 미리 안 고친다"고 보류해뒀던 걸 사용자가 직접
재요청해서 착수. 이전 정규식 토크나이저(`[\\w가-힣]+`)는 "프로젝트를"과
"프로젝트가"를 서로 다른 토큰으로 잡고, "내용을"/"정리해서"/"만들어줘"
같은 조사/어미 결합형을 통째로 하나의 불용어 항목으로 일일이 등록해야
했다. kiwipiepy는 형태소 단위로 쪼개서(명사/조사/어미/동사를 구분) 이
문제를 구조적으로 없앤다 — "내용을"→"내용"(NNG)+"을"(JKO)로 분리되니
_STOPWORDS엔 "내용"만 있으면 "내용을"/"내용은"/"내용이"도 자동으로 걸림.
명사류 태그(NNG/NNP/SL/SH/SN)만 신호로 남기고 조사/어미/동사(JKO/EC/VV
등)는 자동 제외 — "정리해서"/"만들어줘" 같은 동사 활용형 전체가 스톱워드
목록 없이도 자동으로 걸러진다. Lazzy_App_OS_Monorepo가 뉘앙스 톤 자동조절
(D-SERVER-063)에 실전 채택한 선례. 새 의존성(kiwipiepy) — 이미 로컬에
설치돼 있었지만, **미설치 환경에서도 안 죽게 정규식 폴백을 유지**한다
(import 실패 시 자동으로 예전 방식 사용).

**주의(실측)**: `Kiwi()` 최초 초기화가 ~1.4초, 첫 tokenize 호출까지 합쳐
~3초 걸린다(모델 로딩) — CLI는 매번 새 프로세스라 매 호출마다 이 비용을
낸다. 모듈 전역 싱글턴으로 한 프로세스 안에서는 한 번만 초기화(GUI는
계속 떠있는 한 프로세스라 최초 1회만 비용 지불).
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

try:
    from kiwipiepy import Kiwi
    _KIWIPIEPY_AVAILABLE = True
except ImportError:
    _KIWIPIEPY_AVAILABLE = False

_kiwi_instance = None  # 지연 싱글턴 — 실제 쓰일 때(첫 tokenize 호출)만 초기화


def _get_kiwi():
    global _kiwi_instance
    if _kiwi_instance is None:
        _kiwi_instance = Kiwi()
    return _kiwi_instance


# 명사류 태그만 신호로 취급 — NNG(일반명사)/NNP(고유명사)/SL(외국어)/
# SH(한자)/SN(숫자). NNB(의존명사: 것/수/때 등)와 NP(대명사)는 문법적
# 도구 단어라 제외, 동사/형용사/조사/어미(VV/VA/JKO/EC 등)도 당연히 제외.
_NOUN_TAGS = {"NNG", "NNP", "SL", "SH", "SN"}

_STOPWORD_LEN_MIN = 2  # 이보다 짧은 토큰(조사/1글자 등)은 노이즈로 버림
_REFERENCE_PRONOUNS = {
    "이거", "그거", "저거", "이것", "그것", "저것", "이런거", "그런거", "이걸", "그걸",
}
# D-033 도입, D-034에서 축소 — 동사 활용형 기반 항목(정리해서/만들어줘/
# 해줘/합니다/있습니다/됩니다/주세요/해주세요 등)은 kiwipiepy의 품사
# 필터링이 자동으로 걸러줘서 더 이상 개별 등록 불필요. 명사인데 주제와
# 무관한 메타 어휘만 남김.
_STOPWORDS = {
    "내용", "대화", "관련", "정리", "부탁", "요청", "필요", "그것", "이것", "저것",
}


def tokenize(text: str) -> set[str]:
    """D-034: kiwipiepy로 형태소 분석 후 명사류(_NOUN_TAGS)만 신호로 남긴다
    — 조사/어미/동사 활용은 자동으로 제외되고, "프로젝트를"/"프로젝트가"가
    같은 토큰 "프로젝트"로 합쳐진다. kiwipiepy가 없거나 분석 중 예외가
    나면 예전 정규식 방식으로 자동 폴백(이 모듈은 이 의존성 없이도 계속
    동작해야 함 — 선택적 의존성 원칙)."""
    text = (text or "").lower().strip()
    if not text:
        return set()
    if _KIWIPIEPY_AVAILABLE:
        try:
            tokens = _get_kiwi().tokenize(text)
            words = {t.form for t in tokens if t.tag in _NOUN_TAGS}
        except Exception:
            words = set(re.findall(r"[\w가-힣]+", text))
    else:
        words = set(re.findall(r"[\w가-힣]+", text))
    return {w for w in words if len(w) >= _STOPWORD_LEN_MIN and w not in _STOPWORDS}


def needs_clarification(text: str) -> bool:
    """user_info_indexer.py의 "물어보기 원칙" 이식 — 후보가 하나도 없을 때
    무조건 "관련 없음"으로 단정하지 않고, 텍스트 자체가 짧거나 지시대명사
    위주라 애초에 판단 근거가 부족해 보이면 True. 호출부(GUI/CLI)가 이걸로
    "후보 없음(진짜 무관)" vs "정보 부족(되물어야 함)" 메시지를 구분한다.

    D-034 수정: 대명사 감지는 tokenize()가 아니라 원문 리터럴 부분매치로
    한다 — kiwipiepy 도입 후 tokenize()가 명사류만 남기는데, "이거"/"그거"
    는 품사가 NP(대명사)라 애초에 tokenize() 결과에 안 남는다. tokenize()
    로만 판단하면 "이거" 같은 순수 대명사 입력이 words=빈 집합이 돼서
    `if not words: return False`에 걸려 정작 가장 전형적인 "애매한 요청"
    을 못 잡는 역설이 생겼다(실측으로 발견)."""
    text_lower = (text or "").lower()
    if not text_lower.strip():
        return False
    has_pronoun = any(p in text_lower for p in _REFERENCE_PRONOUNS)
    words = tokenize(text)
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


def compute_idf(corpora: dict[str, str]) -> dict[str, float]:
    """D-033 — corpora: {문서id: 텍스트}. 각 토큰이 몇 개 문서(document
    frequency)에 등장하는지로 역문서빈도를 계산한다 — 정보검색의 표준
    TF-IDF 기법. 여러 문서(=여러 루트)에 흔하게 나오는 단어("코드"/
    "프로젝트"/"규칙" 같은 일반 개발 어휘)는 낮은 가중치, 소수 문서에만
    나오는 특이 단어는 높은 가중치를 받는다. 스무딩(+1)을 적용해서 흔한
    단어도 완전히 0이 되진 않는다(여전히 약한 신호로는 남음)."""
    doc_count = max(len(corpora), 1)
    df: dict[str, int] = {}
    for text in corpora.values():
        for token in tokenize(text):
            df[token] = df.get(token, 0) + 1
    return {token: math.log((doc_count + 1) / (freq + 1)) + 1 for token, freq in df.items()}


def _weighted_overlap_score(matched: set[str], text_words: set[str], idf: dict[str, float]) -> float:
    """겹친 단어들의 IDF 합 / 질의 전체 단어의 IDF 합 — "질의 중 얼마나
    의미있게(흔하지 않은 단어 위주로) 겹쳤는지" 비율. idf에 없는 토큰은
    기본 가중치 1.0(중립) — compute_idf에 안 쓰인 corpus 밖 단어일 수
    있어서 0 취급하면 부당하게 불리해짐."""
    if not text_words:
        return 0.0
    total = sum(idf.get(w, 1.0) for w in text_words)
    if total <= 0:
        return 0.0
    matched_weight = sum(idf.get(w, 1.0) for w in matched)
    return matched_weight / total


SCOPE_MATCH_BONUS = 0.3  # D-033: floor(고정값) 대신 additive(더하기) — 키워드 점수를 안 뭉갬


def classify_content(text: str, roots: list[dict], idf: dict[str, float] | None = None) -> list[dict]:
    """신호1(키워드겹침)과 신호2(scope리터럴매치)를 독립적으로 구해 합집합—
    하나만 걸려도 채택, 둘 다 걸리면 순위가 위로 간다.

    D-033 점수 산정: 키워드 겹침은 IDF 가중 비율(_weighted_overlap_score),
    scope 신호는 그 위에 SCOPE_MATCH_BONUS를 **더한다**(예전엔 max()로
    고정값 0.5를 강제해서, "코드"/"규칙"처럼 거의 모든 루트에 있는 흔한
    단어만 걸려도 서로 다른 루트들이 전부 똑같이 0.5점 동점이 되는 문제가
    실측(D-032)으로 확인됐다 — floor는 이미 있는 키워드 점수의 차등을
    뭉개버리지만 additive는 안 뭉갠다).

    idf 생략 시 이 roots의 label+referenceCondition만으로 자체 계산
    (standalone 사용 시 기본값). router_orchestrator는 README까지 합친
    더 풍부한 corpus로 계산한 idf를 넘겨서 구조화 신호와 프로즈 신호가
    일관된 가중치 기준을 쓰게 한다.

    반환: [{rootLabel, rootPath, score, matchedKeywords, reason, signals}, ...]
    score 내림차순, 동점이면 signals 개수 많은 쪽이 위(신호 2개 다 걸린
    후보 우대). 이 shape은 계약 — 나중에 신호를 더 추가해도 유지."""
    text_words = tokenize(text)
    text_lower = (text or "").lower()
    if not text_words:
        return []

    if idf is None:
        corpora = {
            r["label"]: " ".join([r.get("label", "") or "", r.get("referenceCondition", "") or ""])
            for r in roots
        }
        idf = compute_idf(corpora)

    candidates = []
    for r in roots:
        keyword_overlap = _keyword_signal(text_words, r)
        scope_hit = _scope_literal_signal(text_lower, r)
        if keyword_overlap is None and scope_hit is None:
            continue  # 두 신호 다 없으면 후보 제외

        signals = []
        reasons = []
        matched = sorted(keyword_overlap) if keyword_overlap else []
        score = _weighted_overlap_score(set(matched), text_words, idf) if matched else 0.0

        if keyword_overlap:
            signals.append("키워드겹침")
            preview = ", ".join(matched[:5]) + ("..." if len(matched) > 5 else "")
            reasons.append(f"키워드 겹침(IDF가중) {len(matched)}개: {preview}")
        if scope_hit:
            signals.append("scope일치")
            reasons.append(f"scope 문구 '{scope_hit}'가 내용에 그대로 등장")
            score += SCOPE_MATCH_BONUS

        candidates.append({
            "rootLabel": r["label"],
            "rootPath": r["path"],
            "score": round(min(score, 1.0), 3),
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

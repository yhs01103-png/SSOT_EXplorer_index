"""router_classifier.py 전용 테스트 — D-029, D-030(다중신호+CLI 업그레이드).
모듈이 Qt를 안 쓰는 순수 함수라 test_main.py의 qapp 픽스처 없이도 독립적
으로 돈다."""
from __future__ import annotations

import json
import subprocess
import sys

import pytest

import router_classifier as rc


def test_weighted_overlap_score_is_public_contract():
    """D-043(code-review 발견) — router_orchestrator.py가 이미 이 함수를
    직접 가져다 쓰고 있어서 언더스코어 프리픽스(내부 전용 표시)가 실제
    계약과 안 맞았음 — 공개 이름으로 승격됐다는 걸 잠가둠."""
    idf = {"흔한": 0.5, "특이한": 3.0}
    score = rc.weighted_overlap_score({"특이한"}, {"흔한", "특이한"}, idf)
    assert 0.0 < score <= 1.0


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
#
# D-034: 아래 테스트들은 실제 국어사전 단어만 쓴다 — kiwipiepy는 사전에
# 없는 조어("특이어" 등)를 문맥에 따라 다르게 쪼개서(형태소 분석기 특성상
# 미등록어 처리가 확률적), 예전에 임의로 지어낸 복합어 픽스처가 깨진 걸
# 발견하고 전부 실제 단어로 교체(D-034).

def test_compute_idf_downweights_terms_common_across_roots():
    """"코드"가 모든 문서에 나오고 "특이"는 하나에만 나오면, 후자가 훨씬
    높은 가중치를 받아야 한다 — IDF의 핵심 성질."""
    corpora = {
        "a": "코드 프로젝트 규칙",
        "b": "코드 프로젝트 문서",
        "c": "코드 특이 사항",
    }
    idf = rc.compute_idf(corpora)
    assert idf["특이"] > idf["코드"]


def test_classify_content_idf_differentiates_generic_vs_specific_match():
    """D-032 실측 문제의 재현+회귀 테스트 — "코드"/"프로젝트"/"규칙"처럼
    거의 모든 루트에 흔한 단어만 걸린 루트보다, 그 단어들에 더해 특이
    단어까지 겹친 루트가 확실히 더 높은 점수를 받아야 한다(예전엔 둘 다
    scope 신호면 강제로 0.5 동점이었음)."""
    roots = [
        {"label": "generic_only", "path": "C:\\g", "scope": "", "referenceCondition": "코드 프로젝트 규칙 문서"},
        {"label": "generic_plus_specific", "path": "C:\\gs", "scope": "", "referenceCondition": "코드 프로젝트 규칙 문서 범용 모음집"},
        {"label": "unrelated", "path": "C:\\u", "scope": "", "referenceCondition": "고양이 강아지 물고기 이야기"},
    ]
    text = "코드 프로젝트 규칙 문서 범용 모음집 작업"
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


# ------------------------------------------ D-063/D-065: 단어 역할 태깅(O-007/008)
#
# 실측(kiwipiepy 직접 실행, 2026-08-19) 기반 — "말고"는 VV"말"+EC"고",
# "아니라"는 VCN"아니"+EC"라"로 쪼개진다는 걸 먼저 확인하고 작성됨. 이
# 실측 없이 리터럴 문자열 매치로 짰으면 조용히 아무 효과가 없었을
# 케이스라, 여기 회귀 테스트로 그 실제 토큰 분해 형태를 잠가둔다.
#
# D-065: role은 단어 문자열이 아니라 label_role(tokens, root)로 루트별
# 위치 기준으로 판정한다(O-015 수정) — 아래 테스트는 그 API로 작성됨.

def _label_role_for(text: str, label: str) -> str:
    tokens = rc._kiwi_tokens(text)
    return rc.label_role(tokens, {"label": label})


def test_label_role_destination_particle_marks_target():
    assert _label_role_for("이건 coding_nomal에 넣어야지", "coding_nomal") == "target"


def test_label_role_malgo_contrastive_splits_mention_and_target():
    text = "flutter_app 말고 coding_nomal에 저장해줘"
    assert _label_role_for(text, "flutter_app") == "mention"
    assert _label_role_for(text, "coding_nomal") == "target"


def test_label_role_anira_contrastive_splits_mention_and_target():
    text = "flutter_app 아니라 coding_nomal에 넣어"
    assert _label_role_for(text, "flutter_app") == "mention"
    assert _label_role_for(text, "coding_nomal") == "target"


def test_label_role_no_pattern_is_neutral():
    assert _label_role_for("flutter_app 관련 메모", "flutter_app") == "neutral"


def test_label_role_label_not_in_text_is_neutral():
    assert _label_role_for("전혀 다른 내용", "flutter_app") == "neutral"


def test_label_role_shared_subtoken_does_not_bleed_across_labels():
    """D-065 회귀 테스트 — O-015 그 자체. "flutter_App"과 "Local_APP"이
    "app" 조각을 공유해도, 실제로 "에" 조사 옆에 있는 local_app만 target이고
    배경 언급인 flutter_app은 neutral이어야 한다(예전 버그는 둘 다 target
    이었음 — 문자열이 같다는 이유만으로)."""
    text = "flutter_app 얘기하다 나온건데 이건 coding_nomal 말고 local_app에 넣어야지"
    assert _label_role_for(text, "flutter_app") == "neutral"
    assert _label_role_for(text, "coding_nomal") == "mention"
    assert _label_role_for(text, "local_app") == "target"


def test_classify_content_mention_penalty_beats_target_bonus_ranking():
    """O-007 재현 시나리오 — "flutter_app 말고 coding_nomal에 저장" 같은
    문장에서, 문자열만 겹치는 flutter_App보다 실제 목적지로 지목된
    Coding_Nomal이 위로 와야 한다."""
    roots = [
        {"label": "flutter_App", "path": "C:\\f", "scope": "", "referenceCondition": "flutter app 개발"},
        {"label": "coding_nomal", "path": "C:\\c", "scope": "", "referenceCondition": "coding nomal 규칙"},
    ]
    text = "flutter_app 말고 coding_nomal에 저장해줘"
    results = rc.classify_content(text, roots)
    by_label = {c["rootLabel"]: c for c in results}
    assert by_label["coding_nomal"]["score"] > by_label["flutter_App"]["score"]
    assert by_label["coding_nomal"]["matchedKeywordRoles"].get("nomal") == "target"
    assert by_label["flutter_App"]["matchedKeywordRoles"].get("app") == "mention"


def test_classify_content_shared_subtoken_labels_ranked_correctly():
    """D-065 — classify_content() 레벨에서도 O-015가 실제로 고쳐졌는지
    확인. "app"을 공유하는 두 루트(flutter_App/Local_APP) 중 진짜 목적지
    (Local_APP, "에" 조사 옆)만 가점을 받아야 한다."""
    roots = [
        {"label": "flutter_App", "path": "C:\\f", "scope": "", "referenceCondition": "flutter app 개발"},
        {"label": "coding_nomal", "path": "C:\\c", "scope": "", "referenceCondition": "coding nomal 규칙"},
        {"label": "local_app", "path": "C:\\l", "scope": "", "referenceCondition": "local app 자료"},
    ]
    text = "flutter_app 얘기하다 나온건데 이건 coding_nomal 말고 local_app에 넣어야지"
    results = rc.classify_content(text, roots)
    by_label = {c["rootLabel"]: c for c in results}
    assert by_label["local_app"]["matchedKeywordRoles"].get("app") == "target"
    assert by_label["flutter_App"]["matchedKeywordRoles"].get("app") == "neutral"
    assert by_label["local_app"]["score"] > by_label["flutter_App"]["score"]


def test_classify_content_cli_output_includes_matched_keyword_roles(tmp_path):
    """D-063 신규 필드가 CLI JSON 출력에도 실려나가는지(shape 계약 확인)."""
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
    payload = json.loads(result.stdout)
    assert "matchedKeywordRoles" in payload["candidates"][0]


def test_cli_registry_load_error_returns_json_error_ascii_safe(tmp_path):
    """D-053(H-010) — _cli_common() 통합 과정에서 에러 출력의 ensure_ascii
    불일치(예전엔 에러만 False, 성공 출력은 기본값 True)를 같이 잡았다 —
    레지스트리 파일이 없을 때도 성공 출력과 동일하게 순수 ASCII(\\uXXXX
    이스케이프)로만 나가는지 잠가둔다(한글이 원문 그대로 섞여 나오면
    회귀)."""
    missing_registry = tmp_path / "does-not-exist.json"

    result = subprocess.run(
        [sys.executable, rc.__file__, "--text", "아무 내용", "--registry", str(missing_registry)],
        capture_output=True, text=True, encoding="utf-8", timeout=15,
    )
    assert result.returncode == 1
    assert result.stdout.strip().isascii()
    payload = json.loads(result.stdout)
    assert "error" in payload

"""router_orchestrator.py 전용 테스트 — D-032. router_proposals.py처럼
PROPOSALS_LOG_PATH/TRUST_STATE_PATH를 격리해야 신뢰폐루프 주석 단계가
실제 사용자 데이터를 안 건드린다."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta

import pytest

import router_embeddings as re_
import router_keyword_registry as kr
import router_orchestrator as ro
import router_proposals as rp


@pytest.fixture(autouse=True)
def isolated_router_state(tmp_path, monkeypatch):
    monkeypatch.setattr(rp, "PROPOSALS_LOG_PATH", tmp_path / "proposals.json")
    monkeypatch.setattr(rp, "TRUST_STATE_PATH", tmp_path / "trust.json")
    # D-044 — orchestrate()가 이제 키워드 레지스트리도 매 실행마다 건드림
    # (record_keyword_hits/try_promote/sweep) — 기본 경로를 그대로 두면
    # keyword_registry_path를 명시 안 하는 기존 테스트들이 실제 사용자
    # 파일(~/.claude/scripts/ssot_keyword_registry.json)을 건드리게 된다.
    monkeypatch.setattr(kr, "KEYWORD_REGISTRY_PATH", tmp_path / "keywords.json")
    # D-067 — embed_query_text가 이제 진짜 로컬 모델을 돈다(fastembed).
    # 이 파일의 테스트들은 orchestrator가 semantic 단계를 "제대로 호출하고
    # 결과를 기록하는지"만 검증하면 되지, 매번 수백MB 모델을 실제로 띄울
    # 필요는 없다(D-024 결정적/빠른 테스트 원칙) — 기본값은 예전과 같은
    # "미연결" 경로로 되돌려두고, 실제 연결 시 동작만 별도 테스트에서
    # 명시적으로 확인한다.
    monkeypatch.setattr(
        re_,
        "embed_query_text",
        lambda text: (_ for _ in ()).throw(re_.EmbeddingProviderNotConfigured("test stub")),
    )
    yield


# --------------------------------------------------------------- _find_readme

def test_find_readme_flat_location(tmp_path):
    (tmp_path / "README.md").write_text("내용", encoding="utf-8")
    assert ro._find_readme(tmp_path) == tmp_path / "README.md"


def test_find_readme_dot_claude_location(tmp_path):
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    (claude_dir / "README.md").write_text("내용", encoding="utf-8")
    assert ro._find_readme(tmp_path) == claude_dir / "README.md"


def test_find_readme_missing_returns_none(tmp_path):
    assert ro._find_readme(tmp_path) is None


# --------------------------------------------------------- orchestrate 병합

def test_orchestrate_merges_structured_and_prose_only_candidates(tmp_path):
    """referenceCondition을 씀 — scope는 D-030 수정으로 "키워드겹침"이
    아니라 "scope일치" 신호를 낸다(router_classifier._keyword_signal이
    scope를 안 봄), 구조화 키워드겹침 신호를 확실히 내려면 referenceCondition.
    D-034: 실제 국어사전 단어("보안")만 씀 — kiwipiepy가 미등록 조어를
    문맥별로 다르게 쪼개서 예전 임의 복합어 픽스처가 깨진 걸 발견하고 교체."""
    prose_only_dir = tmp_path / "prose_only"
    prose_only_dir.mkdir()
    (prose_only_dir / "README.md").write_text("보안 정책 안내", encoding="utf-8")

    structured_only_dir = tmp_path / "structured_only"
    structured_only_dir.mkdir()

    roots = [
        {"label": "prose_only", "path": str(prose_only_dir), "scope": "", "referenceCondition": ""},
        {"label": "structured_only", "path": str(structured_only_dir), "scope": "", "referenceCondition": "보안 정책"},
    ]
    result = ro.orchestrate("보안 정책 문서", roots, log_path=tmp_path / "log.json")
    labels = {c["rootLabel"] for c in result["candidates"]}
    assert labels == {"prose_only", "structured_only"}

    by_label = {c["rootLabel"]: c for c in result["candidates"]}
    assert "프로즈검색" in by_label["prose_only"]["signals"]
    assert "키워드겹침" not in by_label["prose_only"]["signals"]
    assert "키워드겹침" in by_label["structured_only"]["signals"]


def test_orchestrate_combines_signals_for_same_root(tmp_path):
    root_dir = tmp_path / "both"
    root_dir.mkdir()
    (root_dir / "README.md").write_text("보안 정책 안내문", encoding="utf-8")

    roots = [{"label": "both", "path": str(root_dir), "scope": "", "referenceCondition": "보안 정책"}]
    result = ro.orchestrate("보안 정책 문서", roots, log_path=tmp_path / "log.json")
    assert len(result["candidates"]) == 1
    cand = result["candidates"][0]
    assert set(cand["signals"]) == {"키워드겹침", "프로즈검색"}


def test_orchestrate_reports_six_steps(tmp_path):
    """D-044 — 키워드 레지스트리(3.5단계)+시맨틱 스켈레톤(4단계) 추가로
    3단계였던 파이프라인이 5단계가 됨. D-063 — AI 판단 스켈레톤(4.5단계)
    추가로 6단계가 됨. semantic 단계는 D-067로 실제 연결됐지만, 이 파일의
    autouse 픽스처(isolated_router_state)가 기본적으로 "미연결" 경로로
    되돌려두므로 아래는 여전히 그 폴백 계약을 검증한다 — "연결됨" 경로는
    test_orchestrate_semantic_stage_runs_when_provider_available 참고."""
    roots = [{"label": "x", "path": str(tmp_path), "scope": "", "referenceCondition": ""}]
    result = ro.orchestrate("아무 내용", roots, log_path=tmp_path / "log.json")
    stage_names = [s["stage"] for s in result["steps"]]
    assert stage_names == [
        "structured", "prose_scan", "keyword_registry", "semantic", "ai_judgment", "trust_annotation",
    ]
    semantic_step = next(s for s in result["steps"] if s["stage"] == "semantic")
    assert semantic_step["skipped"] is True  # 임베딩 프로바이더 미연결 스텁(테스트 격리)
    ai_step = next(s for s in result["steps"] if s["stage"] == "ai_judgment")
    assert ai_step["skipped"] is True  # AI 판단 프로바이더 미연결(D-063, O-014)


def test_orchestrate_reports_elapsed_ms_per_stage_and_total(tmp_path):
    """2026-08-23(D-076) — 개발자 탭 벤치마크 뷰용 스테이지별 소요시간.
    실제 값은 머신마다 다르므로 "0 이상 숫자로 존재하는지"만 검증하고,
    totalElapsedMs가 각 스테이지 합과 일치하는지로 집계 로직을 확인한다."""
    roots = [{"label": "x", "path": str(tmp_path), "scope": "", "referenceCondition": ""}]
    result = ro.orchestrate("아무 내용", roots, log_path=tmp_path / "log.json")
    for step in result["steps"]:
        assert isinstance(step["elapsedMs"], (int, float))
        assert step["elapsedMs"] >= 0
    assert result["totalElapsedMs"] == round(sum(s["elapsedMs"] for s in result["steps"]), 2)


def test_orchestrate_semantic_stage_runs_when_provider_available(tmp_path, monkeypatch):
    """D-067 — 임베딩 프로바이더가 실제로 연결돼 있으면 semantic 단계가
    skipped=False로 기록돼야 한다. 이 테스트의 roots는 구조화/scope 신호가
    전혀 안 걸려 merged가 비어있으므로(label "x", referenceCondition ""),
    D-092(O-016 A안) 도입 후에도 embed_text 호출 없이(아래 별도 테스트가
    이 부분을 명시적으로 검증) skipped=False만 그대로 유지된다."""
    monkeypatch.setattr(re_, "embed_query_text", lambda text: [0.1, 0.2, 0.3])
    roots = [{"label": "x", "path": str(tmp_path), "scope": "", "referenceCondition": ""}]
    result = ro.orchestrate("아무 내용", roots, log_path=tmp_path / "log.json")
    semantic_step = next(s for s in result["steps"] if s["stage"] == "semantic")
    assert semantic_step["skipped"] is False
    assert semantic_step["boostedCount"] == 0


# ------------------------------------------------- D-092: O-016 A안(시맨틱 가점)

def test_orchestrate_semantic_boosts_existing_candidate_score(tmp_path, monkeypatch):
    """O-016 A안 — 이미 keyword/scope 신호로 merged에 오른 후보만 유사도로
    additive 가점을 받는다(D-033 원칙과 동일 모양). 벡터를 [1,0]으로 고정해
    코사인 유사도를 1.0으로 결정적으로 만든다."""
    monkeypatch.setattr(re_, "embed_query_text", lambda text: [1.0, 0.0])
    monkeypatch.setattr(re_, "embed_text", lambda text: [1.0, 0.0])
    root_dir = tmp_path / "root"
    root_dir.mkdir()
    roots = [{"label": "root", "path": str(root_dir), "scope": "특수키워드", "referenceCondition": ""}]

    result = ro.orchestrate("특수키워드 내용", roots, log_path=tmp_path / "log.json")
    cand = result["candidates"][0]
    assert "시맨틱매치" in cand["signals"]
    # scope일치 단독 점수(0.3, SCOPE_MATCH_BONUS) + EMBEDDING_MATCH_BONUS(0.2)*유사도(1.0)
    assert cand["score"] == pytest.approx(0.3 + ro.EMBEDDING_MATCH_BONUS, abs=0.001)
    semantic_step = next(s for s in result["steps"] if s["stage"] == "semantic")
    assert semantic_step["boostedCount"] == 1


def test_orchestrate_semantic_skips_boost_below_min_similarity(tmp_path, monkeypatch):
    """유사도가 DEFAULT_MIN_SIMILARITY 미만이면 가점도, "시맨틱매치" 신호도
    안 붙는다 — 직교 벡터([1,0] vs [0,1])로 유사도 0.0을 만든다."""
    monkeypatch.setattr(re_, "embed_query_text", lambda text: [1.0, 0.0])
    monkeypatch.setattr(re_, "embed_text", lambda text: [0.0, 1.0])
    root_dir = tmp_path / "root"
    root_dir.mkdir()
    roots = [{"label": "root", "path": str(root_dir), "scope": "특수키워드", "referenceCondition": ""}]

    result = ro.orchestrate("특수키워드 내용", roots, log_path=tmp_path / "log.json")
    cand = result["candidates"][0]
    assert "시맨틱매치" not in cand["signals"]
    assert cand["score"] == pytest.approx(0.3, abs=0.001)
    semantic_step = next(s for s in result["steps"] if s["stage"] == "semantic")
    assert semantic_step["boostedCount"] == 0


def test_orchestrate_semantic_does_not_embed_when_no_candidates(tmp_path, monkeypatch):
    """O-016 A안의 핵심 범위 제한 — keyword/scope 신호가 전혀 없어 merged가
    비어있으면 embed_text가 아예 호출되지 않는다(루트 전체를 매번 임베딩하는
    B안과 다르게 비용이 자연히 낮다는 설계 근거를 직접 검증). embed_text가
    호출되면 즉시 실패하는 스파이를 심는다."""
    monkeypatch.setattr(re_, "embed_query_text", lambda text: [1.0, 0.0])

    def _fail_if_called(text):
        raise AssertionError("merged에 없는 후보까지 embed_text를 호출하면 안 됨(O-016 A안 범위 밖)")

    monkeypatch.setattr(re_, "embed_text", _fail_if_called)
    root_dir = tmp_path / "root"
    root_dir.mkdir()
    roots = [{"label": "root", "path": str(root_dir), "scope": "", "referenceCondition": ""}]

    result = ro.orchestrate("전혀 무관한 질의", roots, log_path=tmp_path / "log.json")
    assert result["candidates"] == []


# -------------------------------------------------- D-044: 키워드 레지스트리

def test_orchestrate_records_matched_keywords_as_candidates(tmp_path):
    root_dir = tmp_path / "root"
    root_dir.mkdir()
    roots = [{"label": "root", "path": str(root_dir), "scope": "", "referenceCondition": "보안 정책"}]
    kw_path = tmp_path / "keywords.json"

    ro.orchestrate("보안 정책 문서", roots, log_path=tmp_path / "log.json", keyword_registry_path=kw_path)
    registry = kr.load_keyword_registry(kw_path)
    assert registry["보안"]["status"] == "candidate"
    assert registry["정책"]["status"] == "candidate"


def test_orchestrate_promotes_keyword_and_applies_score_bonus(tmp_path):
    """관측 임계값(hitCount/기간)을 이미 채운 candidate가 있으면, 이번
    실행에서 바로 active로 승급되고 그 실행 자체의 점수에도 보너스가
    붙는다(Lazzy 원본과 동일 — record 직후 바로 promote 체크)."""
    root_dir = tmp_path / "root"
    root_dir.mkdir()
    roots = [{"label": "root", "path": str(root_dir), "scope": "", "referenceCondition": "보안 정책"}]
    kw_path = tmp_path / "keywords.json"

    now = datetime.now()
    seeded = {
        "보안": {
            "status": "candidate",
            "hitCount": kr.PROMOTION_HIT_THRESHOLD - 1,  # 이번 관측 한 번 더하면 임계 도달
            "firstSeenAt": (now - timedelta(days=kr.PROMOTION_MIN_SPAN_DAYS)).strftime("%Y-%m-%d %H:%M:%S"),
            "lastSeenAt": (now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"),
        }
    }
    kr._save(seeded, kw_path)

    result = ro.orchestrate("보안 정책 문서", roots, log_path=tmp_path / "log.json", keyword_registry_path=kw_path)
    kw_step = next(s for s in result["steps"] if s["stage"] == "keyword_registry")
    assert kw_step["promotedCount"] == 1
    assert kw_step["bonusAppliedCount"] == 1
    cand = result["candidates"][0]
    assert "활성키워드" in cand["signals"]
    assert kr.load_keyword_registry(kw_path)["보안"]["status"] == "active"


def test_orchestrate_no_candidates_reports_needs_clarification(tmp_path):
    result = ro.orchestrate("이거", [], log_path=tmp_path / "log.json")
    assert result["candidates"] == []
    assert result["needsClarification"] is True


# --------------------------------------------------------- 신뢰 폐루프

def test_orchestrate_annotates_trusted_candidate(tmp_path):
    root_dir = tmp_path / "trusted_root"
    root_dir.mkdir()
    roots = [{"label": "trusted_root", "path": str(root_dir), "scope": "특수키워드", "referenceCondition": ""}]

    candidate = {"rootLabel": "trusted_root", "rootPath": str(root_dir), "score": 0.5, "reason": "테스트"}
    for _ in range(rp.TRUST_PROMOTION_STREAK):
        rp.record_decision(candidate, "x", "approved")

    result = ro.orchestrate("특수키워드 관련 내용", roots, log_path=tmp_path / "log.json")
    assert result["candidates"][0]["trusted"] is True
    assert result["candidates"][0]["acceptanceRate"] == 1.0


def test_orchestrate_untrusted_candidate_shows_false(tmp_path):
    root_dir = tmp_path / "x"
    root_dir.mkdir()
    roots = [{"label": "x", "path": str(root_dir), "scope": "특수키워드", "referenceCondition": ""}]
    result = ro.orchestrate("특수키워드 관련 내용", roots, log_path=tmp_path / "log.json")
    assert result["candidates"][0]["trusted"] is False
    assert result["candidates"][0]["acceptanceRate"] is None


# --------------------------------------------------- D-094: 신뢰 점수 가점(결정 번복)

def test_orchestrate_trust_bonus_applies_to_trusted_candidate_score(tmp_path):
    """D-094 — trusted면 SCOPE_MATCH_BONUS(0.3) 위에 TRUST_MATCH_BONUS(0.1)가
    additive로 더해진다(다른 신호와 동일 모양) — 예전엔 참고 정보로만 붙고
    점수는 그대로였음."""
    root_dir = tmp_path / "trusted_root"
    root_dir.mkdir()
    roots = [{"label": "trusted_root", "path": str(root_dir), "scope": "특수키워드", "referenceCondition": ""}]
    candidate = {"rootLabel": "trusted_root", "rootPath": str(root_dir), "score": 0.5, "reason": "테스트"}
    for _ in range(rp.TRUST_PROMOTION_STREAK):
        rp.record_decision(candidate, "x", "approved")

    result = ro.orchestrate("특수키워드 관련 내용", roots, log_path=tmp_path / "log.json")
    cand = result["candidates"][0]
    assert cand["score"] == pytest.approx(0.3 + rp.TRUST_MATCH_BONUS, abs=0.001)
    assert "신뢰보너스" in cand["signals"]
    trust_step = next(s for s in result["steps"] if s["stage"] == "trust_annotation")
    assert trust_step["bonusAppliedCount"] == 1


def test_orchestrate_trust_bonus_does_not_add_new_candidates(tmp_path):
    """D-094 — 다른 additive 신호와 동일 원칙: keyword/scope/prose 신호로
    merged에 오른 후보가 하나도 없으면(이 요청과 겹치는 게 전혀 없으면)
    trusted 이력이 있어도 신규 후보를 만들지 않는다."""
    root_dir = tmp_path / "trusted_root"
    root_dir.mkdir()
    roots = [{"label": "trusted_root", "path": str(root_dir), "scope": "", "referenceCondition": ""}]
    candidate = {"rootLabel": "trusted_root", "rootPath": str(root_dir), "score": 0.5, "reason": "테스트"}
    for _ in range(rp.TRUST_PROMOTION_STREAK):
        rp.record_decision(candidate, "x", "approved")

    result = ro.orchestrate("전혀 무관한 질의", roots, log_path=tmp_path / "log.json")
    assert result["candidates"] == []


def test_orchestrate_untrusted_candidate_gets_no_bonus(tmp_path):
    root_dir = tmp_path / "x"
    root_dir.mkdir()
    roots = [{"label": "x", "path": str(root_dir), "scope": "특수키워드", "referenceCondition": ""}]
    result = ro.orchestrate("특수키워드 관련 내용", roots, log_path=tmp_path / "log.json")
    cand = result["candidates"][0]
    assert cand["score"] == pytest.approx(0.3, abs=0.001)  # SCOPE_MATCH_BONUS만, 신뢰 가점 없음
    assert "신뢰보너스" not in cand["signals"]
    trust_step = next(s for s in result["steps"] if s["stage"] == "trust_annotation")
    assert trust_step["bonusAppliedCount"] == 0


# --------------------------------------------------------------------- 로깅

def test_orchestrate_logs_run(tmp_path):
    log_path = tmp_path / "log.json"
    roots = [{"label": "x", "path": str(tmp_path), "scope": "특수키워드", "referenceCondition": ""}]
    ro.orchestrate("특수키워드 내용", roots, log_path=log_path)
    runs = ro.load_orchestration_log(log_path)
    assert len(runs) == 1
    assert runs[0]["candidateCount"] == 1
    assert runs[0]["topCandidate"]["rootLabel"] == "x"
    assert len(runs[0]["steps"]) == 6  # D-063 — 6단계 파이프라인


def test_orchestrate_logs_accumulate_across_runs(tmp_path):
    log_path = tmp_path / "log.json"
    roots = [{"label": "x", "path": str(tmp_path), "scope": "특수키워드", "referenceCondition": ""}]
    ro.orchestrate("특수키워드 1", roots, log_path=log_path)
    ro.orchestrate("특수키워드 2", roots, log_path=log_path)
    runs = ro.load_orchestration_log(log_path)
    assert len(runs) == 2
    assert [r["id"] for r in runs] == [1, 2]


def test_load_orchestration_log_missing_file_returns_empty(tmp_path):
    assert ro.load_orchestration_log(tmp_path / "does-not-exist.json") == []


def test_orchestrate_log_leaves_no_tmp_file(tmp_path):
    log_path = tmp_path / "log.json"
    roots = [{"label": "x", "path": str(tmp_path), "scope": "특수키워드", "referenceCondition": ""}]
    ro.orchestrate("특수키워드 내용", roots, log_path=log_path)
    leftovers = list(log_path.parent.glob(log_path.name + ".tmp*"))
    assert leftovers == []


# --------------------------------------------------------------------- CLI

def test_cli_end_to_end(tmp_path):
    root_dir = tmp_path / "flutter_App"
    root_dir.mkdir()
    (root_dir / "README.md").write_text("플러터 앱 개발 안내", encoding="utf-8")
    registry = tmp_path / "ssot-roots.json"
    registry.write_text(json.dumps({
        "roots": [{"label": "flutter_App", "path": str(root_dir), "scope": "플러터 앱 개발", "referenceCondition": ""}],
    }), encoding="utf-8")
    log_path = tmp_path / "log.json"
    keyword_registry_path = tmp_path / "keywords.json"  # 서브프로세스라 monkeypatch가 안 먹음 — CLI 플래그로 격리

    result = subprocess.run(
        [
            sys.executable, ro.__file__,
            "--text", "플러터 앱 개발 메모",
            "--registry", str(registry),
            "--log-path", str(log_path),
            "--keyword-registry-path", str(keyword_registry_path),
        ],
        capture_output=True, text=True, encoding="utf-8", timeout=15,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["candidates"][0]["rootLabel"] == "flutter_App"
    assert len(payload["steps"]) == 6  # D-063 — 6단계 파이프라인
    assert keyword_registry_path.exists()  # --keyword-registry-path가 실제로 거기에 씀
    assert log_path.exists()  # --log-path로 지정한 파일에 기록됐는지(실제 사용자 로그 안 건드림)

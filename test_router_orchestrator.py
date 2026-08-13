"""router_orchestrator.py 전용 테스트 — D-032. router_proposals.py처럼
PROPOSALS_LOG_PATH/TRUST_STATE_PATH를 격리해야 신뢰폐루프 주석 단계가
실제 사용자 데이터를 안 건드린다."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

import router_orchestrator as ro
import router_proposals as rp


@pytest.fixture(autouse=True)
def isolated_router_state(tmp_path, monkeypatch):
    monkeypatch.setattr(rp, "PROPOSALS_LOG_PATH", tmp_path / "proposals.json")
    monkeypatch.setattr(rp, "TRUST_STATE_PATH", tmp_path / "trust.json")
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


def test_orchestrate_reports_three_steps(tmp_path):
    roots = [{"label": "x", "path": str(tmp_path), "scope": "", "referenceCondition": ""}]
    result = ro.orchestrate("아무 내용", roots, log_path=tmp_path / "log.json")
    stage_names = [s["stage"] for s in result["steps"]]
    assert stage_names == ["structured", "prose_scan", "trust_annotation"]


def test_orchestrate_no_candidates_reports_needs_clarification(tmp_path):
    result = ro.orchestrate("이거", [], log_path=tmp_path / "log.json")
    assert result["candidates"] == []
    assert result["needsClarification"] is True


# --------------------------------------------------------- 신뢰 폐루프 주석

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


# --------------------------------------------------------------------- 로깅

def test_orchestrate_logs_run(tmp_path):
    log_path = tmp_path / "log.json"
    roots = [{"label": "x", "path": str(tmp_path), "scope": "특수키워드", "referenceCondition": ""}]
    ro.orchestrate("특수키워드 내용", roots, log_path=log_path)
    runs = ro.load_orchestration_log(log_path)
    assert len(runs) == 1
    assert runs[0]["candidateCount"] == 1
    assert runs[0]["topCandidate"]["rootLabel"] == "x"
    assert len(runs[0]["steps"]) == 3


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

    result = subprocess.run(
        [
            sys.executable, ro.__file__,
            "--text", "플러터 앱 개발 메모",
            "--registry", str(registry),
            "--log-path", str(log_path),
        ],
        capture_output=True, text=True, encoding="utf-8", timeout=15,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["candidates"][0]["rootLabel"] == "flutter_App"
    assert len(payload["steps"]) == 3
    assert log_path.exists()  # --log-path로 지정한 파일에 기록됐는지(실제 사용자 로그 안 건드림)

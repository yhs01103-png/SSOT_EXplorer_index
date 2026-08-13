"""SSOT_Explorer 라우터 — 오케스트레이션(2026-08-14 D-032).

"요청만 전달하는 파일" — 실제 판단 로직은 router_classifier.py(구조화 신호)
/ router_proposals.py(신뢰 폐루프)에 그대로 두고, 이 파일은 그 둘을 단계별로
내려가며 호출해서 합치고, 매 단계를 로그로 남기는 얇은 디스패처다.

단계(사용자가 명시한 순서 — "레지스트리존슨 + 프로즈모음집존슨 + 앱폐루프 +
구조화기반 인덱싱"):
  1단계 구조화 신호 — router_classifier.classify_content()(레지스트리
        label/scope/referenceCondition, 순수 JSON 기반, 빠름)
  2단계 프로즈 검색 — 등록 루트들의 README.md를 **그 자리에서 실시간으로
        스캔**(레지스트리로 복사/이관 안 함 — "README 내용 이관 금지"
        원칙 그대로 유지, 사용자가 명시적으로 재확인: "일단 실시간
        스캔으로 가고 나중에 db 붙으면 그때 구조화". 1단계보다 느리지만
        루트가 몇 개 안 돼서(현재 5개) 비용 낮음)
  3단계 신뢰 폐루프 주석 — router_proposals.is_trusted()/acceptance_rate()
        로 각 후보에 신뢰도 정보를 붙임(순위를 바꾸진 않음 — D-029 "항상
        사람 확인" 원칙과 같은 이유로, 과거 승인이력이 자동으로 우선순위를
        좌우하게 하지 않음. 참고 정보로만)

매 실행마다 3단계 각각 "뭘 시도했고 몇 개 나왔는지"를 기록해서
ORCHESTRATION_LOG_PATH에 원자적 쓰기로 남긴다 — router_proposals의
"제안+결정을 로그로"와 같은 폐루프 철학을, 오케스트레이션 파이프라인
전체로 확장한 것("이것도 폐루프형식"). 나중에 이 로그를 보면 "그 요청이
왜 이 폴더로 갔는지" 전체 이력을 재구성할 수 있다.

CLI: `python router_orchestrator.py --text "..."` — router_classifier.py의
CLI와 같은 계약(JSON 입출력)이지만 3단계를 전부 거친 최종 결과를 준다.

**D-033(2026-08-14) — IDF 공유 + additive 병합으로 정밀도 개선**: D-032
직후 실제 질의("이 대화 내용을 범용 코드 프로젝트 규칙으로 만들어줘")로
돌려보니 정답이 5순위→공동1위(4파전 동점)로만 개선됐다 — floor(고정값)
병합 방식이 "흔한 단어만 걸려도 전부 0.5"로 뭉개는 게 원인. 이제 등록
루트 전체(레지스트리 텍스트 + README 실시간 스캔)를 합친 corpus로 IDF를
한 번 계산해서 1단계(classify_content)와 2단계(프로즈검색) 둘 다 같은
가중치 기준을 쓰게 하고, 병합도 max()(floor) 대신 +=(additive)로 바꿨다.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import router_classifier
import router_proposals

ORCHESTRATION_LOG_PATH = Path.home() / ".claude" / "scripts" / "ssot_orchestrator_log.json"
README_FILENAME = "readme.md"
PROSE_MATCH_WEIGHT = 0.4  # D-033: 프로즈검색 신호가 additive로 기여하는 최대 가중치


def _find_readme(root_path: Path) -> Path | None:
    """find_index_files(main.py)와 같은 두 위치(플랫 루트 / .claude 하위)를
    본다 — 컨벤션이 갈리는 루트(flutter_App은 .claude 하위, 나머지는 플랫)
    둘 다 놓치지 않기 위함. Qt 의존 없이 이 모듈 안에서 독립적으로 재구현
    (router_classifier.py처럼 Qt 미의존 순수 모듈 유지 원칙)."""
    for base in (root_path, root_path / ".claude"):
        if not base.is_dir():
            continue
        try:
            for entry in base.iterdir():
                if entry.is_file() and entry.name.lower() == README_FILENAME:
                    return entry
        except OSError:
            continue
    return None


def _read_readme(root_path: Path) -> tuple[str, str] | None:
    """README.md를 그 자리에서 읽기만(복사 안 함) — (경로문자열, 내용) 또는
    None. IDF corpus 구성과 2단계 매치 둘 다 이 함수로 딱 한 번만 읽는다."""
    readme = _find_readme(root_path)
    if not readme:
        return None
    try:
        return str(readme), readme.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def orchestrate(text: str, roots: list[dict], log_path: Path | None = None) -> dict:
    """3단계를 순서대로 실행하고 병합 결과 + 단계별 로그를 반환한다.
    log_path를 지정하면 그쪽에 기록(테스트 격리용) — 생략 시 기본
    ORCHESTRATION_LOG_PATH."""
    steps = []
    text_words = router_classifier.tokenize(text)

    # 0단계(신호 아님, 준비) — 레지스트리 텍스트 + README 실시간 스캔을
    # 합친 corpus로 IDF를 한 번 계산 — 1/2단계가 같은 가중치 기준을 쓰게.
    readme_cache: dict[str, tuple[str, str] | None] = {}
    corpora: dict[str, str] = {}
    for r in roots:
        label = r["label"]
        readme_hit = _read_readme(Path(r["path"]))
        readme_cache[label] = readme_hit
        registry_text = " ".join([r.get("label", "") or "", r.get("referenceCondition", "") or ""])
        corpora[label] = registry_text + " " + (readme_hit[1] if readme_hit else "")
    idf = router_classifier.compute_idf(corpora)

    # 1단계 — 구조화 신호(공유 idf 사용)
    structured = router_classifier.classify_content(text, roots, idf=idf)
    steps.append({"stage": "structured", "candidateCount": len(structured)})
    merged: dict[str, dict] = {
        c["rootLabel"]: {**c, "signals": list(c["signals"])} for c in structured
    }

    # 2단계 — 프로즈 검색(같은 idf로 가중치, additive 병합 — floor 아님)
    prose_hit_count = 0
    for r in roots:
        label = r["label"]
        readme_hit = readme_cache.get(label)
        if not readme_hit:
            continue
        readme_path, content = readme_hit
        overlap = text_words & router_classifier.tokenize(content)
        if not overlap:
            continue
        prose_hit_count += 1
        matched_keywords = sorted(overlap)
        preview = ", ".join(matched_keywords[:5])
        prose_score = router_classifier._weighted_overlap_score(overlap, text_words, idf) * PROSE_MATCH_WEIGHT
        if label in merged:
            merged[label]["signals"].append("프로즈검색")
            merged[label]["matchedKeywords"] = sorted(set(merged[label]["matchedKeywords"]) | overlap)
            merged[label]["score"] = round(min(merged[label]["score"] + prose_score, 1.0), 3)
            merged[label]["reason"] += f" / README 검색 겹침(IDF가중, {readme_path}): {preview}"
        else:
            merged[label] = {
                "rootLabel": label,
                "rootPath": r["path"],
                "score": round(prose_score, 3),
                "matchedKeywords": matched_keywords,
                "reason": f"README 검색 겹침(IDF가중, {readme_path}): {preview}",
                "signals": ["프로즈검색"],
            }
    steps.append({"stage": "prose_scan", "candidateCount": prose_hit_count})

    # 3단계 — 신뢰 폐루프 주석(순위는 안 바꿈, 참고 정보만 붙임)
    trusted_count = 0
    for label, cand in merged.items():
        cand["trusted"] = router_proposals.is_trusted(label)
        cand["acceptanceRate"] = router_proposals.acceptance_rate(label)
        if cand["trusted"]:
            trusted_count += 1
    steps.append({"stage": "trust_annotation", "trustedCount": trusted_count})

    candidates = sorted(
        merged.values(), key=lambda c: (len(c["signals"]), c["score"]), reverse=True
    )
    result = {
        "needsClarification": not candidates and router_classifier.needs_clarification(text),
        "candidates": candidates,
        "steps": steps,
    }
    _log_run(text, result, log_path or ORCHESTRATION_LOG_PATH)
    return result


def _log_run(text: str, result: dict, log_path: Path) -> None:
    """매 오케스트레이션 실행을 원자적 쓰기로 기록 — router_proposals의
    "제안+결정 로그"와 같은 폐루프 철학을 파이프라인 전체로 확장."""
    runs = load_orchestration_log(log_path)
    top = result["candidates"][0] if result["candidates"] else None
    runs.append({
        "id": len(runs) + 1,
        "ranAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "queryPreview": (text or "")[:200],
        "steps": result["steps"],
        "candidateCount": len(result["candidates"]),
        "topCandidate": {"rootLabel": top["rootLabel"], "score": top["score"]} if top else None,
    })
    router_proposals.atomic_write_json(log_path, runs)


def load_orchestration_log(log_path: Path | None = None) -> list[dict]:
    """지금까지의 오케스트레이션 실행 이력 — "이 요청이 왜 이 폴더로
    갔는지" 전체 이력 조회용. log_path 생략 시 기본 ORCHESTRATION_LOG_PATH."""
    path = log_path or ORCHESTRATION_LOG_PATH
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return []


# --------------------------------------------------------------------- CLI

def _run_cli() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="레지스트리+README 실시간검색+신뢰폐루프를 단계별로 거친 최종 분류 제안(JSON)"
    )
    parser.add_argument("--text", required=True, help="분류할 내용. '-'면 stdin에서 읽음")
    parser.add_argument("--registry", default=None, help="ssot-roots.json 경로(생략 시 기본 위치)")
    parser.add_argument(
        "--log-path", default=None,
        help="오케스트레이션 로그 파일 경로(생략 시 기본 위치 — 테스트 등에서 격리용)",
    )
    args = parser.parse_args()

    text = sys.stdin.read() if args.text == "-" else args.text
    registry_path = Path(args.registry) if args.registry else router_classifier._default_registry_path()
    log_path = Path(args.log_path) if args.log_path else None

    try:
        data = json.loads(registry_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as e:
        print(json.dumps({"error": str(e)}))
        return 1

    roots = data.get("roots", [])
    result = orchestrate(text, roots, log_path=log_path)
    print(json.dumps(result, indent=2))  # ensure_ascii=True(기본) — 인코딩 사고 방지(D-030과 동일 이유)
    return 0


if __name__ == "__main__":
    sys.exit(_run_cli())

"""SSOT_Explorer — AI 툴별 규칙 파일 동기화(2026-08-21, D-068).

`main.py`의 `SyncFormatsDialog`(QDialog)가 이 로직을 전부 갖고 있었다 —
콘텐츠 생성(FORMAT_TARGETS/generate_*)은 이미 순수 함수였지만, "파일에 실제로
쓸지 말지" 판단과 손편집 파일 덮어쓰기 확인은 `QMessageBox.question()` 호출로
GUI 프로세스 안에 갇혀 있어서, GUI를 안 띄우면 동기화 자체를 실행할 방법이
없었다(CLI/MCP 어디에도 없음 — 이 프로젝트의 6개 MCP 도구는 P-01 원칙상
전부 읽기 전용이라 애초에 쓰기를 하지 않고, router_classifier.py/router_
orchestrator.py의 CLI는 classify만 한다).

이 모듈은 그 판단 로직을 GUI에서 뽑아낸 것 — "덮어쓰려면 확인이 필요한가"를
`needs_confirmation()`으로 순수 함수화하고, 실제 호출자(GUI든 미래의 CLI든)가
그 결과를 보고 사용자에게 물어본 뒤 `force=True`로 재호출하는 흐름으로
분리했다. `main.py`는 이제 이 모듈을 호출만 하고, 확인창 표시만 자기 책임으로
남긴다("메인은 오케스트레이션 호출만" 원칙 — router_orchestrator.py가
classify 쪽에서 이미 하고 있던 것과 같은 분리를 sync 쪽에도 적용).
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

SYNC_MARKER = "SSOT Explorer가 동기화"  # 두 생성 모드(포인터/전체복제) 공통 마커


def resolve_claude_md_target(folder: Path) -> Path:
    """이 폴더의 CLAUDE.md를 어디에 쓰거나 읽어야 하는지 결정한다 — 이미
    `.claude\\CLAUDE.md`(flutter_App 등의 컨벤션)가 있으면 그쪽, 아니면
    플랫 루트(새 루트는 기본이 플랫). find_index_files와 같은 두 위치를
    본다 — 여기서 어긋나면 엉뚱한 곳에 새 파일이 생기고 기존 파일은 안 지켜짐."""
    nested = folder / ".claude" / "CLAUDE.md"
    if nested.exists():
        return nested
    return folder / "CLAUDE.md"


# --------------------------------------------------------- AI 툴 포맷 어댑터
#
# 2026-08-13: CLAUDE.md 전용이던 걸 여러 AI 코딩 툴 포맷으로 확장. 같은
# referenceCondition(레지스트리, 단일 소스)에서 툴별 규칙 파일을 각각 생성 —
# "여러 AI 툴을 섞어 쓰는데 지침 파일이 서로 어긋난다"는 문제를 정면으로 겨냥.
#
# 2026-08-14(D-036, H-006): `.cursorrules`/`.windsurfrules`(플랫 단일파일)가
# 실제로는 이미 폐기된 레거시 포맷임을 상용비교분석(D-027) 중 발견 — Cursor는
# `.cursor/rules/*.mdc`(디렉토리, MDC 프론트매터), Windsurf는
# `.windsurf/rules/*.md`(디렉토리)로 이전됨. 신규 생성은 디렉토리 포맷을
# 우선하고, 레거시 플랫 파일은 "이미 있을 때만" 계속 동기화(legacy=True) —
# 새로 만들지는 않되 과거에 만들어둔 파일이 낡은 채로 방치되지도 않게.
# AGENTS.md는 30개+ 툴이 네이티브 지원하는 1차 공용 포맷으로 재포지셔닝.
# 포맷을 추가하려면 FORMAT_TARGETS에 한 줄만 추가하면 됨(파일명 + 경로 함수).

FORMAT_TARGETS: dict[str, dict] = {
    "CLAUDE.md": {
        "tool": "Claude Code",
        "resolver": lambda root: resolve_claude_md_target(root),
    },
    "AGENTS.md": {
        "tool": "범용(AGENTS.md 표준 — 30개+ 툴 네이티브 지원)",
        "resolver": lambda root: root / "AGENTS.md",
    },
    ".cursor/rules/ssot-index.mdc": {
        "tool": "Cursor",
        "resolver": lambda root: root / ".cursor" / "rules" / "ssot-index.mdc",
        "frontmatter": "---\ndescription: SSOT 인덱스 포인터\nalwaysApply: true\n---\n\n",
    },
    ".windsurf/rules/ssot-index.md": {
        "tool": "Windsurf",
        "resolver": lambda root: root / ".windsurf" / "rules" / "ssot-index.md",
        "frontmatter": "---\ntrigger: always_on\n---\n\n",
    },
    ".cursorrules": {
        "tool": "Cursor(레거시 — 이미 있을 때만 동기화, 신규 생성 안 함)",
        "resolver": lambda root: root / ".cursorrules",
        "legacy": True,
    },
    ".windsurfrules": {
        "tool": "Windsurf(레거시 — 이미 있을 때만 동기화, 신규 생성 안 함)",
        "resolver": lambda root: root / ".windsurfrules",
        "legacy": True,
    },
}

RESULT_ICONS = {
    "ok": "✅",
    "skip": "⏭ 건너뜀(손편집 보호)",
    "skip-legacy": "⏭ 건너뜀(레거시, 신규생성 안 함)",
    "needs-confirmation": "❓ 확인 필요(손편집 파일 — force로 재호출)",
    "fail": "❌ 실패",
}


def resolve_format_target(root: Path, format_name: str) -> Path:
    return FORMAT_TARGETS[format_name]["resolver"](root)


def generate_init_pointer(entry: dict, format_name: str, registry_path: Path) -> str:
    """평소 모드 — 순수 포인터. 어떤 포맷(CLAUDE.md/AGENTS.md/Cursor/Windsurf 등)
    이든 내용은 동일 — 파일명만 다르다. 레지스트리가 곧 SSOT라 내용을 여기
    박아넣지 않는다(중복 없음)."""
    today = datetime.now().strftime("%Y-%m-%d")
    has_readme_cond = bool((entry.get("readmeReferenceCondition") or "").strip())
    readme_line = (
        "\nREADME.md도 있다면 그 참고조건도 같은 항목에 있다.\n"
        if has_readme_cond else ""
    )
    web_url = (entry.get("webArtifactUrl") or "").strip()
    is_web_primary = entry.get("primarySource") == "web"
    # 2026-08-13(O-001): "정본"이라는 단어는 실제로 웹이 유일한 정본일 때만
    # 붙인다 — 예전엔 webArtifactUrl만 있으면 무조건 "정본"이라 적어서, 로컬
    # referenceCondition이 여전히 메인인 경우까지 오해를 줄 수 있었다.
    if web_url and is_web_primary:
        web_line = (
            f"⚠️ 이 루트는 웹 아티팩트가 유일한 정본이다(로컬 참조조건은 참고용): "
            f"{web_url}\n"
        )
    elif web_url:
        web_line = f"웹 아티팩트(참고, 정본 아님): {web_url}\n"
    else:
        web_line = ""
    return (
        f"# {entry['label']} — SSOT 인덱스 ({format_name} init — {SYNC_MARKER}, "
        "손으로 고치지 말 것)\n\n"
        "이 폴더는 SSOT 레지스트리에 등록되어 있다. 실제 참조조건/인덱싱 규칙은 "
        "항상 아래 레지스트리 파일에서 확인한다 — 이 파일은 포인터일 뿐, 내용을 "
        "여기 복붙하지 않는다. CLAUDE.md/AGENTS.md/Cursor/Windsurf 등 여러 AI 툴 "
        "포맷 전부 같은 레지스트리 항목에서 나온 동일 내용이다 — 툴마다 따로 안 "
        "써도 됨.\n\n"
        f"레지스트리: `{registry_path}`\n"
        f"이 폴더의 항목: label == \"{entry['label']}\"\n"
        f"{web_line}"
        f"{readme_line}\n"
        "---\n"
        f"동기화: {today} (SSOT Explorer)\n"
    )


def generate_full_export_pointer(entry: dict, format_name: str) -> str:
    """전체 내보내기 모드 — 참조조건 전문을 그대로 박아넣는다(레지스트리/앱
    없이도 그 AI 툴이 그대로 읽을 수 있게). 포맷 무관 동일 내용."""
    today = datetime.now().strftime("%Y-%m-%d")
    condition = (entry.get("referenceCondition") or "").strip() or "(비어있음)"
    readme_condition = (entry.get("readmeReferenceCondition") or "").strip()
    readme_section = (
        f"\n## README.md 참고 조건\n\n{readme_condition}\n" if readme_condition else ""
    )
    web_url = (entry.get("webArtifactUrl") or "").strip()
    is_web_primary = entry.get("primarySource") == "web"
    web_section = ""
    web_warning = ""
    if web_url and is_web_primary:
        web_section = f"\n## 웹 아티팩트\n\n**유일한 정본**: {web_url}\n"
        # O-001: 로컬이 정본이 아닌데 "완전판"으로 내보내면 스냅샷이 금방
        # 낡아 오해를 줄 수 있어 경고를 맨 앞에 박아둔다.
        web_warning = (
            "⚠️ 이 루트는 웹 아티팩트가 정본입니다 — 아래 참조 조건은 내보내기 "
            f"시점({today}) 로컬 스냅샷일 뿐이며 최신이 아닐 수 있습니다. 최신 "
            f"내용은 반드시 위 URL에서 확인하세요.\n\n"
        )
    elif web_url:
        web_section = f"\n## 웹 아티팩트\n\n참고(정본 아님): {web_url}\n"
    return (
        f"# {entry['label']} — SSOT 인덱스 ({format_name} 전체 내보내기 — "
        f"{SYNC_MARKER}, 손으로 고치지 말 것)\n\n"
        "이 파일은 SSOT 레지스트리에서 전체 내보내기(export)로 생성됐다 — 레지스트리나 "
        "SSOT Explorer 없이도 이 파일 하나만으로 완결된다.\n\n"
        f"{web_warning}"
        "## 참조 조건\n\n"
        f"{condition}\n"
        f"{readme_section}"
        f"{web_section}\n"
        "---\n"
        f"내보내기: {today} (SSOT Explorer)\n"
    )


def generate_init_claude_md(entry: dict, registry_path: Path) -> str:
    """하위호환 wrapper — CLAUDE.md는 generate_init_pointer의 특수 케이스."""
    return generate_init_pointer(entry, "CLAUDE.md", registry_path)


def generate_init_readme_md(entry: dict, registry_path: Path) -> str:
    """README도 평소엔 순수 포인터 — README 참고조건은 레지스트리에 있다."""
    today = datetime.now().strftime("%Y-%m-%d")
    return (
        f"# {entry['label']} (init — {SYNC_MARKER}, 손으로 고치지 말 것)\n\n"
        "이 폴더의 README 참고조건은 SSOT 레지스트리(`readmeReferenceCondition`)에 "
        "있다 — 여기 복붙하지 않는다.\n\n"
        f"레지스트리: `{registry_path}`\n"
        f"이 폴더의 항목: label == \"{entry['label']}\"\n\n"
        "---\n"
        f"동기화: {today} (SSOT Explorer)\n"
    )


def generate_full_export_readme_md(entry: dict) -> str:
    """전체 내보내기 모드의 README — readmeReferenceCondition 전체를 그대로 박아넣는다."""
    today = datetime.now().strftime("%Y-%m-%d")
    condition = (entry.get("readmeReferenceCondition") or "").strip() or "(비어있음)"
    return (
        f"# {entry['label']} (전체 내보내기 — {SYNC_MARKER}, 손으로 고치지 말 것)\n\n"
        f"{condition}\n\n"
        "---\n"
        f"내보내기: {today} (SSOT Explorer)\n"
    )


def generate_full_export_claude_md(entry: dict) -> str:
    """하위호환 wrapper — CLAUDE.md는 generate_full_export_pointer의 특수 케이스."""
    return generate_full_export_pointer(entry, "CLAUDE.md")


# ------------------------------------------------------------- 실제 쓰기 판단
#
# D-068 — 여기부터가 SyncFormatsDialog에서 뽑아낸 부분. GUI 프로세스 없이도
# "이 포맷을 지금 써도 되는가"를 판단할 수 있어야 CLI/스크립트에서 호출
# 가능해진다.

def needs_confirmation(root_path: Path, format_name: str) -> bool:
    """True면 기존 파일이 있는데 SYNC_MARKER가 없다 — 손으로 쓴 내용일 수
    있어 force 없이는 덮어쓰면 안 된다는 뜻. 레거시 포맷이 아직 없는 경우
    (신규 생성 안 함)는 별개로 write_one_format이 skip-legacy로 처리한다."""
    target = resolve_format_target(root_path, format_name)
    if not target.exists():
        return False
    existing = target.read_text(encoding="utf-8", errors="replace")
    return SYNC_MARKER not in existing


def write_one_format(
    root_path: Path, entry: dict, format_name: str, registry_path: Path, *, force: bool = False
) -> str:
    """`RESULT_ICONS`의 키 중 하나를 반환한다: ok/skip/skip-legacy/fail.
    `needs_confirmation()`은 이 함수가 호출하지 않는다 — 순서는 호출자
    (`sync_root`) 책임: 확인이 필요한 포맷은 이 함수를 아예 안 부르거나
    `force=True`로 불러야 한다."""
    info = FORMAT_TARGETS[format_name]
    target = info["resolver"](root_path)
    if info.get("legacy") and not target.exists():
        return "skip-legacy"  # 레거시 포맷은 이미 있을 때만 갱신, 신규 생성 안 함
    if target.exists() and not force:
        existing = target.read_text(encoding="utf-8", errors="replace")
        if SYNC_MARKER not in existing:
            return "skip"
    try:
        target.parent.mkdir(parents=True, exist_ok=True)  # .cursor/rules 등 신규 디렉토리
        body = info.get("frontmatter", "") + generate_init_pointer(entry, format_name, registry_path)
        target.write_text(body, encoding="utf-8")
        return "ok"
    except OSError:
        return "fail"


def sync_root(
    root_path: Path,
    entry: dict,
    registry_path: Path,
    *,
    formats: list[str] | None = None,
    force: bool = False,
) -> dict[str, str]:
    """루트 하나를 지정한 포맷들로 동기화 — GUI/CLI 공용 진입점.

    `formats` 생략 시 FORMAT_TARGETS 전체. `force=False`(기본)면 손편집이
    의심되는 포맷은 실제로 쓰지 않고 `"needs-confirmation"`만 반환한다 —
    호출자(GUI는 QMessageBox, CLI는 터미널 프롬프트나 `--yes` 플래그)가
    사용자 확인을 받은 뒤 그 포맷만 다시 `force=True`로 불러야 실제로
    쓰인다. 이 함수 자체는 확인을 어떻게 받을지 전혀 모른다 — GUI 의존성
    없음(D-068)."""
    targets = formats if formats is not None else list(FORMAT_TARGETS)
    results: dict[str, str] = {}
    for fmt in targets:
        if not force and needs_confirmation(root_path, fmt):
            results[fmt] = "needs-confirmation"
            continue
        results[fmt] = write_one_format(root_path, entry, fmt, registry_path, force=force)
    return results

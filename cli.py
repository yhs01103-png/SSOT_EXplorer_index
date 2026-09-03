"""SSOT_Explorer — 앱(PySide6 GUI) 없이 동작하는 커맨드라인 진입점
(2026-08-21, D-070).

O-017에서 정한 순서의 3번째 항목 — classify는 이미 CLI 계약이 있었고
(router_classifier.py/router_orchestrator.py의 `--text`), D-068/D-069로
sync/register도 순수 함수가 됐으니 이제 서브커맨드로 하나로 묶는다.

이 모듈은 router_orchestrator/router_classifier/router_sync/router_registry
/router_proposals만 임포트한다 — `main`도 `ssot_mcp_server`도 안 건드리므로
PySide6/fastembed 둘 다 필요 없다(pyproject.toml의 `core` extras만으로
이 파일 전체가 동작한다는 게 이 모듈의 존재 이유).

서브커맨드:
  ssot classify <text>            router_orchestrator의 6단계 파이프라인
  ssot classify <text> --fast     router_classifier 1단계만(더 빠름)
  ssot sync <label>                등록된 루트 하나를 AI 툴 포맷으로 동기화
  ssot register <path> --label X  새 루트 등록
  ssot init [path]                등록 후보 폴더 나열(등록은 안 함, 신호만 —
                                   P-01과 같은 원칙: 실제 등록 여부는 사람이 판단)

모든 명령은 사람이 읽는 출력이 기본이고, `--json`으로 기계가 읽는 JSON으로
바꿀 수 있다(파이프라인/스크립트에서 쓰기 위함)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import router_classifier
import router_orchestrator
import router_proposals
import router_registry
import router_sync

_NOISE_DIR_NAMES = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build",
    ".dart_tool", ".gradle", "Pods", ".pytest_cache", ".mypy_cache", "target",
}


def _default_registry_path() -> Path:
    return router_proposals.resolve_registry_path()


def _read_text_arg(value: str) -> str:
    return sys.stdin.read() if value == "-" else value


# --------------------------------------------------------------------- classify

def _cmd_classify(args: argparse.Namespace) -> int:
    registry_path = Path(args.registry) if args.registry else _default_registry_path()
    text = _read_text_arg(args.text)
    roots = router_registry.load_roots(registry_path)

    if args.full:
        # 6단계 전체(키워드 레지스트리+시맨틱+AI판단 스켈레톤). 시맨틱
        # 단계가 fastembed 모델을 로드한다 — 이미 로컬 캐시에 있으면
        # 수백ms지만, 첫 실행이거나 HF_HOME/캐시 위치가 평소와 다르면
        # 모델을 새로 받느라 몇 분+네트워크가 걸릴 수 있다(D-070 실측
        # 확인 — 이래서 기본값이 아니다).
        result = router_orchestrator.orchestrate(text, roots)
    else:
        # 기본값 — 1단계(키워드+IDF)만, 네트워크/무거운 모델 로드 없음.
        # CLI의 첫인상은 항상 빠르고 오프라인이어야 한다는 원칙(D-070).
        candidates = router_classifier.classify_content(text, roots)
        result = {
            "needsClarification": not candidates and router_classifier.needs_clarification(text),
            "candidates": candidates,
        }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    candidates = result.get("candidates", [])
    if not candidates:
        hint = " (모호함 — 더 구체적인 텍스트 필요)" if result.get("needsClarification") else ""
        print(f"매치되는 루트 없음{hint}")
        return 0
    for c in candidates:
        print(f"{c['score']:.3f}  {c['rootLabel']:<24} {c.get('reason', '')}")
    return 0


# ------------------------------------------------------------------------ sync

def _cmd_sync(args: argparse.Namespace) -> int:
    registry_path = Path(args.registry) if args.registry else _default_registry_path()
    roots = router_registry.load_roots(registry_path)
    entry = next((r for r in roots if r["label"] == args.label), None)
    if entry is None:
        print(f"'{args.label}' 라벨을 레지스트리에서 못 찾음. `ssot list`로 등록된 라벨 확인.", file=sys.stderr)
        return 1

    root_path = Path(entry["path"])
    formats = args.formats or list(router_sync.FORMAT_TARGETS)

    results = router_sync.sync_root(root_path, entry, registry_path, formats=formats, force=args.force)

    needs_confirm = [f for f, r in results.items() if r == "needs-confirmation"]
    if needs_confirm and not args.force:
        if args.yes:
            confirmed = needs_confirm
        elif not sys.stdin.isatty():
            print(
                "다음 포맷들이 손편집된 것으로 보여 확인이 필요합니다(비대화형 세션이라 "
                f"건너뜀 — --yes 또는 --force로 재실행): {', '.join(needs_confirm)}",
                file=sys.stderr,
            )
            confirmed = []
        else:
            confirmed = []
            for fmt in needs_confirm:
                target = router_sync.resolve_format_target(root_path, fmt)
                answer = input(f"{target}\n  자동생성 표식이 없습니다 — 손으로 쓴 내용일 수 있습니다. 덮어쓸까요? [y/N] ")
                if answer.strip().lower() == "y":
                    confirmed.append(fmt)
        if confirmed:
            results.update(
                router_sync.sync_root(root_path, entry, registry_path, formats=confirmed, force=True)
            )

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for fmt, result in results.items():
            print(f"{result:<18} {fmt}")
    return 0 if all(r in ("ok", "skip", "skip-legacy") for r in results.values()) else 1


# -------------------------------------------------------------------- register

def _cmd_register(args: argparse.Namespace) -> int:
    registry_path = Path(args.registry) if args.registry else _default_registry_path()
    path = str(Path(args.path).resolve())
    entry = {"label": args.label, "path": path, "referenceCondition": args.condition or ""}
    try:
        router_registry.add_root(entry, registry_path)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 1
    except router_registry.RegistryConflictError as e:
        print(str(e), file=sys.stderr)
        return 1

    # 2026-09-04 — GUI(main.py add_root)와 동일하게 하위 폴더 README 추적
    # 기준점을 등록 시점에 찍어둔다(D-0XX). 실패해도 등록 자체는 이미
    # 끝났으니 조용히 넘어간다 — 다음 워치독 스캔이 빈 스냅샷 기준으로
    # 다시 시작할 뿐.
    try:
        snapshot = router_registry.scan_subfolder_readmes(Path(path))
        router_registry.save_folder_snapshot(args.label, snapshot)
    except OSError:
        pass

    print(f"등록됨: {args.label} -> {path}")
    return 0


# ------------------------------------------------------------------------ init

def _cmd_init(args: argparse.Namespace) -> int:
    """등록 후보만 나열한다 — 절대 자동 등록하지 않는다(P-01과 같은 원칙:
    신호만 주고, 실제로 등록할지는 사람이 `ssot register`로 직접 결정)."""
    registry_path = Path(args.registry) if args.registry else _default_registry_path()
    scan_root = Path(args.path).resolve()
    if not scan_root.is_dir():
        print(f"디렉터리 아님: {scan_root}", file=sys.stderr)
        return 1

    roots = router_registry.load_roots(registry_path)
    registered_paths = {str(Path(r["path"]).resolve()) for r in roots}

    candidates = []
    for entry in sorted(scan_root.iterdir()):
        if not entry.is_dir() or entry.name in _NOISE_DIR_NAMES or entry.name.startswith("."):
            continue
        if str(entry.resolve()) in registered_paths:
            continue
        candidates.append(entry)

    if args.json:
        print(json.dumps([str(c) for c in candidates], ensure_ascii=False, indent=2))
        return 0

    if not candidates:
        print("등록 후보 없음(전부 이미 등록됐거나 노이즈 폴더로 제외됨).")
        return 0
    print(f"{scan_root} 밑 등록 후보 {len(candidates)}개(직접 등록: ssot register <path> --label <name>):")
    for c in candidates:
        print(f"  {c}")
    return 0


# ------------------------------------------------------------------------- list

def _cmd_list(args: argparse.Namespace) -> int:
    registry_path = Path(args.registry) if args.registry else _default_registry_path()
    roots = router_registry.load_roots(registry_path)
    if args.json:
        print(json.dumps(roots, ensure_ascii=False, indent=2))
        return 0
    if not roots:
        print("등록된 루트 없음.")
        return 0
    for r in roots:
        print(f"{r['label']:<24} {r['path']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ssot", description="SSOT_Explorer — GUI 없이 분류/동기화/등록")
    sub = parser.add_subparsers(dest="command", required=True)

    p_classify = sub.add_parser("classify", help="텍스트가 어느 등록 루트와 관련 있는지 분류")
    p_classify.add_argument("text", help="분류할 내용. '-'면 stdin에서 읽음")
    p_classify.add_argument(
        "--full", action="store_true",
        help="6단계 전체 파이프라인(시맨틱/AI판단 포함) — 기본값은 1단계만(빠름, 오프라인). "
             "첫 실행 시 임베딩 모델을 새로 받느라 몇 분 걸릴 수 있음",
    )
    p_classify.add_argument("--registry", default=None, help="ssot-roots.json 경로(생략 시 기본 위치)")
    p_classify.add_argument("--json", action="store_true", help="JSON으로 출력")
    p_classify.set_defaults(func=_cmd_classify)

    p_sync = sub.add_parser("sync", help="등록된 루트 하나를 CLAUDE.md/AGENTS.md/Cursor/Windsurf로 동기화")
    p_sync.add_argument("label", help="레지스트리에 등록된 루트의 label")
    p_sync.add_argument("--formats", nargs="+", default=None, help="동기화할 포맷만 선택(생략 시 전체)")
    p_sync.add_argument("--force", action="store_true", help="손편집 파일도 확인 없이 덮어씀")
    p_sync.add_argument("--yes", action="store_true", help="확인이 필요한 항목을 전부 예로 처리(비대화형 자동화용)")
    p_sync.add_argument("--registry", default=None, help="ssot-roots.json 경로(생략 시 기본 위치)")
    p_sync.add_argument("--json", action="store_true", help="JSON으로 출력")
    p_sync.set_defaults(func=_cmd_sync)

    p_register = sub.add_parser("register", help="새 프로젝트 루트를 레지스트리에 등록")
    p_register.add_argument("path", help="등록할 폴더 경로")
    p_register.add_argument("--label", required=True, help="이 루트를 가리킬 이름")
    p_register.add_argument("--condition", default="", help="참조조건(비워두면 나중에 채워도 됨)")
    p_register.add_argument("--registry", default=None, help="ssot-roots.json 경로(생략 시 기본 위치)")
    p_register.set_defaults(func=_cmd_register)

    p_init = sub.add_parser("init", help="이 경로 밑에서 아직 등록 안 된 후보 폴더를 나열(자동 등록 안 함)")
    p_init.add_argument("path", nargs="?", default=".", help="스캔할 경로(기본: 현재 디렉터리)")
    p_init.add_argument("--registry", default=None, help="ssot-roots.json 경로(생략 시 기본 위치)")
    p_init.add_argument("--json", action="store_true", help="JSON으로 출력")
    p_init.set_defaults(func=_cmd_init)

    p_list = sub.add_parser("list", help="등록된 루트 목록")
    p_list.add_argument("--registry", default=None, help="ssot-roots.json 경로(생략 시 기본 위치)")
    p_list.add_argument("--json", action="store_true", help="JSON으로 출력")
    p_list.set_defaults(func=_cmd_list)

    return parser


def _fix_windows_console_encoding() -> None:
    """이 프로젝트가 반복해서 겪은 패턴(D-030, `_cli_common`의 ensure_ascii
    등) — Windows 기본 콘솔(cp949)은 한글/em-dash를 못 쓴다. 여기 help
    텍스트/상태 메시지 전부 한글이라, `ssot --help`조차 UnicodeEncodeError로
    죽는 걸 D-070 스모크테스트에서 실제로 재현·확인했다. stdout/stderr를
    UTF-8로 재설정(Python 3.7+ TextIOWrapper.reconfigure) — 최신 터미널
    (Windows Terminal/PowerShell 7)에서는 이걸로 완전히 해결되고, 정말
    옛날 콘솔이라 그래도 안 되면(reconfigure 자체가 없는 스트림 등) 조용히
    넘어간다 — 인코딩 문제로 CLI 전체가 죽는 것보다는 최선을 다한 뒤
    계속 동작하는 쪽이 낫다."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name)
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8")
            except Exception:
                pass


def main(argv: list[str] | None = None) -> int:
    _fix_windows_console_encoding()
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

"""SSOT_Explorer 백그라운드 워치독(2026-08-28, D-088) — GUI 앱도 Claude Code
세션도 열려 있지 않을 때 도는 세 번째 감지 경로.

**배경**: "앱 안 켜도 계속 도는 감지 시스템" 논의(D-087 직전)에서 GUI 버튼은
불필요하다고 결론남 — 사람이 수동으로 문제를 먼저 알아채야 하는 경우가
실질적으로 없고(구조적 문제는 전부 자동 감지 대상), 이 스크립트가 그 자동
감지를 실제로 수행한다. Windows 작업 스케줄러에 `python ssot_background_
watchdog.py`를 주기 실행으로 등록해두면(이 세션에선 등록까지는 안 함 —
시스템 설정 변경이라 별도 승인 필요), GUI/Claude Code 세션 여부와 무관하게
독립적으로 돈다.

**흐름**: 스캔(경로존재/README존재/README신선도(mtime)/라벨 폴더 SSOT-LABEL
마커 일치) → 문제 발견 시 `router_registry.add_pending_action()`으로
D-087의 대기 큐에 구조화된 요청을 남김(이미 같은 target+action이 큐에
있으면 중복 큐잉 안 함) → 새로 큐잉된 게 있으면 Windows 토스트로 알림.
**여기까지가 이 스크립트의 끝** — 실제 승인 대화(README 생성/경로 되돌리기/
은퇴)는 사람이 다음 Claude Code 세션을 열었을 때 그 세션 안에서 진행된다
(P-01과 동일한 원칙: 이 스크립트도 프로젝트 파일을 절대 안 쓴다, 레지스트리
자신의 pendingActions 배열에만 기록).

**GUI/MCP 어느 쪽에도 안 묶임**: router_registry.py(D-069/071/087)만
쓴다 — PySide6도 mcp SDK도 임포트 안 해서, `pip install ssot-explorer`
(core만)로도 그대로 동작한다. 토스트 라이브러리(win11toast, `notify`
extra)는 선택적 — 없으면 큐잉까지만 하고 토스트는 조용히 생략(로그만
남김), 스캔/큐잉 자체가 실패하는 일은 없다.

**2026-09-03(D-0XX) 갱신**: roots[] 6개 전부에 SSOT-LABEL 마커를 소급
삽입 완료 — 이제 roots[]도 labeledFolders[]와 동일하게 경로존재/README
신선도**+ 마커 일치**까지 검사한다(마커 불일치도 `modify_readme`로
큐잉). 작업 스케줄러 등록 자체(schtasks 명령 실행)는 시스템 설정
변경이라 이 스크립트를 실행 파일로 준비하는 것과 별개로 사용자 승인
후 진행한다.

**2026-09-04(D-0XX) 갱신**: 루트 자신의 README뿐 아니라 그 밑 전체
하위 폴더(재귀)까지 추적 범위를 넓혔다 — `router_registry.
scan_subfolder_readmes()`로 매 스캔마다 "README 없는 폴더"/"등록 시점
(또는 지난 스캔)엔 있었는데 지금은 사라진 README"를 잡아 `subfolder`
타겟으로 큐잉한다. 기준점은 `router_registry.FOLDER_SNAPSHOT_PATH`(레지
스트리 본체와 별개 파일)에 저장되는 이전 스캔 스냅샷 — 잦은 mtime 변경은
의도적으로 무시(노이즈), 존재/삭제 여부만 본다.

**(D-095, 2026-09-04) — 작업 스케줄러 등록 자체를 실행 가능하게**: 위
D-0XX(2026-09-03) 단락이 지적한 대로, 이 스크립트는 "GUI/세션 없이도 자동
으로 돈다"고 문서에 적어놓고도 정작 스케줄러 등록 경로가 없어 실제로는
사람이 매번 수동 실행해야 했다(상용 비교 분석에서 "자동"이라는 이름과
실체가 어긋난다고 지적된 지점). `build_schtasks_command()`/
`install_scheduled_task()`/`uninstall_scheduled_task()`를 추가해 CLI
(`ssot schedule-watchdog`)로 실제 등록까지 할 수 있게 한다. 등록 자체는
여전히 시스템 설정 변경이라 CLI 쪽에서 사람 확인(또는 `--yes`) 후에만
실행한다 — 이 파일이 스스로 자신을 등록하는 일은 없다(P-01과 동일 원칙:
이 모듈은 명령을 구성/실행하는 함수만 제공, 언제 실행할지는 호출부 책임).

사용법(단독 실행):
    python ssot_background_watchdog.py

작업 스케줄러 등록(Windows, 사람 확인 필요):
    ssot schedule-watchdog
"""
from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import router_proposals
import router_registry
from router_paths import (
    WATCHDOG_LOG_PATH,  # D-098, O-021 Stage 1 — 경로 레이어로 이관, 재노출만
)
from router_proposals import is_developer_mode, resolve_registry_path

log = logging.getLogger("ssot_explorer")

README_STALE_DAYS = 30  # ssot_mcp_server.README_STALE_DAYS와 동일값 유지
DEFAULT_TASK_NAME = "SSOT_Explorer_Watchdog"
DEFAULT_SCHEDULE_TIME = "09:00"  # HH:MM, schtasks /st 형식

# 2026-08-28 — "감지→큐잉→토스트" 각 단계가 실제로 뭘 근거로 판단했는지
# 남기는 런타임 로그. router_orchestrator.ORCHESTRATION_LOG_PATH와 동일
# 위치/패턴(원자적 쓰기, id+ranAt, load_*_log() 리더) — 다른 로그뷰와
# 같은 자리에서 개발자 탭이 그대로 보여줄 수 있게.
# **단순 디버그 로그가 아니다** — pendingActions[]는 처리 완료되면 그
# 항목을 지우고 이력을 안 남기므로(D-087), "fix_path가 실제로 얼마나
# 자주 걸리는지"를 시간을 두고 판단할 수 있는 유일한 축적 지점이 이
# 로그다. O-017(이동추적 알고리즘 투자 여부)이 "실사용 데이터가 쌓이면
# 판단"이라고 미뤄둔 바로 그 데이터를 여기서 모은다 — 그래서 상한을
# 다른 진단성 로그(세션 컨텍스트 로그 500개)보다 넉넉하게 잡는다.
# (WATCHDOG_LOG_PATH는 router_paths.py에서 이관된 값 — 상단 import 참고)
WATCHDOG_LOG_MAX_ENTRIES = 2000


class ToastProviderNotConfigured(Exception):
    """win11toast(선택적 의존성, `notify` extra)가 설치 안 됐을 때 — 스캔/
    큐잉은 그대로 진행되고 토스트만 건너뛴다(router_embeddings.
    EmbeddingProviderNotConfigured와 동일한 스켈레톤 패턴, D-044/067)."""


def send_toast(title: str, body: str) -> None:
    try:
        from win11toast import toast
    except ImportError as e:
        raise ToastProviderNotConfigured(
            "win11toast가 설치돼 있지 않습니다 — `pip install ssot-explorer[notify]`"
        ) from e
    toast(title, body)


def _already_queued(pending: list[dict], target_type: str, target_label: str, action_type: str) -> bool:
    return any(
        a.get("targetType") == target_type
        and a.get("targetLabel") == target_label
        and a.get("actionType") == action_type
        for a in pending
    )


def load_watchdog_log(log_path: Path | None = None) -> list[dict]:
    """지금까지의 워치독 실행 이력 — 각 실행이 무엇을 검사했고(checkedRoots/
    checkedLabeledFolders), 무엇을 발견했으며(findings, evidence 포함),
    토스트를 실제로 띄웠는지(toastFired)까지 전부 남아있다. log_path 생략
    시 기본 WATCHDOG_LOG_PATH."""
    path = log_path or WATCHDOG_LOG_PATH
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return []


def _log_run(
    checked_roots: int,
    checked_labeled_folders: int,
    findings: list[dict],
    toast_fired: bool,
    log_path: Path,
    error: str | None = None,
) -> None:
    """매 실행을 원자적 쓰기로 기록(router_orchestrator._log_run과 동일
    패턴) — 상한 도달 시 오래된 것부터 버린다(세션 컨텍스트 로그와 동일
    관례, 단 이 로그는 O-017 판단 데이터라 상한 자체를 훨씬 넉넉하게 잡음,
    WATCHDOG_LOG_MAX_ENTRIES 참고).

    D-096 — `error`가 있으면(main()이 스캔 도중 예외를 잡은 경우) 그대로
    같이 남긴다 — 무인 실행이라 이 로그 자체가 "그날 실패했었다"는 걸 알 수
    있는 유일한 흔적이다(전에는 예외가 여기까지 오지도 못하고 죽어서 로그
    자체가 안 남았음)."""
    runs = load_watchdog_log(log_path)
    runs.append({
        "id": len(runs) + 1,
        "ranAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "checkedRoots": checked_roots,
        "checkedLabeledFolders": checked_labeled_folders,
        "findings": findings,
        "newFindingsCount": len(findings),
        "toastFired": toast_fired,
        "error": error,
    })
    runs = runs[-WATCHDOG_LOG_MAX_ENTRIES:]
    router_proposals.atomic_write_json(log_path, runs)


def _scan(registry_path: Path) -> list[dict]:
    """실제 스캔 본체 — 문제를 찾을 때마다(아직 큐에 없는 것만)
    pendingActions에 큐잉하고, 그 판단의 근거(evidence: 어느 파일/경로를
    봤는지, mtime 격차가 며칠인지, 마커에 실제로 뭐가 적혀 있었는지)까지
    담은 딕셔너리를 반환한다. scan_and_queue()(사람이 읽을 요약 문자열만
    필요한 기존 호출부/테스트용)와 main()(토스트+로그, evidence까지 필요)
    이 공유하는 단일 스캔 경로 — 로직을 두 곳에 복제하지 않는다."""
    if not is_developer_mode(registry_path):
        return []

    pending = router_registry.load_pending_actions(registry_path)
    findings: list[dict] = []

    def queue(target_type: str, target_label: str, action_type: str, note: str, evidence: dict) -> None:
        if _already_queued(pending, target_type, target_label, action_type):
            return
        request_id = router_registry.add_pending_action(
            {
                "targetType": target_type,
                "targetLabel": target_label,
                "actionType": action_type,
                "note": note,
            },
            registry_path,
        )
        pending.append({"targetType": target_type, "targetLabel": target_label, "actionType": action_type})
        findings.append({
            "targetType": target_type,
            "targetLabel": target_label,
            "actionType": action_type,
            "note": note,
            "evidence": evidence,
            "requestId": request_id,
        })

    for r in router_registry.load_roots(registry_path):
        label = r.get("label", "")
        path_str = r.get("path", "")
        root_path = Path(path_str)
        if not root_path.is_dir():
            queue(
                "root", label, "fix_path", "경로가 존재하지 않음 - 이동/삭제 확인 필요",
                {"checkedPath": path_str},
            )
            continue

        # 2026-09-04 — 하위 폴더 전체 재귀 스캔(D-0XX, 사용자 요청 "파일
        # 추적"). 루트 자신의 README 상태(freshness/marker, 아래)와는
        # 독립적으로 항상 돈다 — 루트 자신의 README가 stale이어도 하위
        # 폴더 추적은 계속 유효해야 함. 잦은 mtime 변경은 무시하고 "README
        # 없음"/"있다가 사라짐" 두 가지만 본다.
        old_snapshot = router_registry.load_folder_snapshot(label)
        new_snapshot = router_registry.scan_subfolder_readmes(root_path)
        for rel_path, has_readme in new_snapshot.items():
            if has_readme:
                continue
            # 지난 스냅샷에 True로 있다가 지금 False면 "사라짐"이 더 구체적인
            # 신호라 그쪽만 큐잉한다 — 둘 다 큐잉하면 같은 폴더에 대해
            # create_readme+readme_deleted가 동시에 뜨는 중복이 됨.
            if old_snapshot.get(rel_path) is True:
                queue(
                    "subfolder", f"{label}:{rel_path}", "readme_deleted",
                    "README.md가 있었는데 사라짐(폴더 삭제 포함)",
                    {"rootLabel": label, "relativePath": rel_path},
                )
            else:
                queue(
                    "subfolder", f"{label}:{rel_path}", "create_readme",
                    "README.md 없음(하위 폴더)",
                    {"rootLabel": label, "relativePath": rel_path, "checkedPath": str(root_path / rel_path)},
                )
        router_registry.save_folder_snapshot(label, new_snapshot)

        freshness = router_registry.check_root_readme_freshness(r, README_STALE_DAYS)
        if freshness["status"] == "no_readme":
            queue(
                "root", label, "create_readme", "README.md 없음",
                {
                    "searchedPaths": [
                        str(root_path / "README.md"),
                        str(root_path / ".claude" / "README.md"),
                    ]
                },
            )
            continue
        if freshness["status"] == "stale":
            queue(
                "root", label, "modify_readme", f"README가 {freshness['gapDays']}일 뒤처짐(mtime 기준)",
                {
                    "readmePath": freshness.get("readmePath"),
                    "gapDays": freshness["gapDays"],
                    "staleThresholdDays": README_STALE_DAYS,
                },
            )

        # 2026-09-03 — roots[]도 labeledFolders[]와 동일하게 SSOT-LABEL
        # 마커 검사(라벨-폴더-README 3자 일치). README가 "수정"돼 다른
        # 라벨을 자기선언하게 되거나 마커 자체가 없어지면(fresh/stale
        # 여부와 무관하게) 여기서 잡는다 — freshness가 이미 찾아둔
        # readmePath를 재사용해 find_index_files를 두 번 안 부른다.
        readme_path_str = freshness.get("readmePath")
        if readme_path_str:
            marker = router_registry.read_ssot_label_marker(Path(readme_path_str))
            if marker != label:
                queue(
                    "root", label, "modify_readme",
                    f"SSOT-LABEL 마커 불일치(실제: {marker!r})",
                    {"readmePath": readme_path_str, "expectedLabel": label, "markerFound": marker},
                )

    for f in router_registry.load_labeled_folders(registry_path):
        label = f.get("label", "")
        path_str = f.get("path", "")
        folder_path = Path(path_str)
        if not folder_path.is_dir():
            queue(
                "labeledFolder", label, "fix_path", "경로가 존재하지 않음 - 이동/삭제 확인 필요",
                {"checkedPath": path_str},
            )
            continue
        readme_path = folder_path / "README.md"
        if not readme_path.is_file():
            queue(
                "labeledFolder", label, "create_readme", "README.md 없음",
                {"checkedPath": str(readme_path)},
            )
            continue
        marker = router_registry.read_ssot_label_marker(readme_path)
        if marker != label:
            queue(
                "labeledFolder", label, "modify_readme",
                f"SSOT-LABEL 마커 불일치(실제: {marker!r})",
                {"readmePath": str(readme_path), "expectedLabel": label, "markerFound": marker},
            )

    return findings


def scan_and_queue(registry_path: Path) -> list[str]:
    """레지스트리를 한 번 훑어 문제를 찾고, 아직 큐에 없는 것만 pendingActions
    에 추가한다. 새로 큐잉된 항목의 사람이 읽을 요약 문장 목록을 반환한다
    (빈 리스트 = 새로 발견된 문제 없음). 개발자 모드가 꺼져 있으면 아예
    스캔하지 않는다(다른 자동화 표면과 동일한 게이팅, D-057). 근거(evidence)
    까지 포함한 원본 데이터가 필요하면 `_scan()`을 직접 쓰거나, 실제 실행
    이력은 `load_watchdog_log()`(main()이 호출 시마다 기록)를 확인할 것 —
    이 함수 자체는 로그를 남기지 않는다(단독 호출/테스트 시에도 매번 로그
    파일이 늘어나는 걸 막기 위함, 실제 로그는 main() 경로에서만 쌓인다)."""
    findings = _scan(registry_path)
    return [f"[{finding['targetLabel']}] {finding['note']}" for finding in findings]


def main() -> None:
    """실제 작업 스케줄러가 매일 실행하는 진입점 — scan_and_queue()와 달리
    이 경로에서만 `WATCHDOG_LOG_PATH`에 실행 기록을 남긴다(검사한 루트/
    라벨폴더 개수, 발견 목록 + 근거, 토스트를 실제로 띄웠는지까지). 알림
    본문은 요약(최대 5줄)이지만, 로그에는 요약이 아니라 findings 전체와
    evidence가 그대로 남는다 — "무슨 파일을, 무슨 근거로 판단했는지"는
    알림이 아니라 이 로그에서 확인한다.

    D-096 — `_scan()`을 try/except로 감싼다. add_pending_action이 재시도해도
    (RegistryConflictError를 5번 다 소진했거나, 정말 예상 못 한 다른 예외가
    나면) 무인 실행이라 이 함수 자체가 여기서 죽으면 _log_run이 아예
    호출 안 돼 그날 실행 흔적이 통째로 사라진다(작업 스케줄러 로그를
    따로 안 보는 한 알 방법이 없음) — 예외를 잡아 로그에 error로 남기고
    계속 진행한다(main.py의 sys.excepthook과 같은 "안 죽는 게 최우선"
    원칙, 대상만 GUI 다이얼로그 대신 이 로그)."""
    registry_path = resolve_registry_path()
    error_message: str | None = None
    try:
        findings = _scan(registry_path)
    except Exception as e:
        log.error("워치독 스캔 실패: %s", e, exc_info=True)
        findings = []
        error_message = f"{type(e).__name__}: {e}"

    roots_count = len(router_registry.load_roots(registry_path))
    labeled_count = len(router_registry.load_labeled_folders(registry_path))

    toast_fired = False
    if findings:
        notices = [f"[{f['targetLabel']}] {f['note']}" for f in findings]
        body = "\n".join(notices[:5])
        if len(notices) > 5:
            body += f"\n...외 {len(notices) - 5}건"
        try:
            send_toast("SSOT_Explorer - 확인 필요", body)
            toast_fired = True
        except ToastProviderNotConfigured as e:
            log.info(f"토스트 알림 생략({e}) - 큐잉은 완료됨: {notices}")
    elif error_message:
        try:
            send_toast("SSOT_Explorer - 워치독 실행 실패", error_message[:200])
            toast_fired = True
        except ToastProviderNotConfigured as e:
            log.info(f"토스트 알림 생략({e}) - 실패만 로그에 남김: {error_message}")

    _log_run(roots_count, labeled_count, findings, toast_fired, WATCHDOG_LOG_PATH, error=error_message)


# ---------------------------------------------------- D-095: 작업 스케줄러 등록

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def resolve_watchdog_command() -> list[str]:
    """스케줄러가 실제로 실행할 명령. pip/pipx로 설치돼 `ssot-watchdog`
    콘솔 스크립트(pyproject.toml [project.scripts])가 PATH에 있으면 그걸
    최우선으로 쓴다 — 가상환경 경로에 안 묶이는 독립 실행 파일이라
    스케줄러가 어떤 계정/세션으로 돌든 안전. 없으면(소스에서 직접
    돌리는 개발 환경) `<현재 인터프리터> ssot_background_watchdog.py`로
    폴백 — main.py의 find_python_interpreter()와 같은 이유로 frozen
    상태(PyInstaller)에서 sys.executable이 자기 자신을 가리키는 경우는
    이 스크립트엔 해당 없음(워치독은 exe로 안 묶임, README 참고)."""
    installed = shutil.which("ssot-watchdog")
    if installed:
        return [installed]
    return [sys.executable, str(Path(__file__).resolve())]


def build_schtasks_command(
    task_name: str = DEFAULT_TASK_NAME,
    time_str: str = DEFAULT_SCHEDULE_TIME,
    command: list[str] | None = None,
) -> list[str]:
    """실제 실행 없이 schtasks 명령 argv만 구성(순수 함수, 테스트 가능) —
    install_scheduled_task()가 이걸 그대로 subprocess에 넘긴다. `/f`로
    동일 이름 작업이 이미 있으면 덮어써서 재등록이 중복 생성이 안 되게
    한다 — dev_mode 토글처럼 "언제든 다시 실행해도 안전"이 이 프로젝트의
    일관된 원칙."""
    if not _TIME_RE.match(time_str):
        raise ValueError(f"time_str은 HH:MM 형식이어야 함(24시간제): {time_str!r}")
    cmd = command or resolve_watchdog_command()
    task_run = " ".join(f'"{part}"' if " " in part else part for part in cmd)
    return [
        "schtasks", "/create",
        "/tn", task_name,
        "/tr", task_run,
        "/sc", "daily",
        "/st", time_str,
        "/f",
    ]


def build_schtasks_delete_command(task_name: str = DEFAULT_TASK_NAME) -> list[str]:
    return ["schtasks", "/delete", "/tn", task_name, "/f"]


def build_schtasks_query_command(task_name: str = DEFAULT_TASK_NAME) -> list[str]:
    return ["schtasks", "/query", "/tn", task_name]


def is_scheduled_task_installed(task_name: str = DEFAULT_TASK_NAME) -> bool:
    """이미 등록돼 있는지 — CLI가 등록 전에 현재 상태를 보여줄 때 씀.
    schtasks가 없는 플랫폼(비-Windows)이나 조회 자체가 실패하면 "없음"으로
    취급(설치 여부를 몰라서 죽는 것보다 안전한 쪽으로 폴백)."""
    try:
        result = subprocess.run(
            build_schtasks_query_command(task_name),
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def install_scheduled_task(
    task_name: str = DEFAULT_TASK_NAME,
    time_str: str = DEFAULT_SCHEDULE_TIME,
    command: list[str] | None = None,
) -> subprocess.CompletedProcess:
    """실제 schtasks /create를 실행한다 — 이 함수를 언제 부를지(사람 확인
    거쳤는지)는 호출부(cli.py) 책임, 여기선 명령 구성+실행만."""
    return subprocess.run(
        build_schtasks_command(task_name, time_str, command),
        capture_output=True, text=True, timeout=15,
    )


def uninstall_scheduled_task(task_name: str = DEFAULT_TASK_NAME) -> subprocess.CompletedProcess:
    return subprocess.run(
        build_schtasks_delete_command(task_name),
        capture_output=True, text=True, timeout=15,
    )


if __name__ == "__main__":
    main()

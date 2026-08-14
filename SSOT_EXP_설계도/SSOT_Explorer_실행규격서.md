================================================================
SSOT_Explorer — 실행규격서
================================================================
기준 버전: v1.0
최종수정: 2026-08-14 (H-007 — D-005~D-036 전체 반영한 전면 재작성)
원칙: 지금 코드가 정확히 어떻게 동작하는지만 기록한다. "왜"는 결정이력
      파일(D-번호)에, 계획/예정 항목은 넣지 않는다(구현 완료분만).

⚠️ 이전 판(2026-08-13 표기, 실제로는 v1.0 MVP 시절 그대로 방치)은 레지스트리
도입 이전(D-006 이전) 상태만 기록하고 있었다 — 이번 판은 main.py 1635줄 +
router_*.py 4개 파일을 직접 다시 읽고 전면 재작성한 것.

[1] 시스템 개요
- 단일 프로세스 데스크톱 GUI 앱(main.py, 1635줄) + 이 앱과 완전히 독립적으로
  동작하는 순수함수 모듈 4개(router_classifier.py/router_orchestrator.py/
  router_proposals.py/router_watcher.py, Qt 미의존 — CLI로도 단독 호출 가능).
  GUI는 PySide6.
- 목적: (1) 여러 개의 독립된 프로젝트 루트("SSOT 루트")를 하나의 트리에서
  탐색 + 각 폴더의 CLAUDE.md/README.md를 옆에서 바로 읽는 뷰어(Windows
  탐색기 보조/대체) (2) 등록된 루트의 AI 툴별 규칙 파일(CLAUDE.md/AGENTS.md/
  Cursor/Windsurf)을 레지스트리 하나에서 동기화 (3) 새 문서를 붙여넣으면
  등록 루트 중 어디로 보내야 할지 자동 제안(휴리스틱 라우터).
- 서버/DB/외부 네트워크 API 없음 — 전부 로컬 파일시스템 읽기/쓰기. 유일한
  "쓰기"는 (a) 레지스트리 JSON (b) 등록 루트의 규칙파일(CLAUDE.md 등,
  SYNC_MARKER 있는 파일만) (c) SaveDocumentDialog에서 사용자가 승인 버튼을
  누른 신규 문서 1건 — 그 외 기존 파일 이동/삭제/이름변경은 전면 안 함(P-01).
- 데이터 흐름의 중심(SSOT)은 앱이 아니라 레지스트리 JSON 1개 파일
  (`flutter_App\.claude\ssot-roots.json`) — main.py, 드리프트체크 스크립트,
  SessionStart/PostToolUse 훅 스크립트(이 레포 밖, `~/.claude/`)가 전부 이
  파일 하나를 공유해서 읽는다.

[2] 데이터 구조

[2-1] 레지스트리 파일(`REGISTRY_PATH`, main.py:114)
- 경로: `Path.home()/OneDrive/Desktop/SSOT/SSOT_Coding_File/flutter_App/
  .claude/ssot-roots.json`(하드코딩, 사용자 1인용이라 설정파일 분리 없음).
- 최상위 키: `roots`(배열), `sharedDocs`(배열), `relations`(배열),
  `$comment`(있으면 save_roots가 보존만 하고 무시).
- `roots[i]` 필드(load_roots가 없으면 기본값으로 채움, main.py:158):
  - `label`(str, 필수) — 표시 이름, 트리/다이얼로그 전반의 식별자로도 쓰임
  - `path`(str, 필수) — 절대경로
  - `referenceCondition`(str, 기본 "") — CLAUDE.md/AGENTS.md/Cursor/Windsurf
    전부 이 텍스트로 동기화되는 실질적 규칙 SSOT(프로즈)
  - `readmeReferenceCondition`(str, 기본 "") — README.md는 안 건드리되
    "언제 여는지"만 요약
  - `webArtifactUrl`(str, 기본 "") — claude.ai 아티팩트 등 웹 문서 URL
  - `primarySource`(str, 기본 "local") — `"local"` | `"web"`. web이면
    referenceCondition은 참고용 스냅샷일 뿐, webArtifactUrl이 유일한 정본
  - `owner`(str, 기본 "") / `scope`(str, 기본 "") /
    `lastReviewed`(str YYYY-MM-DD, 기본 "") — Backstage catalog-info.yaml
    방식의 경량 스키마. `review_age_days(entry)`가 오늘과의 일수 차 계산
    (형식 오류/누락 시 None), 180일(`REVIEW_STALE_DAYS`) 초과 시 관리자
    패널에서 ⚠️
  - `dependsOnDocs`(list[str], 기본 []) — `sharedDocs[].label` 참조,
    영향범위 전파(드리프트 스크립트가 그 공용문서 해시 변경 시 여기 걸린
    루트만 "반영 필요" 표시)
- `sharedDocs[i]`: `{label, path}` — 여러 루트가 참조하는 공용 컨벤션 문서
- `relations[i]`: `{fromPath, toPath, reason, bidirectional(기본 True)}` —
  임의 경로 대 경로 관계(등록된 루트뿐 아니라 그 하위 폴더도 대상). 프리픽스
  매치(`_is_or_under`)로 역조회.

[2-2] 저장 안전성(save_roots, main.py:276)
- 원자적 쓰기: 같은 폴더에 `.tmp<pid>`로 먼저 쓰고 `os.replace()`로 치환.
- 낙관적 동시성 제어: `load_roots()`가 읽을 때마다 파일 해시를 모듈 전역
  `_LAST_KNOWN_HASH`에 저장. `save_roots()`는 쓰기 직전 디스크 현재 해시를
  재확인 — 다르면(다른 기기/세션이 먼저 저장) `RegistryConflictError`를
  던지고 중단. 호출부(add_root/`_remove_root_at`/mark_reviewed) 전부 이
  예외를 잡아 경고 후 `load_roots()`로 재동기화.
- `roots` 배열만 교체 저장하고 `sharedDocs`/`relations`/`$comment`는 기존
  파일에서 읽어와 병합 보존(D-020에서 발견된 유실 버그의 재발 방지).

[2-3] 런타임 데이터(비영속)
- `QTreeWidgetItem.data(0, Qt.UserRole)`에 각 노드 절대경로 저장.
- `SSOTExplorer.roots`: `load_roots()` 결과를 메모리에 들고 있다가 트리
  구성/동기화/삭제 등에서 재사용, 변경 시 `save_roots()` 후 다시 로드.
- QSettings(`"SSOT_Explorer","SSOT_Explorer"`, Windows에선
  `HKCU\Software\SSOT_Explorer\SSOT_Explorer`): `windowGeometry`,
  `splitterState`, `lastSelectedPath` — `closeEvent`에서 저장, `__init__`
  에서 복원(`_restore_state`, `reveal_path`로 트리 펼침까지 복원).

[2-4] 로그 파일(레지스트리 밖, 전부 `~/.claude/scripts/`)
- `ssot_explorer.log`(`LOG_PATH`) — 앱 자체 로거(`_setup_logger`) +
  미처리예외 훅(`_install_crash_logging`)이 기록.
- `ssot-index-drift.log`(`DRIFT_LOG_PATH`) — 드리프트 스크립트 실행 로그.
- `ssot_orchestrator_log.json` — `router_orchestrator.orchestrate()`를
  CLI/GUI 어느 경로로 실행해도 매 실행마다 원자적 쓰기로 누적 기록
  (`atomic_write_json`, 단계별 결과+최상위 후보+타임스탬프).
- `ssot_router_proposals.json` / `ssot_router_trust.json` — `router_
  proposals.py`가 관리하는 승인/취소 이력과 root_label별 신뢰 상태
  (`TRUST_PROMOTION_STREAK=5`).

[3] 컴포넌트/모듈 구조
- 폴더 구조:
  ```
  Local_APP\SSOT_Explorer\
    ├── main.py                     (GUI 전체, 1635줄)
    ├── router_classifier.py        (분류 "서버" 두뇌, Qt 미의존)
    ├── router_orchestrator.py      (3단계 캐스케이드 디스패처)
    ├── router_proposals.py         (제안/승인/취소 이력 + 신뢰 폐루프)
    ├── router_watcher.py           (InboxWatcher 스켈레톤, 미구현)
    ├── test_main.py / test_router_*.py  (pytest, 총 94개)
    ├── requirements.txt            (PySide6, kiwipiepy)
    ├── requirements-dev.txt        (pytest==9.1.1, pyinstaller==6.22.0)
    ├── README.md
    ├── .claude\CLAUDE.md
    └── SSOT_EXP_설계도\
          ├── SSOT_Explorer_최신_설계결정이력_TODO.md
          ├── SSOT_Explorer_레거시_설계결정이력_정책맵.md
          ├── SSOT_Explorer_상용비교분석.md
          └── SSOT_Explorer_실행규격서.md (이 파일)
  ```
- main.py 안 클래스 6개: `SSOTExplorer(QMainWindow)`(메인), `SearchWorker
  (QThread)` + `SearchDialog(QDialog)`(백그라운드 재귀 검색), `Management
  Dialog(QDialog)`(레지스트리+드리프트 뷰), `SyncFormatsDialog(QDialog)`
  (포맷별 동기화), `SaveDocumentDialog(QDialog)`(새 문서 저장 라우팅 UI).
- router_*.py는 GUI에 의존하지 않는 순수 함수/얇은 클래스라 `python
  router_orchestrator.py --text "..."`처럼 단독 CLI로도 동작(아래 [8]).

[4] 유틸 함수 목록(주요 것만 — 전체는 main.py 참고)

main.py:
- `resolve_claude_md_target(folder) -> Path` — `.claude\CLAUDE.md`가 있으면
  그쪽, 아니면 플랫 `CLAUDE.md`. find_index_files와 동일 규칙 공유.
- `find_index_files(folder) -> dict` — folder 바로 밑 + `.claude\` 하위
  까지 claude.md/readme.md(대소문자 무시)를 찾아 `{소문자파일명: Path}`.
- `resolve_format_target(root, format_name) -> Path` — FORMAT_TARGETS의
  resolver 실행.
- `generate_init_pointer(entry, format_name) -> str` / `generate_full_
  export_pointer(entry, format_name) -> str` — 포인터 모드(레지스트리
  참조 문구만) / 전체 내보내기 모드(참조조건 전문 포함) 텍스트 생성,
  포맷 무관 공통 로직 + primarySource=web일 때 경고 문구 분기.
- `format_registry_text(roots)` / `format_shared_docs_text(shared_docs)`
  — 관리자 패널에 보여줄 사람이 읽기 좋은 텍스트로 정리(raw JSON 아님).
- `get_available_drives() -> list[str]` — 존재하는 드라이브 문자만(내용
  스캔 없음).
- `find_relations_for_path(target, relations) -> list[dict]` — prefix
  매치로 관계 역조회.

router_classifier.py:
- `tokenize(text) -> list[str]` — kiwipiepy 설치돼 있으면 형태소 분석
  (명사류 NNG/NNP/SL/SH/SN만 신호로 남김), 없거나 분석 실패 시 정규식
  (`[\w가-힣]+`)으로 자동 폴백. `_STOPWORDS`(내용/대화/관련 등 메타 어휘)
  제거.
- `compute_idf(corpora: dict[str, str]) -> dict[str, float]` — 등록 루트
  label+referenceCondition을 문서 집합으로 본 표준 TF-IDF 역문서빈도.
- `classify_content(text, roots, idf=None) -> list[dict]` — 독립 신호
  2개(키워드겹침 IDF가중치, scope 리터럴매치 `SCOPE_MATCH_BONUS=0.3`
  additive)를 합쳐 label별 순위 매김.
- `needs_clarification(text) -> bool` — 후보 0개일 때 "무관"과 "정보부족
  (짧음/지시대명사)"을 구분(대명사 감지는 원문 리터럴 매치, tokenize
  결과에 안 의존 — kiwi가 대명사를 걸러내는 것과의 상호작용 버그 회피).
- CLI: `python router_classifier.py --text "..." [--registry PATH]`

router_orchestrator.py:
- `orchestrate(text, roots, log_path=None) -> dict` — 3단계: (1)
  `classify_content()`(구조화 신호) (2) 등록 루트 README.md 실시간 스캔
  (`_find_readme`/`_prose_scan_signal`, 복사 안 하고 그 자리에서 매번
  읽음) (3) `router_proposals.is_trusted()`/`acceptance_rate()` 주석(순위
  안 바꿈, 참고 정보만). 여러 단계가 겹친 루트는 신호 개수까지 합산해서
  병합. 결과를 `atomic_write_json`으로 로그에 누적.
- CLI: `python router_orchestrator.py --text "..." [--registry PATH]
  [--log-path PATH]`

router_proposals.py:
- `record_decision(candidate, content_preview, decision) -> dict` —
  제안/승인/취소 이력 원자적 쓰기 기록.
- `acceptance_rate(root_label=None) -> float | None` — 승인율(전체 또는
  루트별).
- `is_trusted(root_label) -> bool` / `_update_trust(...)` — 연속 5승인
  시 승급, 1회 거부 시 즉시 리셋+강등. 신뢰돼도 승인 절차 자동 생략은
  안 함(UI 배지로만 노출).

router_watcher.py:
- `class InboxWatcher` — `start()`가 `NotImplementedError`(O-006, 의도된
  스켈레톤, 아직 미구현).

[5] 핵심 로직 명세

[5-1] 트리 지연 로딩(populate_roots → add_children_placeholder →
on_item_expanded)
1. 앱 시작 시 등록 루트를 최상위 노드로 추가(구분선 뒤에 드라이브 목록도
   최상위로 추가, `get_available_drives()` — D-028). 하위 폴더가 있으면
   더미 자식("...") 하나만 붙여 화살표만 보이게(실제 스캔 안 함).
2. 노드를 펼치면(itemExpanded) 더미 자식을 지우고 그 순간에만 1단계
   스캔해서 자식 추가(파일도 표시, D-007) — 각 자식도 다시 더미 자식으로
   지연 로딩 준비.
3. "."으로 시작하는 폴더는 숨김, 단 `.claude`만 예외로 노출(D-009).
4. `reveal_path(target)`가 구분선(경로 데이터 없는 최상위 항목)을 만나면
   건너뜀(D-028에서 발견된 TypeError 버그 수정 반영).

[5-2] 인덱스 표시(style_item) — 폴더에 `find_index_files()` 결과가 있으면
QTreeWidgetItem 폰트를 굵게 + 툴팁에 파일명 표시.

[5-3] 뷰어(on_selection_changed) — 선택한 폴더의 claude.md/readme.md를
`setMarkdown()`으로 렌더링(D-022, 파일 라벨은 `**굵게**`만 써서 파일 자체
`#` 제목 레벨과 안 겹치게). 위에 관계 패널(`update_relations_panel`) —
`find_relations_for_path()` 결과가 있으면 "🔗 연관된 인덱싱 폴더 + 이유"
목록, 더블클릭 시 반대쪽 경로로 `reveal_path` 이동. 관계 없으면 자동 숨김.

[5-4] AI 툴별 동기화(SyncFormatsDialog, D-013~D-036)
- `FORMAT_TARGETS`(main.py): 포맷명 → `{tool, resolver, legacy?,
  frontmatter?}` 딕셔너리 6개.
  1. `CLAUDE.md` → `resolve_claude_md_target()`
  2. `AGENTS.md` → `root/AGENTS.md`(30개+ 툴 네이티브 지원 1차 공용 포맷)
  3. `.cursor/rules/ssot-index.mdc` → MDC 프론트매터
     `description/alwaysApply: true`(Cursor 신포맷)
  4. `.windsurf/rules/ssot-index.md` → 프론트매터 `trigger: always_on`
     (Windsurf 신포맷)
  5. `.cursorrules`(legacy=True) → 이미 있을 때만 갱신, 신규 생성 안 함
  6. `.windsurfrules`(legacy=True) → 동일
- `_write_one(format_name, force)`: legacy 포맷이 없으면 `"skip-legacy"`,
  대상이 있고 `SYNC_MARKER`가 없으면(=손편집) `force=False`일 때 `"skip"`,
  아니면 부모 디렉토리 생성 후(`.cursor/rules/` 등) 프론트매터+포인터
  본문을 써서 `"ok"`. 개별 버튼(`sync_one`)은 손편집 파일 감지 시
  `QMessageBox.question`으로 덮어쓰기 확인 후 `force=True`로 재시도.
  `sync_all`은 6개 포맷 전부 순회.
- `primarySource=="web"`이면 다이얼로그 상단에 경고 라벨.

[5-5] 전체 내보내기(export_all_roots) — CLAUDE.md만 대상(다른 포맷은
"평소엔 포인터로 충분, 완전 독립이 필요할 때만"이라는 전제라 CLAUDE.md
1개로 한정). 손편집(SYNC_MARKER 없음) 루트는 건너뛰고 보고. README.md도
readmeReferenceCondition이 있으면 같은 규칙으로 같이 내보냄.

[5-6] 앱 시작 시 전체 루트 자동 init(`_ensure_all_roots_initialized`,
`__init__`에서 호출) — 등록 루트 중 CLAUDE.md가 아예 없는 것만 골라
`generate_init_claude_md()`로 생성. 있으면(손편집이든 이미 동기화된 것
이든) 절대 안 건드림 — SYNC_MARKER 확인조차 불필요.

[5-7] 검색(SearchDialog + SearchWorker) — Ctrl+F로 포커스, QThread에서
`os.walk` 재귀 검색(UI 안 멈춤), 다이얼로그 닫히면 `cancel()`+`wait()`로
정리. 결과 더블클릭 시 `reveal_path`로 트리 이동.

[5-8] 새 문서 저장(SaveDocumentDialog, D-029~D-034) — 텍스트 붙여넣기 →
`run_classification()`이 `router_orchestrator.orchestrate()` 호출(GUI/CLI
동일 결과 보장) → 후보 목록(신뢰 배지 포함) 표시 → 후보+파일명 선택 →
"저장" 버튼을 눌러야만 실제 파일 씀(P-01의 유일한 조건부 예외, 항상 사용자
승인 게이트) → `router_proposals.record_decision()`으로 승인/취소 둘 다
기록. 취소해도 로그는 남음.

[5-9] 오류 로깅/크래시 처리(D-025) — 모듈 로드 시 `_setup_logger()`가
`logging.getLogger("ssot_explorer")`에 StreamHandler+FileHandler 구성.
`_install_crash_logging()`이 `sys.excepthook`을 교체해 미처리 예외를
(1) 로그 파일 기록 (2) `QMessageBox.critical`로 사용자 알림 (3) 원래
excepthook도 호출. 슬롯(버튼 클릭 등) 안 예외는 이벤트 루프를 안 죽이고
계속 실행(알림만 뜸) — 시작 단계 예외만 그대로 종료(창이 안 열렸으니
복구할 게 없어 정상).

[5-10] 레지스트리 동시성/원자성 — [2-2] 참고.

[6] 화면 구성
- `QMainWindow`, 초기 크기 1100x700.
- `QSplitter`(가로): 좌측 `QTreeWidget`(트리, 비율 1) / 우측 상단 관계
  패널(`QListWidget`, 관계 없으면 숨김) + `QTextBrowser`(뷰어, 비율 2).
- 툴바(`_build_toolbar`, QStyle 표준 아이콘만 사용 — 자산 파일 없음):
  [루트 추가 / 루트 삭제 / 새로고침(F5)] | [AI 툴별 동기화 / 전체
  내보내기] | [검색창(Ctrl+F)] | [관리자 패널 / 새 문서 저장].
- 단축키: Ctrl+F(검색창 포커스, WindowShortcut) / Delete(트리 최상위=루트
  선택 시에만 삭제 확인창, WidgetShortcut로 스코프 제한).
- 우클릭 메뉴(트리 노드): 탐색기로 열기 / VS Code로 열기(`code` CLI) /
  여기서 터미널 열기(`cmd /K`) / 여기서 Claude Code 실행(`cmd /K "cd /d
  ... && claude"`, O-002) / 경로 복사 / 웹 아티팩트 열기(webArtifactUrl
  있을 때만 노출).
- 다이얼로그 4개: `SearchDialog`(검색 결과 리스트), `ManagementDialog`
  (레지스트리+sharedDocs 정리뷰 800x600, 드리프트 로그 실시간 스트리밍,
  "지금 드리프트 체크 실행" 버튼), `SyncFormatsDialog`(440x300, 포맷별
  버튼 6개+전체 버튼+리뷰완료 버튼), `SaveDocumentDialog`(텍스트 입력→
  분류결과→저장).

[7] 자동 실행/스케줄러 명세
- 앱 자체는 백그라운드 상시 감시 없음(수동 실행, `python main.py` 또는
  `dist\SSOT_Explorer.exe`).
- 이 레포 밖(`~/.claude/`)에 있는, 앱과 독립적으로 동작하는 자동화 3개:
  1. **SessionStart 훅**(`~/.claude/hooks/ssot_session_context.py`,
     D-031/D-032) — Claude Code 세션 시작(startup/resume/clear/compact
     전부)마다 stdin의 `cwd`가 등록 루트(또는 하위)와 겹치면 owner/scope/
     리뷰상태/primarySource경고/relations/**다른 등록 루트 전체 목록**+
     오케스트레이터 CLI 안내를 `additionalContext`로 즉시 주입. CLAUDE.md
     파일 존재 여부·최신 여부와 완전히 무관 — 레지스트리를 직접 읽음.
  2. **PostToolUse 훅**(`~/.claude/hooks/ssot_index_reminder.py`, 순수
     Python, 2026-08-13부로 옛 .ps1에서 교체) — 반응형 리마인더.
  3. **드리프트 체크**(`~/.claude/scripts/ssot_index_drift_check.py`,
     순수 Python) — Windows 작업 스케줄러가 매일 09:00 실행, 파일 해시
     스냅샷 비교(`ssot-index-snapshot.json`) + sharedDocs 해시 추적(영향
     범위 전파) + 리뷰 신선도(180일) 체크. 앱의 "지금 드리프트 체크 실행"
     버튼은 이 스크립트를 QProcess로 대신 실행해줄 뿐(보너스 기능,
     `find_python_interpreter()`로 exe 상태에서도 진짜 python 탐색).

[8] API/CLI 명세
- GUI 네트워크 API 없음. 대신 router 모듈 2개가 독립 CLI로 동작:
  - `python router_classifier.py --text "..." [--registry PATH]` —
    구조화 신호(classify_content)만, 더 빠름. `--text -`면 stdin에서 읽음.
    stdout에 JSON(ensure_ascii=True, 인코딩 사고 방지) 후보 목록.
  - `python router_orchestrator.py --text "..." [--registry PATH]
    [--log-path PATH]` — 3단계 캐스케이드 전부 거친 최종 결과(권장,
    SaveDocumentDialog와 동일 로직). 매 실행이 `ssot_orchestrator_log.json`
    (또는 `--log-path`)에 누적 기록됨.
  - 용도: Claude Code 세션 중 "이 대화 내용을 규칙으로 정리해줘" 같은
    요청을 받았을 때, GUI 없이 이 CLI로 목적지 후보를 먼저 조회.

[9] 실행 방법
- 배포용: `dist\SSOT_Explorer.exe` 더블클릭(설치 불필요, 단일 실행파일,
  kiwipiepy 모델 포함 ~152MB).
- 개발용: `pip install -r requirements.txt` 후 `python main.py`.
- exe 재빌드: `pip install -r requirements-dev.txt` 후
  `python -m PyInstaller --noconfirm --windowed --onefile --name
  "SSOT_Explorer" --collect-all kiwipiepy_model --collect-all kiwipiepy
  main.py`(D-034 — `--collect-all` 2개 필수, 없으면 kiwipiepy 모델이 안
  담겨 조용히 정규식 폴백으로 빠짐).
- 회귀 테스트: `pip install -r requirements-dev.txt` 후 `pytest -q` —
  94개(test_main.py 50 + test_router_classifier.py 15 +
  test_router_orchestrator.py 14 + test_router_proposals.py 13 +
  test_router_watcher.py 2), 전부 실제 사용자 레지스트리/QSettings/로그
  파일을 안 건드리는 격리된 임시 경로에서 실행(autouse fixture).

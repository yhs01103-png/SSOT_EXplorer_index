# SSOT Explorer

SSOT 인덱싱 트리 전용 탐색기 대체 뷰어 + 다중 AI 툴 규칙 동기화 도구. Windows
탐색기 대신, 각 폴더의 CLAUDE.md/README.md 내용을 트리 옆에서 바로 볼 수 있고,
등록된 루트의 규칙을 CLAUDE.md/AGENTS.md/.cursorrules/.windsurfrules로 동시에
맞출 수 있다.

## 실행

- 배포용: `dist\SSOT_Explorer.exe` 더블클릭(설치 불필요, 단일 실행파일)
- 개발용: `pip install -r requirements.txt` 후 `python main.py`
- exe 재빌드: `pip install -r requirements-dev.txt` 후
  `python -m PyInstaller --noconfirm --windowed --onefile --name "SSOT_Explorer" main.py`
- **회귀 테스트**(2026-08-13 도입, D-024 — Lazzy_App_OS_Monorepo/server의
  `test_*.py`+pytest 컨벤션 이식): `pip install -r requirements-dev.txt` 후
  `pytest -q`. `test_main.py`가 레지스트리 로드/저장, D-021 원자적쓰기+동시성
  충돌감지, D-023 primarySource, 툴바/단축키 등을 실제 사용자 레지스트리·
  QSettings를 안 건드리는 격리된 임시 경로에서 검증한다 — 코드 고칠 때마다
  스크래치 테스트를 새로 써서 지우는 대신 여기 추가해서 계속 쌓아간다.

## 기능

- 좌측: 트리(지연 로딩, 폴더+파일 전부 표시, `.claude` 폴더도 노출) —
  CLAUDE.md/README.md 있는 폴더는 굵게. 등록된 루트 밑에 **전체 드라이브**
  (C:\, D:\ 등)도 최상위로 노출(2026-08-13, D-028) — 등록 안 된 폴더도
  탐색기 대신 이 트리에서 바로 찾아갈 수 있음(내용은 펼칠 때만 읽음, 앱
  켤 때 미리 스캔 안 함)
- 우측: 선택한 폴더의 CLAUDE.md/README.md를 마크다운으로 렌더링해서 표시.
  그 위에 **관계 패널**(D-028) — 선택한 폴더가 레지스트리 `relations`에
  걸리면(등록된 루트든 아니든) "🔗 연관된 인덱싱 폴더 + 이유"를 보여줌,
  더블클릭하면 그 폴더로 트리가 이동. 관계 없으면 자동으로 숨겨짐
- 상단 검색창(Ctrl+F로 포커스): 이름으로 재귀 검색(백그라운드 스레드라 큰
  루트에서도 UI 안 멈춤) → 결과 더블클릭 시 트리에서 그 위치로 이동
- **+ 루트 추가 / − 루트 삭제 / 새로고침(F5)**: 레지스트리 갱신 + 새 루트는
  등록 즉시 init CLAUDE.md 자동 생성. 트리에서 루트 선택 후 Delete 키로도
  삭제 가능(하위 폴더 선택 시엔 동작 안 함 — 오조작 방지)
- **앱 시작 시 전체 루트 자동 init**(2026-08-14, D-031): 등록된 루트 중
  init CLAUDE.md가 아예 없는 것만 골라 자동 생성 — 손편집이든 이미 있는
  파일이든 절대 안 건드림.
- **SessionStart 훅**(`~/.claude/hooks/ssot_session_context.py`, D-031,
  SSOT_Explorer 앱과 별개로 항상 동작): Claude Code를 등록된 SSOT 루트
  (또는 그 하위)에서 열면, 그 폴더에 CLAUDE.md가 있든 없든 최신이든
  아니든 상관없이 레지스트리를 직접 읽어 owner/scope/리뷰상태/관련폴더를
  세션 시작 시 바로 주입. 파일 동기화가 밀려 있어도 Claude Code만큼은
  항상 최신 정보를 봄.
- **선택 루트 동기화 (AI 툴별)**: 다이얼로그에서 CLAUDE.md/AGENTS.md/
  .cursorrules/.windsurfrules 중 골라서(또는 전체 한번에) 같은 참조조건으로
  동기화. 손으로 쓴 파일은 확인 후에만 덮어씀. "리뷰 완료로 표시" 버튼도 여기.
- **전체 내보내기**: 등록된 모든 루트의 CLAUDE.md를 참조조건 전문 포함
  완전판으로 — 레지스트리/앱 없이도 동작하게 만드는 스냅샷
- 더블클릭: 폴더는 탐색기로, 파일은 기본 프로그램으로 엶
- 우클릭: 탐색기로 열기 / VS Code로 열기 / 터미널 열기 / **여기서 Claude Code
  실행**(cd 후 `claude` 바로 실행) / 경로 복사 / 웹 아티팩트 열기(등록돼
  있으면) — 결과는 하단 상태바에 표시
- **관리자 패널**(툴바): 루트별 owner/scope/리뷰 경과일(180일 초과 시 ⚠️)
  포함 정리된 레지스트리 뷰, "지금 드리프트 체크 실행"(실시간 진행상황 스트리밍)
- 창 크기/좌우 분할 비율/마지막 선택 위치를 다음 실행 때 그대로 복원(QSettings)
- **오류 로깅**(2026-08-13, D-025): 미처리 예외는 `~/.claude/scripts/
  ssot_explorer.log`에 기록되고 사용자에게 다이얼로그로 알림 — exe가
  `--windowed`(콘솔 없음)라 로그 파일 없이는 문제 진단이 불가능했음.
  버튼 클릭 같은 슬롯 안 예외는 알림만 뜨고 앱은 계속 실행됨.
- **새 문서 저장**(툴바, D-029~D-033): 텍스트를 붙여넣으면
  `router_orchestrator.py`가 3단계 캐스케이드로 등록 루트 중 맞는 곳을
  제안 — (1) `router_classifier.py`: 레지스트리 label/referenceCondition
  키워드겹침(IDF 가중치, D-033) + scope 리터럴매치(Lazzy_App_OS_Monorepo의
  user_info_indexer.py 다중신호 구조를 실제로 읽고 이식) (2) 등록 루트
  README.md를 그 자리에서 실시간 스캔(레지스트리로 복사 안 함 — README는
  항상 그 폴더에만 있다는 원칙 유지), 같은 IDF 가중치 공유 (3)
  `router_proposals.py`의 신뢰 폐루프(confidence_calibrator.py 이식, 연속
  5승인→승급/1회거부로 즉시 강등) 주석. 여러 루트에 흔한 단어("코드"/
  "프로젝트")는 IDF로 가중치를 낮추고, "내용을"/"대화" 같은 요청 형식
  어휘는 불용어로 걸러냄(D-033). AI 없는 휴리스틱 v1 — 여전히 완벽하진
  않음(정직한 실측 기록은 결정이력 D-033 참고). 사용자가 후보+파일명을
  고르고 "저장" 버튼을 눌러야만 실제로 파일이 써짐 — SSOT_Explorer
  전체에서 새 파일을 쓰는 유일한 지점(P-01의 조건부 예외, 아래 참고).
  승인/취소는 `router_proposals.py`가 기록, 신뢰됨 후보는 "✅신뢰됨"
  배지(승급해도 승인 절차 자동 생략은 안 함). "새 파일이 생기면 자동
  추적"(`router_watcher.py`)은 아직 스켈레톤만(O-006).
- **CLI 진입점**: `python router_orchestrator.py --text "..."`(3단계 전부
  거친 최종 결과, D-032 권장) 또는 `router_classifier.py --text "..."`
  (구조화 신호만, 더 빠름, D-030) — GUI 없이 아무 Claude Code 세션에서나
  직접 호출 가능, `--registry` 생략 시 기본 레지스트리 위치. "대화 내용을
  규칙으로 정리해줘" 같은 요청을 받았을 때 이걸로 목적지 후보를 먼저
  조회하고, 그 루트의 `referenceCondition`을 읽어 기존 컨벤션에 맞춰
  작성하는 용도. 매 오케스트레이터 실행은 `~/.claude/scripts/
  ssot_orchestrator_log.json`에 단계별 이력으로 기록됨.
- **SessionStart 훅 보강**(D-032): `ssot_session_context.py`가 발동할
  때마다 relations 명시 여부와 무관하게 "다른 등록 루트 전체" 목록과
  오케스트레이터 CLI 호출법을 항상 같이 안내.

## 이 앱이 안 하는 것

- **파일 변경 감지(드리프트) 상시 감시**: 앱 자체는 백그라운드 감시 안 함 —
  별도 스크립트(`~/.claude/scripts/ssot_index_drift_check.py`, 순수 Python,
  Windows 작업 스케줄러가 매일 09:00 실행)와 훅 스크립트
  (`~/.claude/hooks/ssot_index_reminder.py`)가 담당. 둘 다 2026-08-13부로
  PowerShell(.ps1)에서 순수 Python으로 교체 — 크로스플랫폼(Windows/Mac/Linux)
  이고, exe 없이 `python3`만 있으면 동작. 옛 .ps1 파일은 참고용으로만 보존
  (더 이상 자동 실행 안 됨). 앱의 "지금 드리프트 체크 실행"은 이 스크립트를
  대신 실행해줄 뿐(보너스 기능).
- **README.md 생성/편집**: 안 함 — README는 각 프로젝트의 실제 규칙이라
  건드리지 않음. 레지스트리엔 "언제 여는지" 짧은 참조조건만 유지.
- **자유 폴더에 임의로 규칙파일 생성**: 안 함 — 생성/동기화는 **등록된 루트만**
  대상. 프로젝트 자체 CLAUDE.md는 여전히 사람/Claude Code가 직접 작성.
- **파일 복사/이동/삭제/이름변경(자동)**: 안 함(P-01, 고위험이라 의도적으로
  제외) — 2026-08-13(D-029)부터 유일한 예외는 "새 문서 저장" 다이얼로그의
  신규 파일 쓰기뿐이고, 그마저도 매번 사용자가 승인 버튼을 눌러야만
  실행됨. 기존 파일 이동/삭제/이름변경은 여전히 전면 안 함.

## 레지스트리(`ssot-roots.json`) — 단일 소스

`flutter_App\.claude\ssot-roots.json`이 유일한 소스(2026-08-13부로 이 위치로
이동, 예전엔 `~/.claude/` 밑 전역 위치) — 이 앱, 드리프트 스크립트, 훅
스크립트가 전부 이 파일을 공유해서 읽는다. 각 루트 항목:

- `referenceCondition` — 실질적 규칙 SSOT(프로즈). CLAUDE.md/AGENTS.md/
  .cursorrules/.windsurfrules 전부 이걸로 동기화됨(포인터 모드 — 내용은 항상
  레지스트리 확인, 파일엔 복붙 안 함. "전체 내보내기"만 예외적으로 전문을 박음)
- `readmeReferenceCondition` — README.md는 안 건드리되, 언제 여는지의 요약
- `webArtifactUrl` — claude.ai 아티팩트 등 웹 문서 URL(있으면)
- `primarySource` — `"local"`(기본) | `"web"`. `"web"`이면 `webArtifactUrl`이
  **유일한 정본**이고 로컬 참조조건은 참고용 스냅샷일 뿐 — init/전체내보내기
  둘 다 그 사실을 문구로 명시하고, 동기화 다이얼로그에도 경고가 뜬다(Lazzy_
  App_OS_Monorepo가 문서 2개를 웹 전용으로 전환한 사례를 이식, D-023)
- `owner` / `scope` / `lastReviewed` — 프로즈+경량 스키마 하이브리드
  (Backstage catalog-info.yaml 방식). 도구가 검증 가능한 최소 필드만 —
  나머지는 계속 자유 프로즈
- **참조조건 수정은 Claude Code가**: 앱 UI로 편집하지 않음 — 대화 중 레지스트리
  JSON을 직접 고침
- **기존 손편집 내용 보호**: flutter_App/Local_APP/Coding_Nomal/개발자 전용
  어플 4개는 사람이 공들여 쓴 CLAUDE.md라 동기화 마커가 없음 — 동기화를 눌러도
  확인창 없이는 안 덮어씀(D-010/P-05)

현재 등록 루트(5개): flutter_App, Local_APP, Coding_Nomal, 개발자 전용 어플,
coding_admin.

최상위 `relations`(D-028, 2026-08-13) — 루트 항목이 아니라 최상위 배열:
`{fromPath, toPath, reason, bidirectional}`. 등록된 루트든 그 밑 임의
폴더든 경로가 fromPath/toPath와 같거나 하위면 매치 — 트리에서 그 폴더를
클릭하면 관계 패널에 표시됨. dependsOnDocs와 같은 원칙(명시적 선언, 자동
스캔 안 함) — Claude Code가 대화 중 직접 채운다.

## 설계 문서

`SSOT_EXP_설계도\` 폴더 — 결정이력/TODO, 정책맵, 실행규격서, 상용/표준
비교분석 4파일(v1.0 단일 레포 구조).

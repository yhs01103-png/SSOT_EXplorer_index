================================================================
SSOT_Explorer — 최신 설계결정이력 + TODO
================================================================
기준 버전: v1.0
최종수정: 2026-08-14 (D-041)
원칙: 가장 최근 라운드의 신규 결정(D-번호)과 전체 TODO(H-번호)만 담는다.
      더 오래된 결정은 레거시 파일로 이동.

관련 아티팩트(웹, 참고용 — 이 문서가 정본, 아티팩트는 가독성 좋은 스냅샷):
- 인수인계 노트(구현도+D-001~D-034 이력+붙여넣을 프롬프트):
  https://claude.ai/code/artifact/b38c1d60-e6c8-46f4-99e0-d21b4330a768
- 상용/표준 비교분석(가독성 재구성판, 원본은 SSOT_Explorer_상용비교분석.md,
  v2 갱신 2026-08-14 — D-037, Ruler 신규발견+opcode정체+잠재력재평가):
  https://claude.ai/code/artifact/115070d7-977d-4f0c-8e4f-54786416af7b

================================================================
PART 1 — 최신 설계 결정 (라운드 1, 2026-08-12)
================================================================

[D-001] 읽기 전용 MVP로 시작
결정: v1은 트리 뷰 + CLAUDE.md/README.md 뷰어 + 더블클릭 탐색기 열기만 구현.
      파일 복사/이동/삭제/이름변경 같은 실제 탐색기 조작 기능은 넣지 않는다.
이유: 실제 파일시스템 조작 기능은 실수 시 되돌리기 어려운 위험도 높은 작업이라,
      먼저 "보는" 용도로 검증한 뒤 필요성이 확인되면 별도 라운드로 추가한다.

[D-002] GUI 툴킷은 PySide6
결정: Tkinter(표준 내장) 대신 PySide6(PyQt 계열)를 채택.
이유: "탐색기 대체" 수준의 UX가 목표라 트리뷰/스플리터 등 완성도 있는 위젯이
      필요 — Tkinter보다 PySide6가 이 용도에 적합. 대신 pip install 필요.

[D-003] 트리 데이터는 QTreeWidget + 지연 로딩(수동 구현)
결정: QFileSystemModel(단일 루트 전제) 대신 QTreeWidget을 직접 채워 넣는 방식.
      폴더를 펼칠 때(itemExpanded)만 하위 폴더를 스캔한다.
이유: SSOT 루트가 4개(서로 다른 드라이브/부모 경로)라 단일 루트를 가정하는
      QFileSystemModel로는 표현이 안 됨. 지연 로딩은 대형 폴더 전체 스캔을 피함.

[D-004] 인덱스 파일 판별은 파일명만(claude.md/readme.md, 대소문자 무시)
결정: 폴더 안에 CLAUDE.md 또는 README.md가 있으면 그 폴더를 "인덱싱 대상"으로
      보고 트리에서 굵게 표시. 내용은 검사하지 않음(존재 여부만).
이유: 지금 SSOT 트리의 실제 컨벤션과 일치(CLAUDE.md/claude.md 대소문자 혼용
      확인됨).

[D-005] 설계 문서를 `SSOT_EXP_설계도\` 하위 폴더로 분리
결정: 3개 설계 문서를 프로젝트 루트에서 `SSOT_EXP_설계도\` 폴더 안으로 이동.
이유: Lazzy_App_OS_Monorepo의 `프로젝트_설계도_SSOT\` 관례와 통일 — 코드 파일
      (main.py 등)과 설계 문서를 폴더 레벨에서 분리해두면 프로젝트 루트가 덜
      복잡해짐. 사용자가 직접 폴더 생성 후 이동(2026-08-13), 문서 내 경로
      참조(.claude\CLAUDE.md, 실행규격서 [3])만 뒤따라 갱신.

[D-006] 루트 목록을 코드 하드코딩에서 공유 레지스트리(JSON)로 이관
결정: SSOT 루트 목록의 SSOT를 `~/.claude/ssot-roots.json` 하나로 통일.
      main.py, ssot-index-drift-check.ps1, ssot-index-reminder.ps1이 전부 이
      레지스트리를 읽는다. 앱에는 "+ 루트 추가 / - 루트 삭제" UI를 붙여서 이
      파일을 직접 갱신 — 하나만 고치면 3개 소비자 전부에 즉시 반영됨.
이유: 같은 루트 목록이 4곳(main.py/드리프트스크립트/훅스크립트/flutter_App
      CLAUDE.md 프로즈)에 중복 존재하던 걸 발견 — 이 중 "단순 목록" 성격인
      3곳(코드 3개)만 구조화 데이터로 통일. CLAUDE.md/README의 서술형 내용은
      계속 텍스트 파일이 SSOT로 유지(P-04 참고) — 이중관리 위험 없이 "구조화
      데이터 + 텍스트 SSOT"를 공존시킴.

[D-007] v2 기능: 파일도 트리에 표시 + 검색 + 우클릭 메뉴 + exe 패키징
결정: 트리에 폴더뿐 아니라 파일도 표시(더블클릭 시 기본 프로그램으로 열림).
      상단 검색창(재귀 검색 + 결과 더블클릭 시 트리에서 위치로 이동). 우클릭
      메뉴(탐색기로 열기/VS Code로 열기/터미널 열기/경로 복사). PyInstaller로
      `dist\SSOT_Explorer.exe` 단일 실행파일 빌드.
이유: MVP를 넘어 "실제 앱"으로 — 실제 파일 조작(복사/이동/삭제)은 고위험이라
      이번 라운드에 안 넣음(D-001/P-01 원칙 유지, 필요해지면 별도 라운드).

[D-008] 인덱스 없는 폴더 → 골격 생성 버튼 + 관리자 패널 추가
결정: 선택한 폴더에 CLAUDE.md/README.md가 둘 다 없으면 우측 패널에 "생성" 버튼이
      뜨고, 누르면 이 프로젝트 전체에서 써온 표준 골격(CLAUDE.md=인덱싱 전용,
      README.md=실제 규칙, 내용은 빈 템플릿)을 그 자리에 생성한다. 하나라도
      이미 있으면 버튼 자체를 숨긴다(부분 덮어쓰기 모호성 회피, 안전 우선).
      + 툴바에 "관리자 패널" 추가 — ssot-roots.json 내용 + 드리프트 로그를
      보여주고, "지금 드리프트 체크 실행" 버튼으로 드리프트 스크립트를 즉시
      실행할 수 있다(읽기 전용 P-01 범위 밖 — 앱 자신의 제어 파일만 다룸).
이유: "관례를 지키게 강제하는 앱"이라는 애초 목적에 맞게, 새 폴더에 관례를
      까먹고 안 만드는 걸 앱이 UI로 유도. 관리자 패널은 드리프트 감지 결과를
      별도 로그 파일 열지 않고 앱 안에서 바로 확인/재실행할 수 있게.

[D-009] find_index_files가 .claude\ 하위도 같이 검사, 트리도 .claude 폴더 노출
결정: find_index_files(folder)가 folder 바로 밑뿐 아니라 folder\.claude 밑도
      같이 스캔(바로 밑 파일 우선). 트리의 dot-폴더 숨김 필터에서 `.claude`만
      예외로 두어 일반 폴더처럼 펼쳐볼 수 있게 함(.git 등 나머지는 계속 숨김).
      관리자 패널의 "지금 드리프트 체크 실행"에 진행 표시(⏳ 실행 중 →
      ✅ 완료/❌ 실패, 버튼 비활성화)를 추가.
이유: flutter_App처럼 CLAUDE.md가 `.claude\CLAUDE.md`에 있는(플랫이 아닌) 루트를
      바로 밑 파일만 보고 "인덱스 없음"으로 오판 → 생성 버튼이 잘못 뜨는 문제
      발견. 드리프트 체크는 몇 초 걸리는데 클릭 후 아무 표시 없어 멈춘 것처럼
      보이는 문제도 같이 수정.

[D-010] 아키텍처 전환: CLAUDE.md=init 산출물, 레지스트리=실제 SSOT (P-04 갱신)
결정: 레지스트리(ssot-roots.json) 각 항목에 referenceCondition(참조조건, 프로즈)
      필드 추가. 각 루트의 CLAUDE.md는 이제 이 필드로부터 "동기화"해서 만드는
      init 산출물 — 직접 손으로 고치는 대상이 아님(고쳐도 다음 동기화 때
      덮어써짐, 파일 안에 그렇게 명시). README.md 자동생성은 중단(양방향
      아니라서 불필요 판단). "+ 루트 추가"는 등록과 동시에 init CLAUDE.md를
      바로 생성(새 루트라 안전). "선택 루트 CLAUDE.md 동기화" 버튼으로 언제든
      재생성 가능하되, 기존 CLAUDE.md에 동기화 마커가 없으면(=손으로 쓴 내용일
      가능성) 확인창을 띄워 실수로 덮어쓰지 않게 함.
      + 관리자 패널의 드리프트 체크를 QProcess로 바꿔 진행상황을 실시간
      스트리밍(스캔 중인 루트, 발견된 변경 각각을 즉시 표시).
이유: "레지스트리가 단순 목록 이상의 역할을 못 하게" 막았던 P-04를, 이번엔
      의도적으로 완화 — CLAUDE.md가 레지스트리로부터 항상 재생성 가능한
      산출물이 되므로(참조조건이 바뀌면 동기화 버튼 한 번으로 항상 일치),
      원래 걱정했던 "손 편집 vs 앱 데이터가 서로 다른 이야기를 하게 되는"
      이중관리 위험이 이 구조에서는 발생하지 않음. 단, 이미 사람이(그리고
      Claude Code가) 공들여 쓴 flutter_App/Local_APP/Coding_Nomal/개발자 전용
      어플 4개 루트의 실제 CLAUDE.md는 동기화 마커가 없어 안전장치가 걸림 —
      이 4개는 당분간 레지스트리의 referenceCondition을 "요약 참고용"으로만
      쓰고, 실제 CLAUDE.md 본문은 계속 사람이 관리(4개 파일 확인 완료 — 마커
      없음, 실수로 덮어써질 일 없음).
영향: Claude Code가 앱 없이 세션만 열어도 동일한 정보를 볼 수 있어야 한다는
      제약(대화 중 명시됨) — CLAUDE.md(init)에 참조조건 텍스트가 그대로
      박히므로(레지스트리를 또 열어볼 필요 없이) 이 제약 충족.

[D-011] readmeReferenceCondition 필드 추가 + 관리자 패널 정리된 텍스트로 표시
결정: 레지스트리 각 항목에 readmeReferenceCondition(README 참고조건) 필드
      추가 — CLAUDE.md(init) 참조조건과 별도로, "이 루트에 README.md가 있다면
      언제 참고하는지"를 표현. init CLAUDE.md 생성 시 이 필드가 있으면
      "## README.md 참고 조건" 섹션으로 같이 박아 넣는다. 관리자 패널
      registry_view는 raw JSON 대신 format_registry_text()로 루트별 정리된
      텍스트(경로/참조조건/README참고)로 표시.
이유: Coding_Nomal 계열 루트들은 README가 실제 "문서 인덱스 표" 역할을 하고
      있어 CLAUDE.md 참조조건과는 별도 성격 — 하나로 뭉치면 구분이 안 됨.
      raw JSON 노출은 사람이 읽기 불편해서 정리된 뷰로 교체.
확인: 4개 기존 루트 중 flutter_App만 README 없음(확인함), 나머지 3개는
      readmeReferenceCondition 채움. 4개 다 여전히 실제 CLAUDE.md 내용은
      요약만 반영 — 전체 내용을 레지스트리로 복제하지는 않음(정보손실/JSON
      비대화 방지, D-010 rationale 그대로 유지).

[D-012] init을 순수 포인터로 되돌리고 "전체 내보내기"를 별도 모드로 분리
결정: generate_init_claude_md()를 참조조건 텍스트를 박아넣던 방식에서 순수
      포인터("레지스트리에서 확인하라"만 담음)로 되돌림. 대신
      generate_full_export_claude_md() + "전체 내보내기" 툴바 버튼을 신설 —
      등록된 모든 루트를 한 번에 완전판(참조조건 전문 포함)으로 써서 레지스트리/
      앱 없이도 Claude Code가 그대로 읽을 수 있게 만드는 스냅샷 기능. 둘 다
      SYNC_MARKER로 표시되고, 동기화 마커 없는(손편집) CLAUDE.md는 두 모드
      모두에서 건너뛴다.
이유: "평소엔 레지스트리가 SSOT라 CLAUDE.md는 얇은 포인터 하나면 됨, 앱을
      더 이상 안 쓰게 될 때만 통째로 복제해서 독립시키면 됨" — 이 두 단계를
      명확히 나누는 게 평소엔 중복 없고, 필요할 때는 완전히 독립 가능.

[D-013][버그수정] resolve_claude_md_target 누락으로 flutter_App 보호 실패
결정: add_root/sync_selected_root/export_all_roots 전부 `루트/CLAUDE.md`
      플랫 경로만 확인하고 있었음 — flutter_App은 실제 CLAUDE.md가
      `.claude\CLAUDE.md`(중첩)에 있어서, 안전장치(동기화 마커 확인)가 그
      존재를 못 보고 플랫 루트에 새 파일을 만들 뻔했음(중복 파일 생성
      위험). find_index_files와 동일한 로직의 resolve_claude_md_target()을
      신설해 세 곳 전부 이걸 쓰도록 통일.
검증: 4개 루트 전부 실제 파일로 재확인 — flutter_App이 이제 정확히
      `.claude\CLAUDE.md`를 가리키고, 4개 다 마커 없음(보호됨) 확인됨.

[D-014] 4개 루트 CLAUDE.md 전체 이관 + 레지스트리 위치를 flutter_App\.claude\로 이동
결정: flutter_App/Local_APP/Coding_Nomal/개발자 전용 어플의 실제 CLAUDE.md
      전문(요약 아님)을 레지스트리 referenceCondition으로 이관하고, 4개 실제
      CLAUDE.md는 init 포인터로 교체(D-010에서 "새 루트부터"였던 걸 기존
      4개까지 확장). 레지스트리 파일 자체도 `~/.claude/ssot-roots.json`에서
      `flutter_App\.claude\ssot-roots.json`으로 이동 — 사용자가 flutter_App을
      가장 자주 열어서 세션 시작 시 바로 확인 가능하게. 드리프트/훅 스크립트
      기본 경로도 같이 갱신.
      README.md는 그대로 둠(정정, 아래 [D-015] 참고) — CLAUDE.md만 이관 대상.
이유: "각 루트 CLAUDE.md=레지스트리 산출물"이라는 원칙을 기존 4개까지
      일관되게 적용. 레지스트리 위치는 순수 사용자 편의(가장 자주 여는 곳).
검증: 이관 후 4개 CLAUDE.md 원문 길이(4667/1412/957/1019자) 확인, JSON
      파싱/드리프트스크립트/훅스크립트/앱 전부 새 경로에서 정상 재확인.

[D-015][정정] README.md는 이관 대상 아님 — 참조조건만 레지스트리에
결정: 위 D-014 실행 중 README.md까지 전체 이관 + init 포인터로 교체했다가,
      "README는 각 프로젝트의 실제 규칙이라 건드리면 안 된다"는 정정을 받아
      즉시 원복. README.md 3개(Local_APP/Coding_Nomal/개발자 전용 어플) 원문
      그대로 복원, 레지스트리의 readmeReferenceCondition은 전문이 아니라
      "언제 여는지"의 짧은 요약으로 되돌림(D-011 상태로 복귀).
이유: CLAUDE.md는 원래도 인덱싱 전용(짧고 포인터 성격)이라 레지스트리
      산출물화가 자연스럽지만, README.md는 그 자체가 "실제 규칙 본문"이라
      실제 작업 시 사람/Claude Code가 직접 읽고 고치는 대상 — 레지스트리로
      흡수하면 그 상시 작업 흐름이 깨짐.
검증: 드리프트체크로 원복 정확성 검증 — README 3개는 변경 없음(이전 스냅샷과
      완전 일치)으로 확인, CLAUDE.md 4개만 변경 감지됨.

[D-016] coding_admin(5번째 루트) 신설 등록
[2026-08-14 공개 전 마스킹 — 아래는 원문의 개인정보(절대경로+구체적 보관물
내용)를 가린 것, 결정 자체의 내용은 그대로]
결정: 개인 하드코딩용 정보 보관 폴더(이미 존재하던 폴더, 코드/설계 패턴이
      아닌 민감정보 성격)를 레지스트리에 5번째 루트로 등록. init CLAUDE.md +
      README.md 신규 생성(안의 개별 파일 내용은 열어보지 않음 — 폴더 성격만
      기록).
이유: 사용자 요청. 코드/설계 패턴 저장소들과 성격이 달라(민감정보 창고)
      README에 "내용을 다른 곳으로 복붙/요약해서 옮기지 않는다" 주의문구를
      명시적으로 추가.
확인: Coding_Nomal의 하위 워크스페이스(코드_프로젝트_범용규칙/모든_표본_
      일상_전략)는 이번 이관 대상이 아니었음을 재확인 — 등록된 루트(현재 5개)
      만 이 시스템(init/레지스트리)의 대상이고, 그 밑 하위 폴더들은 원본
      CLAUDE.md/README.md 그대로 유지.

[D-017] webArtifactUrl 필드 + 다중 AI 툴 포맷 어댑터(CLAUDE.md/AGENTS.md/
.cursorrules/.windsurfrules)
결정: ① 레지스트리 항목에 webArtifactUrl(claude.ai 아티팩트 등 웹 정본 URL)
      추가 — init 파일에 "웹 아티팩트(정본): url" 줄로 포함, 우클릭 메뉴에
      "웹 아티팩트 열기" 액션(webbrowser.open) 추가.
      ② generate_init_claude_md를 generate_init_pointer(entry, format_name)
      제네릭 함수로 일반화 — FORMAT_TARGETS 딕셔너리(CLAUDE.md/AGENTS.md/
      .cursorrules/.windsurfrules → 파일 경로 resolver)를 기준으로 같은
      참조조건에서 포맷별 파일을 생성. "선택 루트 동기화" 버튼이 이제
      SyncFormatsDialog를 열어서, 포맷별 버튼(4개) + "전체 한번에" 버튼을
      제공 — 각 포맷 독립적으로 SYNC_MARKER 안전장치 적용.
이유: "여러 AI 툴(Cursor/Windsurf 등)을 섞어 쓰는데 지침 파일이 서로
      어긋난다"는 실제 문제를 정면으로 겨냥 — RuleSync/knowhub 같은 기성
      툴들이 푸는 문제(배포)와 달리, 이건 우리 시스템의 "레지스트리=SSOT,
      파일=산출물" 구조 위에 포맷 어댑터만 얹으면 되는 낮은 비용의 확장.
검증: 4개 포맷 전부 pointer/export 생성 + SYNC_MARKER 포함 확인, 경로
      resolver(CLAUDE.md만 .claude 중첩 지원, 나머지는 플랫) 확인.

[D-018] 프로즈 전용 → 프로즈+경량 스키마 하이브리드(Backstage catalog-info.yaml 방식)
결정: 레지스트리 각 항목에 얇은 검증 가능 필드 3개 추가 — `owner`, `scope`
      (workspace/workspace-parent/personal-archive/security-vault),
      `lastReviewed`(YYYY-MM-DD). referenceCondition 등 자유 프로즈는 그대로
      유지 — 도구가 검증할 수 있는 최소한만 스키마화. 관리자 패널
      (format_registry_text)에 리뷰 경과일 표시(180일 초과 시 ⚠️), 동기화
      다이얼로그에 "리뷰 완료로 표시" 버튼 추가. 드리프트 스크립트에도
      같은 180일 기준 리뷰 신선도 체크 추가 — 실행할 때마다(매일 09:00
      포함) 자동으로 "리뷰 필요" 로그 남김, AI 호출 없이 순수 날짜 계산.
이유: referenceCondition이 순수 자유텍스트라 오타/누락을 도구가 검증 못 하는
      문제 지적받음 — Backstage catalog-info.yaml(구조 메타)+TechDocs(자유
      프로즈) 병행 모델처럼, LLM 가독성 유지하면서 최소한의 자동 체크
      (오래된 리뷰 감지)만 가능하게 함.
검증: 오래된 lastReviewed(589일 전)로 스테일니스 감지 실제 발동 확인,
      전체 5개 루트 owner=yhs01/scope 분류/lastReviewed=오늘로 일괄 갱신
      (방금 전 대화에서 전부 직접 검증했으므로).

레이어 분리(파이프라인/전역설정 계층): 사용자 요청으로 지금은 보류 —
"나중에 커지면 참조해서" 라는 명시적 결정. §설계_방법론_참고.md 단순성
원칙("판단 기준: 시니어 엔지니어가 봐도 과하다 싶으면 단순화")에 부합.

[D-019] 드리프트/훅 스크립트를 PowerShell → 순수 Python으로 교체(크로스플랫폼)
결정: `ssot-index-drift-check.ps1`/`ssot-index-reminder.ps1`을
      `ssot_index_drift_check.py`/`ssot_index_reminder.py`로 재작성 —
      settings.json 훅 커맨드, Windows 작업 스케줄러, 앱의 QProcess 호출
      전부 Python 쪽으로 갱신. 옛 .ps1 파일은 삭제 안 하고 레거시 표시만
      추가(더 이상 자동 실행 안 됨, 참고용 보존).
      앱의 QProcess 실행 경로는 `sys.executable`이 아니라
      `find_python_interpreter()`로 — exe로 패키징된 상태에서 sys.executable은
      SSOT_Explorer.exe 자기 자신을 가리켜서 못 쓰기 때문에, 그 경우만
      `shutil.which("python")`으로 진짜 인터프리터를 찾음.
이유: PS1은 Windows 전용이라 "다른 사용자가 설치해서 바로 쓸 수 있는" 조건
      (OS 종속 스크립트 제거)을 막고 있었음 — 파일 해시 비교 정도는 순수
      Python으로 충분해서 제품화 장벽만 제거하는 저위험 작업으로 판단(1·2순위
      기능 강화보다는 후순위였으나 사용자가 즉시 진행 요청).
[버그수정] Get-FileHash(PowerShell, 대문자 hex) vs hashlib.hexdigest()(Python,
      소문자 hex) — 같은 SHA256 값인데 문자열 비교라 레거시 PS1 스냅샷과 비교
      시 전 파일이 "수정됨"으로 오탐(실측 확인: `AWDSD\ios\...\README.md`
      양쪽 해시 직접 비교해서 대소문자 차이뿐임을 증명). diff_snapshots에서
      항상 `.lower()` 비교하도록 수정. 오탐으로 로그에 남은 대량 잘못된
      드리프트 기록(수백 건)도 정리.
검증: 파이프 테스트(드리프트/훅 둘 다) 통과, 실제 훅 발동 확인, Windows
      작업 스케줄러로 실제 실행해서 `Last Result: 0`(성공) 확인, 수정 후
      재실행 시 오탐 없이 "변경 없음" 확인, exe 재빌드 크래시 없음.

영향범위 전파(affected-graph, Nx 유사 개념): 사용자 제안으로 백로그만 기록,
구현 안 함 — "공용 컨벤션 문서 하나가 바뀌면 그걸 참조하는 모든 루트의
CLAUDE.md/AGENTS.md에 '변경분 반영 필요' 표시". 루트가 지금 5개 수준을 넘어
수십 개가 될 때 가치가 생기는 기능이라 지금은 명시적으로 후순위(레이어 분리와
같은 이유 — 규모 대비 과한 엔지니어링). 나중에 구현할 때 참고할 방향: 레지스트리
항목 간 "참조하는 공용 문서" 관계를 별도 필드로 표현 → 그 문서 hash가 바뀌면
참조하는 루트들의 lastReviewed를 자동으로 무효화(또는 별도 "반영 필요" 플래그).

[D-020] 영향범위 전파(affected-graph) — 안1: 명시적 의존성 선언으로 구현
결정: 다안 비교(안1 명시적 필드 / 안2 텍스트 자동스캔 / 안3 해시추적만) 제시 후
      안1 채택. 레지스트리에 최상위 `sharedDocs`(label/path) 추가 + 각 root에
      `dependsOnDocs`(label 배열) 추가. 첫 공용문서로
      `클로드_코드_답변_전역규칙.md` 등록, flutter_App만 dependsOnDocs에
      걸어둠(그 CLAUDE.md가 이 문서의 위치/역할을 구조적으로 설명하고 있어서
      — 나머지 4개 루트는 "이미 자동로드됨"이라는 사실만 언급해 내용 무관하게
      항상 참이라 의존 안 걺). 드리프트 스크립트가 sharedDocs 해시도 추적,
      바뀌면 dependsOnDocs에 그 label 걸린 루트만 "반영 필요"로 로그.
      관리자 패널에 sharedDocs 섹션 + 루트별 "공용문서 의존" 표시 추가.
이유: Nx affected-graph처럼 실제 사용 가치는 있지만, 자동 텍스트 스캔(안2)은
      오탐/누락으로 신뢰도가 떨어져 기능 무력화 위험 — 정확성이 핵심 가치라
      명시적 선언 방식(안1) 채택.
[버그수정] save_roots()가 roots만 담아 파일 전체를 덮어써서, sharedDocs가
      루트 추가/삭제 등 저장할 때마다 사라지는 문제 발견 — 기존 파일을 먼저
      읽어 sharedDocs/$comment를 보존하는 병합 저장으로 수정(sharedDocs 넣은
      직후라 실제 데이터 유실 전에 잡음).
검증: 스크래치 환경에서 실제로 공용문서 내용 변경 → dependsOnDocs 건 루트만
      "반영 필요" 발동, 안 건 루트는 미발동 확인. save_roots 병합 보존도
      실제 저장 전후 sharedDocs 개수 비교로 검증. exe 재빌드 크래시 없음.

[D-021] 레지스트리 쓰기 안전성 — 원자적 쓰기 + 낙관적 동시성 제어(락 아님)
결정: save_roots()/load_roots()에 두 겹 방어 추가.
      (1) 원자적 쓰기 — 같은 폴더에 임시파일(.tmp<pid>)로 먼저 쓰고
          os.replace()로 치환(Windows/POSIX 둘 다 원자적). 쓰다 죽어도
          절반짜리 JSON이 실제 파일명으로 안 남음.
      (2) 낙관적 동시성 제어 — load_roots()가 읽을 때마다 파일 해시를
          모듈 전역 `_LAST_KNOWN_HASH`에 기억. save_roots()는 쓰기 직전
          디스크 현재 해시를 다시 재서 비교 — 다르면(그 사이 다른
          기기/세션이 먼저 저장) `RegistryConflictError`를 던지고
          중단(조용히 덮어쓰지 않음). 호출부(add_root/remove_root/
          mark_reviewed) 3곳 모두 이 예외를 잡아 경고 + load_roots()로
          최신 상태 재동기화.
이유: 레지스트리(ssot-roots.json)가 OneDrive로 여러 기기에 동기화됨 — 진짜
      리스크는 "다른 기기가 그 사이 먼저 저장"이지, 이 앱 프로세스 내부의
      동시 쓰기가 아님(단일 프로세스·단일 스레드라 내부 경합 자체가 없고,
      드리프트 스크립트는 읽기 전용이라 겹칠 일도 없음). OS 뮤텍스형 락은
      "같은 기기 안에서 두 프로세스가 동시에 쓰는" 상황에만 의미가 있는데
      그 상황이 실제로 없으므로 우선순위 낮음 — 대신 HTTP ETag/If-Match와
      같은 원리의 "읽은 시점 기준값을 쓰기 직전 재확인" 쪽이 이 프로젝트의
      실제 리스크에 더 정확히 맞음.
검증: 스크래치 환경에서 (a) 최초 생성 시 충돌 오탐 없음 (b) 정상
      load→수정→save 흐름 충돌 없음 (c) load 이후 "다른 기기"가 파일을
      직접 바꾼 걸 시뮬레이션 → save 시 RegistryConflictError 발생 확인
      (d) 충돌 발생 시 디스크의 external 기록이 실제로 안 덮어써지고
      보존됨 확인 (e) 정상 저장 후 임시파일이 안 남고 정리됨 확인 — 5개 전부
      통과. 앱 smoke-test(기동→타이틀 확인→종료) + exe 재빌드 후 동일
      smoke-test 통과.

[D-022] UI 편의성/최적화 라운드 — 4개 항목 동시 진행
결정: 사용자에게 후보 4개를 제시(AskUserQuestion) → 전부 선택돼 한 라운드에
      같이 반영.
      (1) 마크다운 렌더링 — 뷰어가 CLAUDE.md/README.md를 setPlainText 대신
          setMarkdown으로 표시(파일 라벨은 굵게(**)만 써서 파일 자체 # 제목
          레벨과 안 겹치게 함). 검색은 SearchWorker(QThread)로 분리 —
          이전엔 SearchDialog.__init__ 안에서 os.walk를 동기로 돌려서 큰
          루트에서 모달 전체가 멈췄음. 다이얼로그 닫힐 때 worker.cancel() +
          wait()로 정리.
      (2) 단축키 + 새로고침 + 상태바 — Ctrl+F(검색창 포커스, WindowShortcut),
          Delete(트리 최상위=루트 선택 시에만 삭제, WidgetShortcut로 스코프
          제한 — 검색창에서 텍스트 지울 때 오조작 방지), F5/새로고침 버튼
          신설(예전엔 외부 변경사항 보려면 앱 재시작해야 했음). remove_root
          로직을 _remove_root_at()으로 추출해 툴바 버튼과 Delete 단축키가
          공유. add_root/remove_root/경로복사/AI툴별동기화 결과를 상단
          상태바로 통일(다이얼로그 안에서만 뜨던 메시지는 다이얼로그가 닫히면
          같이 사라졌음).
      (3) 창/트리 상태 기억 — QSettings("SSOT_Explorer","SSOT_Explorer")로
          windowGeometry/splitterState/lastSelectedPath를 closeEvent에서
          저장, 시작 시 복원(마지막 선택 경로는 reveal_path 재사용으로 트리
          펼침까지 복원). Windows에선 파일 없이 레지스트리
          HKCU\Software\SSOT_Explorer\SSOT_Explorer에 저장.
      (4) 툴바 아이콘 + 정리 — QStyle 표준 아이콘(SP_FileDialogNewFolder/
          SP_TrashIcon/SP_BrowserReload/SP_DialogApplyButton/SP_DriveFDIcon/
          SP_FileDialogDetailedView) 사용 — 별도 이미지 자산 없이 동작해서
          PyInstaller 패키징에 영향 없음. [루트 추가/삭제/새로고침] |
          [AI툴별 동기화/전체 내보내기] | [검색] | [관리자 패널] 순서로
          그룹 재배치, 각 액션에 툴팁 추가.
이유: 넷 다 순수 부가기능이라 서로 의존성 낮고 한 라운드에 같이 검증 가능—
      개별 PR처럼 쪼갤 이유가 없어서 묶어서 진행.
검증: 스크래치 환경에서 QApplication 인스턴스화 후 9개 항목(아이콘 6개 전부
      null 아님, QSettings 인스턴스 확인, 상태바 메시지, setMarkdown 빈
      문서 아님, Ctrl+F/Delete 단축키 등록 확인, refresh_tree 무예외 실행,
      _remove_root_at/on_delete_key 메서드 존재, close 시 windowGeometry
      저장) 전부 통과. 테스트 중 생성된 QSettings 값은 실제 사용 왜곡 방지를
      위해 즉시 clear(). 앱 smoke-test(기동→타이틀 확인→종료) + exe 재빌드
      후 동일 smoke-test 통과.

[D-023] Lazzy_App_OS_Monorepo ↔ SSOT_Explorer 양방향 이식 라운드
결정: 사용자 요청으로 flutter_App\Lazzy_App_OS_Monorepo(.claude/CLAUDE.md,
      프로젝트_설계도_SSot\, server/client 하위 .claude, Skirpt\)를 훑어
      이식 후보를 정리 → AskUserQuestion으로 우선순위 선택 → 아래 2건은 이번
      라운드에 바로 구현, 나머지 3건은 O-번호(미결)로만 기록.
      즉시 구현:
      (O-001) primarySource 필드("local" 기본 / "web") 추가 — Lazzy가 결정
        이력 문서 2개를 로컬 md 동결 + 웹 아티팩트 단독 정본으로 전환한 사례
        (2026-08-11, "가독성이 떨어져서 웹이 낫다")를 SSOT_Explorer 스키마로
        일반화. generate_init_pointer/generate_full_export_pointer가
        primarySource=="web"일 때만 "유일한 정본" 문구+경고를 붙이고, 아니면
        webArtifactUrl이 있어도 "참고, 정본 아님"으로 정확히 표시(예전엔
        webArtifactUrl만 있으면 무조건 "정본"이라고 오표기했음 — 부수적으로
        같이 고침). format_registry_text에 🌐웹정본 태그, SyncFormatsDialog에
        경고 라벨 추가.
      (O-002) 트리 우클릭 메뉴에 "여기서 Claude Code 실행" 추가 — Lazzy의
        Skirpt\Claude_Code_CLC_play.cmd(`cmd /K "cd /d ... && claude"`) 패턴
        그대로 차용.
      O-번호로만 기록(미결, 실행 안 함): 등록 스코프를 서브프로젝트(레포 안
        레포)까지 확장할지, Lazzy에 드리프트감지/리뷰신선도 적용할지, Lazzy
        결정이력에 원자적쓰기/낙관적동시성 적용할지 — 상세는 문서 하단
        "미결 (O-번호)" 참고.
이유: Lazzy 쪽에서 이미 "O-번호(미결) + 재논의 조건" 카테고리를 자체 결정이력에
      쓰고 있었고(`O-003 Hub↔Jarvis 양방향 이식 후보`가 정확히 오늘과 같은
      성격의 항목), SSOT_Explorer 결정이력엔 이 카테고리가 없어 "알지만 지금은
      안 하기로 한 것"을 기록할 자리가 없었다 — 이번 기회에 SSOT_Explorer도
      같은 카테고리를 도입해 형식을 통일.
검증: 스크래치 환경에서 9개 항목 검증 — (a)(b) 필드 없는 기존 항목은 load_roots
      가 "local"로 기본값 채움, 명시 지정한 "web"은 유지 (c) primarySource=web
      일 때만 init pointer에 "유일한 정본"+⚠️ 문구 (d) local이면 webArtifactUrl
      있어도 "참고, 정본 아님"으로만 표시 (e) 전체 내보내기에도 참조조건 앞에
      경고 배너 (f) format_registry_text 🌐웹정본 태그 (g)(h) SyncFormatsDialog
      경고 라벨이 web일 때만 뜨고 local일 땐 안 뜸 (i) 컨텍스트메뉴 소스에
      "여기서 Claude Code 실행" 액션 + cd/d+claude 커맨드 존재 확인 — 9개 전부
      통과. 현재 등록된 5개 루트는 전부 webArtifactUrl 비어있어 primarySource
      필드 추가가 기존 동작에 영향 없음(순수 추가). 앱 smoke-test(기동→타이틀
      확인→종료) + exe 재빌드 후 동일 smoke-test 통과.

[D-024] pytest 회귀 테스트 스위트 도입 + requirements.txt/requirements-dev.txt 분리
결정: 사용자가 "코드 자체로도" 이식 후보를 확인해달라 요청 → Lazzy_App_OS_
      Monorepo\server\ 전체(core/tools/scripts/.github/workflows) 코드 레벨
      스캔. 발견: server는 모듈 30개+ 전부 test_*.py 1:1 대응 + `pytest -q` +
      `.github/workflows/tests.yml`(server/** 변경 시만 CI 실행)인데, 반대로
      SSOT_Explorer는 자동화 테스트 파일이 0개 — 이번 세션 검증마다(D-021 5개,
      D-022 9개, D-023 9개) 스크래치 폴더에 test 스크립트를 새로 써서 한 번
      돌리고 지웠음, 재실행 가능한 회귀 방지막이 전혀 안 남는 방식이었다.
      → `test_main.py`(conftest.py 없이 파일 하나, Lazzy 서버와 같은 저비용
      컨벤션) 신설, 총 19개 테스트: load/save 라운드트립, D-020 sharedDocs
      보존 회귀, D-021 원자적쓰기+동시성충돌(최초생성/정상흐름/충돌감지/
      충돌시미보존확인/임시파일미잔존 5개), D-023 primarySource(기본값/
      web유지/init문구분기/전체내보내기경고/레지스트리태그/동기화다이얼로그
      경고on-off), review_age_days 예외처리, 툴바 아이콘 6개, SSOTExplorer
      인스턴스화+단축키+refresh_tree, O-002 컨텍스트메뉴 소스확인.
      `isolated_registry`/`isolated_qsettings` fixture로 실제 사용자 레지스트리
      (flutter_App\.claude\ssot-roots.json)와 실제 Windows 레지스트리
      (HKCU\Software\SSOT_Explorer\SSOT_Explorer)를 절대 안 건드리게 격리.
      `requirements.txt`(PySide6)/`requirements-dev.txt`(pytest==9.1.1,
      pyinstaller==6.22.0 — 둘 다 로컬에 이미 설치된 버전 그대로 고정,
      pytest 버전은 Lazzy와 동일) 신설, README에 실행법 추가.
      역방향(SSOT_Explorer → Lazzy) 코드 이식은 확인 결과 없음: D-021
      원자적쓰기 후보였으나 Lazzy server 전체에서 `.write_text/open(...,'w')/
      json.dump`로 직접 파일에 쓰는 프로덕션 코드가 0건(전부 SQLAlchemy/
      PocketBase 경유, DB 트랜잭션이 이미 원자성 보장) — grep으로 실제
      확인 후 기각. client(Dart/Flutter)는 언어 자체가 달라 코드 이식 후보
      없음(확인만 하고 스킵).
이유: 지금까지의 "스크래치 테스트 작성→1회 실행→삭제" 방식은 검증 순간에만
      유효하고 다음 변경에 대한 안전망이 안 남는다 — Lazzy가 이미 검증한
      1:1 test 파일 컨벤션(무거운 fixture 인프라 없이도 충분)을 그대로
      가져오는 게 SSOT_Explorer 규모에 맞는 가장 낮은 비용의 해법.
검증: `pytest -q` 19개 전부 통과(0.51초). 실행 후 실제 QSettings 키
      (`QSettings("SSOT_Explorer","SSOT_Explorer").allKeys()`)가 빈 배열임을
      별도 확인해서 격리가 실제로 작동하는지 재확인.

[D-025] 로깅 인프라 도입 — Lazzy_App_OS_Monorepo/core/log/jarvis_log.py 이식
결정: 사용자가 "코드 레벨 인프라/기능 양방향 이식"을 더 확인해달라 요청
      (D-024 답변 이후 재질문) → server/core/log/jarvis_log.py를 다시 확인.
      그 파일 docstring에 실측 사고 기록: 예전엔 print()로 로그를 찍었는데
      Windows 콘솔(cp949 등)이 이모지/em-dash를 못 만나면 UnicodeEncodeError
      로 프로세스 자체가 죽었다(2026-07-26, DB연결실패 로그 찍다가 앱 기동이
      죽음) — logging.StreamHandler.emit()이 쓰기 실패를 내부에서 삼켜
      (handleError()) 예외를 다시 안 던지는 성질로 갈아타서 해결.
      SSOT_Explorer는 import logging/print()/sys.excepthook이 전부 0줄 —
      exe가 --windowed(콘솔 없음)라 지금 뭔가 예외가 나면 사용자 눈엔 그냥
      조용히 멈추거나 사라지는 것처럼 보임(진단할 로그 파일도 없음).
      → `LOG_PATH`(`~/.claude/scripts/ssot_explorer.log`) + `log`
      (`logging.getLogger("ssot_explorer")`, StreamHandler+FileHandler)를
      모듈 로드 시 바로 구성. `_install_crash_logging()`이 `sys.excepthook`을
      교체해 미처리 예외를 (1) 로그 파일 기록 (2) QMessageBox.critical로
      사용자에게 표시 (3) 원래 excepthook도 그대로 호출(콘솔 확인용)
      — `main()`에서 QApplication 생성 직후 호출. PySide6은 슬롯(버튼클릭
      콜백 등) 안 예외를 Qt C++ 스택으로 못 풀어서 sys.excepthook으로
      넘기는데, 그 경우 이벤트 루프 자체는 안 죽고 계속 돈다(=런타임 슬롯
      예외는 로그+알림만 뜨고 앱은 안 멈춤. 시작 단계 예외는 그대로 종료됨
      — 창이 아예 안 열렸으니 복구할 게 없어서 정상).
이유: Lazzy가 실제로 겪은 사고(print()+이모지+Windows콘솔=프로세스 사망)의
      재발을 막는 설계 원칙 자체가 SSOT_Explorer에도 그대로 적용됨 — 이
      앱도 상태바 메시지에 이모지를 잔뜩 쓰고 있어(✅❌⚠️🔄🗑📋🌐) 나중에
      어딘가 print()가 추가되는 순간 같은 사고가 재현될 수 있는 구조였음.
      게다가 --windowed exe라 로그 파일 없이는 사후진단 자체가 불가능.
검증: `test_main.py`에 3개 추가(로거 이름/핸들러 타입 확인, excepthook 교체
      확인, 실제 예외 발생시켜 log.error+QMessageBox.critical 둘 다 호출되는지
      — QMessageBox.critical은 monkeypatch로 목업해서 테스트 중 실제 모달이
      뜨는 걸 방지) — pytest 전체 22개 전부 통과. 앱 smoke-test로 정상 실행 시
      `ssot_explorer.log`가 실제로 생성됨을 확인(빈 파일 — 에러 없었으므로
      정상). exe 재빌드 후 동일 smoke-test 통과.

[D-026] git 저장소 초기화 — 첫 커밋(D-001~D-025 전체 스냅샷)
결정: 사용자가 "커밋은 항상 하고 있는거지?"라고 질문 → 확인해보니 이
      프로젝트뿐 아니라 상위 폴더 전부(Local_APP, SSOT_Coding_File, SSOT,
      Desktop) 어디에도 .git이 없어 커밋이 한 번도 없었음(`git status`가
      모든 상위 경로에서 "not a git repository" 반환으로 실측 확인).
      → `SSOT_Explorer\` 폴더에 `git init` + `.gitignore`(build/, dist/,
      *.spec, __pycache__/, .pytest_cache/ — 전부 재생성 가능한 산출물)
      + 첫 커밋(10개 파일, 2336줄, D-001~D-025 전체 반영 상태).
이유: OneDrive 동기화는 파일 백업만 해주지 diff/롤백/커밋 단위 이력을 안
      준다 — main.py 58KB+test_main.py 11KB+설계문서 다수가 지금까지 전부
      "지금 상태"만 존재하고 과거 시점으로 되돌아갈 방법이 없었다. CI(D-024
      TODO)도 git 저장소 없인 아예 불가능해서 선행조건이었음.
검증: `git log --oneline`으로 root-commit 1개 존재 확인, `git status`로
      더 이상 "not a git repository" 안 뜨는지 확인.

[D-027] 상용/표준 비교분석 문서 신설 — Lazzy 아이언맨_자비스_비교분석.md 방법론 이식
결정: 사용자가 "최고급 상용작이랑 정밀분석 먼저 해달라" 요청 →
      `SSOT_EXP_설계도\SSOT_Explorer_상용비교분석.md` 신설(4번째 설계문서).
      WebSearch로 Backstage(3,400개+ 회사 채택, catalog-info.yaml,
      TechDocs, 250개+ 플러그인), RuleSync(8개 AI툴 포맷 지원, CLI+웹SaaS,
      복수 독립구현), AGENTS.md 표준(2025-08 OpenAI 발표→Linux Foundation
      Agentic AI Foundation 이관, 30개+ 툴 네이티브 지원, 저장소 60,000개+)
      실시간 확인 후 축A(인프라 성숙도)/축B(기능완성도) 정밀 대조.
      **⚠️ 조사 중 실제 코드 결함 발견**: `.cursorrules`(단일파일)는 이미
      폐기(Cursor는 `.cursor/rules/*.mdc` 디렉토리로 이전), `.windsurfrules`도
      레거시(Windsurf는 `.windsurf/rules/` 권장, 과도기로만 구버전 지원) —
      SSOT_Explorer가 지금 생성하는 두 포맷이 최신 Cursor에서 아예 안 읽힐
      수 있음. → H-006으로 등록(아래), 사용자가 분석 먼저 요청했으므로 이번
      라운드에선 코드 수정 안 하고 문서화만.
이유: 이 앱을 실사용 계속할지/어디까지 발전시킬지 판단하려면 "이미 있는
      상용/표준 도구 대비 뭐가 겹치고 뭐가 다른지"를 정직하게 봐야 함 —
      Lazzy가 검증한 축A/축B + 정직성조건 방법론을 그대로 가져오는 게
      가장 낮은 비용으로 같은 rigor를 얻는 방법.
검증: 출처 8개 전부 각주로 URL 명시(추측 표시 없이 실제 검색 결과 기반),
      SSOT_Explorer 쪽 서술은 전부 실제 코드(main.py) 확인 후 작성.
[정정, 2026-08-13 같은 날] 사용자가 "인덱싱 전용앱이 상용작에 없나?"라고
      재질문 → 재검색 결과 "직접 경쟁 상대는 없다"는 D-027의 첫 결론이
      부정확했음을 발견. **Claudia**(marcusbey/claudia)와 **opcode**
      (winfunc/opcode 원본)가 실제로 "Project Scanner: CLAUDE.md 파일 전부
      찾기" GUI 기능을 갖춘 오픈소스 앱으로 존재[9][10] — WebFetch로 두
      프로젝트 문서 직접 확인 결과 "찾기+에디터+미리보기"까지만 하고
      다중포맷동기화/드리프트감지/리뷰신선도/영향범위전파/레지스트리 통합
      관리는 없음을 확인. 문서 자체를 수정(정정 섹션 추가 + 종합 결론
      4개 항목으로 재작성 + 출처 [9][10] 추가) — "정직성 조건" 원칙상
      최초 결론을 지우지 않고 정정 이력을 남기는 방식 채택.

[D-028] 전체 드라이브 탐색 + 관계(relations) 구조화 — Lazzy "능동적 인덱싱" 이식
결정: 사용자가 "Lazzy의 인덱싱 참조조건 능동성을 가져와서 파일로 구조화"
      제안(잠재력 평가 직후) → 둘 다 지금 바로 설계+구현.
      (1) 전체 드라이브 탐색 — `get_available_drives()`가 존재하는 드라이브
        문자만 확인(내용 스캔 없음, stat만), `populate_roots()`가 등록된
        루트 뒤에 구분선(Qt.NoItemFlags, 선택 불가) + 드라이브별 최상위
        항목을 추가. 실제 폴더 내용은 기존 지연로딩(on_item_expanded)을
        그대로 재사용 — 앱 켤 때 전체를 미리 스캔하지 않음(느리고 대부분
        무관하므로 의도적으로 안 함).
      (2) 관계 구조화 — 레지스트리에 최상위 `relations` 배열 신설
        (`{fromPath, toPath, reason, bidirectional}`). `find_relations_for_path()`
        가 경로 prefix 매치(`_is_or_under`)로 역조회 — 등록된 루트든 임의
        드라이브 밑 폴더든 상관없이 매치됨. UI: 뷰어 위에 관계 패널
        (QListWidget, 관계 없으면 자동 숨김) 신설, 더블클릭 시 반대쪽 경로로
        `reveal_path` 이동. dependsOnDocs(D-020)와 같은 원칙 — 자동 텍스트
        스캔 대신 명시적 선언(프로즈 관계는 파싱 신뢰도가 낮음).
      (3) 실 데이터 4건 채움 — 기존 각 루트 referenceCondition 프로즈에
        이미 있던 양방향 참조(flutter_App↔Local_APP, flutter_App↔
        Coding_Nomal, flutter_App↔개발자 전용 어플, 개발자 전용 어플↔
        모든_표본_일상_전략)를 relations로 구조화 이관.
      [버그수정] 구현 중 `reveal_path()`가 구분선(경로 데이터 없는 최상위
        항목)을 만나면 `Path(None)`에서 TypeError로 죽는 걸 발견 — 최상위
        루프에서 데이터 없는 항목은 건너뛰도록 방어 추가. 이 드라이브탐색
        기능을 넣기 전엔 모든 최상위 항목이 항상 경로를 가졌어서 드러난 적
        없던 잠재 버그.
이유: 지금까지 레지스트리는 "루트가 뭘 갖고 있는지"만 구조화했지 "루트끼리/
      임의 폴더끼리 왜 연관되는지"는 프로즈에 묻혀 있어 앱이 몰랐다 —
      Lazzy CLAUDE.md들의 "언제/왜 여는지" 조건표+양방향 역참조 스타일을
      구조화 데이터로 승격하면 사람이 프로즈를 안 읽어도 앱이 대신
      보여줄 수 있다. 전체 드라이브 노출은 "등록 안 된 폴더를 클릭해도
      관계가 뜨는" 시나리오 자체를 가능하게 하는 전제조건.
검증: test_main.py에 11개 추가(드라이브 목록에 현재 드라이브 포함,
      _is_or_under 자기자신/하위/무관/상위 4가지, find_relations_for_path
      from쪽매치/to쪽매치(양방향)/단방향이면 to쪽 무시/무관시 빈배열 4가지,
      load_relations bidirectional 기본값, save_roots가 relations 보존
      (D-020 sharedDocs 패턴과 동일), populate_roots+reveal_path가 구분선
      섞여도 안 죽음(버그 회귀 테스트), update_relations_panel이 관계
      있으면 보이고 없으면 숨겨짐) — pytest 전체 32개 전부 통과. 앱
      smoke-test 중 크래시로그(ssot_explorer.log) 비어있음 확인(에러 없음).
      exe 재빌드 후 동일 smoke-test 통과. 레지스트리에 실제 relations 4건
      기입 완료(flutter_App.claude\ssot-roots.json).

[D-029] "저장 → 자동 분류 제안" 라우터 신설 — 컨트롤타워 비전의 1단계
결정: 사용자가 D-028 다음으로 더 큰 그림 제시 — "코어 폴더(컨트롤타워)
      하나에서 레지스트리로 모든 경로 관리, 문서 저장 시 구조화+프로즈
      기반으로 어느 폴더에 저장할지 자동 판단(1단계 수동지정 → 2단계
      등록만 하면 자동라우팅 → 3단계 각 폴더 규칙까지 자동로드), AI 결합
      시 규칙 자체도 AI가 만들고 새 파일 생기면 추적해서 자동 배속".
      AskUserQuestion 2라운드로 두 갈림길 확정:
      (1) "AI"의 정체 — Claude Code(세션 중 제가 직접 판단) **+** 앱 자체
        내장 API 둘 다 원함, 단 앱 내장 쪽은 "이번엔 틀만 구축"(서버/
        클라이언트로 구조 분리는 하되 실제 AI 호출은 나중).
      (2) 자동 배속 방식 — 절대 자동실행 안 함, 항상 "제안만(자세한 설명
        포함) → 사용자가 승인/취소 버튼 → 결과를 로그로 기록해 나중에
        정밀도 올리는 재료로".
      구현: `router_classifier.py`("서버" 두뇌, Qt 미의존 순수함수 —
      classify_content()가 등록 루트 label/scope/referenceCondition과
      입력 텍스트의 키워드 겹침으로 순위 매김, AI로 내부만 교체해도 반환
      shape 유지되게 설계) + `router_proposals.py`(제안/승인/취소 이력을
      원자적 쓰기로 기록, acceptance_rate() — Lazzy의 ConfidenceJudgment/
      confidence_calibrator 폐루프 패턴의 축소판) + `router_watcher.py`
      (InboxWatcher 스켈레톤만, start()가 NotImplementedError — "새 파일
      생기면 자동추적"의 실제 구현은 다음 라운드) + main.py에
      `SaveDocumentDialog`(내용 붙여넣기→분류 제안 목록→후보 선택+파일명
      →승인 버튼 눌러야만 실제 저장, 취소해도 로그는 남음) + 툴바 "새
      문서 저장" 액션.
      **P-01 조건부 예외**: 이 다이얼로그가 SSOT_Explorer 전체에서 실제로
      새 파일을 쓰는 유일한 지점이 됨 — 다만 매번 사용자가 명시적으로
      승인 버튼을 눌러야만 실행되게 게이트를 걸어서, "고위험 자동화 금지"
      원칙 자체는 유지하면서 "승인 있으면 쓰기 가능"으로 범위를 좁혀서 열었다.
이유: server/client 모듈 분리(router_classifier/proposals/watcher를
      main.py=클라이언트GUI와 분리)로 나중에 실제 프로세스 분리(서버
      프로세스+API)로 갈 때 인터페이스를 안 건드려도 되게 미리 깔아둠 —
      직전 라운드(협업제품 로드맵 질문)에서 나온 "서버+DB로 가려면
      client/server 분리부터"라는 답이 이번 기능에도 그대로 적용됨.
      휴리스틱(비AI) 분류기로 시작한 이유: 새 의존성/API비용/네트워크
      없이 지금 당장 파이프라인 전체(제안→승인→저장→로그)가 실제로
      동작하는 걸 증명하는 게 먼저이고, "정확도"는 나중에 안쪽만 갈아
      끼우면 됨(계약이 되는 반환 shape을 먼저 고정해둔 이유).
검증: 신규 테스트 3파일(test_router_classifier.py 6개, test_router_proposals.py
      8개, test_router_watcher.py 2개) + test_main.py에 D-029 통합 테스트
      8개 추가 — 전부 실제 사용자 로그(~/.claude/scripts/
      ssot_router_proposals.json)를 안 건드리게 격리(isolated_router_proposals
      autouse fixture). [실수 발견+수정] 첫 실행 때 QMessageBox.information
      을 mock 안 하고 save_to_selected()를 직접 호출하는 테스트가 있어서
      진짜 모달이 뜨며 pytest 전체가 멈춘 걸 발견(D-025에서 이미 겪은
      함정과 같은 종류) — monkeypatch로 고치고 재검증. pytest 전체 55개
      전부 통과. 앱 smoke-test(크래시로그 비어있음 확인) + exe 재빌드 후
      동일 smoke-test 통과(router_*.py 3개 모두 PyInstaller가 로컬 import로
      자동 번들 — 추가 설정 불필요 확인).

[D-030] router 다중신호 구조 + 신뢰 폐루프 실이식 + CLI 진입점
결정: 사용자가 D-029 직후 세 가지 재요청 — (1) "Lazzy 인덱싱, 코드레벨로
      본 거 맞냐"는 질문에 정직하게 확인한 결과 D-028/D-029 둘 다 실제
      코드가 아니라 프로즈/비교문서 설명만 보고 이식한 것으로 드러남 →
      실제로 `server/core/orchestrators/user_info_indexer.py`,
      `confidence_calibrator.py`를 읽고 진짜 구조를 확인 (2) "폐루프는
      이식하면 좋겠다" (3) "IDE 플러그인은 각 IDE가 이미 네이티브 지원하는데,
      맥락/규칙을 확인해주는 앱이 따로 있냐" — WebSearch로 확인(별도
      commercial-app 없음, "nearest file wins"로 IDE 자체가 처리하는 게
      업계 표준이라 별도 앱이 오히려 불필요한 구조임을 확인) (4) 핵심 동기 —
      "클로드코드 쓰다가 '이 대화 범용규칙으로 만들어줘' 해도 한마디로
      안 됐다, 그 폴더 찾아서 규칙 참조까지 하는 게 목표였다".
      구현:
      - router_classifier.py: user_info_indexer.py의 "독립 신호 여러 개를
        구해 id 기준 합집합(가중합 아님)" 구조를 2신호로 이식 — 신호1(label/
        referenceCondition 키워드겹침), 신호2(scope 리터럴 매치, Lazzy의
        서브카테고리 패턴매치 자리). 처음엔 scope를 신호1 해시택에도
        같이 넣어서 두 신호가 사실상 안 독립적이었던 설계결함을 테스트
        작성 중 발견해서 분리 수정.
      - needs_clarification(): user_info_indexer.py 34~39행 "물어보기 원칙"
        이식 — 후보 0개일 때 "무관"과 "정보부족(짧음/지시대명사)"을 구분.
      - CLI 진입점(`python router_classifier.py --text "..."`) 신설 — 이게
        사용자의 핵심 요구사항에 대한 직접 답. GUI 없이 Claude Code가 세션
        중 아무 때나 직접 호출해서 JSON으로 후보를 받을 수 있음. 출력은
        ensure_ascii=True(기본값)로 인코딩 사고(이 프로젝트에서 반복된
        패턴) 원천봉쇄.
      - router_proposals.py: confidence_calibrator.py의 신뢰승급/강등을
        root_label 단위로 축소 이식(`_update_trust`, `is_trusted`,
        `TRUST_PROMOTION_STREAK=5`) — 연속 5승인 시 승급, 단 1회 거부로
        즉시 리셋+강등(보수적, Lazzy와 동일). trusted==True여도 승인
        절차 자동 생략은 안 함(D-029 "항상 사람 확인" 원칙 유지 — Lazzy
        원본의 mark_trusted_auto 리뷰생략은 의도적으로 이식 안 함) — UI에
        "✅신뢰됨" 배지로만 노출.
      [실측] CLI로 실제 레지스트리에 질의해보니 분류가 틀림(위 O-007
      실측사례 참고) — 정직하게 그대로 보고하고 O-007에 근거로 남김.
이유: "구조는 도메인 무관하게 재사용 가능"이라는 사용자 관찰이 맞았음 —
      user_info_indexer.py는 대화기억 인덱싱이지만 "독립신호 합집합" 자체는
      SSOT 문서 라우팅에도 그대로 옮겨졌다. CLI 진입점은 사용자가 실제로
      겪은 마찰(GUI 뒤에 숨은 로직을 세션 중에 못 씀)을 직접 해소.
검증: test_router_classifier.py에 다중신호 독립성(2개), 물어보기원칙(3개),
      CLI(2개, subprocess로 실제 실행) 추가. test_router_proposals.py에
      신뢰승급/강등/독립추적/원자적쓰기 5개 추가(TRUST_STATE_PATH도
      isolated_proposals_log/isolated_router_proposals 픽스처에서 같이
      격리 — 안 했으면 실사용자 파일 오염 위험 있었음, 코드리뷰 중 발견).
      pytest 전체 67개 통과. CLI 실제 실행(진짜 레지스트리 대상)으로
      end-to-end 확인 — 기술적으로는 정상 동작, 분류 정확도는 위 실측대로
      한계 확인. 앱/exe smoke-test 통과.

[D-031] SessionStart 훅(md 없이 레지스트리 직접 확인) + 앱 시작 시 전체 루트 자동 init
결정: 사용자가 D-030 직후 원래 요구를 재정리 — "등록된 SSOT 루트 어디서
      Claude Code를 켜든 md 파일을 따로 안 만들어도 레지스트리 컨텍스트를
      확인하게 할 수 있냐" + "SSOT_Explorer를 켜놓으면 등록된 인덱싱 폴더를
      전부 init 상태로 유지해달라". 정확한 구현 전에 Claude Code 공식
      문서(SessionStart 훅 스키마)를 WebFetch로 먼저 확인(훅은 전체 세션에
      영향을 주므로 추측으로 안 짬) — stdin에 `cwd` 필드가 있음을 확인 후 구현.
      (1) `~/.claude/hooks/ssot_session_context.py`(신규, SessionStart 훅) —
      `cwd`가 등록된 루트(또는 그 하위)와 겹치면 owner/scope/리뷰상태/
      primarySource경고/관련폴더(relations)를 additionalContext로 즉시
      주입. **그 폴더에 CLAUDE.md가 있는지 없는지, 최신인지와 완전히
      무관** — 레지스트리를 직접 읽으므로 파일 동기화가 밀려 있어도
      Claude Code만큼은 항상 최신. 전문(referenceCondition)은 안 박고
      포인터만(이 프로젝트 전체 원칙과 동일) — Claude Code가 필요하면
      레지스트리를 직접 Read. `~/.claude/settings.json`에 SessionStart
      항목 추가(matcher 없음 — startup/resume/clear/compact 전부 적용,
      컨텍스트 재주입이 특히 유용한 상황들이라 의도적으로 전부 포함).
      기존 ssot_index_reminder.py(PostToolUse, 반응형)의 자매 훅(선제형).
      (2) `SSOTExplorer._ensure_all_roots_initialized()`(main.py 신규 메서드,
      `__init__`에서 자동 호출) — 등록된 루트 중 init CLAUDE.md가 아예 없는
      것만 골라 자동 생성(add_root()가 신규 루트 1개에 하던 걸 앱 시작 시
      전체로 확장). 기존 파일 있으면(손편집이든 이미 동기화됐든) 절대
      안 건드림 — "없는 것만 채운다"라 SYNC_MARKER 확인조차 불필요.
이유: CLAUDE.md 파일 동기화(수동 버튼 클릭)에 의존하면 "안 눌렀다/밀렸다"
      만큼 Claude Code가 낡은 정보를 볼 위험이 있음 — 레지스트리를 세션
      시작 시 직접 읽는 훅이 그 위험을 구조적으로 없앤다. CLAUDE.md 생성
      기능 자체는 그대로 유지 — Cursor/Windsurf 등 훅 미지원 툴은 여전히
      물리 파일이 필요해서 폐기 대상이 아니라 상호보완 관계.
검증: `ssot_session_context.py`를 WebFetch로 확인한 정확한 stdin 스키마로
      파이프 테스트(Bash echo는 백슬래시 경로를 깨뜨려서 실패 — 파일
      리다이렉션으로 재시도해 실제 등록 루트 cwd에서 owner/scope/관련폴더
      3개가 정확히 포함된 additionalContext 생성 확인, 무관한 cwd에선
      조용히 빈 출력 확인). settings.json은 Python으로 JSON 유효성 +
      SessionStart 항목 존재 + 기존 PostToolUse 보존 확인(jq 미설치라
      대체). SessionStart는 세션 시작 시에만 발동해서 이번 턴 안에서 직접
      발동 증명은 불가(다음 세션부터 적용, 사용자에게 안내 필요) — 이건
      Claude Code 훅 자체의 구조적 한계.
      main.py 쪽은 test_main.py에 3개 추가(누락 루트에 실제 생성/기존
      파일 안 건드림/존재 안 하는 경로 조용히 건너뜀) — pytest 전체 70개
      통과. 실제 레지스트리(5개 루트, 전부 이미 init 있음)로 앱 smoke-test
      해서 "이미 있으면 아무것도 안 건드림" 경로도 실사용 데이터로 확인
      (파일 타임스탬프 불변 확인). exe 재빌드 후 동일 smoke-test 통과.

[D-032] router 오케스트레이션(단계별 캐스케이드+전체이력로그) + SessionStart 훅 보강
결정: 사용자가 "레지스트리JSON + 프로즈모음집JSON + 앱폐루프 + 구조화인덱싱을
      단계별로 내려가는 오케스트레이션(요청만 전달하는 파일)에 넣고, 그것도
      전체이력 로그를 폐루프 형식으로 남겨달라 + SessionStart 훅이 관련폴더
      뿐 아니라 등록루트 전체를 항상 알려줘야 하는 거 맞지" 요청.
      **원칙 충돌 확인 후 조율**: "README 내용을 구조화해서 앱에 종속"은
      D-014/D-015에서 사용자가 직접 정정한 "README 이관 금지" 원칙과
      충돌 — AskUserQuestion으로 확인, "일단 실시간 스캔, 나중에 DB
      붙으면 그때 구조화"로 합의(README 원본은 항상 그 폴더에만 있고,
      오케스트레이터가 매 요청마다 그 자리에서 열어서 검색만 함 — 복사/
      이관 없음, 원칙 안 깨짐).
      구현:
      - `router_orchestrator.py`(신규, "요청만 전달하는" 얇은 디스패처) —
        3단계 캐스케이드: (1) router_classifier.classify_content()(구조화)
        (2) 등록 루트 README.md 실시간 스캔(신규 `_find_readme`/
        `_prose_scan_signal`, main.py find_index_files와 같은 두 위치
        규칙, Qt 미의존) (3) router_proposals.is_trusted()/
        acceptance_rate() 주석(순위는 안 바꿈, 참고정보만). 같은 루트에
        여러 단계가 걸리면 신호를 합쳐서(신호 개수로도 순위 반영) 한
        후보로 병합.
      - 매 실행을 `ssot_orchestrator_log.json`에 원자적 쓰기로 기록
        (단계별 결과+최상위 후보+타임스탬프) — router_proposals 원자적
        쓰기 헬퍼를 `atomic_write_json`으로 공개 이름 변경해 재사용(3번째
        모듈에서 필요해져서 리팩터).
      - CLI(`python router_orchestrator.py --text "..." [--log-path ...]`)
        — router_classifier CLI와 같은 계약, 3단계 전부 거친 최종 결과.
        `--log-path`는 테스트 격리/로그분리용 신설 옵션.
      - `main.py`의 `SaveDocumentDialog.run_classification()`을
        router_classifier 단독 호출에서 router_orchestrator.orchestrate()
        호출로 교체 — GUI와 CLI가 정확히 같은 결과를 내게 통일(신뢰배지도
        이제 orchestrate()가 이미 채워주는 필드 재사용, 중복 호출 제거).
      - `~/.claude/hooks/ssot_session_context.py`(이 레포 밖) 보강 —
        발동할 때마다 relations 명시적 선언과 무관하게 "다른 등록 루트
        전체"(이름+경로) 목록을 항상 붙이고, 애매한 요청 시 오케스트레이터
        CLI 호출법도 안내 문구로 포함.
      [실측 개선 확인] D-030에서 실패했던 예시("이 대화 내용을 범용 코드
      프로젝트 규칙으로 만들어줘")를 오케스트레이터로 재실행 — 정답
      Coding_Nomal이 5순위(0.125)에서 공동 1위(0.5, README 프로즈매치로
      승격)로 올라옴. 다만 여전히 4파전 동점이라 "완전한 해결"은 아님 —
      정직하게 그대로 기록.
이유: 사용자가 지적한 "요청만 전달하는 파일"(오케스트레이터)로 계층을
      분리하면 판단 로직(classifier/proposals)은 안 건드리고 캐스케이드
      순서/로깅만 이 파일에서 관리할 수 있어 유지보수가 쉬움. README를
      복사 안 하고 실시간 스캔만 하는 건 이번 세션 초반에 이미 검증된
      원칙(D-014/D-015)을 지키면서도 정확도를 올리는 유일한 방법.
검증: test_router_orchestrator.py 신규 14개(README 두 위치 탐색 3개,
      신호 병합/합산 2개, 3단계 보고 확인, 물어보기원칙 연동, 신뢰폐루프
      주석 2개, 로깅 4개(누적/원자성/빈파일), CLI e2e 1개 — 전부
      --log-path로 실사용자 로그 격리). test_main.py는 기존 D-029/D-030
      테스트가 orchestrate() 경유로도 그대로 통과함을 재확인(인터페이스
      호환 유지). pytest 전체 84개 통과. 훅은 파일 리다이렉션으로 재검증
      (다른 등록 루트 4개 전체 목록 + 오케스트레이터 CLI 안내 문구 정상
      포함 확인). 실제 레지스트리로 CLI 수동 실행 후 결과 확인, 테스트
      생성 로그는 정리(실사용자 로그 오염 방지). 앱/exe smoke-test 통과.

[D-033] IDF 가중치 + floor→additive 전환 + 메타어휘 불용어 — 정밀도 2차 개선
결정: 사용자가 D-032 실측 결과("정답이 5순위→공동1위로만 개선, 완전 해결
      아님")를 보고 "더 정밀하게 할 방법이 있나?" 질문 → 원인 진단 후 2단계
      개선.
      **원인 진단**: 토크나이저 문제가 아니라 "점수를 고정값(floor)으로
      뭉개는 방식" — scope 신호/프로즈 신호가 걸리면 무조건
      `score = max(score, 0.5)`라 "코드"/"프로젝트"/"규칙"처럼 거의 모든
      루트에 흔한 단어만 걸려도 서로 다른 루트 4개가 정확히 0.5 동점이
      됨.
      **1차 개선 — IDF(역문서빈도) + additive**: `router_classifier.
      compute_idf()`(신규, 표준 TF-IDF 기법, 등록 루트 label+
      referenceCondition으로 문서빈도 계산) 도입 — 여러 루트에 흔한
      단어는 가중치 낮추고 소수 루트에만 있는 특이 단어는 높임.
      `_weighted_overlap_score()`로 키워드겹침 점수를 IDF 가중 비율로
      바꾸고, scope 신호는 `SCOPE_MATCH_BONUS=0.3`을 **더하는**(floor 아닌)
      방식으로 전환. router_orchestrator도 레지스트리+README를 합친 corpus
      로 IDF를 한 번 계산해서 1단계(classify_content에 idf 파라미터로
      전달)/2단계(프로즈매치)가 같은 가중치 기준을 쓰게 통일, 병합도
      `+=`(additive)로 전환.
      [실측] 재실행 결과 동점은 깨졌으나 방향이 잘못됨 — flutter_App이
      "내용을"/"대화" 두 단어만 겹쳐서 최고점(0.560), 정답 Coding_Nomal은
      4파전 그룹 안에서 오히려 꼴찌(0.219)로 밀림.
      **2차 개선 — 메타/요청 어휘 불용어**: 근본 원인 재진단 — "이 **대화
      내용을** ... 정리해서 만들어줘" 같은 요청 문장의 "내용을"/"대화"는
      주제와 무관한 요청 표현 자체인데, 등록 루트 설명 텍스트엔 마침
      드물게 나오는 말이라 IDF가 부당하게 높은 가중치를 줘버림(IDF는
      "드물다=중요하다"를 가정하는데, 이 경우 "드물다"의 원인이 "무관한
      요청형식 어휘"였다는 게 문제). `_STOPWORDS` 신설(내용/대화/관련/
      정리/만들어줘/해줘 등 메타 어휘), `tokenize()`가 걸러냄.
      [재실측] Coding_Nomal이 "4파전 꼴찌(0.219)"에서 **2등(0.442)**으로
      개선 — 1등(개발자 전용 어플, 0.596)과는 근소한 차이로 남음("코드"+
      "프로젝트" 2단어 겹침이 "범용"+"코드" 2단어 겹침보다 근소하게 앞섬).
      **여기서 멈추기로 판단**: 이 이상 정밀도를 올리려면 "가장 특이한
      단어 하나"가 결정적 신호가 되게 하는 재설계(가중합이 아니라
      최댓값/우세신호 기반)나 진짜 의미이해(AI)가 필요한 지점 — 휴리스틱
      키워드매칭의 자연스러운 한계로 판단, 이미 만들어둔 승인/취소
      폐루프(D-030 신뢰승급)가 실사용 데이터로 자연 보정할 영역으로 남김.
이유: "코드"/"프로젝트" 같은 범용 개발 어휘가 모든 루트 설명에 등장하는
      건 이 도메인(같은 사용자의 코딩 프로젝트 모음)의 구조적 특성이라,
      순수 빈도 기반 신호로는 한계가 뚜렷함 — IDF+불용어 조합까지가
      "새 의존성 없이, 이번 세션 예산 안에서" 합리적으로 개선 가능한
      선이라고 판단.
검증: test_router_classifier.py에 IDF 전용 테스트 2개(공통어 vs 특이어
      가중치 차이, 일반+특이 혼합매치가 일반매치 단독보다 높은 점수) 추가,
      기존 D-030 테스트 1개는 점수 고정값(0.5) 가정이 깨져서
      SCOPE_MATCH_BONUS 상수 참조로 수정. test_main.py 1개는 불용어 제거로
      질의가 짧아져 "물어보기" 분기로 새는 걸 발견해 질의 문구를 더 명확한
      것으로 교체. pytest 전체 86개 통과. 실제 등록 레지스트리로 CLI를
      3회 반복 실행(IDF만 적용 → 방향 오류 발견 → 불용어 추가 → 재검증)해서
      매번 실측 데이터로 개선/회귀를 직접 확인 — 추측으로 한 번에 끝내지
      않고 각 변경의 실제 효과를 데이터로 검증. 앱/exe smoke-test 통과.

[D-034] kiwipiepy(한국어 형태소 분석기) 이식 — O-007 재논의
결정: 사용자가 "형태소 툴 합치기 가능해?" 직접 요청 — O-007("아직 문제로
      확인 안 된 건 미리 안 고친다"고 보류)을 명시적으로 재논의. 이미
      로컬에 설치돼 있음을 확인(`pip install kiwipiepy` → already
      satisfied) 후 실제 tokenize 결과를 실측해서 효과 확인 후 착수.
      구현: `tokenize()`를 kiwipiepy 형태소 분석 기반으로 교체 — 명사류
      태그(NNG/NNP/SL/SH/SN)만 신호로 남기고 조사/어미/동사(JKO/EC/VV 등)
      는 자동 제외. "내용을"→"내용"(NNG)+"을"(JKO)로 분리되니 _STOPWORDS도
      동사활용형 항목(정리해서/만들어줘/해줘/합니다/있습니다 등, D-033에서
      개별 등록했던 것들)을 통째로 뺄 수 있었음 — 품사필터링이 자동으로
      처리. kiwipiepy 미설치/분석실패 시 예전 정규식 방식으로 자동 폴백
      (선택적 의존성 원칙 — router_classifier.py는 이 의존성 없이도 계속
      동작해야 함). Kiwi() 인스턴스는 모듈 전역 지연 싱글턴(초기화 ~1.4초
      +첫호출 ~0.2초 — CLI는 매 프로세스마다 이 비용 지불, GUI는 프로세스
      생존 동안 1회만).
      [버그 발견+수정] needs_clarification()의 대명사 감지가 tokenize()
      결과에 의존했는데, kiwi가 대명사(NP 태그, "이거"/"그거" 등)를 명사류
      밖으로 걸러내면서 `if not words: return False`에 먼저 걸려 "가장
      전형적인 애매한 요청"을 오히려 못 잡는 역설 발생 — 대명사 감지를
      tokenize() 결과가 아니라 원문 리터럴 부분매치로 분리해서 수정.
      [테스트 픽스처 문제 발견+수정] 기존 테스트들이 지어낸 복합어("특이어",
      "특수프로즈키워드" 등)를 썼는데, kiwipiepy는 미등록어를 문맥별로
      확률적으로 다르게 분할해서(같은 문자열이 앞뒤 맥락에 따라 다르게
      쪼개짐) 픽스처가 깨짐 — 전부 실제 국어사전 단어("보안"/"정책"/
      "고양이" 등)로 교체.
      [재실측] 실패 예시("이 대화 내용을 범용 코드 프로젝트 규칙으로
      만들어줘") 재실행 — Coding_Nomal이 "공동 2위"에서 **공동 1위**
      (flutter_App/coding_admin과 동점, 1.000점=상한)로 개선. 다만 새로운
      동점 상대(coding_admin)가 나타남 — coding_admin의 참조조건이 "코드_
      프로젝트_범용규칙과는 다르다"는 부정 비교 문장으로 그 이름을
      언급하는데, kiwi가 밑줄로 묶인 복합어를 "코드"+"프로젝트"+"범용"+
      "규칙" 4개 개별 명사로 정확히 분해하면서 이 "언급"이 오히려 더 잘
      잡히게 됨(예전 정규식 토크나이저는 밑줄을 \w로 취급해 통째로 한
      토큰이라 안 걸렸었음) — 형태소 분석의 정밀도 향상이 "언급 vs 실제
      소유" 문제(O-008)를 다른 방식으로 다시 드러낸 것. 정직하게 기록.
이유: 사용자가 O-007의 재논의 조건(정확도 부족 데이터 확인)을 기다리지
      않고 직접 재개를 요청 — 이미 로컬에 설치돼 있어 마찰 없이 검증
      가능했고, 실측해보니 "프로젝트를"/"프로젝트가" 통합 등 실질적 개선
      효과가 확인돼 진행이 타당했음.
검증: `pip install kiwipiepy`로 설치 확인(이미 설치돼 있었음). 실제
      tokenize() 결과를 스크래치에서 여러 문장으로 직접 확인(디버깅
      목적). pytest 전체 86개 통과(6개 실패 → 원인별 수정 → 재검증, 이번
      라운드도 추측 없이 실측 기반). 실제 등록 레지스트리로 CLI 재실행해서
      before/after 순위 변화 직접 확인. exe 빌드 시 `--collect-all
      kiwipiepy_model --collect-all kiwipiepy` 플래그 없으면 모델 파일이
      안 담겨 조용히 폴백되는 문제를 미리 인지하고 README 빌드 명령에
      반영 — exe 용량이 152MB로 커진 것으로 모델 파일이 실제 번들됐음을
      간접 확인. 앱/exe smoke-test 통과.

[D-035] 인수인계 노트 + 상용비교분석 재구성판을 웹 아티팩트 2개로 발행
결정: (1) 다음 세션이 그대로 이어받을 수 있는 "인수인계 노트"(구조 다이어그램
      + 핵심 파일 지도 + D-001~D-034 결정이력 개요 + 미결/TODO 요약 + 검증
      의식 + 원칙 + 붙여넣을 프롬프트 전문)를 새로 작성해 아티팩트로 발행.
      (2) D-027에서 만든 `SSOT_Explorer_상용비교분석.md`(220줄, 프로즈 위주)를
      사용자가 읽기 좋은 형태(축A/축B별 카드+색상 판정 태그, 각주 링크화)로
      재구성해 별도 아티팩트로 발행. 두 아티팩트 모두 이 md 파일들이 정본이고
      아티팩트는 "가독성 최적화 스냅샷"이라는 종속 관계로 문서 상단에 명시.
이유: 사용자가 두 URL을 지정하며 "여기에 현재 코드 구현도+프롬프트", "여기에
      최고급 사용작 정밀분석"을 요청. 다만 두 URL 모두 확인해보니 이미 다른
      프로젝트(Lazzy_App_OS/Hub_App_winter 자비스·AI Hub 경쟁력 진단, 각각
      2026-07-29/07-30 작성)의 완결된 아티팩트가 들어있었음 — 내가 쓰지 않은
      콘텐츠를 설명과 확인 없이 덮어쓰지 않는다는 원칙에 따라 먼저 사용자에게
      "URL1/URL2에 이미 SSOT_Explorer와 무관한 다른 리포트가 있는데 덮어써도
      되는지" 확인받았고, 둘 다 "덮어쓰기"로 명시적 승인받은 뒤 진행.
      "앱에 등록해줘"는 SSOT_Explorer 자체가 레지스트리에 별도 루트로 등록된
      게 아니라 Local_APP 루트 밑 sub-app 1개라서(`webArtifactUrl`/
      `primarySource` 필드는 루트 단위 스코프라 SSOT_Explorer 한 개만 가리키게
      쓰면 Local_APP 전체 10개 sub-app 스코프를 왜곡함) — 레지스트리 스키마를
      건드리지 않고 이 결정이력 문서 상단에 "관련 아티팩트" 링크로 등록하는
      쪽을 택함. 스코프가 안 맞는 필드에 억지로 넣는 것보다 정확함.
검증: WebFetch로 두 URL 기존 콘텐츠를 실제로 읽고 확인(추측 아님) → 충돌 발견
      → AskUserQuestion으로 사용자에게 명시적 확인받음(자동 진행 안 함) →
      승인 후 `Artifact` 도구로 `force:true` 발행 → 두 URL 다 발행 성공 확인.
      registry(`webArtifactUrl` 등)는 건드리지 않음 — grep으로 main.py의
      실제 사용처(377/417/498/508/767/1557행) 확인 후 루트 단위 스코프임을
      코드로 재확인하고 스키마 변경 안 하기로 판단.

[D-036] .cursorrules/.windsurfrules 최신 포맷 갱신 — H-006 구현
결정: D-027 상용비교분석에서 발견한 문제(H-006) 해결 — 사용자가 "P1으로 가자"
      요청. FORMAT_TARGETS를 튜플에서 딕셔너리(tool/resolver/legacy/
      frontmatter)로 확장하고, 새 항목 2개 추가:
      - `.cursor/rules/ssot-index.mdc`(Cursor 신포맷, MDC 프론트매터
        `alwaysApply: true` — 예전 플랫 `.cursorrules`가 항상 포함되던 동작과
        동등하게 유지)
      - `.windsurf/rules/ssot-index.md`(Windsurf 신포맷, 프론트매터
        `trigger: always_on`)
      기존 `.cursorrules`/`.windsurfrules`는 `legacy: True`로 남겨 완전 폐기는
      안 함(안(3) 채택) — `_write_one()`이 legacy 포맷은 파일이 이미 있을
      때만 갱신하고 신규 생성은 안 함(`skip-legacy` 결과). 디렉토리 포맷은
      `target.parent.mkdir(parents=True, exist_ok=True)`로 `.cursor/rules/`
      등 없는 디렉토리도 자동 생성. AGENTS.md는 코멘트/tool 라벨에서
      "30개+ 툴 네이티브 지원" 문구로 1차 공용 포맷 재포지셔닝(안(2), 코드
      구조 변경은 불필요 — 이미 딕셔너리 순서상 CLAUDE.md 다음이라 UI
      노출 순서는 그대로 유지).
      SyncFormatsDialog._write_one/sync_one/sync_all, 헤더 텍스트,
      툴팁까지 전부 갱신 — `.cursorrules`/`.windsurfrules` 하드코딩된
      언급을 전부 "Cursor/Windsurf 등"으로 일반화(포맷이 또 바뀌어도 문서
      텍스트가 안 낡게).
이유: 있는 기능이 이미 낡아서 실제로 최신 Cursor/Windsurf에서 안 읽힐 수
      있는 상태(H-006 원인)를 그대로 두면 "AI 툴별 동기화" 기능 자체가
      무의미해짐 — 우선순위 P1에 맞게 바로 진행. 레거시 완전 삭제 대신
      "있으면 유지, 신규는 안 만듦"으로 조율한 건 과거에 이미 만들어둔
      실사용 파일(있다면)을 갑자기 방치하지 않으면서도, 새 루트에는 낡은
      포맷을 안 심는 절충안.
검증: 신규 pytest 8개 추가(FORMAT_TARGETS에 신포맷 키 존재+legacy 아님 2개,
      레거시 2개 legacy=True 확인 1개, resolve_format_target 디렉토리 경로
      해석 2개, 실제 파일쓰기로 mdc 프론트매터/alwaysApply 확인 1개,
      windsurf trigger 확인 1개, 레거시 미존재시 skip-legacy+파일미생성
      확인 1개, 레거시 존재시 정상 갱신 확인 1개, sync_all 6개 포맷 전부
      보고+레거시 2개만 건너뜀 확인 1개) — pytest 전체 94개 통과. 앱
      smoke-test(`python main.py` 4초 실행 후 종료, ssot_explorer.log
      0바이트로 크래시 없음 확인) 통과.

[D-037] H-007(실행규격서 전면 재작성) + 상용비교분석 v2 재조사·아티팩트 갱신
결정: 사용자가 "h007 하고 이 앱을 최고급 상용작이랑 정밀 분석해서 하드코딩
      웹주소에 업데이트해줘(나아갈 방향, 잠재력, 그런것들)" 요청 — 두 작업
      동시 진행.
      (1) H-007: `SSOT_Explorer_실행규격서.md`를 main.py(1635줄) +
      router_*.py 4개 파일을 직접 다시 읽고 전면 재작성. 이전 판은
      "최종수정: 2026-08-13" 표기와 달리 실제 내용은 D-006 이전(레지스트리
      없음, 4개 하드코딩 루트, 읽기전용) 상태로 방치돼 있었음 — 레지스트리
      스키마 전체(9개 필드)/원자성+동시성/클래스 6개/router 모듈 4개 CLI
      계약/훅 3종/화면구성/pytest 94개 breakdown까지 지금 코드 기준으로
      새로 기록.
      (2) 상용비교분석 v2: WebSearch로 재조사(Cursor .mdc/Windsurf 프론트
      매터 스키마 재검증, AGENTS.md 채택현황, Claudia/opcode 근황, Backstage
      근황 + 신규 검색 "AI 규칙 라우터/자동분류 도구"). 발견:
      - **Ruler(intellectronica/ruler)**: v1 조사에 없던 오픈소스 도구 —
        `.ruler/` 마크다운 하나에서 여러 AI 툴 설정으로 자동 배포,
        SSOT_Explorer의 FORMAT_TARGETS와 정확히 같은 발상. MCP 설정 배포/
        생성파일 gitignore 자동화 등 SSOT_Explorer에 없는 기능도 보유 —
        "포맷 동기화" 축은 v1보다 독자성이 더 약해졌음을 정직하게 반영.
      - **opcode(옛 Claudia) 정체 확인**: 2026-01-23 리브랜딩 발표했지만
        실제 마지막 릴리스는 2025-08-31, 7개월간 업데이트 없음 — v1이
        "직접 경쟁 상대"로 정정했던 항목의 실사용 위협도가 낮아짐.
      - **라우터/오케스트레이션(D-029~034) 비교 대상 못 찾음**: "AI 문서
        자동분류" 재검색해도 전부 다른 층위(범용 파일정리 도구 등) —
        "세상에 없다"보다 "니치가 좁아 아무도 문제를 안 만들었다"로
        정직하게 해석.
      - v1이 지적했던 `.cursorrules`/`.windsurfrules` 결함은 D-036에서
        실제로 해소됐음을 반영(항목 검증 상태를 ⚠️→✅로 갱신).
      **나아갈 방향과 잠재력 재평가 섹션 신설**(사용자가 명시 요청) —
      결론은 v1과 동일("제품 잠재력은 낮음, 개인용 도구 가치는 높음")
      유지하되, 근거를 갱신: 포맷동기화 축은 더 나빠짐(Ruler), 경쟁압력은
      줄었지만 이건 자신의 성과가 아니므로 플러스로 안 침(정직성 조건),
      라우터가 유일한 신규 자산이지만 "제품 잠재력"으로 이어지려면 실사용
      데이터 검증이 먼저 필요하다고 명시. 나아갈 방향 4개 우선순위 권고
      (라우터 정확도 검증 > 포맷은 더 넓히지 말고 차별점에 집중 > 배포는
      여전히 후순위 > "안 낡게 유지"가 최우선) — 전부 기존 O-007/O-008/
      H-005/H-006 결정과 정합되게 구성, 새 방향을 창작하지 않음.
      `SSOT_Explorer_상용비교분석.md`를 v1→v2로 갱신(원본 md가 정본, D-035
      원칙 유지), 웹 아티팩트(115070d7-977d-4f0c-8e4f-54786416af7b)를 같은
      URL로 재발행(`Artifact` 도구 `url` 파라미터, 기존 링크 유지) — 디자인
      토큰(팔레트/타이포/카드 컴포넌트)은 기존 발행분과 동일하게 재사용하고
      콘텐츠만 갱신(정체성 일관성). README.md의 `.cursorrules/.windsurfrules`
      하드코딩 언급 2곳도 D-036 반영 누락이 발견돼 같이 정정(부수 수정).
이유: H-007은 "지금 코드가 정확히 어떻게 동작하는지"라는 이 문서 자체의
      원칙이 D-006 이후 8개 라운드(D-006~D-036) 동안 전혀 안 지켜지고
      있었다는 걸 D-036 직후 재확인한 것 — 더 미룰수록 실행규격서가
      코드와 멀어지는 폭이 커짐. 상용비교분석 v2는 "경쟁 구도는 시간이
      지나면 바뀐다"는 걸 실제로 보여준 사례(v1의 결함 지적→v2에서 해소
      확인, v1엔 없던 Ruler 등장, v1의 경쟁자가 v2엔 정체) — 일회성 분석이
      아니라 주기적으로 재검증해야 유효한 문서라는 걸 이번 라운드가
      실증했다.
검증: 실행규격서는 main.py grep(클래스/함수 시그니처, FORMAT_TARGETS,
      REGISTRY_PATH, 토큰 개수)으로 직접 대조 확인. 상용비교분석은 신규
      출처 8개(WebSearch 실시간, [11]~[19]) 전부 각주 URL 명시, 기존 출처
      10개 유지. 웹 아티팩트는 WebFetch로 기존 발행본 원문(HTML/CSS 전체)을
      먼저 읽어 디자인 토큰을 확인한 뒤 그 위에 콘텐츠만 교체 — "확인 없이
      덮어쓰지 않는다"(D-035) 원칙 유지, 발행 성공 확인(동일 URL 응답).
      pytest는 이번 라운드에서 코드 변경이 없어 재실행 생략(문서/README
      변경만).

[D-038] GitHub 원격 연결(H-005) + CI + 레지스트리 스키마 검증(잠재력 갱신
방향 #2/#3 실행)
결정: 직전 라운드에서 "잠재력을 올리려면 뭐가 필요한지" 질문에 4개 저비용
      항목(라우터 데이터축적/CI연결/스키마검증/포지셔닝)을 제시 → 사용자가
      "3번부터 진행해, 그사이에 깃허브 연결하고 올테니까"로 3번(스키마
      검증)을 지시하며 병행으로 GitHub 저장소를 직접 생성 → URL
      (`github.com/yhs01103-png/SSOT_EXplorer_index`)을 대화 중 전달받아
      원격 연결까지 같이 처리(2번도 자연스럽게 완료).
      (1) H-005 완료: `git remote add origin` + `git push -u origin master`
      로 로컬 D-001~D-037 전체 이력 푸시. `.github/workflows/tests.yml`
      신설(Lazzy_App_OS_Monorepo/server 패턴과 동일 구조) — push/PR마다
      ubuntu-latest에서 `pytest -q` 자동 실행. PySide6는 GUI 프레임워크라
      CI 러너에 디스플레이가 없어서 `QT_QPA_PLATFORM=offscreen`으로 xvfb
      없이 QApplication 인스턴스화(세션 스코프 qapp 픽스처가 이미 이렇게
      한 번만 만듦). Python 3.12 고정(3.14는 로컬 기준이나 kiwipiepy 등
      일부 의존성의 최신 CPython 휠 지원이 아직 안 늦을 수 있어 더 넓게
      지원되는 버전으로 낮춰 CI 실패 위험을 줄임). 저장소는 GitHub API로
      확인 시도했으나 404(비공개 저장소로 추정, WebFetch는 미인증이라
      확인 불가 — `gh` CLI도 이 환경에 미설치) — 실제 Actions 실행 결과는
      사용자가 GitHub 웹에서 직접 확인 필요.
      (2) 레지스트리 스키마 검증: `REGISTRY_SCHEMA`(JSON Schema draft-07)
      신설 — roots[]/sharedDocs[]/relations[] 각각의 필수 필드(label+path,
      fromPath+toPath)와 타입만 강제, `additionalProperties: True`로 미지
      필드는 항상 허용(실측: main.py가 안 읽는 `matchToken` 필드를 외부
      스크립트가 이미 쓰고 있음을 실제 레지스트리에서 확인 — 스키마가 이걸
      막으면 안 됨). scope는 D-018이 예시로 든 4개 값이 있었지만 enum 강제
      안 함(자유 프로즈 원칙 유지, D-018 하이브리드 그대로) — primarySource
      (local/web 2개 값만 코드가 실제로 분기)와 lastReviewed(YYYY-MM-DD
      패턴)만 형식을 강제. `validate_registry(data)`/`load_registry_raw()`/
      `format_schema_validation_text()` 신설, jsonschema는 kiwipiepy와 같은
      선택적 의존성 원칙(미설치 시 "검증 건너뜀" 문구만, 앱은 안 죽음).
      관리자 패널에 "스키마 검증" 뷰 신설(registry_view와 드리프트 로그
      사이) — `refresh()`가 매번 재검증해서 표시.
이유: 직전 라운드 잠재력 분석이 권고한 우선순위(1 라우터검증 > 2 CI >
      3 스키마 > 4 포지셔닝)를 사용자가 그대로 승인하고 실행 지시 —
      "안 낡게 유지"가 아니라 "격차를 실제로 좁히는" 라운드. CI/스키마
      둘 다 상용비교분석(D-027/D-037)이 "격차 큼"으로 지적한 항목을
      직접 겨냥.
검증: pytest 신규 9개 추가(스키마 정상케이스/필수필드누락/타입오류/
      enum+날짜형식오류/미지필드허용/텍스트포맷팅/raw로더 파일없음+
      라운드트립/관리자패널 통합) — 전체 94→103개 통과. 실제 사용자
      레지스트리(`flutter_App\.claude\ssot-roots.json`)로 `validate_
      registry()`를 직접 실행해 "✅ 검증 통과" 확인(추측 아닌 실측).
      git push 성공 확인(`* [new branch] master -> master`), 앱
      smoke-test(4초 실행, 크래시로그 0바이트) 통과.

[D-039] 공개 저장소 전환 준비 — 레지스트리 경로 이식성 + 개인정보 마스킹 +
MIT LICENSE
결정: 사용자가 "저장소 공개로 올려도 되나? 다운받아서 다른 클라이언트가
      써보고 리뷰받을 수 있게 해둬도 되나?" 질문 → 바로 승인/거부 대신
      먼저 코드/문서를 실제로 스캔해 3가지 문제를 확인 후 보고, Ask
      UserQuestion으로 각각 확인받고 진행(하드코딩 시크릿은 없음을 이미
      확인했지만, 공개 여부를 좌우하는 나머지 3가지는 사용자 판단 영역).
      (1) **경로 이식성(승인: "지금 고치고 공개")**: `main.py`의
      `REGISTRY_PATH`가 특정 사용자의 실제 OneDrive 절대경로로 하드코딩돼
      있어서, 남이 그대로 클론해 실행하면 앱이 텅 빈 상태로만 뜨고 제대로
      못 써봄(다운로드=가능, 실사용 리뷰=사실상 불가능했던 상태) — 이래선
      "다운받아서 써보고 리뷰"라는 목적 자체가 성립 안 함이라고 먼저 지적.
      `resolve_registry_path()` 신설(`SSOT_REGISTRY_PATH` 환경변수 우선,
      없으면 범용 기본값 `~/.claude/ssot-roots.json` — D-014 이전에 실제로
      쓰던 전역 위치로 복귀, 우연이 아니라 이미 검증된 값이라 재사용) —
      `router_classifier._default_registry_path()`도 동일 로직으로 통일
      (CLI/GUI 결과가 어긋나지 않게). 이 컴퓨터에서 실사용이 끊기지 않게
      `SSOT_REGISTRY_PATH`를 Windows 사용자 환경변수로 영구 등록(새
      터미널/재시작 세션부터 적용, 이번 세션엔 즉시 반영 안 됨 — OS
      환경변수의 구조적 한계, 사용자에게 안내 필요).
      (2) **개인 식별정보(승인: "공개 전에 정리")**: 코드/문서 전체를
      grep해 실제로 뭐가 노출되는지 먼저 목록화(추측 아님) — README/
      실행규격서에 있던 실제 OneDrive 경로 문구를 전부 제거하고 환경변수
      기준 설명으로 교체, README의 "현재 등록 루트(5개): ..." 줄(개인
      레지스트리 실제 내용 노출)을 삭제하고 일반 설명으로 대체. 결정이력의
      [D-016]은 절대경로+구체적 보관물 설명이 있던 유일한 항목이라 "공개
      전 마스킹" 표시를 명시적으로 남기고 내용만 가림(이력 자체를 조용히
      고치지 않는다는 이 프로젝트 정직성 원칙과, 개인정보 보호 요청이
      충돌하는 지점이라 "왜 가렸는지"를 이렇게 흔적으로 남기는 절충안
      채택). 나머지 결정이력 본문(flutter_App/Local_APP/Coding_Nomal/
      개발자 전용 어플 같은 프로젝트 코드네임 언급)은 그대로 둠 — 실제
      경로/내용이 아니라 라벨 수준이라 위험도가 낮고, 1000줄 넘는 이력
      전체를 다시 쓰면 이 문서가 기록으로서 갖는 가치 자체가 훼손된다고
      판단(사용자에게 "이 정도까지만 했다"를 투명하게 보고 — 더 철저한
      비공개를 원하면 이 문서 자체를 공개 레포에서 빼는 대안도 있다고
      같이 안내).
      (3) **LICENSE(승인: "MIT 추가")**: 루트에 `LICENSE`(MIT, 2026,
      GitHub 아이디 `yhs01103-png` 기준 — 실명이 아니라 이미 저장소 URL
      자체로 공개돼 있는 식별자를 재사용) 신설, README에 배지 추가.
이유: "공개해도 되냐"는 질문에 즉답하지 않고, 먼저 실제로 뭐가 노출되는지
      grep으로 확인한 뒤 사용자가 결정할 수 있게 구조화해서 물어본 것 —
      되돌리기 어려운(공개했다가 비공개로 돌려도 그 사이 캐시/포크는 회수
      안 됨) 작업이라 추측이나 임의 판단으로 진행하지 않는다는 원칙
      그대로. 저장소 공개/비공개 전환 자체는 GitHub Settings 영역이라
      이 세션 권한 밖(gh CLI 미인증) — 코드/문서 준비까지만 담당.
검증: pytest 신규 3개(`resolve_registry_path` 환경변수/기본값 분기 2개,
      router_classifier 기본경로가 main.py와 일치 1개) — 전체 103→106개
      통과. 실제로 환경변수 설정/해제 양쪽으로 `main.py`를 직접 실행해
      REGISTRY_PATH가 각각 올바르게 갈리고, 미설정 시 빈 목록으로 조용히
      시작함(크래시 없음)을 실측 확인. grep으로 README/실행규격서에서
      개인 경로 문자열 전부 제거됐음을 재확인. 앱 smoke-test 통과.

[D-040] 공개 준비 마무리 — 신선 클론 검증 + exe 재빌드
결정: 사용자가 "exe 빌드까지 해준거지? + 다음스탭가자" 질문 → 확인해보니
      `dist\SSOT_Explorer.exe`가 그날 새벽(01:52) 빌드본으로 D-036~D-039가
      전혀 반영 안 된 상태였음을 그대로 보고(안 했으면서 했다고 안 함) —
      곧장 두 가지 진행.
      (1) **신선 클론 검증**: 스크래치 폴더에 GitHub 원격에서 실제로
      `git clone`(공개/비공개와 무관하게, 이 계정 권한으로) → `SSOT_
      REGISTRY_PATH` 환경변수 없이(`env -u`) `pytest -q`(106개 통과) +
      `python main.py` 실행 — 빈 레지스트리로 조용히 기동(크래시 없음)까지
      실측 확인. "다운받아서 다른 사람이 써볼 수 있는 상태"라는 D-039의
      목표를 말로만 아니라 실제 재현으로 검증한 것.
      (2) **exe 재빌드**: `python -m PyInstaller --collect-all kiwipiepy_model
      --collect-all kiwipiepy ...` 재실행 시도 → `PermissionError`로 1차
      실패, 원인 확인 결과 **예전 exe 프로세스 2개가 3시간 넘게 실행 중**
      (PID 5192/12648, 11:43 시작 — 사용자가 H-004 겸 직접 열어보고 있었을
      가능성)이라 파일이 잠겨 있었음. 사용자 것일 수 있는 실행 중인 창을
      확인 없이 강제 종료하지 않고 먼저 물어봄 → "닫아주고 재빌드"로 명시
      승인받은 뒤 종료 + 재빌드. 새 exe(160,927,198 bytes, 15:21) 생성 확인,
      더블클릭과 동등한 방식(직접 실행)으로 스모크테스트 — 크래시로그
      0바이트, 프로세스 정상 기동 확인 후 테스트 인스턴스는 정리(종료).
이유: "빌드까지 해준거지?"라는 확인 질문에 실제로는 안 했으면서 넘어가지
      않고 사실대로 보고한 뒤 즉시 처리 — 이 프로젝트 전체의 정직성 원칙
      (검증 안 한 걸 했다고 안 함)이 이번에도 그대로 적용됨. 실행 중인
      타인(사용자)의 프로세스를 임의로 안 죽이고 확인받은 것도 같은 원칙의
      연장(하드 리버스 어려운 동작 전 확인).
검증: 위 서술 자체가 검증 기록 — 클론 테스트(pytest 106개+실행 크래시없음),
      exe 빌드 로그 exit code 0, exe 실행 후 로그파일 0바이트, 프로세스
      리스트로 좀비 인스턴스 없음 재확인.
      H-004(exe 더블클릭 실행 확인)는 이번에 "직접 실행"까지는 확인됐으나
      "사용자 본인이 탐색기에서 더블클릭"은 여전히 별개 확인 필요 — 새
      빌드본 기준으로 TODO 유지.

[D-041] H-003 구현 — 대소문자 중복 인덱스 파일 방어 코드
결정: "코드적으로 다음 스텝" 3개(코드리뷰→H-003→O-006 경량화) 순서 승인받고
      2번째로 진행. 원 결정문의 "보류 — 실제 문제 재현 시" 원칙을 사용자가
      명시적으로 뒤집어 지금 방어 코드로 미리 달아두기로 함.
      `find_index_files()`의 `found.setdefault(entry.name.lower(), entry)`가
      같은 폴더 안에서 대소문자만 다른 두 파일이 동시에 걸리면 OS 디렉토리
      순회 순서에 의존해 비결정적으로 하나만 남기고 있었음(Windows에서는
      파일시스템 자체가 대소문자를 구분 안 해 이 상황이 물리적으로 발생
      불가능하지만, 이 프로젝트는 크로스플랫폼을 표방(D-019/D-039)해서
      대소문자 구분 파일시스템에선 실제로 벌어질 수 있음).
      `pick_canonical_index_file(key, paths)`(순수 함수, 디스크 접근 없음)로
      분리 — `CANONICAL_INDEX_NAMES`(`CLAUDE.md`/`README.md`) 우선 채택,
      둘 다 비표준 표기면 이름 사전순으로 결정적 선택. `find_index_files`는
      이제 같은 base 안에서 같은 lower-key로 여러 개가 잡히면 이 함수로
      해소하고, 어느 게 무시됐는지 `log.warning`으로 남김(D-025 로깅 인프라
      재사용). 함수 docstring의 개인 예시("flutter_App 등")도 D-039 정신에
      맞춰 일반화(부수 정리).
이유: 재현 안 된 이론상 버그를 미리 고치는 게 이 프로젝트의 기존 원칙
      ("아직 문제로 확인 안 된 건 미리 안 고친다", O-007 등에서 반복)과는
      결이 다르지만, 사용자가 이번엔 명시적으로 그 원칙을 접고 방어코드를
      요청 — 비용이 낮고(순수 함수 분리+피드백 로깅뿐, 기존 동작 변경
      없음) 크로스플랫폼 표방과 직접 관련된 항목이라 타당한 예외로 판단.
검증: pytest 신규 6개(canonical 우선 선택 2개, 정상 단일파일 케이스,
      플랫vs.claude 하위 우선순위, 실제 케이스-센서티브 파일시스템 없이도
      회귀 검증하는 iterdir/is_file 목업 통합테스트, 존재 안 하는 폴더)
      — 전체 106→112개 통과. 앱 smoke-test(크래시로그 0바이트) 통과.

================================================================
PART 2 — TODO
================================================================

🔴 P0/P1
(없음 — MVP 최초 커밋 상태)

🟡 P2
✅ H-001  실제 GUI 렌더링 육안 확인               | 2026-08-12
  대상: main.py 전체
  사용자가 직접 python main.py 실행해서 확인하기로 함(개발측은 백그라운드
  실행+크래시 없음까지만 검증).

✅ H-002  Local_APP CLAUDE.md 인덱스 표에 SSOT_Explorer 행 추가  | 2026-08-12
  대상: Local_APP\CLAUDE.md
  표에 SSOT_Explorer 행 추가 완료, 전용 규칙 "있음"으로 표시.

✅ H-004  exe 실제 더블클릭 실행 확인(사용자)  | 2026-08-14
  대상: dist\SSOT_Explorer.exe (D-040 재빌드본, 160.9MB)
  사용자가 GitHub 공개 전환과 함께 직접 더블클릭 실행 확인 완료.

✅ H-003  대소문자 중복 방지(같은 폴더에 CLAUDE.md와 claude.md가 동시에 있는 경우)  | 2026-08-14
  대상: main.py의 find_index_files() / pick_canonical_index_file()
  D-041에서 구현 완료 — 사용자가 "보류" 원칙을 뒤집고 방어코드 요청.
  CANONICAL_INDEX_NAMES 우선 채택 + 결정적 폴백, log.warning으로 무시된
  파일 기록.

✅ H-005  GitHub 원격 저장소 연결 + CI(.github/workflows/tests.yml, Lazzy 패턴)  | 2026-08-14
  대상: 저장소 전체
  D-038에서 완료 — origin=github.com/yhs01103-png/SSOT_EXplorer_index,
  push 성공(D-001~D-037 전체 이력) + tests.yml 신설. Actions 실제 실행결과는
  비공개 저장소로 추정(API 404, gh CLI 미설치라 이 환경에서 미확인) — 사용자
  GitHub 웹에서 최초 실행 결과 확인 필요.

✅ H-006  .cursorrules/.windsurfrules 최신 포맷으로 갱신 + AGENTS.md 1차 포맷화  | 2026-08-14
  대상: main.py의 FORMAT_TARGETS, SyncFormatsDialog
  D-036에서 구현 완료 — 안(1)(2)(3) 전부 반영. `.cursor/rules/ssot-index.mdc`
  (alwaysApply 프론트매터) + `.windsurf/rules/ssot-index.md`(always_on
  프론트매터) 신설, 레거시 `.cursorrules`/`.windsurfrules`는 "있을 때만
  동기화, 신규 생성 안 함"으로 유지. pytest 94개 통과, smoke-test 통과.

✅ H-007  SSOT_Explorer_실행규격서.md 전면 재작성  | 2026-08-14
  대상: SSOT_EXP_설계도\SSOT_Explorer_실행규격서.md
  D-037에서 완료 — main.py/router_*.py 직접 재확인 후 D-001~D-036 전체
  반영해 전면 재작성(레지스트리 스키마/원자성+동시성/클래스구조/CLI계약/
  훅3종/pytest94개 breakdown까지).

================================================================
=== 미결 (O-번호, OPEN) ===
================================================================
Lazzy_App_OS_Monorepo(프로젝트_설계도_SSot\Jarvis_결정이력_TODO.md)의 O-번호
관례를 이식(D-023) — "알지만 지금은 실행 안 하기로 한 것"을 형식 갖춰 기록.
형식: [O-번호] 제목 / 임시결정 / 재논의 조건 / 관련 D-번호.

[O-003] 등록 스코프를 "루트 바로 밑 프로젝트 폴더"에서 서브프로젝트(레포 안
레포, 예: Lazzy_App_OS_Monorepo의 server/.claude, client/.claude)까지 확장할지.
임시결정: 확장 안 함 — 지금 스코프 유지. Lazzy_App_OS_Monorepo 자체는
flutter_App 루트 밑 "바로 밑 프로젝트 폴더" 1개로만 잡히고, 그 안의
server/.claude/CLAUDE.md·client/.claude/CLAUDE.md 2개는 여전히 SSOT_Explorer
레지스트리 밖(사람이 손으로 직접 관리) — "마스터본은 이미 로드돼있다" 문구가
3곳(root/.claude, server/.claude, client/.claude)에 거의 동일하게 손으로
복붙돼 있어 어긋날 여지가 있으나, 아직 실제 불일치 사고는 없음.
재논의 조건: 이 3개 CLAUDE.md 사이 실제 불일치가 발견되거나, 비슷한 서브프로젝트
구조(레포 안 레포)를 가진 다른 루트가 늘어나 일반화 가치가 커질 때.
관련 D-번호: D-023.

[O-004] Lazzy_App_OS_Monorepo에 SSOT_Explorer식 드리프트 감지/리뷰 신선도
체크(REVIEW_STALE_DAYS)를 적용할지.
임시결정: 적용 안 함 — Lazzy는 결정이력을 매 세션 사람이 직접 갱신하는
프로세스가 이미 확고하게 작동 중이라 자동 감지의 한계효용이 낮음.
재논의 조건: Lazzy 결정이력 갱신이 실제로 누락되는 사고가 발생하거나, 문서가
더 커져서(현재 Jarvis_Server_결정이력_TODO.md 216KB) 수동 관리 부담이 한계에
달할 때.
관련 D-번호: D-023.

[O-005] Lazzy_App_OS_Monorepo 결정이력 md에도 D-021식 원자적 쓰기+낙관적
동시성 제어를 적용할지.
임시결정: 적용 안 함 — Lazzy 쪽 편집은 전부 사람이 Claude Code 세션 중 Edit
툴로 직접 하는 방식이라 save_roots() 같은 프로그램적 자동 저장 경로가 없어
리스크 표면이 다름(D-021은 "여러 기기의 서로 다른 프로세스가 같은 파일에
자동 저장" 문제, Lazzy는 "여러 세션의 사람이 같은 파일을 손으로 편집" 문제).
게다가 결정이력 4개 파일은 git 비커밋 정책이라 애초에 커밋 충돌 리스크 자체가
낮게 설계돼 있음.
재논의 조건: 여러 기기에서 동시에 Lazzy 세션을 열고 같은 결정이력 파일을
편집하다 실제로 내용이 유실되는 사고가 생기면 재검토.
관련 D-번호: D-021, D-023.

[O-006] router_watcher.py의 InboxWatcher 실제 구현(새 파일 자동감지) +
분류기를 AI(Claude API 등)로 교체.
임시결정: 둘 다 스켈레톤만(D-029) — 실제 감시는 InboxWatcher.start()가
NotImplementedError, 분류는 휴리스틱(키워드 겹침) v1만. 사용자가 명시적으로
"이번엔 틀만 구축"을 요청해서 의도된 보류.
재논의 조건: 휴리스틱 분류기의 제안 승인율(router_proposals.acceptance_rate())
이 실사용으로 충분히 쌓여서 "휴리스틱으론 한계"가 데이터로 확인되거나,
감시 대상 Inbox 폴더 운영 방식(어디를 감시할지, watchdog 의존성 추가 여부)
이 먼저 정해지면 착수. 실제 붙일 때 감안할 것: 전체 드라이브 감시는
노이즈가 너무 커서 비현실적 — 지정된 Inbox 폴더 1~2개로 한정, Qt 이벤트
루프 안 막게 별도 스레드/프로세스, 디바운스 필요(router_watcher.py 상단
주석에 이미 적어둠).
관련 D-번호: D-028, D-029.

[O-007] router_classifier.py의 토크나이저를 kiwipiepy(한국어 형태소
분석기)로 교체.
임시결정: 지금은 단순 정규식 분리(`[\w가-힣]+`)만 — 조사/어미가 안 떨어져
나가서 "프로젝트를"과 "프로젝트가"가 다른 토큰으로 잡히는 등 정확도
한계가 있음. Lazzy_App_OS_Monorepo가 뉘앙스 톤 자동조절(D-SERVER-063)에
이미 kiwipiepy를 실전 채택한 선례가 있어 이식 후보로 적합.
재논의 조건: O-006과 마찬가지로 휴리스틱 v1의 정확도가 실사용상 부족함이
데이터(acceptance_rate 낮음)로 확인되면. 그 전엔 새 의존성(kiwipiepy)을
미리 넣지 않음 — 아직 문제로 확인 안 된 것을 앞서 고치지 않는다는 원칙.
[실측 사례, D-030] CLI로 실제 등록 레지스트리에 "이 대화 내용을 범용 코드
프로젝트 규칙으로 정리해서 만들어줘"를 넣어보니 정답(Coding_Nomal\코드_
프로젝트_범용규칙)이 5순위(0.125점)로 밀리고, 그 폴더를 교차참조로
"언급"만 한 flutter_App이 1순위(0.5점)로 나옴 — flutter_App의
referenceCondition 프로즈 안에 정답 폴더 이름이 그대로 적혀 있어서
키워드가 우연히 더 많이 겹친 것. 토크나이저 문제(조사 분리)보다는
"언급 vs 실제 소유"를 구분 못 하는 더 근본적인 한계로 보임 — kiwipiepy
만으론 안 풀릴 수 있고, 신호 가중치 재설계(예: referenceCondition 안에서
그 루트 "자기 자신"을 가리키는 문장에 더 높은 가중치)가 같이 필요할 수
있음. 재논의 판단에 참고할 것.
[갱신, D-033] IDF+불용어까지 적용해서 재실측 — 정답이 최하위에서 공동
2위까지 올라옴(더는 최하위 아님). "언급 vs 소유" 구분 문제는 여전히
완전히는 안 풀림(개발자 전용 어플이 근소하게 1위 유지) — kiwipiepy가
지금 시점에 이 특정 문제를 풀어줄 가능성은 낮다고 재확인(조사분리
문제가 아니라 "어떤 단어가 결정적 신호인지" 판단의 문제). O-008 참고.
관련 D-번호: D-029, D-030, D-033.

[O-008] 신호 결합 방식을 가중합(weighted sum)에서 최댓값/우세신호
(max-signal) 기반으로 재설계하거나, AI(Claude API) 기반 판단으로 교체.
임시결정: 지금은 가중합(IDF 가중치들을 더해서 비교) — "코드"+"프로젝트"
2단어 겹침이 "범용"+"코드" 2단어 겹침을 근소하게 이기는 것처럼, 매치
개수가 개별 단어의 특이도보다 결과에 더 큰 영향을 줄 수 있음(D-033
실측). "가장 특이한 단어 하나"가 결정적이어야 하는 경우엔 가중합이
부적합할 수 있음.
재논의 조건: router_proposals.acceptance_rate()로 실사용 승인율 데이터가
쌓여서 특정 패턴(예: "여러 루트가 근소한 점수차로 경합하는 질의")의
실패율이 눈에 띄게 확인되면. 그 전엔 이론적 추측만으로 재설계 안 함 —
D-033에서 이미 "추측 대신 매 변경을 실측으로 검증"한 방식을 유지.
관련 D-번호: D-030, D-033.

================================================================
변경이력
================================================================
v1.0 (2026-08-12): 최초 스캐폴딩. 읽기 전용 MVP 구현 완료, 설계 문서 초기화.

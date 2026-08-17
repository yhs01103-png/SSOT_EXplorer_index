================================================================
SSOT Explorer — 상용/표준 비교분석 (v3, 2026-08-17 갱신)
================================================================
인프라 성숙도 × 기능 완성도 정밀 대조 + 나아갈 방향/잠재력 재평가

두 축으로 지금 앱을 잰다 — (A) 인프라·엔지니어링 관행을 동종 카테고리
상용/오픈소스 제품과, (B) 기능·개념 완성도를 "이상적인 개인용 SSOT 레지스트리
도구"(Backstage+Ruler/RuleSync+AGENTS.md 표준의 장점을 합친 합성 이상향)와
대조한다. Lazzy_App_OS_Monorepo의 `아이언맨_자비스_비교분석.md` 방법론을
그대로 이식(D-023).

- **v1 기준일**: 2026-08-13 (대상: D-001~D-026)
- **v2 기준일**: 2026-08-14 (대상: D-001~D-036 — router 오케스트레이션/
  relations/SessionStart 훅/IDF+kiwipiepy/H-006 포맷 갱신까지 반영)
- **v3 기준일(이 문서)**: 2026-08-17 (대상: D-001~D-055 — GitHub CI+
  레지스트리 스키마 검증(D-038)/Inbox 감시(D-042)/맥락형 인덱싱 5단계
  확장(D-044)/MCP 서버 신설+Claude Code 등록(D-048~050)/경로 삭제·이동
  감지(D-052)/QThread 분리·CLI·원자적쓰기 리팩터(D-051, D-053~055)까지
  전부 반영, 사용자 요청으로 재조사)
- **근거**: 코드 직접 확인(main.py/router_*.py/ssot_mcp_server.py/
  test_*.py) + WebSearch(2026-08-17 실시간 검색, 출처 각주 표기) — 추측
  없음

---

## 방법론 — 정직성 조건

**(A) 상용/오픈소스 제품** — Backstage(Spotify/CNCF), RuleSync, Ruler
(intellectronica/ruler), AGENTS.md 표준(Linux Foundation Agentic AI
Foundation)에 대해 **공개적으로 검색 확인된 사실**만 기준으로 삼는다.
내부 구현을 안다고 주장하지 않는다.

**(B) 이상적 SSOT 레지스트리 도구** — 실존 단일 제품이 아니라 합성 이상향.
방향성 지표로만 쓴다.

SSOT_Explorer 쪽 사실은 전부 실제 코드(`main.py`, `router_*.py`,
`ssot_mcp_server.py`, `test_*.py`) 기준.

---

## 축 A — 인프라 · 엔지니어링 성숙도

### 회귀 테스트 / CI — `v3: 격차 좁혀짐(CI 실제로 생김)` 📈
- **SSOT_Explorer**: pytest **192개**(v2 시점 94개 → 2배+ 증가 — D-038
  스키마 검증 9개, D-048~052 MCP/드리프트 관련, D-051~055 QThread/CLI/
  원자적쓰기 리팩터 회귀테스트 등이 계속 합류). **D-038(2026-08-14, 이
  문서 v2 갱신 직후)에서 GitHub 원격 저장소 연결 완료**
  (`github.com/yhs01103-png/SSOT_EXplorer_index`) + `.github/workflows/
  tests.yml` 신설 — push/PR마다 ubuntu-latest에서 `pytest -q` 자동 실행
  (`QT_QPA_PLATFORM=offscreen`으로 xvfb 없이 QApplication 인스턴스화).
  다만 실제 Actions 실행 결과는 저장소가 비공개로 추정돼 API/WebFetch로
  확인 불가 — 사용자가 GitHub 웹에서 직접 확인 필요(H-005 노트 그대로
  미확인 상태 유지). 로컬 브랜치가 origin보다 여러 커밋 앞서 있어 최신
  코드(D-053~055 포함)는 아직 원격에 안 올라감.
- **비교 기준**: Backstage/RuleSync/Ruler 전부 GitHub Actions CI, 태그된
  릴리스, 이슈트래커 보유. "CI 자체가 없다"는 v2까지의 격차는 실제로
  좁혀졌다 — 다만 "CI 파일은 있는데 실행 성공 여부가 검증 안 됨"이라는
  새로운 성격의 잔여 격차로 바뀌었을 뿐, 완전히 해소된 건 아니다.

### 배포/설치 방식 — `격차 작음(용도가 다름), 불변`
- v2와 동일 — PyInstaller onefile exe, GUI 전용이라 CI/자동화 파이프라인에
  못 끼워넣는다는 약점도 그대로. router CLI(`router_classifier.py`/
  `router_orchestrator.py --text`)는 여전히 GUI 없이 단독 실행 가능하고,
  이제 **MCP 서버(`ssot_mcp_server.py`, D-048)로도 같은 종류의 데이터를
  세션 중 직접 호출**할 수 있게 됨(아래 신규 섹션 참고) — "GUI 없이 쓸 수
  있는 경로"가 CLI 한 갈래에서 두 갈래로 늘었다.

### 레지스트리 스키마 성숙도 — `v3: 격차 좁혀짐(0→있음)` 📈
- **SSOT_Explorer**: v2까지 "스키마 검증 없음"이었으나 **D-038에서
  JSON Schema(draft-07, `REGISTRY_SCHEMA`) 검증 신설** — `roots[]`/
  `sharedDocs[]`/`relations[]` 필수 필드+타입, `primarySource`/
  `lastReviewed` 형식 강제, `additionalProperties: True`로 미지 필드는
  항상 허용(외부 스크립트가 이미 쓰는 `matchToken` 같은 필드를 안 막기
  위함). 관리자(개발자) 탭에 검증 결과 뷰 신설.
- **비교 기준**: Backstage의 `catalog-info.yaml` 정식 스키마+250개+
  플러그인 생태계[1][2] 대비 여전히 "파일 1개짜리 경량 검증"인 건
  규모상 당연(1인 개인용 vs 3,400개+ 회사가 쓰는 엔터프라이즈
  플랫폼[1]) — "격차 큼·불변"에서 "격차는 있으나 0은 아니게 됨"으로
  성격만 바뀜, 리그 자체가 다르다는 결론은 유지.

### 동시성 안전성 — `격차 없음 · 상대적 강점, 불변`
- v2와 동일 — 원자적 쓰기 + 낙관적 동시성 제어(D-021). **D-055에서
  저수준 temp+os.replace() 구현을 `router_proposals.atomic_write_json()`
  하나로 통합**해 두 파일에 흩어져 있던 구현이 하나로 좁혀짐(내부
  리팩터, 외부 비교에는 영향 없음). Ruler/RuleSync는 단발성 CLI
  실행이라 이 문제 자체가 성립 안 함.

### 로깅/오류 가시성 — `격차 없음, 불변`
- v2와 동일(D-025). **D-052에서 등록 루트 경로 삭제/이동 감지가 드리프트
  로그/개발자 탭/MCP 3곳에 동일 신호로 노출**되도록 확장 — "감지→알림만,
  실제 변경은 사람 승인"이라는 이 프로젝트 일관 원칙 위에서 가시성만
  더 넓힌 것.

---

## 축 B — 기능 · 개념 완성도

### 멀티 AI툴 규칙 동기화 — `격차 있었으나 코드 결함은 해소됨(D-036)` ✅
- **SSOT_Explorer**: CLAUDE.md/AGENTS.md/Cursor(`.cursor/rules/*.mdc`,
  `alwaysApply: true`)/Windsurf(`.windsurf/rules/*.md`,
  `trigger: always_on`) — D-036에서 디렉토리 신포맷으로 갱신, 레거시
  `.cursorrules`/`.windsurfrules`는 있을 때만 유지. v2 이후 포맷 자체의
  추가 변경은 없음(안정 상태).
- **RuleSync**: 8개 포맷 지원[3][4] — 여전히 SSOT_Explorer(6개)보다 넓다.
- **Ruler(intellectronica/ruler)** — v3 재확인 결과 **여전히 활발하게
  유지보수 중, MCP 관련 기능은 오히려 더 심화됨**: 최신 릴리스(v0.3.44
  계열)에서 "에이전트별(per-agent) MCP 서버 설정", "커스텀 MCP 서버
  필드 보존", "에이전트 스코프 MCP 서버 타입 검증" 등이 추가돼 "여러 AI
  툴에 MCP 설정을 나눠 배포"하는 기능이 v2 시점보다 더 정교해졌다[20].
  **단, 이건 여전히 "설정 배포" 방향** — Ruler 자신이 MCP 서버가 돼서
  자기 데이터를 노출하는 게 아니라, 여러 컨슈머 툴에 각자 맞는 MCP 설정
  파일을 나눠주는 것. 아래 신규 섹션(SSOT_Explorer의 MCP 서버)과는
  방향이 정반대라 직접 경쟁이 아니다. Ruler에 없는 것(SSOT_Explorer에
  있는 것)은 v2와 동일 — 레지스트리 통합관리/손편집보호/리뷰신선도/
  relations/라우터/MCP 서버(자기 데이터 노출).
- **더 큰 흐름 재확인**: AGENTS.md는 **60,000개+ 저장소, 20개+ 툴이
  네이티브로 읽는 표준**[16] — v3 재검색에서도 숫자가 그대로 재확인됨,
  드리프트 없음(이미 정착된 상태가 유지 중이라는 뜻으로 해석).

### CLAUDE.md 스캐너를 갖춘 GUI 앱(Claudia/opcode) — `경쟁 압력 정체 지속 재확인` 📉
- v3 재확인 결과: **opcode(Claudia 개명)는 여전히 v0.2.0(2025-08-31
  릴리스)이 최신 — 2026-08-17 기준으로도 새 릴리스 없음**, GitHub
  릴리스 페이지에서 직접 재확인함[21]. v2가 지적한 "7개월 가까이
  업데이트 없음"이 지금은 "1년 가까이"로 더 길어진 상태 — 정체가 일시적
  소강이 아니라 지속 패턴임이 재확인됨.
- **의미**: v2 결론이 그대로 유지·강화됨 — 최소 기능(CLAUDE.md 스캐너)을
  가진 직접 경쟁 앱의 실사용 위협도는 계속 낮은 채로 남아있고,
  SSOT_Explorer는 이 3일 사이에도 D-037~D-055(19개 결정)를 처리해
  갱신 속도 격차가 더 벌어졌다.

### 🆕 라우터/오케스트레이션 — `5단계로 확장, 비교 대상 여전히 못 찾음`
- v2 시점 3단계(구조화 신호+프로즈검색+신뢰폐루프)였던 파이프라인이
  **D-044에서 5단계로 확장**(+키워드/태그 자동승급 레지스트리, +임베딩
  스켈레톤 — 실제 임베딩 프로바이더 연결은 O-009로 보류). 텍스트를
  붙여넣으면 등록된 여러 프로젝트 루트 중 어디로 보내야 할지 자동
  제안 — 항상 사용자 승인이 있어야 실제 저장(P-01 예외, D-029).
  v3에서도 "AI 코딩 어시스턴트 + 문서 자동 분류" 계열로 재검색했으나
  결론은 v2와 동일 — 여러 독립 코딩 프로젝트 레지스트리 중 규칙 SSOT와의
  프로즈 유사도로 목적지를 고르는 이 좁은 문제 정의에 맞는 상용 비교
  대상은 이번에도 안 나옴. "세상에 없는 걸 만들었다"보다 "니치가 너무
  좁아서 상용 제품이 이 문제 자체를 정의할 유인이 없었다"는 정직한
  해석을 유지.

### 🆕 v3 신규 발견 — MCP 서버로 앱 데이터 자체를 노출(D-048~050, D-052)
- **SSOT_Explorer**: `ssot_mcp_server.py`가 `list_ssot_roots`/
  `check_readme_freshness`/`classify_content` 3개 tool을 MCP로 노출 —
  Claude Code(또는 임의 MCP 클라이언트)가 세션 중 이 앱을 열지 않고도
  등록 루트 목록/README 신선도/자동분류 제안을 직접 호출해서 받을 수
  있다. **2026-08-17 사용자가 실제 새 세션에서 등록·연결까지 확인함**
  (`/mcp`로 `ssot-explorer · connected · 3 tools` 실측, D-049/O-011).
  `list_ssot_roots`는 D-052에서 `pathExists` 필드까지 추가돼 "등록은
  됐는데 실제 폴더가 없어진" 상태도 MCP로 그대로 전달됨.
- **비교 조사**: "여러 리포지토리의 경로/메타데이터를 MCP로 노출하는
  repo-registry MCP 서버"라는 **패턴 자체는 MCP 관련 가이드 문서 수준
  에서 개념적으로 언급**되지만[22], SSOT_Explorer처럼 구체적인 오픈소스
  프로젝트/제품으로 확인되는 사례는 이번 재검색에서도 특정하지 못했다.
  Ruler의 MCP 기능(위 섹션)은 정반대 방향(설정을 컨슈머 툴에 배포)이라
  직접 비교 대상이 아니다.
- **정직하게 말해**: 라우터/오케스트레이션 섹션과 같은 이유로 이것도
  "안 나왔다"≠"없다"다 — MCP 생태계 자체가 아직 빠르게 성장 중이라
  (2026년에도 registry/서버 발견 도구가 새로 나오는 중[22]) 몇 달 안에
  비슷한 걸 하는 프로젝트가 등장할 가능성을 배제할 수 없다.

### 레지스트리-as-SSOT + 재생성 가능한 init 파일 — `격차 없음, 불변`
- v2와 동일(Backstage 방향과 일치, D-010).

### 영향범위 전파(affected-graph) — `격차 없음(스코프상 정확한 설계), 불변`
- v2와 동일(D-020).

### 웹 아티팩트를 정본으로 전환하는 모드 — `SSOT_Explorer가 오히려 앞섬, 불변`
- v2와 동일(D-023, primarySource).

### 관계(relations) 구조화 + 전체 드라이브 노출 — `격차 없음, 불변`
- v2와 동일(D-028) — Backstage 엔티티 관계 그래프와 발상은 비슷하나
  대상 층위가 달라 직접 비교보다 "같은 아이디어를 다른 도메인에 적용"
  정도로 기록.

### 🆕 신규(D-042/044/046/047), 비교 대상 없음 — 내부 운영 UX
- **Inbox 감시(D-042)**: 지정 폴더에 새 파일이 생기면 QThread 폴링으로
  감지+로그+상태바 알림(분류 자동연결은 의도적으로 보류, O-006). 자동
  실행은 없음 — 감지→알림만.
- **개발자 콘솔/탭(D-046/047)**: 관리자 패널이 모달에서 상시 탭으로
  승격, 레지스트리/스키마검증/드리프트로그를 한 곳에서 확인. Backstage
  TechDocs와 발상은 약하게 유사하나 규모/성숙도 차이가 커서 직접 비교는
  안 함 — 개인용 도구의 "자기 상태를 스스로 보여주는" 최소 구현 정도로
  기록.

---

## 종합 — 니치 포지셔닝 (v3 갱신)

1. **인프라 격차 두 곳이 실제로 좁혀졌다(v3 신규)**: v1/v2가 "격차 큼"
   으로 지적했던 CI(H-005)와 레지스트리 스키마 검증이 D-038에서 둘 다
   생겼다 — "0에서 있음"으로의 변화라 Backstage 규모와 비교하면 여전히
   격차가 크지만, "아예 없다"는 지적은 더 이상 사실이 아니다.
2. **포맷 동기화 축은 여전히 독자적이지 않고, Ruler는 더 심화됐다**:
   v2에서 발견한 Ruler가 v3 재확인 결과 MCP 설정 배포 기능을 더
   정교하게 다듬는 중이다[20] — 다만 방향이 SSOT_Explorer의 신규 MCP
   서버(3번 항목)와 정반대라 직접 경쟁으로 좁혀지진 않는다.
3. **직접 경쟁(Claudia/opcode)의 정체가 재확인·연장됐다**: v0.2.0(2025-
   08-31)에서 1년 가까이 그대로다[21] — 위협도는 계속 낮은 채 유지.
4. **MCP 서버로 자기 데이터를 노출하는 축은 v3 신규 자산이지만, 라우터
   와 마찬가지로 비교 대상을 못 찾은 것뿐 시장이 검증된 게 아니다** —
   개념 자체는 가이드 문서 수준에서 언급되지만 구체적 경쟁 제품은
   안 나왔다(위 상세 참고).
5. **레지스트리 기반 다중 프로젝트 운영 계층은 여전히 안 보인다**: 파일
   찾기(정체)+포맷 동기화(RuleSync/Ruler)+엔터프라이즈 카탈로그
   (Backstage) 각각은 존재하지만, 이 셋을 한 GUI에서 동시에 하는 도구는
   v3 재조사에서도 못 찾았다 — v1/v2와 같은 정직성 단서 유지.

## 나아갈 방향과 잠재력 재평가 (v3, 2026-08-17 — 사용자 요청)

**제품/시장 잠재력 — v1/v2와 같은 결론("낮은 편")을 유지한다.** CI/
스키마 격차가 좁혀진 건 "인프라를 갖췄다"는 뜻이지 "시장이 있다"는
뜻이 아니다 — 이 구분을 v3에서도 그대로 지킨다:

- **더 나아진 축**: CI(H-005)와 레지스트리 스키마 검증이 실제로 생겼다
  (D-038) — v2가 "배포/공개 근거 약함"의 이유로 들었던 항목 중 하나가
  해소됐다. 다만 이것만으로 공개 결정을 정당화하기엔 부족하다(아래
  권고 3번 참고).
- **비슷하거나 나빠진 축**: 포맷 동기화는 Ruler의 MCP 기능이 더
  심화되면서(v3 재확인) 격차가 좁혀지긴커녕 오히려 더 벌어졌다 — 이
  축으로 독자성을 주장하는 건 v2보다도 더 어려워졌다.
- **유일하게 새로 생긴 자산 두 개**: 라우터/오케스트레이션(5단계로 확장,
  D-044)과 MCP 서버(D-048~050)는 둘 다 비교 대상이 없는 진짜 새 영역
  이다. 다만 둘 다 "제품 잠재력"으로 이어지려면 (a) 이 문제를 겪는
  사람이 이 사용자 혼자가 아니어야 하고 (b) 라우터는 실사용 정확도
  (`acceptance_rate()` 데이터, O-007/O-008), MCP 서버는 실사용 빈도
  (O-011 재논의 조건)로 가치를 증명해야 한다 — 셋 다 아직 미검증.
- 협업/멀티유저/서버 없음은 v1/v2와 구조적으로 동일 — 재설계 없이는
  안 바뀐다.

**개인용 도구로서의 잠재력은 v2보다 더 명확해졌다.** 이 3일
(D-037→D-055, 19개 결정)에서도 같은 패턴이 반복됐다 — 이번 재조사
자체가 실사용 정확도 문제(CI 미검증 상태, ensure_ascii 인코딩 불일치
등 D-054에서 실제로 잡힌 버그)를 찾아내는 도구로 계속 기능했다. "경쟁
비교/코드리뷰를 하다가 자기 결함을 발견하고 바로 고친" 사이클이 세
번째(D-027→D-036, D-043→D-051, 이번 D-054)로 돌았다 — "팔 물건을
만드는 과정"이 아니라 "본인 워크플로우 인프라를 계속 정확하게 유지하는
과정"으로서의 가치는 매 라운드 재확인되고 있다.

**나아갈 방향 (우선순위 순, 정직성 조건 하에 권고)**:
1. **새 기능보다 라우터/MCP 실사용 검증이 먼저** — O-007/O-008(라우터
   `acceptance_rate()`)과 O-011(MCP 실사용 빈도)에 이미 기록된 재논의
   조건을 기다리는 게 맞다. 이론적 재설계나 새 경쟁축 추가를 추측만
   으로 먼저 하지 않는다는 원칙은 v3에서도 유지.
2. **포맷 동기화 축은 계속 "더 넓히기"보다 "Ruler/RuleSync에 없는 것"에
   집중** — Ruler의 MCP 기능이 더 심화된 지금, 포맷 개수 경쟁은 v2보다
   더 투자 대비 가치가 낮다. 레지스트리 통합관리/손편집보호/리뷰신선도/
   relations/MCP 서버(자기 데이터 노출)처럼 SSOT_Explorer만 가진 것을
   계속 다듬는 쪽이 우위를 지키는 길.
3. **배포/공개는 근거가 나아졌지만 아직 결정적이지 않다** — CI(H-005)와
   스키마 검증(D-038)이 생긴 건 "공개할 때 필요한 최소 조건 하나"가
   채워진 것에 가깝다. Actions 실제 실행 결과가 아직 미확인이라는 점
   (이 문서에서도 계속 지적 중)부터 먼저 닫는 게 순서 — 공개 여부
   자체의 결정을 이 문서가 대신 내리지는 않는다.
4. **"있는 걸 안 낡게" 유지가 계속 최우선** — 이 문서 자체가 v1(2026-
   08-13)→v2(2026-08-14)→v3(2026-08-17)로 3번 갱신됐다는 사실이 이
   원칙의 실천 사례. 실행규격서(H-007)도 이 세션 사이 갱신됨.

**결론**: 방향 전환은 필요 없다 — v2 대비 새 비교 대상 없는 자산이
하나 더 늘었고(MCP 서버), 인프라 격차 일부는 실제로 좁혀졌다. 다만
"라우터가 실제로 잘 작동한다"도 "MCP 서버를 실제로 자주 쓴다"도 아직
증명되지 않은 가설이라는 걸 스스로 잊지 않는 게, 이 문서가 세 라운드째
지켜온 정직성 조건의 다음 단계다.

---

## 출처

[1] Backstage Software Catalog — https://backstage.io/docs/features/software-catalog/
[2] Backstage 2026 가이드(Roadie.io) — https://roadie.io/backstage-spotify/
[3] RuleSync(dyoshikawa) — https://github.com/dyoshikawa/rulesync
[4] RuleSync(jpcaparas) — https://github.com/jpcaparas/rulesync
[5] AGENTS.md 가이드(DEV Community) — https://dev.to/skojiocommunity/agentsmd-explained-one-file-for-claude-cursor-copilot-and-windsurf-7dl
[6] Windsurf vs Cursor 2026(Verdent) — https://www.verdent.ai/guides/windsurf-vs-cursor-2026
[7] AGENTS.md 구축 가이드(Augment Code) — https://www.augmentcode.com/guides/how-to-build-agents-md
[8] Agent Rules 커뮤니티 표준 — https://github.com/agent-rules/agent-rules
[9] Claudia(marcusbey) — https://github.com/marcusbey/claudia
[10] opcode(buckstrdr, winfunc/opcode 포크) — https://github.com/buckstrdr/opcode
[11] Ruler v0.3.0 릴리스 — https://github.com/intellectronica/ruler/releases/tag/v0.3.0
[12] Cursor Rules .mdc/alwaysApply 가이드(Morph) — https://www.morphllm.com/cursor-rules-best-practices
[13] Windsurf Rules 가이드(Skillwright) — https://www.skillwright.app/blog/windsurf-rules-guide
[14] Ruler GitHub(intellectronica) — https://github.com/intellectronica/ruler
[15] Ruler 소개(Addo Zhang, Medium) — https://addozhang.medium.com/ruler-unified-configuration-management-for-multiple-ai-coding-assistants-247df7d4754a
[16] AGENTS.md 완전 가이드 2026(Codersera) — https://codersera.com/blog/agents-md-complete-guide-2026/
[17] Best Claude Code GUI 2026(Nimbalyst, opcode 정체 상태 언급) — https://nimbalyst.com/blog/best-claude-code-gui-tools-2026/
[18] winfunc Opcode 발표(X) — https://x.com/getAsterisk/status/1964262082565611873
[19] AI 문서 자동 분류(elDoc) — https://eldoc.online/blog/how-to-organize-files-with-ai/
[20] Ruler 릴리스(v3 재확인 — per-agent MCP 설정 등 심화) — https://github.com/intellectronica/ruler/releases
[21] opcode 릴리스(v3 재확인 — v0.2.0/2025-08-31 이후 신규 릴리스 없음) — https://github.com/winfunc/opcode/releases
[22] Best MCP Servers for Claude Code 2026(MintMCP, repo-registry MCP 서버 패턴 언급) — https://www.mintmcp.com/blog/mcp-servers-claude-code

---
변경이력: v1(2026-08-13, D-027) 최초 작성 → v2(2026-08-14, D-037) 사용자
요청으로 재조사·갱신(Ruler 신규 발견, opcode 정체 확인, D-036 해소 반영,
"나아갈 방향과 잠재력 재평가" 섹션 신설) → v3(2026-08-17, D-055) 사용자
요청으로 재조사·갱신 — CI+레지스트리 스키마 검증(D-038) 실제 확보 반영,
Ruler MCP 기능 심화 재확인, opcode 정체 지속 재확인(1년 가까이), MCP
서버로 자기 데이터 노출(D-048~050)이라는 신규 비교축 추가, 라우터
5단계 확장(D-044) 반영.

================================================================
SSOT Explorer — 상용/표준 비교분석 (v2, 2026-08-14 갱신)
================================================================
인프라 성숙도 × 기능 완성도 정밀 대조 + 나아갈 방향/잠재력 재평가

두 축으로 지금 앱을 잰다 — (A) 인프라·엔지니어링 관행을 동종 카테고리
상용/오픈소스 제품과, (B) 기능·개념 완성도를 "이상적인 개인용 SSOT 레지스트리
도구"(Backstage+Ruler/RuleSync+AGENTS.md 표준의 장점을 합친 합성 이상향)와
대조한다. Lazzy_App_OS_Monorepo의 `아이언맨_자비스_비교분석.md` 방법론을
그대로 이식(D-023).

- **v1 기준일**: 2026-08-13 (대상: D-001~D-026)
- **v2 기준일(이 문서)**: 2026-08-14 (대상: D-001~D-036 — router 오케스트
  레이션/relations/SessionStart 훅/IDF+kiwipiepy/H-006 포맷 갱신까지 전부
  반영, 사용자 요청으로 재조사)
- **근거**: 코드 직접 확인(main.py/router_*.py/test_*.py) + WebSearch
  (2026-08-14 실시간 검색, 출처 각주 표기) — 추측 없음

---

## 방법론 — 정직성 조건

**(A) 상용/오픈소스 제품** — Backstage(Spotify/CNCF), RuleSync, **Ruler**
(intellectronica/ruler — v2에서 신규 추가, 아래 참고), AGENTS.md 표준
(Linux Foundation Agentic AI Foundation)에 대해 **공개적으로 검색 확인된
사실**만 기준으로 삼는다. 내부 구현을 안다고 주장하지 않는다.

**(B) 이상적 SSOT 레지스트리 도구** — 실존 단일 제품이 아니라 합성 이상향.
방향성 지표로만 쓴다.

SSOT_Explorer 쪽 사실은 전부 실제 코드(`main.py`, `router_*.py`,
`test_*.py`) 기준.

---

## 축 A — 인프라 · 엔지니어링 성숙도

### 회귀 테스트 / CI — `격차 큼, 그러나 자체 성장은 뚜렷`
- **SSOT_Explorer**: pytest **94개**(v1 시점 22개 → v2 시점 94개, 4배+
  증가 — router 모듈 4개가 D-029~D-034에서 전부 자기 테스트 파일을 갖고
  합류). git 로컬 저장소만 존재, CI 없음(H-005, 원격 연결 보류 중).
- **비교 기준**: Backstage/RuleSync/Ruler 전부 GitHub Actions CI, 태그된
  릴리스(Ruler는 v0.3.0 등 버전 릴리스 확인됨[11]), 이슈트래커 보유.
  SSOT_Explorer는 여전히 1인 개인용 도구라 이 축의 격차 자체는 v1과 구조적
  으로 동일 — 다만 "테스트가 거의 없다"에서 "테스트는 충실히 쌓고 있는데
  CI로 자동화만 안 됐다"로 격차의 성격이 바뀜.

### 배포/설치 방식 — `격차 작음(용도가 다름), 불변`
- v1과 동일 — PyInstaller onefile exe, GUI 전용이라 CI/자동화 파이프라인에
  못 끼워넣는다는 약점도 그대로. 단, **router CLI(`router_classifier.py`/
  `router_orchestrator.py --text`, D-030/D-032)는 GUI 없이 단독 실행
  가능** — "동기화 결과 검증"은 여전히 CLI로 못 하지만 "분류 결과 조회"는
  이제 CLI로 가능해진 부분적 개선.

### 레지스트리 스키마 성숙도 — `격차 큼, 불변`
- v1과 동일 결론 — Backstage의 정식 스키마+250개+ 플러그인 생태계[1][2]
  대비 "파일 1개짜리 흉내"인 건 규모상 당연(1인 개인용 vs 3,400개+ 회사가
  쓰는 엔터프라이즈 플랫폼[1]).

### 동시성 안전성 — `격차 없음 · 상대적 강점, 불변`
- v1과 동일 — 원자적 쓰기 + 낙관적 동시성 제어(D-021). Ruler/RuleSync는
  단발성 CLI 실행이라 이 문제 자체가 성립 안 함.

### 로깅/오류 가시성 — `격차 없음, 불변`
- v1과 동일(D-025).

---

## 축 B — 기능 · 개념 완성도

### 멀티 AI툴 규칙 동기화 — `격차 있었으나 코드 결함은 해소됨(D-036)` ✅
- **SSOT_Explorer**: CLAUDE.md/AGENTS.md/Cursor(`.cursor/rules/*.mdc`,
  `alwaysApply: true`)/Windsurf(`.windsurf/rules/*.md`,
  `trigger: always_on`) — **2026-08-14(D-036)에 디렉토리 신포맷으로
  갱신**, 레거시 `.cursorrules`/`.windsurfrules`는 있을 때만 유지. 프론트
  매터 스키마(`alwaysApply`/`trigger: always_on`)는 이번 재조사에서
  실시간 재검증함[12][13] — v1이 발견한 "최신 Cursor/Windsurf에서 안
  읽힐 수 있다"는 결함이 실제로 해소됨.
- **RuleSync**: 8개 포맷 지원(Claude/Cursor/Windsurf/Gemini CLI/GitHub
  Copilot/OpenAI Codex/Cline/Junie)[3][4] — 여전히 SSOT_Explorer(6개)
  보다 넓음.
- **🆕 Ruler(intellectronica/ruler)** — v1에는 없던 발견. `.ruler/`
  디렉토리에 마크다운으로 규칙을 한 번 쓰면 여러 에이전트 설정 파일로
  자동 배포하는, **SSOT_Explorer의 FORMAT_TARGETS 동기화와 정확히 같은
  발상**의 도구[14][15]. Copilot/Claude/Cursor/Aider를 명시 지원, 최근
  Kiro/OpenHands 추가, MCP 서버 설정 배포+생성파일 자동 .gitignore까지
  갖춤[14]. **SSOT_Explorer에 없는 것**: MCP 설정 배포, 생성파일
  .gitignore 자동화, 중첩 `.ruler/` 디렉토리로 하위 폴더별 다른 규칙
  적용. **Ruler에 없는 것(SSOT_Explorer에 있는 것)**: 여러 독립 프로젝트
  루트를 하나의 레지스트리로 묶어 관리(Ruler는 리포 1개 안에서만 동작),
  손편집 보호(SYNC_MARKER 확인), 리뷰 신선도, relations, 라우터.
  **의미**: "규칙 파일 하나에서 여러 포맷으로 배포"라는 아이디어 자체는
  이미 활발히 유지보수되는 오픈소스 도구로 존재한다 — SSOT_Explorer가
  포맷 동기화 기능만으로는 더 이상 독자적이지 않음.
- **더 큰 흐름 재확인**: AGENTS.md는 이제 **60,000개+ 저장소, 20개+ 툴이
  네이티브로 읽는 표준**(Codex/Cursor/Copilot/Gemini CLI/Aider/Windsurf/
  Zed/Factory/Jules 등)으로 자리잡음[16] — v1 대비 숫자는 그대로지만
  "일시적 유행이 아니라 정착했다"는 확인.

### CLAUDE.md 스캐너를 갖춘 GUI 앱(Claudia/opcode) — `경쟁 압력 오히려 감소` 📉
- v1에서 "직접 경쟁 상대로 존재함"이라 정정했던 항목 — **v2 재조사 결과
  갱신**: opcode(Claudia 개명)는 2026-01-23에 리브랜딩 발표됐지만, **실제
  마지막 릴리스는 2025-08-31 — 2026년 들어 7개월 가까이 업데이트가 없고
  커뮤니티 대응도 끊긴 상태**로 확인됨[17]. Claude Code 자체는 그 사이
  API/기능이 계속 바뀌었는데 opcode가 못 따라가고 있다는 지적이 출처에
  그대로 나옴[17]. "Opcode 자체 코딩 에이전트" 등 신기능이 X(트위터)
  발표로는 예고됐으나[18] 저장소 활동과는 별개.
- **의미**: v1 결론("최소 기능은 이미 존재")은 여전히 사실이지만, 그
  최소 기능을 제공하는 앱 자체가 정체 상태라 **실사용 위협도는 낮아짐**
  — SSOT_Explorer가 매 라운드 실제로 갱신되고 있다는 점(D-027→D-036,
  하루 만에 10개 결정)이 상대적으로 부각되는 지점.

### 라우터/오케스트레이션(신규 축, D-029~D-034) — `비교 대상을 못 찾음`
- **SSOT_Explorer만의 기능**: 텍스트를 붙여넣으면 등록된 여러 프로젝트
  루트 중 어디로 보내야 할지 휴리스틱(TF-IDF+scope매치+README 실시간
  스캔+신뢰 폐루프)으로 자동 제안 — 항상 사용자 승인이 있어야 실제 저장
  (P-01 예외, D-029).
  v2에서 "AI 코딩 어시스턴트 + 문서를 맞는 폴더로 자동 분류" 키워드로
  재검색했으나[19], 나온 결과는 전부 다른 층위: (1) Ruler류는 "규칙을
  여러 포맷으로 배포"이지 "내용을 보고 목적지 프로젝트를 고르는" 기능이
  아님 (2) elDoc 같은 범용 AI 문서 정리 도구는 "타입/연도/부서별 폴더로
  이동"이라 일반 파일 관리 용도지, "여러 독립 코딩 프로젝트 레지스트리
  중 규칙 SSOT와의 프로즈 유사도로 목적지를 고르는" 이 앱의 좁은 문제
  정의와는 다름. **정직하게 말해**: 이건 "SSOT_Explorer가 세상에 없는
  걸 만들었다"보다는 "이 니치가 너무 좁아서(1인 개발자가 Claude Code로
  여러 프로젝트를 동시에 굴리며 대화 내용을 규칙으로 승격시키는 습관)
  상용 제품이 이 문제 자체를 정의할 유인이 없었다"에 가까움 — 시장이
  없어서 경쟁자가 없는 것과 아무도 안 풀어본 문제를 처음 푼 것은 다르다.

### 레지스트리-as-SSOT + 재생성 가능한 init 파일 — `격차 없음, 불변`
- v1과 동일(Backstage 방향과 일치, D-010).

### 영향범위 전파(affected-graph) — `격차 없음(스코프상 정확한 설계), 불변`
- v1과 동일(D-020).

### 웹 아티팩트를 정본으로 전환하는 모드 — `SSOT_Explorer가 오히려 앞섬, 불변`
- v1과 동일(D-023, primarySource).

### 관계(relations) 구조화 + 전체 드라이브 노출 — `신규(D-028), 비교 대상 없음`
- 등록 루트든 임의 드라이브 밑 폴더든 관계 선언(`{fromPath, toPath,
  reason}`)이 걸리면 트리에서 바로 보여주는 기능. Backstage의 엔티티
  관계 그래프(Component-Component 등)와 발상은 비슷하지만, Backstage는
  같은 카탈로그 안 "서비스 간 소유권/의존 관계"가 대상이고 SSOT_Explorer는
  "문서/폴더 간 프로즈 참조 관계"가 대상이라 층위가 다름 — 직접 비교보다
  "같은 아이디어를 다른 도메인에 적용" 정도로 기록.

---

## 종합 — 니치 포지셔닝 (v2 갱신)

1. **포맷 동기화 축은 더 이상 독자적이지 않다(v2 신규 발견)**: Ruler가
   같은 문제(여러 AI 툴 설정 파일 자동 배포)를 이미 활발하게 유지보수
   중이다[14][15] — v1까지는 RuleSync(넓지만 SaaS 성격)만 알려져 있었는데,
   Ruler는 더 "SSOT_Explorer와 발상이 같은" 순수 오픈소스 동기화 도구다.
2. **직접 경쟁(Claudia/opcode)의 위협은 줄었다**: 최소 기능(CLAUDE.md
   스캐너)을 가진 앱이 실질적으로 정체됐다[17] — "이미 있다"는 사실은
   안 바뀌지만 "계속 갱신되며 위협적이다"는 아니게 됨.
3. **레지스트리 기반 다중 프로젝트 운영 계층은 여전히 안 보인다**: 파일
   찾기(Claudia/opcode, 정체) + 포맷 동기화(RuleSync, Ruler) + 엔터프라이즈
   카탈로그(Backstage) 각각은 존재하지만, 이 셋을 "1인 개발자가 여러
   독립 프로젝트 루트를 넘나들며" 한 GUI에서 동시에(드리프트감지+리뷰
   신선도+영향범위전파+동시성안전+relations) 하는 도구는 이번 재조사
   에서도 못 찾았다 — v1과 같은 정직성 단서 유지("안 나왔다"≠"없다").
4. **라우터/오케스트레이션은 비교 대상 자체가 없는 새 영역이지만, 그건
   시장이 검증됐다는 뜻이 아니다** — 니치가 좁아서 아무도 안 만든
   가능성이 더 크다(위 상세 참고).
5. **즉시 조치 필요 항목 해소**: v1의 `.cursorrules`/`.windsurfrules`
   레거시 포맷 문제는 D-036에서 실제로 고침(H-006 완료).

## 나아갈 방향과 잠재력 재평가 (v2, 2026-08-14 — 사용자 요청)

**제품/시장 잠재력 — v1과 같은 결론("낮은 편")을 유지한다.** 새로 나온
근거(Ruler의 존재, opcode 정체)를 반영해도 방향은 안 바뀐다:

- **더 나빠진 축**: 포맷 동기화는 v1 시점엔 "RuleSync가 이미 더 넓게
  한다" 정도였는데, v2에서 Ruler까지 확인되면서 "이미 활발히 유지보수
  되는 순수 오픈소스 대안이 최소 2개"로 늘었다 — 이 기능 하나만으로
  독자성을 주장하기는 v1보다 더 어려워졌다.
- **비슷하거나 나아진 축**: 직접 경쟁(Claudia/opcode)이 정체되면서 상대
  위협은 줄었지만, 이건 "SSOT_Explorer가 잘해서"가 아니라 "상대가
  멈춰서"라 잠재력 판단에 플러스로 카운트하지 않는다(정직성 조건 —
  경쟁자의 실패는 자신의 성공이 아니다).
- **유일하게 새로 생긴 자산**: 라우터/오케스트레이션은 비교 대상이 없는
  진짜 새 영역이다. 다만 이게 "제품 잠재력"으로 이어지려면 (a) 이 문제를
  겪는 사람이 이 사용자 혼자가 아니어야 하고 (b) 지금의 휴리스틱 정확도
  (D-033/D-034 실측 — 정답이 최하위→공동1위까지는 왔지만 "언급 vs 소유"
  구분은 여전히 못 풂, O-007/O-008)로 실사용 가치를 증명해야 한다 — 둘 다
  아직 미검증. "세상에 없는 기능"과 "팔릴 만한 기능"은 다른 질문이라는
  게 이 재평가의 핵심 정직성 포인트.
- 협업/멀티유저/서버 없음은 v1과 구조적으로 동일 — 재설계 없이는 안 바뀜.

**개인용 도구로서의 잠재력은 v1보다 오히려 더 명확해졌다.** 이 세션
(D-027→D-036, 하루 안에 10개 결정)에서 실제로 드러난 패턴: 상용 비교분석
자체가 실사용 버그(H-006 레거시 포맷)를 찾아내는 도구로 기능했다 — "경쟁
제품과 비교하다가 자기 코드 결함을 발견하고 바로 고친" 사이클이 이미
두 번(D-027 발견→D-036 해결) 돌았다. 이건 "팔 물건을 만드는 과정"이
아니라 "본인 워크플로우 인프라를 계속 정확하게 유지하는 과정"으로서는
확실히 가치가 있다.

**나아갈 방향 (우선순위 순, 정직성 조건 하에 권고)**:
1. **새 기능보다 라우터 정확도 검증이 먼저** — O-007/O-008에 이미 기록된
   재논의 조건(`acceptance_rate()` 데이터 축적)을 기다리는 게 맞다. 지금
   방향(가중합 IDF)을 더 정교하게 다듬는 것보다, 실사용 승인/거부 데이터
   가 쌓이는 걸 먼저 봐야 다음 투자가 정당화된다 — 이론적 재설계를
   추측만으로 먼저 하지 않는다는 이 프로젝트의 기존 원칙과 일치.
2. **포맷 동기화 축은 "더 넓히기"보다 "Ruler/RuleSync에 없는 것"에 집중**
   — 이미 두 오픈소스 대안이 포맷 개수로는 앞선다는 게 이번 재조사의
   결론이라, 포맷 7·8개로 늘리는 경쟁은 투자 대비 가치가 낮다. 대신
   SSOT_Explorer만 가진 것(레지스트리 통합관리/손편집보호/리뷰신선도/
   relations)을 계속 다듬는 쪽이 이미 있는 우위를 지키는 길.
3. **배포/공개는 여전히 근거 약함** — v1 결론 유지. CI(H-005)조차
   "언젠가 오픈소스로 공개할 때"를 준비하는 성격이 크다면 지금은 후순위가
   맞고, "그냥 개인 도구가 안 죽게" 목적이면 이미 git+pytest 94개로
   충분한 안전망이 있다.
4. **실행규격서(H-007)처럼 "있는 걸 안 낡게" 유지가 계속 최우선** — 이
   문서 자체도 v1(D-027, 2026-08-13)에서 v2(D-037, 2026-08-14)로 하루
   만에 갱신됐다는 사실이 이 원칙의 실천 사례.

**결론**: 방향 전환은 필요 없다 — 본인 실사용 인프라로 계속 다듬는 지금
경로가 v1 대비 더 뚜렷하게 정당화된다(라우터라는 비교 대상 없는 자산이
생겼으므로). 다만 "이 라우터가 실제로 잘 작동한다"는 아직 증명되지 않은
가설이라는 걸 스스로 잊지 않는 게, 지금까지 이 문서가 지켜온 정직성
조건의 다음 단계다.

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

---
변경이력: v1(2026-08-13, D-027) 최초 작성 → v2(2026-08-14, D-037) 사용자
요청으로 재조사·갱신 — Ruler 신규 발견, opcode 정체 확인, D-036 해소 반영,
"나아갈 방향과 잠재력 재평가" 섹션 신설.

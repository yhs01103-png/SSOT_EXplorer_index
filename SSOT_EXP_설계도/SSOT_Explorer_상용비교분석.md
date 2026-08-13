================================================================
SSOT Explorer — 상용/표준 비교분석
================================================================
인프라 성숙도 × 기능 완성도 정밀 대조

두 축으로 지금 앱을 잰다 — (A) 인프라·엔지니어링 관행을 동종 카테고리
상용/오픈소스 제품과, (B) 기능·개념 완성도를 "이상적인 개인용 SSOT 레지스트리
도구"(Backstage+RuleSync+AGENTS.md 표준의 장점을 합친 합성 이상향)와 대조한다.
Lazzy_App_OS_Monorepo의 `아이언맨_자비스_비교분석.md` 방법론을 그대로 이식
(D-023에서 이미 여러 관례를 이식한 데 이은 연장선).

- **기준일**: 2026-08-13
- **대상**: SSOT_Explorer(main.py, D-001~D-026 반영 상태)
- **근거**: 코드 직접 확인(main.py/test_main.py) + WebSearch(2026-08-13 실시간
  검색, 출처 각주 표기) — 추측 없음

---

## 방법론 — 정직성 조건

**(A) 상용/오픈소스 제품** — Backstage(Spotify/CNCF), RuleSync(dyoshikawa/
jpcaparas 구현 + rulesync.dev), AGENTS.md 표준(Linux Foundation Agentic AI
Foundation)에 대해 **공개적으로 검색 확인된 사실**만 기준으로 삼는다. 내부
구현을 안다고 주장하지 않는다.

**(B) 이상적 SSOT 레지스트리 도구** — 실존 단일 제품이 아니라 "이 세 도구가
각자 잘하는 걸 한 도구가 다 갖췄다면"이라는 **합성 이상향**이다. 실제로
존재하는 제품이 아니므로 방향성 지표로만 쓴다.

SSOT_Explorer 쪽 사실은 전부 실제 코드(`main.py`, `test_main.py`) 기준.

---

## 축 A — 인프라 · 엔지니어링 성숙도

### 회귀 테스트 / CI — `격차 큼`
- **SSOT_Explorer**: pytest 22개(D-024, 2026-08-13 도입) + git 저장소
  자체가 오늘 처음 생김(D-026). CI 없음(H-005, GitHub 원격 연결 보류 중).
- **비교 기준**: Backstage/RuleSync 둘 다 성숙한 OSS 프로젝트 — GitHub
  Actions CI, 유의적 버전관리, 기여자 다수, 이슈트래커. SSOT_Explorer는
  1인 개인용 도구고 테스트 커버리지 자체가 오늘 막 생겼다는 걸 감안해도
  격차가 크다.

### 배포/설치 방식 — `격차 작음(용도가 다름)`
- **SSOT_Explorer**: PyInstaller onefile exe 더블클릭(설치 불필요) 또는
  `pip install -r requirements.txt` — 완전히 로컬, 서버 없음.
- **비교 기준**: RuleSync는 CLI(npm/pip/composer 설치) + 웹 SaaS(rulesync.dev)
  2트랙. Backstage는 자체 호스팅 웹앱(2~4주 셋업). SSOT_Explorer가 훨씬
  가볍지만, **자동화 파이프라인에 못 끼워넣는다**는 실질적 약점이 있음 —
  GUI 전용이라 CLI 모드가 없어 CI에서 "동기화 결과 검증" 같은 걸 스크립트로
  못 돌림.

### 레지스트리 스키마 성숙도 — `격차 큼`
- **SSOT_Explorer**: JSON 파일 1개, 프로즈+경량스키마 하이브리드(owner/
  scope/lastReviewed/primarySource/dependsOnDocs). 스키마 검증(JSON Schema
  등) 없음 — 필드 오타/타입 오류를 앱이 조용히 `.setdefault()`로 무시.
- **비교 기준**: Backstage의 `catalog-info.yaml`은 엔티티 종류(Component/
  API/Resource/System/Domain/Group/User)별 정식 스키마 + 검증 + 250개+
  플러그인 생태계(시각화, 소유권 그래프, 스캐폴딩 템플릿까지)[1][2]. 격차가
  구조적으로 크다 — SSOT_Explorer는 "파일 1개짜리 Backstage 흉내"에 가깝고,
  이건 규모상 당연한 선택(1인 개인용 vs 3,400개+ 회사가 쓰는 엔터프라이즈
  플랫폼)이라 "따라잡아야 할 격차"라기보다 "애초에 다른 리그"에 가깝다.

### 동시성 안전성 — `격차 없음 · 오히려 상대적 강점`
- **SSOT_Explorer**: 원자적 쓰기(temp+os.replace) + 낙관적 동시성 제어
  (D-021, 2026-08-13) — OneDrive 멀티기기 동기화 리스크를 명시적으로
  설계해서 방어.
- **비교 기준**: RuleSync는 단발성 CLI 실행이라 이 문제 자체가 성립 안 함
  (매번 통째로 재생성). 규모가 작은 개인용 도구치고 이 정도 동시성 설계를
  갖춘 건 드묾 — 축소 비교지만 실질적 강점.

### 로깅/오류 가시성 — `격차 없음(방금 해소, D-025)`
- **SSOT_Explorer**: 파일 로그 + 미처리예외 다이얼로그(2026-08-13 도입).
- **비교 기준**: 이 항목은 애초에 상용 제품과 비교할 축이 아님(둘 다
  당연히 있음) — 오늘 아침까지 SSOT_Explorer엔 이게 없었다는 게 격차였고,
  방금 해소됨.

---

## 축 B — 기능 · 개념 완성도

### 멀티 AI툴 규칙 동기화 — `격차 있음, 그리고 실제 결함 발견` ⚠️
- **SSOT_Explorer**: CLAUDE.md/AGENTS.md/.cursorrules/.windsurfrules 4개
  포맷을 레지스트리 하나에서 동기화(`FORMAT_TARGETS`).
- **RuleSync**: Claude/Cursor/Windsurf/Gemini CLI/GitHub Copilot/OpenAI
  Codex/Cline/Junie **8개 포맷**을 지원[3][4] — SSOT_Explorer의 2배.
- **⚠️ 실제 결함(코드 레벨, 경쟁 비교와 별개로 그 자체로 고쳐야 함)**:
  검색 결과 **`.cursorrules`(단일파일)는 이미 폐기(deprecated)** —
  Cursor는 `.cursor/rules/*.mdc` 디렉토리 구조로 이전했다. **`.windsurfrules`도
  레거시** — Windsurf는 `.windsurf/rules/`를 권장하되 `.windsurfrules`와
  `AGENTS.md`를 둘 다 읽는 과도기 상태다[5][6]. 즉 SSOT_Explorer가 지금
  생성하는 `.cursorrules`/`.windsurfrules`는 **최신 Cursor에서 아예 안 읽힐
  수 있는 포맷**이다 — 이건 "상용 대비 기능이 적다"가 아니라 "지금 있는
  기능이 최신 대상 툴 기준으로 이미 낡았다"는, 우선순위가 더 높은 문제.
- **더 큰 흐름**: AGENTS.md가 2025-08 OpenAI 발표 → Linux Foundation
  Agentic AI Foundation 이관을 거쳐 **Claude Code/Cursor/Windsurf/Copilot/
  Codex/Gemini CLI/Devin/Aider/Amazon Q 등 30개+ 툴이 네이티브로 직접
  읽는 표준**이 됐고 60,000개+ 저장소가 채택 중이다[7][8]. 업계가 "툴마다
  별도 파일"에서 "공용 AGENTS.md 하나 + 툴별은 선택적 오버라이드"로
  수렴하는 중 — SSOT_Explorer가 처음 이 기능을 설계할 때(D-013 근처) 전제로
  삼았던 "AI 툴마다 규칙파일이 어긋난다"는 문제 자체가, 업계 표준화로 인해
  **일부는 이미 저절로 해소되고 있는 문제**라는 뜻이다.

### 레지스트리-as-SSOT + 재생성 가능한 init 파일 — `격차 없음, 방향은 맞음`
- **SSOT_Explorer**: CLAUDE.md 등을 손으로 안 채우고 레지스트리에서 매번
  재생성(포인터 모드) — Backstage의 "메타데이터는 YAML, 실제 문서는 코드
  옆에" 철학과 방향이 같음[1].
- **비교 기준**: Backstage는 TechDocs 플러그인으로 마크다운을 렌더링까지
  해주고 검색 가능한 웹포털로 노출한다 — SSOT_Explorer는 렌더링(D-022
  마크다운 뷰어)까지는 갔지만 검색가능한 웹포털은 없음(로컬 GUI 앱 한계,
  용도가 다르므로 "격차"라기보다 스코프 차이).

### 영향범위 전파(affected-graph) — `격차 없음(스코프상 정확한 설계)`
- **SSOT_Explorer**: dependsOnDocs 명시적 선언 방식(D-020, 안1).
- **비교 기준**: Nx/Backstage류는 실제 import 구문에서 그래프를 자동
  추출한다 — SSOT_Explorer는 "코드 의존성"이 아니라 "프로즈 문서 간 참조
  관계"를 추적하는 거라 자동 스캔이 원천적으로 불가능(코드처럼 파싱 가능한
  구조가 없음). 명시적 선언이 이 도메인에서는 자동화보다 정확하므로, 이건
  "격차"가 아니라 애초에 옳은 설계 판단.

### 웹 아티팩트를 정본으로 전환하는 모드 — `SSOT_Explorer가 오히려 앞섬`
- **SSOT_Explorer**: `primarySource` 플래그(D-023) — 문서가 로컬보다 웹이
  나을 때 그 사실을 스키마 레벨에서 명시하고 동기화 UI가 경고까지 띄움.
- **비교 기준**: Backstage TechDocs는 항상 "레포 안 마크다운이 정본"이
  전제 — "이 문서의 정본은 외부 라이브 URL"이라는 개념 자체가 없음.
  RuleSync도 마찬가지(항상 로컬 rulesync.md가 소스). 작지만 실제로 드문
  기능.

### CLAUDE.md 스캐너를 갖춘 GUI 앱 — `실제로 존재함(2026-08-13 정정)`
- **정정**: 처음 이 문서를 쓸 때 "직접 경쟁 상대는 없다"고 했는데, 재질문
  받고 다시 찾아보니 부정확했다 — **Claudia**(marcusbey/claudia)와
  **opcode**(winfunc/opcode 원본, buckstrdr가 포크)가 실제로 "Project
  Scanner: 프로젝트 안의 CLAUDE.md 파일을 전부 찾아준다" 기능을 갖춘 GUI
  데스크톱 앱이다[9][10]. 둘 다 Claude Code용 종합 GUI 래퍼(세션 관리,
  에이전트, MCP 서버 관리 등)의 부가 기능으로 스캐너를 포함한 구조 — 오픈
  소스(AGPL), 무료, Anthropic 비공식.
- **실제 기능 대조**: WebFetch로 두 프로젝트 문서를 직접 확인한 결과,
  Project Scanner는 **"CLAUDE.md 파일 찾기 + 에디터 + 실시간 마크다운
  미리보기"까지만** — AGENTS.md/.cursorrules/.windsurfrules 등 타 포맷
  동기화, 파일 변경/드리프트 감지, 리뷰 신선도 추적, owner/scope 메타데이터,
  다중 프로젝트를 하나의 레지스트리로 묶어 관리하는 기능은 **문서상 전혀
  언급되지 않음**[9][10].
- **정확한 결론**: "CLAUDE.md를 찾아서 보여주는 GUI"라는 최소 기능
  자체는 이미 상용(정확히는 오픈소스 무료) 앱으로 존재한다 — 이 부분만
  떼놓고 보면 SSOT_Explorer가 "세상에 없는 걸 만든 것"은 아니다. 다만
  그 위에 SSOT_Explorer가 쌓은 나머지(레지스트리 기반 다중포맷 동기화,
  드리프트 감지, 리뷰 신선도, 영향범위 전파, 동시성 안전, primarySource)는
  이 두 앱 어디에도 없다 — "파일 찾기"와 "SSOT 레지스트리 운영"은 기능
  난이도가 다른 층위다.

---

## 종합 — 니치 포지셔닝

1. **"CLAUDE.md 찾아서 보여주는" 최소 기능은 이미 상용에 있다(정정)**:
   Claudia/opcode가 Project Scanner로 이미 제공 중[9][10] — 여기까지는
   SSOT_Explorer의 독자성이 아니다. Backstage는 "이 리그가 아님"(엔터프라이즈
   플랫폼), RuleSync는 "포맷 개수·CLI 자동화"에서 SSOT_Explorer보다 앞선다.
2. **레지스트리 기반 SSOT 운영 계층은 여전히 안 보인다**: 파일 찾기(Claudia/
   opcode) + 포맷 동기화(RuleSync) + 엔터프라이즈 카탈로그(Backstage) 각각은
   상용/오픈소스로 존재하지만, 이 셋을 "1인 개발자가 여러 독립 프로젝트
   루트를 넘나들며" 한 GUI에서 동시에 하는(드리프트감지+리뷰신선도+영향범위
   전파+동시성안전까지 포함) 도구는 이번 조사에서 못 찾았다 — 다만 이건
   "SSOT_Explorer가 유일하다"를 증명한 게 아니라 "이번 검색 범위에서는
   안 나왔다"는 더 약한 주장으로 정정한다(정직성 조건).
3. **니치 시장 자체가 좁다**: 1인 개발자가 여러 프로젝트를 Claude Code로
   동시에 굴리는 사용자층 자체가 작아서, 앱으로 확장할 가치는 "이 사용자
   본인이 실사용하는 한" 유효하고, 그 이상(배포/판매)은 이번 분석 범위 밖.
4. **즉시 조치 필요**: `.cursorrules`/`.windsurfrules` 레거시 포맷 문제
   (위 ⚠️) — 다음 라운드 최우선 후보로 별도 O-번호/TODO 등록 권장.

## 잠재력 평가 (사용자 질문에 대한 직접 답변, 2026-08-13)

**제품/시장 잠재력 — 낮은 편이 맞다.** 얼버무리지 않고 이유:

- 가장 낮은 난이도 기능("CLAUDE.md 찾아서 보여주기")은 이미 무료 오픈소스
  (Claudia/opcode)로 존재 — 여기엔 채울 빈틈이 없다.
- 더 어려운 기능(다중포맷 동기화)은 RuleSync가 이미 더 넓게(8개 포맷 vs
  4개) + 더 이식성 있게(CLI라 CI/스크립트에 끼워넣을 수 있음, SSOT_Explorer는
  GUI 전용이라 자동화 파이프라인에 못 들어감) 하고 있다.
- 이 기능이 푸는 문제 자체("AI 툴마다 규칙파일이 어긋난다")가 AGENTS.md의
  업계 표준화(Linux Foundation 이관, 30개+ 툴 네이티브 지원)로 **구조적으로
  줄어드는 중** — 잘 만들어도 시간이 지날수록 풀 문제 자체가 작아지는
  역풍. 이건 실행력 문제가 아니라 시장 방향의 문제.
- SSOT_Explorer만의 것(primarySource, 명시적 dependsOnDocs, 리뷰신선도)은
  전부 "이미 쓰고 있는 사람에게 소소하게 더 편한" 수준의 부가기능이지,
  그 자체로 신규 사용자를 끌어올 만한 독자적 가치는 아니다.
- 협업/공유 기능이 전혀 없는 단일 사용자·단일 기기(OneDrive 폴더 하나) 도구
  라 태생적으로 Backstage류가 이기는 이유(팀 전체 가시성)를 구조적으로
  가질 수 없다 — 서버/멀티유저/인증을 새로 넣는 건 지금 설계의 연장이
  아니라 사실상 재설계.

**개인용 도구로서의 잠재력은 다른 얘기 — 이미 실현됐다.** 이건 "팔 물건"이
아니라 "본인이 매일 쓰는 워크플로우 인프라"로 봐야 정확하다 — 이 세션에서만
D-020(sharedDocs 버그), D-021(동시성), D-025(로깅) 등 실사용 중 실제로
드러난 문제를 잡아왔고, 오늘 git+테스트+로깅까지 갖춰 유지보수 가능한
상태가 됐다. "제품으로 키울 잠재력"과 "계속 써도 되는 개인 도구로서의
가치"는 서로 다른 축이고, 후자는 낮지 않다.

**결론**: 배포/판매/오픈소스 공개 목적이면 지금 방향에서 더 투자할 근거가
약하다. 본인 실사용 인프라로 계속 다듬는 목적이면(지금까지의 방향) 여전히
타당하다 — 다만 그 경우에도 새 기능보다는 H-006(레거시 포맷 수정)처럼
"이미 있는 걸 안 낡게 유지"가 "상용 대비 기능을 더 넣기"보다 투자 대비
가치가 높다.

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

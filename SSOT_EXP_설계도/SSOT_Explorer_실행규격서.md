================================================================
SSOT_Explorer — 실행규격서
================================================================
기준 버전: v1.0
최종수정: 2026-08-13
원칙: 지금 코드가 정확히 어떻게 동작하는지만 기록한다. "왜"는 결정이력
      파일(D-번호)에, 계획/예정 항목은 넣지 않는다(구현 완료분만).

[1] 시스템 개요
- 단일 파일 데스크톱 GUI 앱(main.py 하나). PySide6 기반.
- 목적: SSOT 인덱싱 트리(CLAUDE.md/README.md 네트워크)를 사람이 눈으로
  탐색하는 읽기 전용 뷰어. Windows 탐색기의 보조/대체 용도.
- 서버/DB/외부 API 없음 — 전부 로컬 파일시스템 읽기.

[2] 데이터 구조
- 영속 데이터 없음(앱 자체는 상태 저장 안 함).
- 런타임 데이터: QTreeWidgetItem.data(0, Qt.UserRole)에 각 노드의 절대경로
  문자열을 저장(폴더 선택/더블클릭 시 이 값으로 실제 경로 조회).
- ROOTS: main.py 상단 리스트, [(표시이름, 절대경로), ...] 4개 항목
  (flutter_App, Local_APP, Coding_Nomal, 개발자 전용 어플).

[3] 컴포넌트/모듈 구조
- main.py 하나만 존재. 클래스 SSOTExplorer(QMainWindow) 하나.
- 폴더 구조(2026-08-13 갱신 — 설계도 폴더 분리):
  Local_APP\SSOT_Explorer\
    ├── main.py
    ├── README.md
    ├── .claude\CLAUDE.md
    └── SSOT_EXP_설계도\
          ├── SSOT_Explorer_최신_설계결정이력_TODO.md
          ├── SSOT_Explorer_레거시_설계결정이력_정책맵.md
          └── SSOT_Explorer_실행규격서.md (이 파일)

[4] 유틸 함수 목록
- find_index_files(folder: Path) -> dict
  folder 바로 밑(1단계)에서 파일명이 claude.md/readme.md(대소문자 무시)인
  파일을 찾아 {소문자파일명: Path} 형태로 반환. 권한 오류는 무시(빈 dict).

[5] 핵심 로직 명세
- 트리 지연 로딩(populate_roots → add_children_placeholder → on_item_expanded):
  1. 앱 시작 시 ROOTS 4개를 최상위 노드로 추가, 각 노드에 하위 폴더가 있으면
     더미 자식("...") 하나만 붙여서 화살표만 보이게 함(실제 스캔 안 함).
  2. 사용자가 노드를 펼치면(itemExpanded) 더미 자식을 지우고, 그 순간에만
     실제 하위 폴더 목록을 1단계 스캔해서 자식으로 추가(각 자식도 다시
     더미 자식 방식으로 지연 로딩 준비).
  3. "."으로 시작하는 폴더(.claude 등)는 트리에 안 보여줌.
- 인덱스 표시(style_item): 폴더에 find_index_files() 결과가 있으면 해당
  QTreeWidgetItem의 폰트를 굵게 설정 + 툴팁에 "claude.md+readme.md" 식으로 표시.
- 내용 뷰어(on_selection_changed): 트리에서 노드 선택 시, 그 폴더의
  claude.md/readme.md를 순서대로(claude.md 먼저) 읽어 텍스트로 이어붙여
  우측 QTextBrowser에 표시. 둘 다 없으면 "없습니다" 안내문.
- 탐색기 위임(on_item_double_clicked): 더블클릭한 노드가 실제 존재하는
  폴더면 os.startfile(경로)로 Windows 탐색기를 엶. 파일 노드는 없음(현재
  트리는 폴더만 표시, 파일은 안 보여줌).

[6] 화면 구성
- QMainWindow, 제목 "SSOT Explorer (읽기 전용)", 초기 크기 1100x700.
- QSplitter(가로 분할): 좌측 QTreeWidget(비율 1) / 우측 QTextBrowser(비율 2).
- 트리 헤더 라벨: "SSOT 인덱싱 트리 (굵게 = CLAUDE.md/README.md 있음)".

[7] 자동 실행/스케줄러 명세
- 해당 없음(수동 실행 앱, `python main.py`).

[8] API 명세
- 해당 없음(로컬 GUI 앱, 네트워크 API 없음).

[9] 실행 방법
- 최초 1회: `pip install PySide6`
- 실행: `python main.py` (Local_APP\SSOT_Explorer\ 안에서)

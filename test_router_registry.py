"""router_registry.py 전용 테스트 — D-069. load_roots/save_roots 자체의
동작(원자적 쓰기/충돌감지/setdefault 필드보정 등)은 main.py가 위임만 하는
얇은 wrapper를 통해 test_main.py의 기존 테스트들이 이미 폭넓게 검증한다
(isolated_registry 픽스처가 m.REGISTRY_PATH를 갈아끼우는 방식) — 여기서는
`add_root`(D-069 신규, register 커맨드 전용)와, GUI 없이 이 모듈만으로
등록이 실제로 되는지만 추가로 검증한다."""
from __future__ import annotations

import router_registry as rr


def test_add_root_appends_and_persists(tmp_path):
    registry_path = tmp_path / "ssot-roots.json"
    rr.add_root({"label": "a", "path": "C:\\a"}, registry_path)
    roots = rr.load_roots(registry_path)
    assert [r["label"] for r in roots] == ["a"]


def test_add_root_rejects_duplicate_label(tmp_path):
    registry_path = tmp_path / "ssot-roots.json"
    rr.add_root({"label": "a", "path": "C:\\a"}, registry_path)
    try:
        rr.add_root({"label": "a", "path": "C:\\b"}, registry_path)
        assert False, "should have raised"
    except ValueError as e:
        assert "a" in str(e)
    # 실패한 시도가 파일을 더럽히지 않았는지
    assert len(rr.load_roots(registry_path)) == 1


def test_load_roots_no_gui_dependency():
    """이 모듈을 임포트해도 PySide6가 전혀 필요 없다는 걸 증명 — sys.modules
    에 PySide6가 없어도(이 테스트 프로세스엔 있을 수 있지만) router_registry
    자체의 import 구문에 PySide6가 안 걸려있는지가 핵심."""
    import ast

    tree = ast.parse(open("router_registry.py", encoding="utf-8").read())
    imported_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_names.add(node.module.split(".")[0])
    assert "PySide6" not in imported_names


def test_different_registry_paths_do_not_share_conflict_state(tmp_path):
    """서로 다른 registry_path는 독립적으로 충돌감지 상태를 추적해야 한다
    (D-069 — main.py 시절엔 프로세스에 레지스트리가 하나뿐이라 문제가 안
    됐지만, CLI는 같은 프로세스에서 여러 레지스트리를 다룰 수 있음)."""
    path_a = tmp_path / "a" / "ssot-roots.json"
    path_b = tmp_path / "b" / "ssot-roots.json"
    rr.save_roots([{"label": "x", "path": "C:\\x"}], path_a)
    # path_b는 한 번도 load/save 안 했으니 last_known_hash가 없어야 하고,
    # 첫 저장은 절대 충돌로 취급되면 안 된다.
    rr.save_roots([{"label": "y", "path": "C:\\y"}], path_b)  # 예외 없어야 함

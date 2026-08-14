"""router_keyword_registry.py 전용 테스트 — D-044(Lazzy keyword_registry.py
경량 이식). 전부 path 파라미터로 실제 사용자 파일(~/.claude/scripts/
ssot_keyword_registry.json)을 안 건드리고 tmp_path로 격리."""
from __future__ import annotations

from datetime import datetime, timedelta

import router_keyword_registry as kr


def test_load_missing_file_returns_empty(tmp_path):
    assert kr.load_keyword_registry(tmp_path / "no-such.json") == {}


def test_record_new_keyword_creates_candidate(tmp_path):
    path = tmp_path / "kw.json"
    touched = kr.record_keyword_hits(["보안"], path)
    assert touched == ["보안"]
    entry = kr.load_keyword_registry(path)["보안"]
    assert entry["status"] == "candidate"
    assert entry["hitCount"] == 1


def test_record_existing_candidate_increments_hit_count(tmp_path):
    path = tmp_path / "kw.json"
    kr.record_keyword_hits(["보안"], path)
    kr.record_keyword_hits(["보안"], path)
    entry = kr.load_keyword_registry(path)["보안"]
    assert entry["hitCount"] == 2


def test_record_does_not_touch_active_or_dormant(tmp_path):
    path = tmp_path / "kw.json"
    kr.record_keyword_hits(["보안"], path)
    registry = kr.load_keyword_registry(path)
    registry["보안"]["status"] = "active"
    kr._save(registry, path)

    touched = kr.record_keyword_hits(["보안"], path)
    assert touched == []  # active는 안 건드림
    assert kr.load_keyword_registry(path)["보안"]["hitCount"] == 1  # 그대로


def test_try_promote_fails_below_threshold(tmp_path):
    path = tmp_path / "kw.json"
    kr.record_keyword_hits(["보안"], path)  # hitCount=1, span=0일
    assert kr.try_promote("보안", path) is False
    assert kr.load_keyword_registry(path)["보안"]["status"] == "candidate"


def test_try_promote_succeeds_when_threshold_met(tmp_path):
    path = tmp_path / "kw.json"
    now = datetime.now()
    registry = {
        "보안": {
            "status": "candidate",
            "hitCount": kr.PROMOTION_HIT_THRESHOLD,
            "firstSeenAt": (now - timedelta(days=kr.PROMOTION_MIN_SPAN_DAYS)).strftime("%Y-%m-%d %H:%M:%S"),
            "lastSeenAt": now.strftime("%Y-%m-%d %H:%M:%S"),
        }
    }
    kr._save(registry, path)
    assert kr.try_promote("보안", path) is True
    assert kr.load_keyword_registry(path)["보안"]["status"] == "active"


def test_try_promote_unknown_keyword_returns_false(tmp_path):
    assert kr.try_promote("없는키워드", tmp_path / "kw.json") is False


def test_sweep_moves_stale_candidates_to_dormant(tmp_path):
    path = tmp_path / "kw.json"
    old = (datetime.now() - timedelta(days=kr.STALE_CANDIDATE_DAYS + 1)).strftime("%Y-%m-%d %H:%M:%S")
    registry = {
        "오래된키워드": {"status": "candidate", "hitCount": 1, "firstSeenAt": old, "lastSeenAt": old},
        "최근키워드": {
            "status": "candidate", "hitCount": 1,
            "firstSeenAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "lastSeenAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
    }
    kr._save(registry, path)
    count = kr.sweep_stale_candidates(path)
    assert count == 1
    updated = kr.load_keyword_registry(path)
    assert updated["오래된키워드"]["status"] == "dormant"
    assert updated["최근키워드"]["status"] == "candidate"


def test_sweep_does_not_touch_active(tmp_path):
    path = tmp_path / "kw.json"
    old = (datetime.now() - timedelta(days=kr.STALE_CANDIDATE_DAYS + 1)).strftime("%Y-%m-%d %H:%M:%S")
    kr._save({"보안": {"status": "active", "hitCount": 10, "firstSeenAt": old, "lastSeenAt": old}}, path)
    assert kr.sweep_stale_candidates(path) == 0
    assert kr.load_keyword_registry(path)["보안"]["status"] == "active"


def test_active_keywords_returns_only_active(tmp_path):
    path = tmp_path / "kw.json"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    kr._save({
        "활성": {"status": "active", "hitCount": 10, "firstSeenAt": now, "lastSeenAt": now},
        "관찰중": {"status": "candidate", "hitCount": 1, "firstSeenAt": now, "lastSeenAt": now},
        "휴면": {"status": "dormant", "hitCount": 1, "firstSeenAt": now, "lastSeenAt": now},
    }, path)
    assert kr.active_keywords(path) == {"활성"}


def test_format_keyword_registry_text_empty():
    assert "없음" in kr.format_keyword_registry_text({})


def test_format_keyword_registry_text_shows_all_three_statuses():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    registry = {
        "활성어": {"status": "active", "hitCount": 10, "firstSeenAt": now, "lastSeenAt": now},
        "관찰어": {"status": "candidate", "hitCount": 3, "firstSeenAt": now, "lastSeenAt": now},
        "휴면어": {"status": "dormant", "hitCount": 1, "firstSeenAt": now, "lastSeenAt": now},
    }
    text = kr.format_keyword_registry_text(registry)
    assert "활성어" in text and "관찰어(3)" in text and "1개" in text


def test_registry_leaves_no_tmp_file(tmp_path):
    path = tmp_path / "kw.json"
    kr.record_keyword_hits(["보안"], path)
    leftovers = list(path.parent.glob(path.name + ".tmp*"))
    assert leftovers == []

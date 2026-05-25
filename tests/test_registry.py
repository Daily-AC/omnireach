import pytest

from omnireach.registry import load_registry


def test_load_registry_returns_all_sources():
    reg = load_registry()
    ids = [s.id for s in reg.sources]
    assert "hackernews" in ids
    assert "web" in ids
    assert "wechat" in ids
    assert "bilibili" in ids
    assert len(reg.sources) == 7


def test_get_by_id():
    reg = load_registry()
    hn = reg.get("hackernews")
    assert hn.tier == "ready"
    assert hn.adapter.endswith("HackerNewsAdapter")


def test_default_in_auto_filters():
    reg = load_registry()
    auto = [s.id for s in reg.default_auto_sources()]
    assert "hackernews" in auto
    assert "rss" not in auto


def test_get_unknown_raises():
    reg = load_registry()
    with pytest.raises(KeyError):
        reg.get("does-not-exist")


def test_source_with_hint_matches_query():
    reg = load_registry()
    hits = reg.sources_matching_hints("YouTube 教程")
    ids = [s.id for s in hits]
    assert "youtube" in ids

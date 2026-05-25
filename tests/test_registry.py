import pytest

from omnireach.registry import load_registry


def test_load_registry_returns_all_sources():
    reg = load_registry()
    ids = [s.id for s in reg.sources]
    assert "hackernews" in ids
    assert "exa" in ids
    assert "wechat" in ids
    assert "bilibili" in ids
    assert "reddit" in ids
    assert "twitter" in ids
    assert "xiaohongshu" in ids
    assert len(reg.sources) == 13


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


def test_registry_loads_trust_field():
    from omnireach.registry import load_registry
    reg = load_registry()
    by_id = {s.id: s for s in reg.sources}
    assert by_id["hackernews"].trust == 0.85
    assert by_id["xiaohongshu"].trust == 0.50


def test_registry_loads_booster_tier():
    from omnireach.registry import load_registry
    reg = load_registry()
    boosters = [s for s in reg.sources if s.tier == "booster"]
    assert {s.id for s in boosters} == {"tavily", "brave", "perplexity", "exa"}


def test_registry_includes_wip_tier():
    from omnireach.registry import load_registry
    reg = load_registry()
    wip = {s.id for s in reg.sources if s.tier == "wip"}
    assert wip == {"wechat", "bilibili"}


def test_registry_has_exa_booster():
    from omnireach.registry import load_registry
    reg = load_registry()
    by_id = {s.id: s for s in reg.sources}
    assert by_id["exa"].tier == "booster"
    assert by_id["exa"].trust == 0.85


def test_registry_web_removed():
    from omnireach.registry import load_registry
    reg = load_registry()
    assert "web" not in {s.id for s in reg.sources}

from omnireach.registry import load_registry
from omnireach.router import RouteRequest, Router


def test_explicit_on_overrides_auto():
    reg = load_registry()
    r = Router(reg)
    route = r.plan(RouteRequest(query="anything", explicit_sources=["hackernews"]))
    assert route.source_ids == ["hackernews"]


def test_auto_uses_hints_first():
    reg = load_registry()
    r = Router(reg)
    route = r.plan(RouteRequest(query="GitHub repo for omnireach"))
    assert "github" in route.source_ids


def test_auto_falls_back_to_defaults_when_no_hint():
    reg = load_registry()
    r = Router(reg)
    route = r.plan(RouteRequest(query="天气怎么样"))
    assert "web" in route.source_ids
    assert "hackernews" in route.source_ids


def test_quick_mode_narrows_to_web_and_hn():
    reg = load_registry()
    r = Router(reg)
    route = r.plan(RouteRequest(query="anything", mode="quick"))
    assert set(route.source_ids) == {"web", "hackernews"}


def test_route_caps_at_five_sources():
    reg = load_registry()
    r = Router(reg)
    route = r.plan(RouteRequest(query="anything", mode="deep"))
    assert len(route.source_ids) <= 5


def test_unknown_explicit_source_recorded_in_route():
    reg = load_registry()
    r = Router(reg)
    route = r.plan(RouteRequest(query="x", explicit_sources=["hackernews", "twiter"]))
    assert route.source_ids == ["hackernews"]
    assert route.unknown_sources == ["twiter"]


def test_route_has_empty_unknown_sources_by_default():
    reg = load_registry()
    r = Router(reg)
    route = r.plan(RouteRequest(query="x"))
    assert route.unknown_sources == []

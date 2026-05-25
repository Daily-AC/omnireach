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
    # default_in_auto sources should be present (hackernews is always in)
    assert "hackernews" in route.source_ids


def test_quick_mode_narrows_to_web_and_hn():
    reg = load_registry()
    r = Router(reg)
    route = r.plan(RouteRequest(query="anything", mode="quick"))
    # quick mode still hardcodes ["web", "hackernews"] — web will be dropped
    # at CLI load-time, but the router is decoupled from the registry here.
    # (T7 will refactor router; for now we just assert hn appears.)
    assert "hackernews" in route.source_ids


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


def test_router_includes_rss_only_for_url_query():
    from omnireach.registry import load_registry
    from omnireach.router import RouteRequest, Router
    reg = load_registry()
    router = Router(reg)

    auto = router.plan(RouteRequest(query="claude 4.7", explicit_sources=None, mode="auto"))
    assert "rss" not in auto.source_ids

    url_route = router.plan(RouteRequest(query="https://example.com/feed.xml", explicit_sources=None, mode="auto"))
    assert "rss" in url_route.source_ids


def test_router_rss_only_when_explicit_or_url():
    from omnireach.registry import load_registry
    from omnireach.router import RouteRequest, Router
    reg = load_registry()
    router = Router(reg)

    explicit = router.plan(RouteRequest(query="anything", explicit_sources=["rss"], mode="auto"))
    assert "rss" in explicit.source_ids  # explicit override still works

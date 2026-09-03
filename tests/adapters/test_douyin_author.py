"""Douyin adapter: mapping the bridge catalog envelope onto SearchResult."""

import pytest

from omnireach.adapters.base import AdapterUnavailable
from omnireach.adapters.douyin import DouyinAdapter
from omnireach.browser_transport import BrowserCommandResult

SEC_UID = "MS4wLjABAAAAAAKy2_R6k-oFWT5E-97gbGZQ1laaweQMWImJDkDaef0"


def _work(index: int, likes: int) -> dict:
    return {
        "rank": index,
        "aweme_id": str(index),
        "desc": f"作品 {index}",
        "url": f"https://www.douyin.com/video/{index}",
        "author": "彭十六elf",
        "sec_uid": SEC_UID,
        "created_at": "2023-08-15T09:28:24.000Z",
        "duration_ms": 25843,
        "media_type": "video",
        "pinned": False,
        "likes": likes,
        "comments": 12,
        "shares": 3,
        "collects": 7,
        "plays": 0,
        "music": "@彭十六elf创作的原声",
        "hashtags": ["卢浮宫"],
        "video_tags": ["随拍"],
    }


def _catalog(**overrides) -> dict:
    return {
        "sec_uid": SEC_UID,
        "nickname": "彭十六elf",
        "followers": 28195000,
        "resolved_from": "search",
        "order": "recent",
        "pages": 83,
        "scanned": 355,
        "complete": True,
        "works": [_work(1, 30), _work(2, 10)],
        **overrides,
    }


def _stub_bridge(monkeypatch, items, captured=None):
    async def fake_run(source, command, payload, opencli_args=None, **kwargs):
        if captured is not None:
            captured.append({
                "source": source,
                "command": command,
                "payload": payload,
                "opencli_args": opencli_args,
                **kwargs,
            })
        return BrowserCommandResult(items=items, adapter="native-chrome")

    monkeypatch.setattr("omnireach.adapters.douyin.run_browser_json", fake_run)


async def test_author_maps_exact_counters_and_keeps_the_chosen_order(monkeypatch):
    captured = []
    _stub_bridge(monkeypatch, [_catalog()], captured)

    identity, results, stats = await DouyinAdapter().author(
        "彭十六", limit=2, order="recent", timeout=90,
    )

    assert identity.id == SEC_UID
    assert identity.followers == 28195000
    assert identity.url == f"https://www.douyin.com/user/{SEC_UID}"
    assert stats == {"order": "recent", "scanned": 355, "complete": True, "pages": 83}
    assert [result.engagement.likes for result in results] == [30, 10]
    # play_count is always 0 on this endpoint, so it must read as unknown.
    assert results[0].engagement.views is None
    assert results[0].engagement.collects == 7
    assert results[0].ts == "2023-08-15T09:28:24.000Z"
    assert results[0].raw["hashtags"] == ["卢浮宫"]
    # Descending scores keep the catalog order through any downstream re-sort.
    assert results[0].score > results[1].score
    assert captured[0]["command"] == "author"
    assert captured[0]["opencli_args"] is None
    assert captured[0]["result_timeout"] == 90
    assert captured[0]["payload"]["include_media_urls"] is False
    # The extension must stop before the bridge does, or a slow catalog returns
    # a bridge timeout instead of the works it already had.
    assert captured[0]["payload"]["budget_ms"] == 76500
    assert captured[0]["payload"]["budget_ms"] < 90 * 1000


async def test_author_forwards_the_media_url_opt_in(monkeypatch):
    captured = []
    _stub_bridge(monkeypatch, [_catalog()], captured)

    await DouyinAdapter().author("彭十六", include_media_urls=True)

    assert captured[0]["payload"]["include_media_urls"] is True


async def test_long_descriptions_become_bounded_titles(monkeypatch):
    work = _work(1, 30)
    work["desc"] = "长" * 600
    _stub_bridge(monkeypatch, [_catalog(works=[work])])

    _, results, _ = await DouyinAdapter().author("彭十六")

    assert len(results[0].title) == 81
    assert results[0].title.endswith("…")
    # content still runs through the shared 500-character snippet validator
    assert len(results[0].content) == 501
    assert results[0].content.endswith("…")


@pytest.mark.parametrize("items", [[], [{"sec_uid": SEC_UID}]])
async def test_malformed_bridge_envelope_is_rejected(monkeypatch, items):
    _stub_bridge(monkeypatch, items)

    with pytest.raises(AdapterUnavailable):
        await DouyinAdapter().author("彭十六")

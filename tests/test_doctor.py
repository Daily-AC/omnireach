import asyncio
import os

from omnireach.doctor import run_doctor


def test_doctor_reports_each_source(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda b: None)
    for env in ("TAVILY_API_KEY", "BRAVE_API_KEY", "PERPLEXITY_API_KEY", "EXA_API_KEY"):
        monkeypatch.delenv(env, raising=False)
    statuses = asyncio.run(run_doctor())
    ids = {s.id for s in statuses}
    assert {"hackernews", "youtube", "github", "reddit", "rss", "exa", "wechat", "bilibili"}.issubset(ids)


def test_doctor_marks_hackernews_ok(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda b: None)
    statuses = asyncio.run(run_doctor())
    hn = next(s for s in statuses if s.id == "hackernews")
    assert hn.ok is True


def test_doctor_marks_rss_ok(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda b: None)
    statuses = asyncio.run(run_doctor())
    rss = next(s for s in statuses if s.id == "rss")
    assert rss.ok is True


def test_doctor_no_wip_sources_in_v0_6():
    statuses = asyncio.run(run_doctor())
    wip = [s for s in statuses if s.tier == "wip"]
    assert wip == []


def test_doctor_marks_youtube_ok_with_binary(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda b: "/usr/bin/yt-dlp" if b == "yt-dlp" else None)
    statuses = asyncio.run(run_doctor())
    yt = next(s for s in statuses if s.id == "youtube")
    assert yt.ok is True


def test_doctor_marks_booster_ok_with_key(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda b: None)
    monkeypatch.setenv("EXA_API_KEY", "exa-x")
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)
    statuses = asyncio.run(run_doctor())
    exa = next(s for s in statuses if s.id == "exa")
    assert exa.ok is True
    tavily = next(s for s in statuses if s.id == "tavily")
    assert tavily.ok is False


def test_doctor_marks_wechat_ok_with_exa_key(monkeypatch):
    import asyncio
    from omnireach.doctor import run_doctor
    monkeypatch.setattr("shutil.which", lambda b: None)
    monkeypatch.setenv("EXA_API_KEY", "x")
    statuses = asyncio.run(run_doctor())
    wc = next(s for s in statuses if s.id == "wechat")
    assert wc.ok is True


def test_doctor_marks_bilibili_ok_with_exa_key(monkeypatch):
    import asyncio
    from omnireach.doctor import run_doctor
    monkeypatch.setattr("shutil.which", lambda b: None)
    monkeypatch.setenv("EXA_API_KEY", "x")
    statuses = asyncio.run(run_doctor())
    bili = next(s for s in statuses if s.id == "bilibili")
    assert bili.ok is True


def test_v093_fetch_backend_doctor_lists_crwl():
    """v0.9.3: doctor probes external fetch backends (currently just crwl)."""
    from omnireach.doctor import run_fetch_backend_doctor
    out = run_fetch_backend_doctor()
    tools = [b.tool for b in out]
    assert "crwl" in tools


def test_v093_fetch_backend_doctor_ok_when_binary_present(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda b: f"/usr/bin/{b}" if b == "crwl" else None)
    from omnireach.doctor import run_fetch_backend_doctor
    out = run_fetch_backend_doctor()
    crwl = next(b for b in out if b.tool == "crwl")
    assert crwl.ok is True
    assert "PATH" in crwl.detail
    assert crwl.fix_hint == ""


def test_v093_fetch_backend_doctor_fail_with_install_hint(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda b: None)
    from omnireach.doctor import run_fetch_backend_doctor
    out = run_fetch_backend_doctor()
    crwl = next(b for b in out if b.tool == "crwl")
    assert crwl.ok is False
    assert "不在 PATH" in crwl.detail
    assert "crawl4ai" in crwl.fix_hint
    assert "crawl4ai-setup" in crwl.fix_hint

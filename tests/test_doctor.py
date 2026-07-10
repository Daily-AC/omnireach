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


def test_fetch_backend_doctor_reports_builtin_http_without_external_binary(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda b: None)
    from omnireach.doctor import run_fetch_backend_doctor
    out = run_fetch_backend_doctor()
    http = next(b for b in out if b.tool == "http")
    assert http.ok is True
    assert "内置" in http.detail
    assert http.fix_hint == ""


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


# ============================================================
# v0.10.1: wechat backend (OpenCLI weixin download --stdout) doctor
# ============================================================


def test_v0101_wechat_backend_doctor_opencli_missing(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda b: None)
    from omnireach.doctor import run_wechat_backend_doctor
    out = run_wechat_backend_doctor()
    assert len(out) == 1
    wb = out[0]
    assert wb.tool == "opencli weixin"
    assert wb.ok is False
    assert "不在 PATH" in wb.detail
    assert "Daily-AC/OpenCLI" in wb.fix_hint


def test_v0101_wechat_backend_doctor_opencli_present_with_stdout(monkeypatch):
    """opencli on PATH AND --stdout flag in help output → ok=True."""
    monkeypatch.setattr("shutil.which", lambda b: f"/usr/local/bin/{b}" if b == "opencli" else None)
    from unittest.mock import MagicMock
    proc = MagicMock()
    proc.returncode = 0
    proc.stdout = """Usage: opencli weixin download [options]
Options:
  --url <url>
  --stdout  Print markdown to stdout
  --window <mode>
  --site-session <mode>
  --keep-tab <bool>
"""
    proc.stderr = ""
    monkeypatch.setattr("subprocess.run", lambda *a, **kw: proc)
    from omnireach.doctor import run_wechat_backend_doctor
    out = run_wechat_backend_doctor()
    wb = out[0]
    assert wb.ok is True
    assert "--stdout" in wb.detail or "在 PATH" in wb.detail


def test_wechat_backend_doctor_rejects_opencli_without_silent_tab_options(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda b: "/usr/local/bin/opencli" if b == "opencli" else None)
    from unittest.mock import MagicMock
    proc = MagicMock()
    proc.returncode = 0
    proc.stdout = "Usage: opencli weixin download\n  --stdout\n"
    proc.stderr = ""
    monkeypatch.setattr("subprocess.run", lambda *a, **kw: proc)
    from omnireach.doctor import run_wechat_backend_doctor
    wb = run_wechat_backend_doctor()[0]
    assert wb.ok is False
    assert "background" in wb.detail


def test_doctor_does_not_treat_openrouter_as_opencli(monkeypatch):
    monkeypatch.setattr(
        "shutil.which", lambda b: "/usr/bin/openrouter" if b == "openrouter" else None
    )
    statuses = asyncio.run(run_doctor())
    twitter = next(s for s in statuses if s.id == "twitter")
    assert twitter.ok is False
    assert "OpenCLI 不在 PATH" in twitter.detail


def test_doctor_reports_reddit_through_opencli(monkeypatch):
    monkeypatch.setattr(
        "shutil.which", lambda b: "/usr/bin/opencli" if b == "opencli" else None
    )
    statuses = asyncio.run(run_doctor())
    reddit = next(s for s in statuses if s.id == "reddit")
    assert reddit.ok is True
    assert reddit.tier == "heavy"
    assert "opencli" in reddit.detail


def test_v0101_wechat_backend_doctor_opencli_missing_stdout_flag(monkeypatch):
    """opencli installed but old build without --stdout flag → ok=False with fork hint."""
    monkeypatch.setattr("shutil.which", lambda b: f"/usr/local/bin/{b}" if b == "opencli" else None)
    from unittest.mock import MagicMock
    proc = MagicMock()
    proc.returncode = 0
    # Old build help text — no --stdout option listed
    proc.stdout = "Usage: opencli weixin download [options]\nOptions:\n  --url <url>\n  --output <dir>\n"
    proc.stderr = ""
    monkeypatch.setattr("subprocess.run", lambda *a, **kw: proc)
    from omnireach.doctor import run_wechat_backend_doctor
    out = run_wechat_backend_doctor()
    wb = out[0]
    assert wb.ok is False
    assert "--stdout" in wb.detail
    assert "Daily-AC/OpenCLI" in wb.fix_hint


def test_v0101_wechat_backend_doctor_opencli_help_nonzero(monkeypatch):
    """opencli installed but `weixin download` subcommand absent → ok=False."""
    monkeypatch.setattr("shutil.which", lambda b: f"/usr/local/bin/{b}" if b == "opencli" else None)
    from unittest.mock import MagicMock
    proc = MagicMock()
    proc.returncode = 1
    proc.stdout = ""
    proc.stderr = "unknown command: weixin"
    monkeypatch.setattr("subprocess.run", lambda *a, **kw: proc)
    from omnireach.doctor import run_wechat_backend_doctor
    out = run_wechat_backend_doctor()
    wb = out[0]
    assert wb.ok is False
    assert "weixin download" in wb.detail
    assert "Daily-AC/OpenCLI" in wb.fix_hint

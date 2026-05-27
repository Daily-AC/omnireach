"""Tests for `omnireach fetch <url>` subcommand (v0.10, v0.10.1 additions)."""

import json as _json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from omnireach.cli import main
from omnireach.commands.fetch import (
    _fetch_via_crwl,
    _fetch_via_jina,
    _fetch_via_opencli_weixin,
    _host_of,
    _looks_like_captcha,
    _resolve_backends,
    _should_emit_json,
)


def test_fetch_help_lists_backend_options():
    runner = CliRunner()
    res = runner.invoke(main, ["fetch", "--help"])
    assert res.exit_code == 0
    assert "crwl" in res.output
    assert "jina" in res.output
    assert "--backend" in res.output


def test_fetch_via_crwl_returns_subprocess_stdout(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda b: f"/usr/local/bin/{b}" if b == "crwl" else None)
    proc = MagicMock()
    proc.returncode = 0
    proc.stdout = "# article title\n\nbody content here"
    proc.stderr = ""
    monkeypatch.setattr("subprocess.run", lambda *a, **kw: proc)
    out = _fetch_via_crwl("https://example.com", timeout=10.0)
    assert "article title" in out


def test_fetch_via_crwl_missing_binary_raises(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda b: None)
    with pytest.raises(RuntimeError) as exc:
        _fetch_via_crwl("https://example.com", timeout=10.0)
    assert "crwl 不在 PATH" in str(exc.value)


def test_fetch_via_crwl_nonzero_exit_raises(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda b: f"/usr/local/bin/{b}")
    proc = MagicMock()
    proc.returncode = 1
    proc.stdout = ""
    proc.stderr = "boom"
    monkeypatch.setattr("subprocess.run", lambda *a, **kw: proc)
    with pytest.raises(RuntimeError) as exc:
        _fetch_via_crwl("https://example.com", timeout=10.0)
    assert "crwl 失败" in str(exc.value)


def test_fetch_via_jina_returns_response_text(monkeypatch):
    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.text = "# jina markdown\n\nhello"

    class FakeClient:
        def __init__(self, *a, **kw): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def get(self, url, headers=None): return fake_resp

    monkeypatch.setattr("omnireach.commands.fetch.httpx.Client", FakeClient)
    out = _fetch_via_jina("https://example.com", timeout=10.0)
    assert "jina markdown" in out


def test_fetch_via_jina_4xx_raises(monkeypatch):
    fake_resp = MagicMock()
    fake_resp.status_code = 404
    fake_resp.text = ""

    class FakeClient:
        def __init__(self, *a, **kw): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def get(self, url, headers=None): return fake_resp

    monkeypatch.setattr("omnireach.commands.fetch.httpx.Client", FakeClient)
    with pytest.raises(RuntimeError) as exc:
        _fetch_via_jina("https://example.com", timeout=10.0)
    assert "404" in str(exc.value)


def test_fetch_auto_falls_back_to_jina_when_crwl_missing(monkeypatch):
    """auto backend: crwl raises (not installed) → jina succeeds → use jina."""
    def fake_crwl(*a, **kw):
        raise RuntimeError("crwl 不在 PATH")
    def fake_jina(url, timeout):
        return "# from jina\nfallback worked"
    monkeypatch.setattr("omnireach.commands.fetch._fetch_via_crwl", fake_crwl)
    monkeypatch.setattr("omnireach.commands.fetch._fetch_via_jina", fake_jina)
    runner = CliRunner()
    res = runner.invoke(main, ["fetch", "https://example.com", "--json"])
    assert res.exit_code == 0
    json_line = next((l for l in res.output.splitlines() if l.strip().startswith("{")), None)
    assert json_line is not None
    data = _json.loads(json_line)
    assert data["backend"] == "jina"
    assert "fallback worked" in data["content_markdown"]


def test_fetch_explicit_crwl_backend_no_fallback(monkeypatch):
    """--backend crwl only tries crwl; if it fails, no jina fallback."""
    def fake_crwl(*a, **kw):
        raise RuntimeError("crwl 不在 PATH")
    monkeypatch.setattr("omnireach.commands.fetch._fetch_via_crwl", fake_crwl)
    runner = CliRunner()
    res = runner.invoke(main, ["fetch", "https://example.com", "--backend", "crwl", "--json"])
    json_line = next((l for l in res.output.splitlines() if l.strip().startswith("{")), None)
    assert json_line is not None
    data = _json.loads(json_line)
    assert data["backend"] is None
    assert data["content_markdown"] == ""
    assert any("crwl" in e for e in data["errors"])


def test_fetch_returns_envelope_with_url_and_backend(monkeypatch):
    monkeypatch.setattr("omnireach.commands.fetch._fetch_via_crwl",
                        lambda url, timeout: "# hello")
    runner = CliRunner()
    res = runner.invoke(main, ["fetch", "https://example.com", "--json"])
    json_line = next((l for l in res.output.splitlines() if l.strip().startswith("{")), None)
    data = _json.loads(json_line)
    assert data["url"] == "https://example.com"
    assert data["backend"] == "crwl"
    assert data["content_markdown"] == "# hello"
    assert data["fetched_at"].endswith("Z")
    assert data["errors"] == []


def test_should_emit_json_explicit_flag_wins():
    assert _should_emit_json(True) is True


def test_should_emit_json_force_env_var(monkeypatch):
    """v0.10: OMNIREACH_FORCE_JSON=1 forces JSON regardless of TTY state."""
    monkeypatch.setenv("OMNIREACH_FORCE_JSON", "1")
    # Even with explicit_flag=False and (hypothetically) isatty=True, should be True
    assert _should_emit_json(False) is True


def test_should_emit_json_force_env_var_accepts_true_yes(monkeypatch):
    for val in ("true", "yes", "TRUE", "YES"):
        monkeypatch.setenv("OMNIREACH_FORCE_JSON", val)
        assert _should_emit_json(False) is True


def test_should_emit_json_force_env_var_off(monkeypatch):
    """OMNIREACH_FORCE_JSON=0 or empty doesn't force; isatty rules."""
    monkeypatch.setenv("OMNIREACH_FORCE_JSON", "0")
    # In CliRunner (non-TTY), should still emit JSON via isatty path
    monkeypatch.setattr("omnireach.commands.fetch.sys.stdout.isatty", lambda: True)
    assert _should_emit_json(False) is False


# ============================================================
# v0.10.1: OpenCLI wechat backend + host-aware routing + CAPTCHA heuristic
# ============================================================


def test_v0101_host_of_extracts_mp_weixin():
    assert _host_of("https://mp.weixin.qq.com/s/abc123") == "mp.weixin.qq.com"
    assert _host_of("https://example.com/foo") == "example.com"
    assert _host_of("not-a-url") == ""


def test_v0101_resolve_backends_auto_wechat_url_goes_opencli():
    """auto + mp.weixin.qq.com → opencli only (no crwl/jina fallback)."""
    assert _resolve_backends("https://mp.weixin.qq.com/s/abc", "auto") == ["opencli"]


def test_v0101_resolve_backends_auto_other_host_preserves_v010():
    """auto + non-wechat host → crwl → jina (v0.10 behavior preserved)."""
    assert _resolve_backends("https://example.com/foo", "auto") == ["crwl", "jina"]


def test_v0101_resolve_backends_explicit_crwl_wins_on_wechat_url():
    """Explicit --backend crwl on mp.weixin.qq.com URL → crwl, NOT opencli.

    Locks the spec §11 Q2 ack semantic: user's explicit choice respected,
    CAPTCHA heuristic will surface verification-page warning afterwards.
    """
    assert _resolve_backends("https://mp.weixin.qq.com/s/abc", "crwl") == ["crwl"]
    assert _resolve_backends("https://mp.weixin.qq.com/s/abc", "jina") == ["jina"]
    assert _resolve_backends("https://mp.weixin.qq.com/s/abc", "opencli") == ["opencli"]


def test_v0101_fetch_via_opencli_missing_binary_raises(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda b: None)
    with pytest.raises(RuntimeError) as exc:
        _fetch_via_opencli_weixin("https://mp.weixin.qq.com/s/abc", timeout=10.0)
    assert "opencli 不在 PATH" in str(exc.value)


def test_v0101_fetch_via_opencli_nonzero_exit_raises(monkeypatch):
    """Branch 1: retcode != 0 → opencli_failed with stderr surfaced."""
    monkeypatch.setattr("shutil.which", lambda b: f"/usr/local/bin/{b}")
    proc = MagicMock()
    proc.returncode = 1
    proc.stdout = ""
    proc.stderr = "could not launch chrome profile"
    monkeypatch.setattr("subprocess.run", lambda *a, **kw: proc)
    with pytest.raises(RuntimeError) as exc:
        _fetch_via_opencli_weixin("https://mp.weixin.qq.com/s/abc", timeout=10.0)
    assert "opencli 失败" in str(exc.value)
    assert "could not launch" in str(exc.value)


def test_v0101_fetch_via_opencli_verification_row_raises_captcha_suspected(monkeypatch):
    """Branch 2: retcode=0 + JSON row with verification-required status."""
    monkeypatch.setattr("shutil.which", lambda b: f"/usr/local/bin/{b}")
    proc = MagicMock()
    proc.returncode = 0
    proc.stdout = _json.dumps([{
        "title": "Error",
        "author": "-",
        "publish_time": "-",
        "status": "failed — verification required in WeChat browser page",
        "size": "-",
        "saved": "-",
    }])
    proc.stderr = ""
    monkeypatch.setattr("subprocess.run", lambda *a, **kw: proc)
    with pytest.raises(RuntimeError) as exc:
        _fetch_via_opencli_weixin("https://mp.weixin.qq.com/s/blocked", timeout=10.0)
    assert "captcha_suspected" in str(exc.value)
    assert "verification required" in str(exc.value)


def test_v0101_fetch_via_opencli_markdown_starting_with_bracket_is_branch_3(monkeypatch):
    """Branch 3: retcode=0 + stdout is real markdown that happens to start with [.

    Lock against the §7.1 startswith-bug regression: a legit article body
    like `[作者按] 这是真文章` must not be misparsed as a JSON row.
    """
    monkeypatch.setattr("shutil.which", lambda b: f"/usr/local/bin/{b}")
    proc = MagicMock()
    proc.returncode = 0
    proc.stdout = "[作者按] 这是真文章\n\n正文内容..."
    proc.stderr = ""
    monkeypatch.setattr("subprocess.run", lambda *a, **kw: proc)
    out = _fetch_via_opencli_weixin("https://mp.weixin.qq.com/s/real", timeout=10.0)
    assert "[作者按]" in out
    assert "正文内容" in out


def test_v0101_fetch_via_opencli_happy_path_plain_markdown(monkeypatch):
    """Branch 3: typical success — markdown body straight to stdout."""
    monkeypatch.setattr("shutil.which", lambda b: f"/usr/local/bin/{b}")
    proc = MagicMock()
    proc.returncode = 0
    proc.stdout = "# 测试文章\n\n> 公众号: 某号\n\n---\n\n正文段落"
    proc.stderr = ""
    monkeypatch.setattr("subprocess.run", lambda *a, **kw: proc)
    out = _fetch_via_opencli_weixin("https://mp.weixin.qq.com/s/abc", timeout=10.0)
    assert out.startswith("# 测试文章")
    assert "正文段落" in out


def test_v0101_looks_like_captcha_detects_wechat_verification_keyword():
    body = "# 看着像文章\n\n" + "x" * 300 + "\n\n环境异常，完成验证后即可继续访问"
    suspicious, kw = _looks_like_captcha(body)
    assert suspicious is True
    assert kw == "环境异常"


def test_v0101_looks_like_captcha_detects_cloudflare():
    body = ("# Stub\n\n" + "Just a moment, Checking your browser before accessing" + "y" * 250)
    suspicious, kw = _looks_like_captcha(body)
    assert suspicious is True
    # Either Just a moment or Checking your browser may match first depending on order
    assert kw in ("Just a moment", "Checking your browser")


def test_v0101_looks_like_captcha_short_payload_returns_false():
    """Short responses don't trigger heuristic (too noisy)."""
    suspicious, _ = _looks_like_captcha("环境异常")
    assert suspicious is False


def test_v0101_looks_like_captcha_real_article_not_flagged():
    body = "# Real article title\n\n" + "This is a long-enough body paragraph with normal content. " * 20
    suspicious, kw = _looks_like_captcha(body)
    assert suspicious is False
    assert kw is None


def test_v0101_fetch_wechat_url_auto_routes_to_opencli(monkeypatch):
    """End-to-end CLI: --backend auto + mp.weixin.qq.com URL → opencli, not crwl."""
    called: dict[str, bool] = {"crwl": False, "jina": False, "opencli": False}

    def fake_crwl(*a, **kw):
        called["crwl"] = True
        return "should not be called"

    def fake_jina(*a, **kw):
        called["jina"] = True
        return "should not be called"

    def fake_opencli(url, timeout):
        called["opencli"] = True
        return "# 文章 via opencli"

    monkeypatch.setattr("omnireach.commands.fetch._fetch_via_crwl", fake_crwl)
    monkeypatch.setattr("omnireach.commands.fetch._fetch_via_jina", fake_jina)
    monkeypatch.setattr("omnireach.commands.fetch._fetch_via_opencli_weixin", fake_opencli)
    runner = CliRunner()
    res = runner.invoke(main, ["fetch", "https://mp.weixin.qq.com/s/abc", "--json"])
    assert res.exit_code == 0
    json_line = next((l for l in res.output.splitlines() if l.strip().startswith("{")), None)
    data = _json.loads(json_line)
    assert data["backend"] == "opencli"
    assert "via opencli" in data["content_markdown"]
    assert called["opencli"] is True
    assert called["crwl"] is False
    assert called["jina"] is False


def test_v0101_fetch_wechat_url_explicit_backend_crwl_respects_user(monkeypatch):
    """Explicit --backend crwl on mp.weixin.qq.com URL → crwl runs (NOT opencli).

    Locks spec §11 Q2: user's explicit choice wins. The crwl response that
    looks like a CAPTCHA should trigger the heuristic and add a
    captcha_suspected entry to errors.
    """
    called: dict[str, bool] = {"crwl": False, "opencli": False}

    def fake_crwl(url, timeout):
        called["crwl"] = True
        # Mock crwl returning a verification page (long enough to pass the 200-char gate)
        return "# Page\n\n" + "环境异常，完成验证后即可继续访问 " * 30

    def fake_opencli(*a, **kw):
        called["opencli"] = True
        return "should not be called"

    monkeypatch.setattr("omnireach.commands.fetch._fetch_via_crwl", fake_crwl)
    monkeypatch.setattr("omnireach.commands.fetch._fetch_via_opencli_weixin", fake_opencli)
    runner = CliRunner()
    res = runner.invoke(main, [
        "fetch", "https://mp.weixin.qq.com/s/abc", "--backend", "crwl", "--json",
    ])
    assert res.exit_code == 0
    json_line = next((l for l in res.output.splitlines() if l.strip().startswith("{")), None)
    data = _json.loads(json_line)
    assert called["crwl"] is True, "explicit --backend crwl must run crwl"
    assert called["opencli"] is False, "explicit --backend crwl must NOT run opencli"
    assert data["backend"] == "crwl"
    # Graceful degrade: markdown still returned (Agent can decide), errors flags CAPTCHA
    assert "环境异常" in data["content_markdown"]
    assert any("captcha_suspected" in e for e in data["errors"])


def test_v0101_fetch_crwl_captcha_heuristic_flags_cloudflare(monkeypatch):
    """crwl returns Cloudflare verification page on non-wechat host → errors has captcha_suspected."""
    def fake_crwl(url, timeout):
        return ("# Page\n\nJust a moment, Checking your browser " + "x" * 250)

    monkeypatch.setattr("omnireach.commands.fetch._fetch_via_crwl", fake_crwl)
    runner = CliRunner()
    res = runner.invoke(main, [
        "fetch", "https://example.com/article", "--backend", "crwl", "--json",
    ])
    json_line = next((l for l in res.output.splitlines() if l.strip().startswith("{")), None)
    data = _json.loads(json_line)
    assert data["backend"] == "crwl"
    assert any("captcha_suspected" in e for e in data["errors"])


def test_v0101_fetch_jina_captcha_heuristic_flags(monkeypatch):
    """jina returns CAPTCHA-shaped content → errors has captcha_suspected."""
    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.text = ("# Stub\n\n请输入验证码 " + "padding " * 60)

    class FakeClient:
        def __init__(self, *a, **kw): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def get(self, url, headers=None): return fake_resp

    monkeypatch.setattr("omnireach.commands.fetch.httpx.Client", FakeClient)
    runner = CliRunner()
    res = runner.invoke(main, [
        "fetch", "https://example.com/page", "--backend", "jina", "--json",
    ])
    json_line = next((l for l in res.output.splitlines() if l.strip().startswith("{")), None)
    data = _json.loads(json_line)
    assert data["backend"] == "jina"
    assert any("captcha_suspected" in e for e in data["errors"])


def test_v0101_fetch_help_lists_opencli_backend_choice():
    """The new opencli backend must be visible in --help so users can discover it."""
    runner = CliRunner()
    res = runner.invoke(main, ["fetch", "--help"])
    assert res.exit_code == 0
    assert "opencli" in res.output

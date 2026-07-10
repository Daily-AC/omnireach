import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.parent


def test_plugin_manifest_is_valid_json():
    data = json.loads((PROJECT_ROOT / ".claude-plugin" / "plugin.json").read_text())
    assert data["name"] == "omnireach"
    assert "skills" in data["components"]


def test_skill_md_exists_and_has_required_frontmatter():
    skill_md = (PROJECT_ROOT / ".claude-plugin" / "skills" / "omnireach" / "SKILL.md").read_text()
    assert skill_md.startswith("---")
    assert "name: omnireach" in skill_md
    assert "description:" in skill_md


def test_skill_md_documents_cli_invocation():
    skill_md = (PROJECT_ROOT / ".claude-plugin" / "skills" / "omnireach" / "SKILL.md").read_text()
    assert "omnireach" in skill_md
    assert "pipx" in skill_md.lower() or "install" in skill_md.lower()


def test_plugin_registers_omnireach_mcp_server():
    data = json.loads((PROJECT_ROOT / ".mcp.json").read_text())
    server = data["mcpServers"]["omnireach"]
    assert server == {"command": "omnireach", "args": ["mcp"]}


def test_skill_requires_mcp_before_browser_automation():
    text = (
        PROJECT_ROOT / ".claude-plugin" / "skills" / "omnireach" / "SKILL.md"
    ).read_text().lower()
    assert "omnireach_search" in text
    assert "omnireach_fetch" in text
    assert "playwright" in text
    assert text.index("omnireach_search") < text.index("playwright")


def test_skill_cli_reference_exists_and_is_installed():
    reference = (
        PROJECT_ROOT
        / ".claude-plugin"
        / "skills"
        / "omnireach"
        / "references"
        / "cli.md"
    )
    assert reference.exists()
    install = (PROJECT_ROOT / "install.sh").read_text()
    assert "references/cli.md" in install

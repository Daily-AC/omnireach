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

"""T4 (AST-15 O1-B): agent write denylist on trusted config/skill paths.

file_write and file_edit must refuse to modify the agent's own persistence
surface — ~/.bytia-kode/.env, ~/.bytia-kode/mcp_servers.json,
~/.bytia-kode/skills/**, ~/bytia/skills/** — while reads stay allowed.

The fixture mirrors the production trust setup (agent.py:
set_trusted_paths([data_dir, ~/bytia]) + set_workspace_root(project)) with
Path.home() monkeypatched to tmp_path.
"""
from pathlib import Path

import pytest

import bytia_kode.tools.registry as registry
from bytia_kode.tools.registry import (
    FileEditTool,
    FileReadTool,
    FileWriteTool,
    set_workspace_root,
)


@pytest.fixture
def trusted_home(tmp_path, monkeypatch):
    """Fake $HOME: ~/.bytia-kode and ~/bytia trusted, project/ as workspace."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    data_dir = tmp_path / ".bytia-kode"
    bytia_dir = tmp_path / "bytia"
    project = tmp_path / "project"
    data_dir.mkdir(parents=True)
    bytia_dir.mkdir(parents=True)
    project.mkdir()
    saved = list(registry._TRUSTED_PATHS)
    registry._TRUSTED_PATHS.clear()
    registry._TRUSTED_PATHS.extend([data_dir.resolve(), bytia_dir.resolve()])
    set_workspace_root(project)
    yield tmp_path
    registry._TRUSTED_PATHS.clear()
    registry._TRUSTED_PATHS.extend(saved)


@pytest.mark.asyncio
async def test_file_write_global_env_denied(trusted_home):
    target = trusted_home / ".bytia-kode" / ".env"
    result = await FileWriteTool().execute(
        path=str(target), content="PROVIDER_BASE_URL=http://evil.example/v1\n"
    )
    assert result.error
    assert "Security violation" in result.output
    assert "read-only for the agent" in result.output
    assert not target.exists()


@pytest.mark.asyncio
async def test_file_write_mcp_servers_denied(trusted_home):
    target = trusted_home / ".bytia-kode" / "mcp_servers.json"
    result = await FileWriteTool().execute(path=str(target), content='{"x": 1}')
    assert result.error
    assert "Security violation" in result.output
    assert not target.exists()


@pytest.mark.asyncio
async def test_file_write_agent_skills_denied(trusted_home):
    target = trusted_home / ".bytia-kode" / "skills" / "user" / "evil" / "SKILL.md"
    result = await FileWriteTool().execute(path=str(target), content="# owned\n")
    assert result.error
    assert "Security violation" in result.output
    assert not target.exists()


@pytest.mark.asyncio
async def test_file_write_bytia_skills_denied(trusted_home):
    target = trusted_home / "bytia" / "skills" / "pwn" / "SKILL.md"
    result = await FileWriteTool().execute(path=str(target), content="# owned\n")
    assert result.error
    assert "Security violation" in result.output
    assert not target.exists()


@pytest.mark.asyncio
async def test_file_edit_replace_env_denied(trusted_home):
    target = trusted_home / ".bytia-kode" / ".env"
    target.write_text("PROVIDER_API_KEY=legit\n")
    result = await FileEditTool().execute(
        path=str(target), strategy="replace",
        old_text="legit", new_text="stolen",
    )
    assert result.error
    assert "Security violation" in result.output
    assert target.read_text() == "PROVIDER_API_KEY=legit\n"  # untouched


@pytest.mark.asyncio
async def test_file_edit_create_in_skills_denied(trusted_home):
    target = trusted_home / ".bytia-kode" / "skills" / "x" / "SKILL.md"
    result = await FileEditTool().execute(
        path=str(target), strategy="create", content="# persistent payload\n"
    )
    assert result.error
    assert "Security violation" in result.output
    assert not target.exists()


@pytest.mark.asyncio
async def test_reads_still_allowed(trusted_home):
    """Reads are deliberately NOT denied (documented decision, T4)."""
    target = trusted_home / ".bytia-kode" / ".env"
    target.write_text("SECRET=keepme\n")
    result = await FileReadTool().execute(path=str(target))
    assert not result.error
    assert "SECRET=keepme" in result.output


@pytest.mark.asyncio
async def test_ordinary_trusted_data_write_unaffected(trusted_home):
    """Session data inside ~/.bytia-kode (non-denylisted) stays writable."""
    target = trusted_home / ".bytia-kode" / "sessions" / "note.md"
    result = await FileWriteTool().execute(path=str(target), content="ok\n")
    assert not result.error, result.output
    assert target.exists()


@pytest.mark.asyncio
async def test_project_write_unaffected(trusted_home):
    target = trusted_home / "project" / "notes.md"
    result = await FileWriteTool().execute(path=str(target), content="ok\n")
    assert not result.error, result.output
    assert target.exists()

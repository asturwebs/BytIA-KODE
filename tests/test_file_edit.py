"""Tests for FileEditTool — search/replace and create strategies."""
import pytest
from pathlib import Path
from bytia_kode.tools.registry import FileEditTool


@pytest.fixture
def tool():
    return FileEditTool()


@pytest.fixture
def tmp_workspace(tmp_path, monkeypatch):
    """Set tmp_path as CWD so _resolve_workspace_path works."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.mark.asyncio
async def test_replace_single_occurrence(tool, tmp_workspace):
    f = tmp_workspace / "test.py"
    f.write_text("def hello():\n    print('world')\n")

    result = await tool.execute(
        path=str(f),
        strategy="replace",
        old_text="print('world')",
        new_text="print('hello')",
    )
    assert not result.error
    assert "Replaced 1 occurrence" in result.output
    assert f.read_text() == "def hello():\n    print('hello')\n"


@pytest.mark.asyncio
async def test_replace_multiple_without_flag(tool, tmp_workspace):
    f = tmp_workspace / "test.py"
    f.write_text("foo = 1\nfoo = 2\n")

    result = await tool.execute(
        path=str(f),
        strategy="replace",
        old_text="foo",
        new_text="bar",
    )
    assert result.error
    assert "Found 2 occurrences" in result.output


@pytest.mark.asyncio
async def test_replace_all_flag(tool, tmp_workspace):
    f = tmp_workspace / "test.py"
    f.write_text("foo = 1\nfoo = 2\n")

    result = await tool.execute(
        path=str(f),
        strategy="replace",
        old_text="foo",
        new_text="bar",
        replace_all=True,
    )
    assert not result.error
    assert "Replaced 2 occurrence" in result.output
    assert f.read_text() == "bar = 1\nbar = 2\n"


@pytest.mark.asyncio
async def test_replace_not_found(tool, tmp_workspace):
    f = tmp_workspace / "test.py"
    f.write_text("hello world\n")

    result = await tool.execute(
        path=str(f),
        strategy="replace",
        old_text="not here",
        new_text="replacement",
    )
    assert result.error
    assert "not found" in result.output


@pytest.mark.asyncio
async def test_replace_strips_indented_text(tool, tmp_workspace):
    """Replace should work when old_text is a substring of the line."""
    f = tmp_workspace / "test.py"
    f.write_text("    print('hello')\n")

    result = await tool.execute(
        path=str(f),
        strategy="replace",
        old_text="print('hello')",  # substring of the indented line
        new_text="print('bye')",
    )
    # Python 'in' does substring matching, so this replaces successfully
    assert not result.error
    assert f.read_text() == "    print('bye')\n"


@pytest.mark.asyncio
async def test_create_new_file(tool, tmp_workspace):
    f = tmp_workspace / "new.py"

    result = await tool.execute(
        path=str(f),
        strategy="create",
        content="# hello\nprint('world')\n",
    )
    assert not result.error
    assert "Created" in result.output
    assert f.read_text() == "# hello\nprint('world')\n"


@pytest.mark.asyncio
async def test_create_existing_file_no_force(tool, tmp_workspace):
    f = tmp_workspace / "existing.py"
    f.write_text("original\n")

    result = await tool.execute(
        path=str(f),
        strategy="create",
        content="new content\n",
    )
    assert result.error
    assert "already exists" in result.output
    assert f.read_text() == "original\n"  # unchanged


@pytest.mark.asyncio
async def test_create_existing_file_with_force(tool, tmp_workspace):
    f = tmp_workspace / "existing.py"
    f.write_text("original\n")

    result = await tool.execute(
        path=str(f),
        strategy="create",
        content="new content\n",
        force=True,
    )
    assert not result.error
    assert f.read_text() == "new content\n"


@pytest.mark.asyncio
async def test_path_traversal_blocked(tool, tmp_workspace):
    result = await tool.execute(
        path="../../../etc/passwd",
        strategy="replace",
        old_text="x",
        new_text="y",
    )
    assert result.error
    assert "Security" in result.output or "escapes" in result.output


@pytest.mark.asyncio
async def test_file_not_found(tool, tmp_workspace):
    result = await tool.execute(
        path="nonexistent.py",
        strategy="replace",
        old_text="x",
        new_text="y",
    )
    assert result.error
    assert "not found" in result.output.lower()


@pytest.mark.asyncio
async def test_create_without_content(tool, tmp_workspace):
    result = await tool.execute(
        path="new.py",
        strategy="create",
    )
    assert result.error
    assert "content" in result.output.lower()


@pytest.mark.asyncio
async def test_replace_without_old_text(tool, tmp_workspace):
    f = tmp_workspace / "test.py"
    f.write_text("hello\n")

    result = await tool.execute(
        path=str(f),
        strategy="replace",
        new_text="bye",
    )
    assert result.error
    assert "old_text" in result.output


@pytest.mark.asyncio
async def test_unknown_strategy(tool, tmp_workspace):
    result = await tool.execute(
        path="test.py",
        strategy="delete",
    )
    assert result.error
    assert "Unknown strategy" in result.output


@pytest.mark.asyncio
async def test_diff_shows_changes(tool, tmp_workspace):
    f = tmp_workspace / "test.py"
    f.write_text("line1\nline2\nline3\n")

    result = await tool.execute(
        path=str(f),
        strategy="replace",
        old_text="line2",
        new_text="modified",
    )
    assert not result.error
    assert "-line2" in result.output
    assert "+modified" in result.output

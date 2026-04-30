import asyncio
from pathlib import Path

import pytest

from bytia_kode.tools.registry import (
    GrepTool,
    GlobTool,
    TreeTool,
    ToolRegistry,
)
from bytia_kode.tools.registry import set_workspace_root


@pytest.fixture(autouse=True)
def _set_workspace(tmp_path):
    set_workspace_root(tmp_path)


class TestGrepTool:
    def test_registered(self):
        assert ToolRegistry().get("grep") is not None

    def test_finds_pattern_in_file(self, tmp_path):
        (tmp_path / "hello.py").write_text("def greet():\n    return 'hello'\n")

        async def run():
            return await GrepTool().execute(pattern="greet", path=str(tmp_path))

        result = asyncio.run(run())
        assert not result.error
        assert "greet" in result.output

    def test_no_match(self, tmp_path):
        (tmp_path / "empty.py").write_text("pass\n")

        async def run():
            return await GrepTool().execute(pattern="nonexistent", path=str(tmp_path))

        result = asyncio.run(run())
        assert "No matches found" in result.output

    def test_include_filter(self, tmp_path):
        (tmp_path / "code.py").write_text("TARGET_PATTERN = True\n")
        (tmp_path / "readme.md").write_text("TARGET_PATTERN here too\n")

        async def run():
            return await GrepTool().execute(
                pattern="TARGET_PATTERN", path=str(tmp_path), include="*.py"
            )

        result = asyncio.run(run())
        assert "code.py" in result.output
        assert "readme.md" not in result.output

    def test_single_file_search(self, tmp_path):
        f = tmp_path / "single.txt"
        f.write_text("line1 match\nline2\nline3 match\n")

        async def run():
            return await GrepTool().execute(pattern="match", path=str(f))

        result = asyncio.run(run())
        assert not result.error
        assert result.output.count("match") == 2


class TestGlobTool:
    def test_registered(self):
        assert ToolRegistry().get("glob") is not None

    def test_finds_python_files(self, tmp_path):
        (tmp_path / "a.py").write_text("")
        (tmp_path / "b.py").write_text("")
        (tmp_path / "c.txt").write_text("")

        async def run():
            return await GlobTool().execute(pattern="*.py", path=str(tmp_path))

        result = asyncio.run(run())
        assert "a.py" in result.output
        assert "b.py" in result.output
        assert "c.txt" not in result.output

    def test_recursive_glob(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "deep.py").write_text("")

        async def run():
            return await GlobTool().execute(pattern="**/*.py", path=str(tmp_path))

        result = asyncio.run(run())
        assert "deep.py" in result.output

    def test_no_matches(self, tmp_path):
        async def run():
            return await GlobTool().execute(pattern="*.xyz", path=str(tmp_path))

        result = asyncio.run(run())
        assert "No files found" in result.output

    def test_not_a_directory(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("content")

        async def run():
            return await GlobTool().execute(pattern="*", path=str(f))

        result = asyncio.run(run())
        assert result.error


class TestTreeTool:
    def test_registered(self):
        assert ToolRegistry().get("tree") is not None

    def test_shows_structure(self, tmp_path):
        (tmp_path / "file.py").write_text("")
        sub = tmp_path / "subdir"
        sub.mkdir()
        (sub / "inner.txt").write_text("hello")

        async def run():
            return await TreeTool().execute(path=str(tmp_path), depth=2)

        result = asyncio.run(run())
        assert "file.py" in result.output
        assert "subdir/" in result.output
        assert "inner.txt" in result.output

    def test_depth_limit(self, tmp_path):
        d1 = tmp_path / "a"
        d1.mkdir()
        d2 = d1 / "b"
        d2.mkdir()
        (d2 / "deep.py").write_text("")

        async def run():
            return await TreeTool().execute(path=str(tmp_path), depth=1)

        result = asyncio.run(run())
        assert "a/" in result.output
        assert "deep.py" not in result.output

    def test_empty_directory(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()

        async def run():
            return await TreeTool().execute(path=str(empty))

        result = asyncio.run(run())
        assert "Empty directory" in result.output

    def test_hides_pycache(self, tmp_path):
        cache = tmp_path / "__pycache__"
        cache.mkdir()
        (cache / "mod.pyc").write_bytes(b"\x00")
        (tmp_path / "code.py").write_text("")

        async def run():
            return await TreeTool().execute(path=str(tmp_path))

        result = asyncio.run(run())
        assert "__pycache__" not in result.output
        assert "code.py" in result.output

    def test_file_sizes(self, tmp_path):
        (tmp_path / "big.bin").write_bytes(b"\x00" * (2 * 1024 * 1024))
        (tmp_path / "small.txt").write_text("hi")

        async def run():
            return await TreeTool().execute(path=str(tmp_path))

        result = asyncio.run(run())
        assert "2MB" in result.output


class TestPanicButtons:
    def test_interrupt_sets_event(self, tmp_path):
        from bytia_kode.agent import Agent
        from bytia_kode.config import AppConfig

        agent = Agent(AppConfig(data_dir=tmp_path / "panic1"))
        assert not agent._cancel_event.is_set()
        agent.interrupt()
        assert agent._cancel_event.is_set()

    def test_kill_clears_event(self, tmp_path):
        from bytia_kode.agent import Agent
        from bytia_kode.config import AppConfig

        agent = Agent(AppConfig(data_dir=tmp_path / "panic2"))
        agent.interrupt()
        assert agent._cancel_event.is_set()
        asyncio.run(agent.kill())
        assert not agent._cancel_event.is_set()

    def test_subprocess_starts_none(self, tmp_path):
        from bytia_kode.agent import Agent
        from bytia_kode.config import AppConfig

        agent = Agent(AppConfig(data_dir=tmp_path / "panic3"))
        assert agent._active_subprocess is None

"""Tests for workspace context generation."""
import hashlib
from pathlib import Path
from unittest.mock import patch

import pytest

from bytia_kode.context import workspace_hash, generate_context, context_path


class TestWorkspaceHash:
    def test_same_path_same_hash(self):
        h1 = workspace_hash("/home/user/project")
        h2 = workspace_hash("/home/user/project")
        assert h1 == h2

    def test_different_paths_different_hash(self):
        h1 = workspace_hash("/home/user/project-a")
        h2 = workspace_hash("/home/user/project-b")
        assert h1 != h2

    def test_hash_is_8_chars(self):
        h = workspace_hash("/any/path")
        assert len(h) == 8


class TestContextPath:
    def test_returns_path_in_contexts_dir(self, tmp_path):
        with patch("bytia_kode.context.CONTEXTS_DIR", tmp_path):
            p = context_path("/home/user/project")
            assert p.parent == tmp_path
            assert p.name.endswith(".md")

    def test_hash_consistency(self, tmp_path):
        with patch("bytia_kode.context.CONTEXTS_DIR", tmp_path):
            p1 = context_path("/home/user/project")
            p2 = context_path("/home/user/project")
            assert p1 == p2


class TestGenerateContext:
    def test_generates_file(self, tmp_path):
        project = tmp_path / "myproject"
        project.mkdir()
        content = generate_context(project)
        assert "# Workspace Context" in content
        assert "myproject" in content

    def test_detects_python_project(self, tmp_path):
        project = tmp_path / "myproject"
        project.mkdir()
        (project / "pyproject.toml").write_text("[project]\nname='myproject'\n")
        (project / "src").mkdir()
        content = generate_context(project)
        assert "Python" in content
        assert "myproject" in content

    def test_detects_node_project(self, tmp_path):
        project = tmp_path / "myproject"
        project.mkdir()
        (project / "package.json").write_text('{"name": "myproject"}')
        content = generate_context(project)
        assert "Node" in content or "JavaScript" in content

    def test_no_project_file(self, tmp_path):
        project = tmp_path / "empty"
        project.mkdir()
        content = generate_context(project)
        assert "# Workspace Context" in content

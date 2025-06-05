#!/usr/bin/env python3
"""Tests for Phase 4 scaffold functionality."""

from pathlib import Path

import pytest

# Import the cleanup script
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from master_cleanup import MasterCleanup  # noqa: E402


class TestPhase4Scaffold:
    """Test suite for Phase 4 scaffold functionality."""

    def test_write_pyproject(self, tmp_path):
        """Test pyproject.toml creation."""
        # Create a simple Python file
        (tmp_path / "foo.py").write_text("print('x')")

        # Run the scaffold
        mc = MasterCleanup(tmp_path, dry_run=False, skip_git=True)
        mc.write_pyproject()

        # Check that pyproject.toml was created
        pyproject_path = tmp_path / "pyproject.toml"
        assert pyproject_path.exists()

        # Check content
        txt = pyproject_path.read_text()
        assert "[project]" in txt
        assert 'name = "' in txt
        assert 'version = "0.0.0"' in txt
        assert 'authors = ["Unknown <user@example.com>"]' in txt
        assert 'requires-python = ">=3.8"' in txt

        # Check that project name is derived from directory
        project_name = tmp_path.name.lower().replace(" ", "-")
        assert f'name = "{project_name}"' in txt

    def test_write_pyproject_already_exists(self, tmp_path):
        """Test that existing pyproject.toml is not overwritten."""
        # Create existing pyproject.toml with custom content
        existing_content = """[project]
name = "my-custom-project"
version = "1.2.3"
"""
        pyproject_path = tmp_path / "pyproject.toml"
        pyproject_path.write_text(existing_content)

        # Run the scaffold
        mc = MasterCleanup(tmp_path, dry_run=False, skip_git=True)
        mc.write_pyproject()

        # Check that content was not changed
        assert pyproject_path.read_text() == existing_content

    def test_write_pyproject_summary(self, tmp_path):
        """Test that scaffold updates summary."""
        mc = MasterCleanup(tmp_path, dry_run=False, skip_git=True)
        mc.write_pyproject()

        # Check summary was updated
        assert "scaffold_pyproject" in mc.summary
        assert mc.summary["scaffold_pyproject"] == str(tmp_path / "pyproject.toml")

    def test_write_pyproject_handles_spaces_in_name(self, tmp_path):
        """Test that spaces in directory names are handled."""
        # Create a directory with spaces
        project_dir = tmp_path / "My Cool Project"
        project_dir.mkdir()

        mc = MasterCleanup(project_dir, dry_run=False, skip_git=True)
        mc.write_pyproject()

        # Check that spaces were replaced with hyphens
        txt = (project_dir / "pyproject.toml").read_text()
        assert 'name = "my-cool-project"' in txt


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

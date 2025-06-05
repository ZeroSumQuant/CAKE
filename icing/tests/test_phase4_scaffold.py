#!/usr/bin/env python3
"""Tests for Phase 4 scaffold functionality."""

# Import the cleanup script
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from icing.master_cleanup import MasterCleanup  # noqa: E402


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

    def test_ensure_stub_files_tests_init(self, tmp_path):
        """Test creation of tests/__init__.py."""
        # Create tests directory
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()

        mc = MasterCleanup(tmp_path, dry_run=False, skip_git=True)
        mc.ensure_stub_files()

        # Check that __init__.py was created
        init_file = tests_dir / "__init__.py"
        assert init_file.exists()
        assert "# Test package" in init_file.read_text()

        # Check summary
        assert "scaffold_stubs" in mc.summary
        assert str(init_file) in mc.summary["scaffold_stubs"]

    def test_ensure_stub_files_notebooks_readme(self, tmp_path):
        """Test creation of notebooks/README.md."""
        # Create notebooks directory
        notebooks_dir = tmp_path / "notebooks"
        notebooks_dir.mkdir()

        mc = MasterCleanup(tmp_path, dry_run=False, skip_git=True)
        mc.ensure_stub_files()

        # Check that README.md was created
        readme_file = notebooks_dir / "README.md"
        assert readme_file.exists()
        content = readme_file.read_text()
        assert "# Notebooks" in content
        assert "Jupyter notebooks" in content
        assert "Best Practices" in content

    def test_ensure_stub_files_src_project_init(self, tmp_path):
        """Test creation of src/<project>/__init__.py."""
        # Create src/project directory structure
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        project_name = tmp_path.name.lower()
        project_dir = src_dir / project_name
        project_dir.mkdir()

        mc = MasterCleanup(tmp_path, dry_run=False, skip_git=True)
        mc.ensure_stub_files()

        # Check that __init__.py was created
        init_file = project_dir / "__init__.py"
        assert init_file.exists()
        assert f'"""Package: {project_name}"""' in init_file.read_text()

    def test_ensure_stub_files_existing_not_overwritten(self, tmp_path):
        """Test that existing files are not overwritten."""
        # Create tests directory with existing __init__.py
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        init_file = tests_dir / "__init__.py"
        existing_content = "# Custom test package\nfrom .fixtures import *\n"
        init_file.write_text(existing_content)

        mc = MasterCleanup(tmp_path, dry_run=False, skip_git=True)
        mc.ensure_stub_files()

        # Check that content was not changed
        assert init_file.read_text() == existing_content

        # Check summary - no files should be created
        assert "scaffold_stubs" not in mc.summary

    def test_ensure_stub_files_no_directories(self, tmp_path):
        """Test behavior when no relevant directories exist."""
        # Just a Python file, no directories
        (tmp_path / "main.py").write_text("print('hello')")

        mc = MasterCleanup(tmp_path, dry_run=False, skip_git=True)
        mc.ensure_stub_files()

        # Check that no files were created
        assert "scaffold_stubs" not in mc.summary

    def test_ensure_stub_files_multiple_creates(self, tmp_path):
        """Test creating multiple stub files in one run."""
        # Create both tests and notebooks directories
        (tmp_path / "tests").mkdir()
        (tmp_path / "notebooks").mkdir()

        mc = MasterCleanup(tmp_path, dry_run=False, skip_git=True)
        mc.ensure_stub_files()

        # Check both files were created
        assert (tmp_path / "tests" / "__init__.py").exists()
        assert (tmp_path / "notebooks" / "README.md").exists()

        # Check summary contains both
        assert "scaffold_stubs" in mc.summary
        assert len(mc.summary["scaffold_stubs"]) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

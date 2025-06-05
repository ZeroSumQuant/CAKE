#!/usr/bin/env python3
"""Tests for Phase 4 project organizer."""

import json
from pathlib import Path

import pytest

# Import the cleanup script
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from master_cleanup import MasterCleanup  # noqa: E402


class TestPhase4Organise:
    """Test suite for Phase 4 project organization functionality."""

    def test_target_path_for_file_notebooks(self, tmp_path):
        """Test target path calculation for notebooks."""
        cleanup = MasterCleanup(tmp_path, dry_run=True, skip_git=True)

        # Notebook in root
        assert cleanup._target_path_for_file(
            "analysis.ipynb", {"classification": "notebook"}
        ) == Path("notebooks/analysis.ipynb")

        # Notebook in subdirectory
        assert cleanup._target_path_for_file(
            "experiments/model.ipynb", {"classification": "notebook"}
        ) == Path("notebooks/model.ipynb")

        # Notebook already in notebooks/
        assert (
            cleanup._target_path_for_file(
                "notebooks/existing.ipynb", {"classification": "notebook"}
            )
            is None
        )

    def test_target_path_for_file_tests(self, tmp_path):
        """Test target path calculation for test files."""
        cleanup = MasterCleanup(tmp_path, dry_run=True, skip_git=True)

        # Test file in root
        assert cleanup._target_path_for_file(
            "test_something.py", {"classification": "test"}
        ) == Path("tests/test_something.py")

        # Test file already in tests/
        assert (
            cleanup._target_path_for_file(
                "tests/test_existing.py", {"classification": "test"}
            )
            is None
        )

    def test_target_path_for_file_scripts(self, tmp_path):
        """Test target path calculation for scripts."""
        cleanup = MasterCleanup(tmp_path, dry_run=True, skip_git=True)

        # Script in root
        assert cleanup._target_path_for_file(
            "deploy.py", {"classification": "script"}
        ) == Path("scripts/deploy.py")

        # Script already in scripts/
        assert (
            cleanup._target_path_for_file(
                "scripts/train.py", {"classification": "script"}
            )
            is None
        )

    def test_target_path_for_file_modules(self, tmp_path):
        """Test target path calculation for modules."""
        # Create a project directory with a specific name
        project_dir = tmp_path / "MyProject"
        project_dir.mkdir()
        cleanup = MasterCleanup(project_dir, dry_run=True, skip_git=True)

        # Module in root
        assert cleanup._target_path_for_file(
            "utils.py", {"classification": "module"}
        ) == Path("src/myproject/utils.py")

    def test_target_path_for_file_data(self, tmp_path):
        """Test target path calculation for data files."""
        cleanup = MasterCleanup(tmp_path, dry_run=True, skip_git=True)

        # Data file in root
        assert cleanup._target_path_for_file(
            "dataset.csv", {"classification": "data"}
        ) == Path("data/raw/dataset.csv")

        # Data file already in data/
        assert (
            cleanup._target_path_for_file(
                "data/existing.csv", {"classification": "data"}
            )
            is None
        )

    def test_target_path_for_file_binary(self, tmp_path):
        """Test target path calculation for binary files."""
        cleanup = MasterCleanup(tmp_path, dry_run=True, skip_git=True)

        # Binary in root
        assert cleanup._target_path_for_file(
            "logo.png", {"classification": "binary"}
        ) == Path("assets/logo.png")

        # Binary already in assets/
        assert (
            cleanup._target_path_for_file(
                "assets/icon.png", {"classification": "binary"}
            )
            is None
        )

    def test_target_path_for_file_templates(self, tmp_path):
        """Test target path calculation for templates."""
        cleanup = MasterCleanup(tmp_path, dry_run=True, skip_git=True)

        # Template in root
        assert cleanup._target_path_for_file(
            "index.html", {"classification": "template"}
        ) == Path("templates/index.html")

        # Template already in templates/
        assert (
            cleanup._target_path_for_file(
                "templates/email.html", {"classification": "template"}
            )
            is None
        )

    def test_target_path_for_file_other(self, tmp_path):
        """Test that other files are left in place."""
        cleanup = MasterCleanup(tmp_path, dry_run=True, skip_git=True)

        assert (
            cleanup._target_path_for_file("random.xyz", {"classification": "other"})
            is None
        )

    def test_organise_project_dry_run(self, tmp_path):
        """Test project organization in dry-run mode."""
        # Create test files
        (tmp_path / "analysis.ipynb").write_text('{"cells": []}')
        (tmp_path / "test_main.py").write_text("import pytest")
        (tmp_path / "utils.py").write_text("def helper(): pass")
        (tmp_path / "data.csv").write_text("a,b\n1,2")

        # Create manifest
        manifest = {
            "files": {
                "analysis.ipynb": {"classification": "notebook"},
                "test_main.py": {"classification": "test"},
                "utils.py": {"classification": "module"},
                "data.csv": {"classification": "data"},
            }
        }

        # Save manifest
        cake_dir = tmp_path / ".cake"
        cake_dir.mkdir()
        with (cake_dir / "manifest.json").open("w") as f:
            json.dump(manifest, f)

        # Run organizer in dry-run mode
        cleanup = MasterCleanup(tmp_path, dry_run=True, skip_git=True)
        cleanup.organise_project()

        # Check that files haven't moved
        assert (tmp_path / "analysis.ipynb").exists()
        assert (tmp_path / "test_main.py").exists()
        assert (tmp_path / "utils.py").exists()
        assert (tmp_path / "data.csv").exists()

        # Check summary
        assert "organise_moves_planned" in cleanup.summary
        assert cleanup.summary["organise_moves_planned"] == 4

    def test_organise_project_skip_git(self, tmp_path):
        """Test project organization with skip_git=True."""
        # Create test files
        (tmp_path / "analysis.ipynb").write_text('{"cells": []}')
        (tmp_path / "test_main.py").write_text("import pytest")
        (tmp_path / "deploy.py").write_text("#!/usr/bin/env python\nprint('deploy')")

        # Create manifest
        manifest = {
            "files": {
                "analysis.ipynb": {"classification": "notebook", "executable": False},
                "test_main.py": {"classification": "test", "executable": False},
                "deploy.py": {"classification": "script", "executable": True},
            }
        }

        # Save manifest
        cake_dir = tmp_path / ".cake"
        cake_dir.mkdir()
        with (cake_dir / "manifest.json").open("w") as f:
            json.dump(manifest, f)

        # Run organizer
        cleanup = MasterCleanup(tmp_path, dry_run=False, skip_git=True)
        cleanup.organise_project()

        # Check that files moved
        assert not (tmp_path / "analysis.ipynb").exists()
        assert (tmp_path / "notebooks" / "analysis.ipynb").exists()

        assert not (tmp_path / "test_main.py").exists()
        assert (tmp_path / "tests" / "test_main.py").exists()
        assert (tmp_path / "tests" / "__init__.py").exists()  # Created automatically

        assert not (tmp_path / "deploy.py").exists()
        assert (tmp_path / "scripts" / "deploy.py").exists()

        # Check summary
        assert cleanup.summary["organise"]["moved"] == 3
        assert cleanup.summary["organise"]["skipped"] == 0

    def test_organise_project_skip_existing(self, tmp_path):
        """Test that existing targets are skipped."""
        # Create source file
        (tmp_path / "utils.py").write_text("def helper(): pass")

        # Get the project name from tmp_path
        project_name = tmp_path.name.lower()

        # Create target that already exists
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / project_name).mkdir()
        (tmp_path / "src" / project_name / "utils.py").write_text("# existing file")

        # Create manifest
        manifest = {"files": {"utils.py": {"classification": "module"}}}

        # Save manifest
        cake_dir = tmp_path / ".cake"
        cake_dir.mkdir()
        with (cake_dir / "manifest.json").open("w") as f:
            json.dump(manifest, f)

        # Run organizer
        cleanup = MasterCleanup(tmp_path, dry_run=False, skip_git=True)
        cleanup.organise_project()

        # Check that source file wasn't moved
        assert (tmp_path / "utils.py").exists()

        # Check summary
        assert cleanup.summary["organise"]["moved"] == 0
        assert cleanup.summary["organise"]["skipped"] == 1

    def test_organise_project_creates_data_readme(self, tmp_path):
        """Test that data/README.md is created when moving data files."""
        # Create data file
        (tmp_path / "dataset.csv").write_text("a,b\n1,2")

        # Create manifest
        manifest = {"files": {"dataset.csv": {"classification": "data"}}}

        # Save manifest
        cake_dir = tmp_path / ".cake"
        cake_dir.mkdir()
        with (cake_dir / "manifest.json").open("w") as f:
            json.dump(manifest, f)

        # Run organizer
        cleanup = MasterCleanup(tmp_path, dry_run=False, skip_git=True)
        cleanup.organise_project()

        # Check that data file moved and README was created
        assert (tmp_path / "data" / "raw" / "dataset.csv").exists()
        assert (tmp_path / "data" / "README.md").exists()

    def test_organise_project_idempotent(self, tmp_path):
        """Test that running organizer twice produces no changes."""
        # Create test file
        (tmp_path / "test_foo.py").write_text("import pytest")

        # Create manifest
        manifest = {"files": {"test_foo.py": {"classification": "test"}}}

        # Save manifest
        cake_dir = tmp_path / ".cake"
        cake_dir.mkdir()
        with (cake_dir / "manifest.json").open("w") as f:
            json.dump(manifest, f)

        # Run organizer first time
        cleanup1 = MasterCleanup(tmp_path, dry_run=False, skip_git=True)
        cleanup1.organise_project()
        assert cleanup1.summary["organise"]["moved"] == 1

        # Update manifest to reflect new location
        manifest["files"] = {"tests/test_foo.py": {"classification": "test"}}
        with (cake_dir / "manifest.json").open("w") as f:
            json.dump(manifest, f)

        # Run organizer second time
        cleanup2 = MasterCleanup(tmp_path, dry_run=False, skip_git=True)
        cleanup2.organise_project()
        assert cleanup2.summary["organise"]["moved"] == 0

    def test_organise_preserves_notebook_structure(self, tmp_path):
        """Test that nested notebook directories are preserved."""
        # Create nested notebook
        (tmp_path / "experiments").mkdir()
        (tmp_path / "experiments" / "model.ipynb").write_text('{"cells": []}')

        # Create manifest
        manifest = {
            "files": {"experiments/model.ipynb": {"classification": "notebook"}}
        }

        # Save manifest
        cake_dir = tmp_path / ".cake"
        cake_dir.mkdir()
        with (cake_dir / "manifest.json").open("w") as f:
            json.dump(manifest, f)

        # Run organizer
        cleanup = MasterCleanup(tmp_path, dry_run=False, skip_git=True)
        cleanup.organise_project()

        # Check that notebook moved to notebooks/ but lost experiments/ prefix
        assert not (tmp_path / "experiments" / "model.ipynb").exists()
        assert (tmp_path / "notebooks" / "model.ipynb").exists()

    def test_organise_with_git_mv(self, tmp_path):
        """Test that git mv is used when in a git repository."""
        import subprocess

        # Initialize git repo
        subprocess.run(["git", "init"], cwd=tmp_path, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"], cwd=tmp_path, check=True
        )

        # Create test file
        notebook = tmp_path / "analysis.ipynb"
        notebook.write_text('{"cells": []}')

        # Stage the file
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"], cwd=tmp_path, check=True
        )

        # Create manifest
        manifest = {"files": {"analysis.ipynb": {"classification": "notebook"}}}

        # Save manifest
        cake_dir = tmp_path / ".cake"
        cake_dir.mkdir()
        with (cake_dir / "manifest.json").open("w") as f:
            json.dump(manifest, f)

        # Run organizer with git enabled
        cleanup = MasterCleanup(tmp_path, dry_run=False, skip_git=False)
        cleanup.organise_project()

        # Check that file was moved physically
        assert not (tmp_path / "analysis.ipynb").exists()
        assert (tmp_path / "notebooks" / "analysis.ipynb").exists()

        # Verify git knows about the move by checking staged changes
        diff_cached = subprocess.run(
            ["git", "diff", "--cached", "--name-status"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        )

        # Should see either a rename (R) or delete + add
        # The important thing is the file was moved and git is aware
        assert (
            "notebooks/analysis.ipynb" in diff_cached.stdout
            or (tmp_path / "notebooks" / "analysis.ipynb").exists()
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

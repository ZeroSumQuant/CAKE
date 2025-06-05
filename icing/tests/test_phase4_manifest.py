#!/usr/bin/env python3
"""Tests for Phase 4 manifest builder."""

import json
from pathlib import Path

import pytest

# Import the cleanup script
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from icing.master_cleanup import MasterCleanup  # noqa: E402


class TestPhase4Manifest:
    """Test suite for Phase 4 manifest functionality."""

    def test_classify_file_notebooks(self, tmp_path):
        """Test classification of Jupyter notebooks."""
        cleanup = MasterCleanup(tmp_path, dry_run=True, skip_git=True)

        # Create test notebook
        notebook = tmp_path / "analysis.ipynb"
        notebook.write_text('{"cells": []}')

        assert cleanup.classify_file(notebook) == "notebook"

    def test_classify_file_tests(self, tmp_path):
        """Test classification of test files."""
        cleanup = MasterCleanup(tmp_path, dry_run=True, skip_git=True)

        # Test with pytest
        test1 = tmp_path / "test_something.py"
        test1.write_text("import pytest\n\ndef test_foo():\n    pass")
        assert cleanup.classify_file(test1) == "test"

        # Test with unittest
        test2 = tmp_path / "test_other.py"
        test2.write_text(
            "import unittest\n\nclass TestCase(unittest.TestCase):\n    pass"
        )
        assert cleanup.classify_file(test2) == "test"

        # Test with pytest in content
        test3 = tmp_path / "conftest.py"
        test3.write_text(
            "# pytest configuration\n@pytest.fixture\ndef setup():\n    pass"
        )
        assert cleanup.classify_file(test3) == "test"

    def test_classify_file_scripts(self, tmp_path):
        """Test classification of executable scripts."""
        cleanup = MasterCleanup(tmp_path, dry_run=True, skip_git=True)

        script = tmp_path / "run_analysis.py"
        script.write_text(
            '''#!/usr/bin/env python3
"""Analysis script."""

def main():
    print("Running analysis")

if __name__ == "__main__":
    main()
'''
        )
        assert cleanup.classify_file(script) == "script"

    def test_classify_file_modules(self, tmp_path):
        """Test classification of regular Python modules."""
        cleanup = MasterCleanup(tmp_path, dry_run=True, skip_git=True)

        module = tmp_path / "utils.py"
        module.write_text("def helper():\n    return 42")
        assert cleanup.classify_file(module) == "module"

    def test_classify_file_data(self, tmp_path):
        """Test classification of data files."""
        cleanup = MasterCleanup(tmp_path, dry_run=True, skip_git=True)

        # CSV file
        csv_file = tmp_path / "data.csv"
        csv_file.write_text("col1,col2\n1,2")
        assert cleanup.classify_file(csv_file) == "data"

        # JSON data file
        json_file = tmp_path / "results.json"
        json_file.write_text('{"key": "value"}')
        assert cleanup.classify_file(json_file) == "data"

        # Parquet file
        parquet_file = tmp_path / "dataset.parquet"
        parquet_file.touch()
        assert cleanup.classify_file(parquet_file) == "data"

    def test_classify_file_documentation(self, tmp_path):
        """Test classification of documentation files."""
        cleanup = MasterCleanup(tmp_path, dry_run=True, skip_git=True)

        # Markdown
        readme = tmp_path / "README.md"
        readme.write_text("# Project\n\nDescription")
        assert cleanup.classify_file(readme) == "documentation"

        # License
        license_file = tmp_path / "LICENSE"
        license_file.write_text("MIT License")
        assert cleanup.classify_file(license_file) == "documentation"

    def test_classify_file_configuration(self, tmp_path):
        """Test classification of configuration files."""
        cleanup = MasterCleanup(tmp_path, dry_run=True, skip_git=True)

        # pyproject.toml
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[tool.black]\nline-length = 100")
        assert cleanup.classify_file(pyproject) == "configuration"

        # .gitignore
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*.pyc\n__pycache__/")
        assert cleanup.classify_file(gitignore) == "configuration"

    def test_classify_file_binary(self, tmp_path):
        """Test classification of binary files."""
        cleanup = MasterCleanup(tmp_path, dry_run=True, skip_git=True)

        # Image file
        image = tmp_path / "logo.png"
        image.write_bytes(b"\x89PNG\r\n\x1a\n")
        assert cleanup.classify_file(image) == "binary"

        # Zip file
        archive = tmp_path / "data.zip"
        archive.touch()
        assert cleanup.classify_file(archive) == "binary"

        # Compiled Python
        pyc = tmp_path / "__pycache__" / "module.cpython-39.pyc"
        pyc.parent.mkdir()
        pyc.touch()
        assert cleanup.classify_file(pyc) == "binary"

    def test_classify_file_template(self, tmp_path):
        """Test classification of template files."""
        cleanup = MasterCleanup(tmp_path, dry_run=True, skip_git=True)

        # HTML template
        html = tmp_path / "index.html"
        html.write_text("<html><body>{{ content }}</body></html>")
        assert cleanup.classify_file(html) == "template"

        # Jinja2 template
        jinja = tmp_path / "email.jinja2"
        jinja.write_text("Hello {{ name }}!")
        assert cleanup.classify_file(jinja) == "template"

    def test_classify_file_shebang_script(self, tmp_path):
        """Test classification of scripts with shebang."""
        cleanup = MasterCleanup(tmp_path, dry_run=True, skip_git=True)

        script = tmp_path / "deploy.py"
        script.write_text("#!/usr/bin/env python3\n\nimport sys\nprint('Deploying...')")
        assert cleanup.classify_file(script) == "script"

    def test_classify_file_other(self, tmp_path):
        """Test classification of other files."""
        cleanup = MasterCleanup(tmp_path, dry_run=True, skip_git=True)

        # Unknown file type
        unknown = tmp_path / "strange.xyz"
        unknown.write_text("unknown content")
        assert cleanup.classify_file(unknown) == "other"

    def test_build_manifest_basic(self, tmp_path):
        """Test basic manifest building."""
        # Create test structure
        (tmp_path / "src").mkdir()
        (tmp_path / "tests").mkdir()
        (tmp_path / "data").mkdir()

        # Add files
        (tmp_path / "src" / "main.py").write_text("def main():\n    pass")
        (tmp_path / "src" / "__init__.py").write_text("")
        (tmp_path / "tests" / "test_main.py").write_text(
            "import pytest\n\ndef test_main():\n    pass"
        )
        (tmp_path / "data" / "sample.csv").write_text("a,b\n1,2")
        (tmp_path / "README.md").write_text("# Test Project")
        (tmp_path / ".gitignore").write_text("*.pyc")
        (tmp_path / "notebook.ipynb").write_text('{"cells": []}')

        cleanup = MasterCleanup(tmp_path, dry_run=True, skip_git=True)
        manifest = cleanup.build_manifest()

        # Check manifest structure
        assert "timestamp" in manifest
        assert "target_path" in manifest
        assert "files" in manifest
        assert "summary" in manifest

        # Check file count
        assert len(manifest["files"]) == 7

        # Check classifications
        assert manifest["summary"]["module"] == 2  # main.py, __init__.py
        assert manifest["summary"]["test"] == 1  # test_main.py
        assert manifest["summary"]["data"] == 1  # sample.csv
        assert manifest["summary"]["documentation"] == 1  # README.md
        assert manifest["summary"]["configuration"] == 1  # .gitignore
        assert manifest["summary"]["notebook"] == 1  # notebook.ipynb

    def test_build_manifest_excludes_hidden(self, tmp_path):
        """Test that hidden files are excluded except for important ones."""
        # Create hidden files
        (tmp_path / ".hidden").write_text("secret")
        (tmp_path / ".gitignore").write_text("*.pyc")
        (tmp_path / ".flake8").write_text("[flake8]\nmax-line-length = 100")
        (tmp_path / ".cache").mkdir()
        (tmp_path / ".cache" / "data.txt").write_text("cached")

        cleanup = MasterCleanup(tmp_path, dry_run=True, skip_git=True)
        manifest = cleanup.build_manifest()

        files = list(manifest["files"].keys())

        # .gitignore and .flake8 should be included
        assert ".gitignore" in files
        assert ".flake8" in files

        # Other hidden files should be excluded
        assert ".hidden" not in files
        assert not any(".cache" in f for f in files)

    def test_build_manifest_excludes_directories(self, tmp_path):
        """Test that common build/cache directories are excluded."""
        # Create directories that should be excluded
        for dirname in ["__pycache__", ".venv", "build", "dist", ".pytest_cache"]:
            (tmp_path / dirname).mkdir()
            (tmp_path / dirname / "file.txt").write_text("should be excluded")

        # Create a normal directory
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("print('hello')")

        cleanup = MasterCleanup(tmp_path, dry_run=True, skip_git=True)
        manifest = cleanup.build_manifest()

        files = list(manifest["files"].keys())

        # Normal file should be included
        assert "src/main.py" in files

        # Excluded directories should not appear
        for dirname in ["__pycache__", ".venv", "build", "dist", ".pytest_cache"]:
            assert not any(dirname in f for f in files)

    def test_build_manifest_saves_to_cake_dir(self, tmp_path):
        """Test that manifest is saved to .cake directory."""
        (tmp_path / "test.py").write_text("print('test')")

        cleanup = MasterCleanup(tmp_path, dry_run=True, skip_git=True)
        manifest = cleanup.build_manifest()

        # Check .cake directory was created
        cake_dir = tmp_path / ".cake"
        assert cake_dir.exists()
        assert cake_dir.is_dir()

        # Check manifest.json was created
        manifest_path = cake_dir / "manifest.json"
        assert manifest_path.exists()

        # Load and verify saved manifest
        with manifest_path.open() as f:
            saved_manifest = json.load(f)

        assert saved_manifest["files"] == manifest["files"]
        assert saved_manifest["summary"] == manifest["summary"]

    def test_manifest_file_info(self, tmp_path):
        """Test that manifest includes file size and suffix."""
        test_file = tmp_path / "large.csv"
        test_content = "col1,col2\n" + "\n".join(f"{i},{i * 2}" for i in range(100))
        test_file.write_text(test_content)

        cleanup = MasterCleanup(tmp_path, dry_run=True, skip_git=True)
        manifest = cleanup.build_manifest()

        file_info = manifest["files"]["large.csv"]
        assert file_info["classification"] == "data"
        assert file_info["size"] == len(test_content.encode())
        assert file_info["suffix"] == ".csv"
        assert "executable" in file_info

    def test_oversize_data_file(self, tmp_path):
        """Test that data files > 20MB are flagged as oversize."""
        # Create a 25MB CSV file
        large_file = tmp_path / "huge_dataset.csv"
        # Create header
        content = "id,value\n"
        # Add rows to exceed 20MB (each row is ~20 bytes)
        for i in range(1500000):  # ~30MB of data
            content += f"{i},{i * 2.5}\n"
        large_file.write_text(content)

        cleanup = MasterCleanup(tmp_path, dry_run=True, skip_git=True)
        manifest = cleanup.build_manifest()

        file_info = manifest["files"]["huge_dataset.csv"]
        assert file_info["classification"] == "data"
        assert file_info["size"] > 20 * 1024 * 1024
        assert file_info.get("oversize") is True
        assert manifest["summary"]["oversize_files"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

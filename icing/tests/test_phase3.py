"""Test Phase 3 transformations: imports, docstrings, formatting, and AST sweep."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from icing.master_cleanup import MasterCleanup


@pytest.fixture
def cleanup():
    """Create a MasterCleanup instance in dry-run mode."""
    return MasterCleanup(Path("."), dry_run=True, skip_git=True)


class TestFixImports:
    """Test fix_imports transformation."""

    @pytest.mark.parametrize(
        "input_code,expected_code",
        [
            # Duplicate imports - keep first occurrence
            (
                "import os\nimport sys\nimport os\n",
                "import os\nimport sys\n",
            ),
            # Multi-import split
            (
                "import os, sys, json\n",
                "import os\nimport sys\nimport json\n",
            ),
            # Preserve noqa comments
            (
                "import unused_module  # noqa: F401\nimport os\n",
                "import os\nimport unused_module  # noqa: F401\n",
            ),
            # Mixed import styles
            (
                "from os import path\nimport os\nfrom os.path import join\n",
                "import os\nfrom os import path\nfrom os.path import join\n",
            ),
            # Aliased imports
            (
                "import numpy as np\nimport numpy\nimport numpy as np\n",
                "import numpy\nimport numpy as np\n",
            ),
        ],
    )
    def test_fix_imports(self, cleanup, tmp_path, input_code, expected_code):
        """Test various import fixing scenarios."""
        test_file = tmp_path / "test.py"
        test_file.write_text(input_code)

        # Mock the target_path to use tmp_path
        cleanup.target_path = tmp_path
        cleanup.dry_run = False  # Actually apply changes for this test

        cleanup.fix_imports()

        result = test_file.read_text()
        assert result == expected_code


class TestFixDocstrings:
    """Test fix_docstrings transformation."""

    @pytest.mark.parametrize(
        "input_code,expected_code",
        [
            # One-liner > 72 chars to multi-line
            (
                'def foo():\n    """This is a very long docstring that exceeds seventy-two characters and should be split."""\n    pass\n',
                'def foo():\n    """\n    This is a very long docstring that exceeds seventy-two characters and should be split.\n    """\n    pass\n',
            ),
            # Normalize triple single quotes
            (
                "def foo():\n    '''Short docstring.'''\n    pass\n",
                'def foo():\n    """Short docstring."""\n    pass\n',
            ),
            # Preserve raw docstrings
            (
                'def foo():\n    r"""Raw docstring with \\n escaped."""\n    pass\n',
                'def foo():\n    r"""Raw docstring with \\n escaped."""\n    pass\n',
            ),
            # Multi-line with wrong closing quote position
            (
                'def foo():\n    """\n    Multi-line\n    docstring."""\n    pass\n',
                'def foo():\n    """\n    Multi-line\n    docstring.\n    """\n    pass\n',
            ),
            # Module-level docstring
            (
                '"""Module docstring."""\n\ndef foo():\n    pass\n',
                '"""Module docstring."""\n\ndef foo():\n    pass\n',
            ),
        ],
    )
    def test_fix_docstrings(self, cleanup, tmp_path, input_code, expected_code):
        """Test various docstring fixing scenarios."""
        test_file = tmp_path / "test.py"
        test_file.write_text(input_code)

        cleanup.target_path = tmp_path
        cleanup.dry_run = False

        cleanup.fix_docstrings()

        result = test_file.read_text()
        assert result == expected_code


class TestASTEmptyBodySweep:
    """Test ast_empty_body_sweep transformation."""

    @pytest.mark.parametrize(
        "input_code,expected_code",
        [
            # Nested empty async def
            (
                "async def outer():\n    async def inner():\n        pass\n",
                "async def outer():\n    async def inner():\n        pass\n    pass\n",
            ),
            # Empty class with docstring
            (
                'class Empty:\n    """Docstring."""\n',
                'class Empty:\n    """Docstring."""\n    pass\n',
            ),
            # Function with only ellipsis
            (
                "def abstract():\n    ...\n",
                "def abstract():\n    ...\n",
            ),
            # Truly empty function (edge case)
            (
                "def empty():\n",
                "def empty():\n    pass\n",
            ),
            # Mix of empty and non-empty
            (
                "def has_code():\n    print('hi')\n\ndef empty():\n\nclass Empty:\n    pass\n",
                "def has_code():\n    print('hi')\n\ndef empty():\n    pass\n\nclass Empty:\n    pass\n",
            ),
        ],
    )
    def test_ast_empty_body_sweep(self, cleanup, tmp_path, input_code, expected_code):
        """Test AST-based empty body detection."""
        test_file = tmp_path / "test.py"
        test_file.write_text(input_code)

        cleanup.target_path = tmp_path
        cleanup.dry_run = False

        cleanup.ast_empty_body_sweep()

        result = test_file.read_text()
        assert result == expected_code


class TestPhase3Integration:
    """Test running Phase 3 transformations together."""

    def test_skip_binary_directories(self, cleanup, tmp_path):
        """Test that binary/generated directories are skipped."""
        # Create directory structure
        (tmp_path / "src").mkdir()
        (tmp_path / "migrations").mkdir()
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "static").mkdir()

        # Add Python files
        (tmp_path / "src" / "main.py").write_text("import os, sys\n")
        (tmp_path / "migrations" / "001_initial.py").write_text("import os, sys\n")
        (tmp_path / "__pycache__" / "cached.py").write_text("import os, sys\n")

        cleanup.target_path = tmp_path
        cleanup.dry_run = False

        cleanup.fix_imports()

        # Only src/main.py should be modified
        assert (tmp_path / "src" / "main.py").read_text() == "import os\nimport sys\n"
        assert (
            tmp_path / "migrations" / "001_initial.py"
        ).read_text() == "import os, sys\n"
        assert (
            tmp_path / "__pycache__" / "cached.py"
        ).read_text() == "import os, sys\n"

    def test_dry_run_skips_formatters(self, cleanup, tmp_path):
        """Test that black/isort are skipped in dry-run mode."""
        test_file = tmp_path / "test.py"
        test_file.write_text("import   os\n")

        cleanup.target_path = tmp_path
        cleanup.dry_run = True  # Dry run mode

        # This should not actually run black/isort
        cleanup.run_black()
        cleanup.run_isort()

        # File should be unchanged
        assert test_file.read_text() == "import   os\n"

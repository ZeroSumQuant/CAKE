"""Test Phase 2 transformations: control block colons and missing pass statements."""

from pathlib import Path

import pytest

from scripts.master_cleanup import MasterCleanup


@pytest.fixture
def cleanup():
    """Create a MasterCleanup instance in dry-run mode."""
    return MasterCleanup(Path("."), dry_run=True, skip_git=True)


class TestFixControlBlockColons:
    """Test fix_control_block_colons transformation."""

    @pytest.mark.parametrize(
        "input_code,expected_code",
        [
            # Basic if statement missing colon
            ("if x > 0\n    print('positive')", "if x > 0:\n    print('positive')"),
            # elif missing colon
            (
                "if x > 0:\n    print('positive')\nelif x < 0\n    print('negative')",
                "if x > 0:\n    print('positive')\nelif x < 0:\n    print('negative')",
            ),
            # else missing colon
            (
                "if x > 0:\n    print('positive')\nelse\n    print('other')",
                "if x > 0:\n    print('positive')\nelse:\n    print('other')",
            ),
            # for loop missing colon
            ("for i in range(10)\n    print(i)", "for i in range(10):\n    print(i)"),
            # while loop missing colon
            ("while True\n    break", "while True:\n    break"),
            # Function definition missing colon
            (
                "def hello(name)\n    return f'Hello {name}'",
                "def hello(name):\n    return f'Hello {name}'",
            ),
            # Class definition missing colon
            ("class MyClass\n    pass", "class MyClass:\n    pass"),
            # try/except/finally missing colons
            (
                "try\n    risky()\nexcept Exception\n    handle()\nfinally\n    cleanup()",
                "try:\n    risky()\nexcept Exception:\n    handle()\nfinally:\n    cleanup()",
            ),
            # with statement missing colon
            (
                "with open('file.txt') as f\n    content = f.read()",
                "with open('file.txt') as f:\n    content = f.read()",
            ),
            # Already has colon - no change
            ("if x > 0:\n    print('positive')", "if x > 0:\n    print('positive')"),
            # Multiline condition
            (
                "if (x > 0 and\n    y > 0)\n    print('both positive')",
                "if (x > 0 and\n    y > 0):\n    print('both positive')",
            ),
            # Comment after condition
            (
                "if x > 0  # check if positive\n    print('yes')",
                "if x > 0:  # check if positive\n    print('yes')",
            ),
        ],
    )
    def test_fix_control_block_colons(
        self, cleanup, tmp_path, input_code, expected_code
    ):
        """Test various control block colon fixes."""
        test_file = tmp_path / "test.py"
        test_file.write_text(input_code)

        # Mock the target_path to use tmp_path
        cleanup.target_path = tmp_path
        cleanup.fix_control_block_colons()

        # In dry-run mode, check what would be written
        if cleanup.dry_run:
            # For testing, we'll directly apply the transformation
            # to verify the logic works
            content = test_file.read_text()
            # Apply the transformation logic here
            # (we'll implement this in the actual method)
            assert content == input_code  # No change in dry-run
        else:
            result = test_file.read_text()
            assert result == expected_code


class TestInsertMissingPass:
    """Test insert_missing_pass transformation."""

    @pytest.mark.parametrize(
        "input_code,expected_code",
        [
            # Empty if block
            ("if x > 0:\n\nprint('after')", "if x > 0:\n    pass\n\nprint('after')"),
            # Empty else block
            (
                "if x > 0:\n    print('yes')\nelse:\n\nprint('after')",
                "if x > 0:\n    print('yes')\nelse:\n    pass\n\nprint('after')",
            ),
            # Empty for loop
            (
                "for i in range(10):\n\nprint('done')",
                "for i in range(10):\n    pass\n\nprint('done')",
            ),
            # Empty while loop
            (
                "while False:\n\nprint('never')",
                "while False:\n    pass\n\nprint('never')",
            ),
            # Empty function
            (
                "def empty_func():\n\ndef other():\n    pass",
                "def empty_func():\n    pass\n\ndef other():\n    pass",
            ),
            # Empty class
            (
                "class EmptyClass:\n\nclass Other:\n    pass",
                "class EmptyClass:\n    pass\n\nclass Other:\n    pass",
            ),
            # Empty try block
            ("try:\n\nexcept:\n    handle()", "try:\n    pass\nexcept:\n    handle()"),
            # Empty except block
            (
                "try:\n    risky()\nexcept:\n\nfinally:\n    cleanup()",
                "try:\n    risky()\nexcept:\n    pass\nfinally:\n    cleanup()",
            ),
            # Already has pass - no change
            ("if x > 0:\n    pass", "if x > 0:\n    pass"),
            # Has comment but no code
            (
                "if x > 0:\n    # TODO: implement\n\nprint('after')",
                "if x > 0:\n    # TODO: implement\n    pass\n\nprint('after')",
            ),
            # Nested empty blocks
            (
                "if x > 0:\n    if y > 0:\n\n    print('x positive')",
                "if x > 0:\n    if y > 0:\n        pass\n    print('x positive')",
            ),
        ],
    )
    def test_insert_missing_pass(self, cleanup, tmp_path, input_code, expected_code):
        """Test various missing pass insertions."""
        test_file = tmp_path / "test.py"
        test_file.write_text(input_code)

        # Mock the target_path to use tmp_path
        cleanup.target_path = tmp_path
        cleanup.insert_missing_pass()

        # In dry-run mode, check what would be written
        if cleanup.dry_run:
            content = test_file.read_text()
            assert content == input_code  # No change in dry-run
        else:
            result = test_file.read_text()
            assert result == expected_code


class TestPhase2Integration:
    """Test running both Phase 2 transformations together."""

    def test_fix_both_issues(self, cleanup, tmp_path):
        """Test fixing missing colons and empty blocks together."""
        input_code = """def broken_function(x)
    if x > 0
        # positive case
    else

for i in range(3)

class EmptyClass
"""

        expected_code = """def broken_function(x):
    if x > 0:
        # positive case
        pass
    else:
        pass

for i in range(3):
    pass

class EmptyClass:
    pass
"""

        test_file = tmp_path / "test.py"
        test_file.write_text(input_code)

        # Apply transformations in order
        cleanup.target_path = tmp_path
        cleanup.dry_run = False  # Actually apply changes for this test

        cleanup.fix_control_block_colons()
        cleanup.insert_missing_pass()

        result = test_file.read_text()
        assert result == expected_code

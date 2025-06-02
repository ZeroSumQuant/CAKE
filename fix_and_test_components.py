#!/usr/bin/env python3
"""Fix and test CAKE components systematically.
"""
import subprocess
import sys
from pathlib import Path


def run_command(cmd, description):
    """Run a shell command and report results."""print(f"\n🔧 {description}...")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"✅ Success")
        if result.stdout:
            print(result.stdout)
    else:
        print(f"❌ Failed")
        if result.stderr:
            print(result.stderr)
        if result.stdout:
            print(result.stdout)
    return result.returncode == 0


def main():
    """Main workflow to fix components."""project_root = Path("/Users/dustinkirby/Documents/GitHub/CAKE")

    # Working components from health check
    working_components = [
        "cake/components/operator.py",
        "cake/components/recall_db.py",
        "cake/components/validator.py",
        "cake/components/snapshot_manager.py",
        "cake/utils/rule_creator.py",
    ]

    print("🎯 CAKE Component Fix & Test Plan")
    print("=" * 60)

    # Step 1: Auto-format working components
    print("\n📋 Step 1: Auto-format working components")
    print("-" * 60)

    for component in working_components:
        file_path = project_root / component
        if file_path.exists():
            # Run black
            run_command(
                f"cd {project_root} && black {component} --line-length 100",
                f"Black formatting {component}",
            )

            # Run isort
            run_command(
                f"cd {project_root} && isort {component} --profile black --line-length 100",
                f"Import sorting {component}",
            )

    # Step 2: Check what issues remain
    print("\n📋 Step 2: Check remaining issues")
    print("-" * 60)

    for component in working_components:
        run_command(
            f"cd {project_root} && flake8 {component} --max-line-length=100 --extend-ignore=E203,W503",
            f"Flake8 check {component}",
        )

    # Step 3: Install minimal dependencies for working components
    print("\n📋 Step 3: Create minimal requirements for working components")
    print("-" * 60)

    minimal_requirements = """# Minimal requirements for working CAKE components
pyyaml>=6.0
"""

    req_file = project_root / "requirements-minimal.txt"
    with open(req_file, "w") as f:
        f.write(minimal_requirements)

    print(f"Created {req_file}")

    # Step 4: Summary
    print("\n📊 Summary")
    print("=" * 60)
    print("1. ✅ Auto-formatted working components")
    print("2. ✅ Created minimal requirements file")
    print("\nNext steps:")
    print("- Fix the truncated cake_adapter.py file")
    print("- Install dependencies: pip install -r requirements-minimal.txt")
    print("- Fix remaining flake8 issues manually")
    print("- Run component health check again")

    # Step 5: Check which dependencies are actually needed
    print("\n📦 Checking actual imports in working components...")
    print("-" * 60)

    imports_needed = set()
    for component in working_components:
        file_path = project_root / component
        if file_path.exists():
            with open(file_path) as f:
                content = f.read()
                # Find all imports
                import_lines = [
                    line
                    for line in content.split("\n")
                    if line.strip().startswith(("import ", "from "))
                ]
                for line in import_lines:
                    if "import" in line:
                        # Extract module name
                        if line.startswith("import "):
                            module = line.split()[1].split(".")[0]
                        else:  # from X import Y
                            module = line.split()[1].split(".")[0]

                        # Skip stdlib and local imports
                        if module not in [
                            "os",
                            "sys",
                            "re",
                            "json",
                            "logging",
                            "typing",
                            "dataclasses",
                            "datetime",
                            "enum",
                            "pathlib",
                            "asyncio",
                            "sqlite3",
                            "pickle",
                            "hashlib",
                            "subprocess",
                            "tempfile",
                            "collections",
                            "cake",
                        ]:
                            imports_needed.add(module)

    if imports_needed:
        print("\nExternal dependencies found in working components:")
        for imp in sorted(imports_needed):
            print(f"  - {imp}")
    else:
        print("\nNo external dependencies found! Working components use only stdlib.")


if __name__ == "__main__":
    main()

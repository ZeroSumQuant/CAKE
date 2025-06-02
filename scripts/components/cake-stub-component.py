#!/usr/bin/env python3
"""Generate CAKE component code from specifications.

This script reads the cake-components-v2.md specification and generates
properly structured component code with all required methods and docstrings.

Usage:
    python cake-stub-component.py --component Operator
    python cake-stub-component.py --component RecallDB --output cake/components/recall_db.py
    python cake-stub-component.py --list
"""import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class ComponentSpec:
    """Represents a component specification."""
    def __init__(
        self,
        name: str,
        description: str,
        methods: List[Dict],
        attributes: List[Dict],
        requirements: List[str],
    ) -> None:
        """Initialize component specification."""self.name = name
        self.description = description
        self.methods = methods
        self.attributes = attributes
        self.requirements = requirements


class SpecificationParser:
    """Parses component specifications from markdown."""
    def __init__(self, spec_file: Path) -> None:
        """Initialize specification parser."""self.spec_file = spec_file
        self.content = spec_file.read_text()

    def get_available_components(self) -> List[str]:
        """Get list of components defined in spec."""components = []

        # Look for component sections
        pattern = r"### (\w+)\s*\n"
        matches = re.findall(pattern, self.content)

        # Filter to actual components
        component_names = [
            "CakeController",
            "Operator",
            "RecallDB",
            "PTYShim",
            "Validator",
            "Watchdog",
            "SnapshotManager",
        ]

        for match in matches:
            if any(comp.lower() in match.lower() for comp in component_names):
                components.append(match)

        return components

    def parse_component(self, component_name: str) -> Optional[ComponentSpec]:
        """Parse specification for a specific component."""section = self._find_component_section(component_name)
        if not section:
            return None

        return ComponentSpec(
            name=component_name,
            description=self._extract_description(section),
            methods=self._parse_methods(section),
            attributes=self._parse_attributes(section),
            requirements=self._parse_requirements(section),
        )

    def _find_component_section(self, component_name: str) -> Optional[str]:
        """Find component section in specification."""pattern = rf"### {component_name}.*?\n(.*?)(?=###|\Z)"
        match = re.search(pattern, self.content, re.DOTALL | re.IGNORECASE)
        return match.group(1) if match else None

    def _extract_description(self, section: str) -> str:
        """Extract component description from section."""desc_match = re.search(r"^(.+?)(?=\n\*\*|$)", section.strip())
        return desc_match.group(1).strip() if desc_match else ""

    def _parse_methods(self, section: str) -> List[Dict]:
        """Parse method specifications."""methods = []

        # Look for method definitions
        method_pattern = r"- `(\w+)\((.*?)\)`(?:\s*-\s*)?(.+?)(?=\n-|\n\n|\Z)"

        for match in re.finditer(method_pattern, section, re.DOTALL):
            method_name = match.group(1)
            params = match.group(2).strip()
            description = match.group(3).strip()

            methods.append(
                {
                    "name": method_name,
                    "params": self._parse_params(params),
                    "description": description,
                    "return_type": self._infer_return_type(method_name, description),
                }
            )

        return methods

    def _parse_params(self, params_str: str) -> List[Tuple[str, str]]:
        """Parse method parameters."""if not params_str:
            return []

        params = []
        for param in params_str.split(","):
            param = param.strip()
            if ":" in param:
                name, type_hint = param.split(":", 1)
                params.append((name.strip(), type_hint.strip()))
            else:
                params.append((param, "Any"))

        return params

    def _parse_attributes(self, section: str) -> List[Dict]:
        """Parse component attributes."""attributes = []

        # Look for state/attribute definitions
        attr_pattern = r"(?:state|attribute)[:\s]+`(\w+)`\s*(?:-\s*)?(.+?)(?=\n|$)"

        for match in re.finditer(attr_pattern, section, re.IGNORECASE):
            attributes.append(
                {
                    "name": match.group(1),
                    "description": match.group(2).strip(),
                    "type": "Any",  # Infer from description if needed
                }
            )

        return attributes

    def _parse_requirements(self, section: str) -> List[str]:
        """Parse requirements/constraints."""requirements = []

        # Look for MUST requirements
        req_pattern = r"MUST\s+(.+?)(?=\n|$)"

        for match in re.finditer(req_pattern, section):
            requirements.append(match.group(1).strip())

        return requirements

    def _infer_return_type(self, method_name: str, description: str) -> str:
        """Infer return type from method name and description."""# Check method name patterns
        if method_name.startswith("is_") or method_name.startswith("has_"):
            return "bool"

        # Check description for return type hints
        desc_lower = description.lower()
        if "return" not in desc_lower:
            return "Any"

        # Map keywords to types
        type_map = {"none": "None", "string": "str", "list": "List[Any]", "dict": "Dict[str, Any]"}

        # Find first matching type or default to Any
        return next(
            (ret_type for keyword, ret_type in type_map.items() if keyword in desc_lower), "Any"
        )


class ComponentGenerator:
    """Generates Python code from component specifications."""
    def __init__(self) -> None:
        """Initialize component generator."""self.imports = {
            "from typing import Dict, List, Optional, Any, Tuple",
            "from dataclasses import dataclass",
            "import asyncio",
            "from abc import ABC, abstractmethod",
        }

    def generate_component(self, spec: ComponentSpec) -> str:
        """Generate Python code for a component."""# Add component-specific imports
        self._add_component_imports(spec)

        # Build code sections
        code_parts = [
            self._generate_header(spec),
            "\n".join(sorted(self.imports)),
            "",
            self._generate_class(spec),
        ]

        return "\n".join(code_parts)

    def _add_component_imports(self, spec: ComponentSpec) -> None:
        """Add component-specific imports."""if spec.name == "RecallDB":
            self.imports.add("import sqlite3")
            self.imports.add("from datetime import datetime, timedelta")
        elif spec.name == "Watchdog":
            self.imports.add("import threading")
            self.imports.add("from queue import Queue")
        elif spec.name == "PTYShim":
            self.imports.add("import pty")
            self.imports.add("import os")
            self.imports.add("import subprocess")

    def _generate_header(self, spec: ComponentSpec) -> str:
        """Generate file header with docstring."""return f'''"""
CAKE {spec.name} Component

{spec.description}

This component is part of the CAKE (Claude Autonomy Kit Engine) system.
Generated from specifications in cake-components-v2.md
"""'''

    def _generate_class(self, spec: ComponentSpec) -> str:
        """Generate class definition."""lines = []

        lines.extend(self._generate_class_header(spec))
        lines.extend(self._generate_constructor(spec))
        lines.extend(self._generate_methods(spec))

        return "\n".join(lines)

    def _generate_class_header(self, spec: ComponentSpec) -> List[str]:
        """Generate class header with docstring."""lines = [f"\nclass {spec.name}:", f'    """{spec.description}']

        if spec.requirements:
            lines.extend(
                ["    ", "    Requirements:", *[f"    - {req}" for req in spec.requirements]]
            )

        lines.extend(['    """', ""])
        return lines

    def _generate_constructor(self, spec: ComponentSpec) -> List[str]:
        """Generate constructor method."""lines = [
            "    def __init__(self, config: Dict[str, Any]):",
            '        """Initialize component with configuration."""',
            "        self.config = config",
        ]

        # Add attributes
        for attr in spec.attributes:
            lines.append(f'        self.{attr["name"]} = None  # {attr["description"]}')

        if not spec.attributes:
            lines.append("        # TODO: Initialize component state")

        lines.append("")
        return lines

    def _generate_methods(self, spec: ComponentSpec) -> List[str]:
        """Generate all methods for the component."""lines = []
        for method in spec.methods:
            lines.extend(self._generate_method(method))
            lines.append("")
        return lines

    def _generate_method(self, method: Dict) -> List[str]:
        """Generate method definition."""lines = []

        lines.extend(self._generate_method_signature(method))
        lines.extend(self._generate_method_docstring(method))
        lines.extend(self._generate_method_body(method))

        return lines

    def _generate_method_signature(self, method: Dict) -> List[str]:
        """Generate method signature."""params = ["self"]
        for param_name, param_type in method["params"]:
            params.append(f"{param_name}: {param_type}")

        return_type = method["return_type"]
        return [f'    def {method["name"]}({", ".join(params)}) -> {return_type}:']

    def _generate_method_docstring(self, method: Dict) -> List[str]:
        """Generate method docstring."""lines = [f'        """{method["description"]}']

        if method["params"]:
            lines.extend(
                [
                    "        ",
                    "        Args:",
                    *[
                        f"            {param_name}: TODO: Add description"
                        for param_name, _ in method["params"]
                    ],
                ]
            )

        if method["return_type"] != "None":
            lines.extend(
                [
                    "        ",
                    "        Returns:",
                    f"            {method['return_type']}: TODO: Add description",
                ]
            )

        lines.append('        """')
        return lines

    def _generate_method_body(self, method: Dict) -> List[str]:
        """Generate method body."""return [
            "        # TODO: Implement this method",
            "        raise NotImplementedError(",
            f'            "{method["name"]} not yet implemented"',
            "        )",
        ]


def _create_argument_parser() -> argparse.ArgumentParser:
    """Create and return the argument parser."""parser = argparse.ArgumentParser(
        description="Generate CAKE component code from specifications",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --component Operator
  %(prog)s --component RecallDB --output cake/components/recall_db.py
  %(prog)s --list

This script reads cake-components-v2.md and generates properly structured
component code with all required methods, attributes, and documentation.
        """,
    )

    parser.add_argument(
        "--component", "-c", help="Component name to generate (e.g., Operator, RecallDB)"
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Output file path (default: cake/components/{component}.py)",
    )
    parser.add_argument("--list", "-l", action="store_true", help="List available components")
    parser.add_argument(
        "--spec-file",
        type=Path,
        default=Path("cake-components-v2.md"),
        help="Path to specification file (default: cake-components-v2.md)",
    )
    parser.add_argument("--force", "-f", action="store_true", help="Overwrite existing files")

    return parser


def _list_components(parser_obj: SpecificationParser) -> None:
    """List available components."""print("Available CAKE Components:")
    print("-" * 30)
    components = parser_obj.get_available_components()
    for comp in components:
        print(f"  - {comp}")


def _generate_output_path(spec: ComponentSpec, output_arg: Optional[Path]) -> Path:
    """Generate output path for component."""if output_arg:
        return output_arg

    # Convert component name to snake_case
    filename = re.sub(r"(?<!^)(?=[A-Z])", "_", spec.name).lower()
    return Path(f"cake/components/{filename}.py")


def _write_component_file(output_path: Path, code: str, force: bool) -> int:
    """Write component code to file."""# Check if file exists
    if output_path.exists() and not force:
        print(f"Error: File already exists: {output_path}")
        print("Use --force to overwrite")
        return 1

    # Create output directory
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write file
    output_path.write_text(code)
    print(f"✓ Generated component: {output_path}")
    return 0


def _process_component_generation(args: argparse.Namespace, parser_obj: SpecificationParser) -> int:
    """Process component generation request."""# Parse component specification
    print(f"Parsing specification for {args.component}...")
    spec = parser_obj.parse_component(args.component)

    if not spec:
        print(f"Error: Component '{args.component}' not found in specification")
        _list_components(parser_obj)
        return 1

    # Generate code
    print("Generating component code...")
    generator = ComponentGenerator()
    code = generator.generate_component(spec)

    # Determine output path and write file
    output_path = _generate_output_path(spec, args.output)
    result = _write_component_file(output_path, code, args.force)

    if result == 0:
        # Print summary
        print(f"\nComponent: {spec.name}")
        print(f"Methods: {len(spec.methods)}")
        print(f"Attributes: {len(spec.attributes)}")
        print(f"Requirements: {len(spec.requirements)}")

    return result


def main() -> int:
    """Main entry point."""
    parser = _create_argument_parser()
    args = parser.parse_args()

    # Check spec file exists
    if not args.spec_file.exists():
        print(f"Error: Specification file not found: {args.spec_file}")
        return 1

    # Create parser
    parser_obj = SpecificationParser(args.spec_file)

    # Handle different modes
    if args.list:
        _list_components(parser_obj)
        result = 0
    elif not args.component:
        parser.print_help()
        result = 1
    else:
        result = _process_component_generation(args, parser_obj)

    return result


if __name__ == "__main__":
    sys.exit(main())

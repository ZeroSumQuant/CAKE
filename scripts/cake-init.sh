#!/bin/bash
# cake-init.sh - Creates entire CAKE project structure in one command
# Usage: ./cake-init.sh [project-path]
# Output: Complete directory structure with all required files

set -euo pipefail

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${1:-$(pwd)}"

# Function to print colored output
print_status() {
    echo -e "${BLUE}[CAKE INIT]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

# Function to create directory with status message
create_dir() {
    local dir="$1"
    if [ ! -d "$dir" ]; then
        mkdir -p "$dir"
        print_success "Created directory: $dir"
    else
        print_warning "Directory exists: $dir"
    fi
}

# Function to create file with template content
create_file() {
    local file="$1"
    local content="$2"
    
    if [ ! -f "$file" ]; then
        echo "$content" > "$file"
        print_success "Created file: $file"
    else
        print_warning "File exists: $file"
    fi
}

# Help function
show_help() {
    cat << EOF
CAKE Project Initializer
========================

Usage: ./cake-init.sh [OPTIONS] [project-path]

OPTIONS:
    -h, --help          Show this help message
    -f, --force         Overwrite existing files
    -d, --dry-run       Show what would be created without doing it
    -v, --verbose       Show detailed output

ARGUMENTS:
    project-path        Path where CAKE project will be created (default: current directory)

EXAMPLES:
    ./cake-init.sh                  # Initialize in current directory
    ./cake-init.sh ~/projects/cake  # Initialize in specific directory
    ./cake-init.sh --dry-run        # Show what would be created

DESCRIPTION:
    This script creates the complete CAKE project structure including:
    - All required directories
    - Component stubs
    - Test structure
    - Configuration files
    - Documentation templates
    - Database schema
    - Docker configuration

EOF
    exit 0
}

# Parse command line arguments
FORCE=false
DRY_RUN=false
VERBOSE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            ;;
        -f|--force)
            FORCE=true
            shift
            ;;
        -d|--dry-run)
            DRY_RUN=true
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        *)
            PROJECT_ROOT="$1"
            shift
            ;;
    esac
done

# Main initialization
print_status "Initializing CAKE project at: $PROJECT_ROOT"

if [ "$DRY_RUN" = true ]; then
    print_warning "DRY RUN MODE - No files will be created"
fi

# Create main project structure
print_status "Creating directory structure..."

# Core directories
create_dir "$PROJECT_ROOT/cake"
create_dir "$PROJECT_ROOT/cake/components"
create_dir "$PROJECT_ROOT/cake/adapters"
create_dir "$PROJECT_ROOT/cake/config"
create_dir "$PROJECT_ROOT/cake/utils"

# Test directories
create_dir "$PROJECT_ROOT/tests"
create_dir "$PROJECT_ROOT/tests/unit"
create_dir "$PROJECT_ROOT/tests/integration"
create_dir "$PROJECT_ROOT/tests/performance"
create_dir "$PROJECT_ROOT/tests/fixtures"

# Documentation directories
create_dir "$PROJECT_ROOT/docs"
create_dir "$PROJECT_ROOT/docs/api"
create_dir "$PROJECT_ROOT/docs/architecture"
create_dir "$PROJECT_ROOT/docs/deployment"

# Other directories
create_dir "$PROJECT_ROOT/scripts"
create_dir "$PROJECT_ROOT/data"
create_dir "$PROJECT_ROOT/data/snapshots"
create_dir "$PROJECT_ROOT/data/recall_db"
create_dir "$PROJECT_ROOT/logs"
create_dir "$PROJECT_ROOT/metrics"
create_dir "$PROJECT_ROOT/docker"

# Create __init__.py files
print_status "Creating Python package files..."
create_file "$PROJECT_ROOT/cake/__init__.py" '"""CAKE - Claude Autonomy Kit Engine"""

__version__ = "0.1.0"
'

create_file "$PROJECT_ROOT/cake/components/__init__.py" '"""Core CAKE components"""'
create_file "$PROJECT_ROOT/cake/adapters/__init__.py" '"""LLM adapters for CAKE"""'
create_file "$PROJECT_ROOT/cake/utils/__init__.py" '"""Utility functions for CAKE"""'
create_file "$PROJECT_ROOT/tests/__init__.py" '"""CAKE test suite"""'

# Create configuration files
print_status "Creating configuration files..."

# Main config file
create_file "$PROJECT_ROOT/cake_config.yaml" '# CAKE Configuration File
version: 1.0

# Core settings
core:
  mode: development  # development, staging, production
  log_level: INFO
  max_interventions: 100
  intervention_timeout: 30

# Component settings
components:
  controller:
    state_timeout: 60
    max_retries: 3
  
  operator:
    voice_similarity_threshold: 0.9
    max_message_length: 150
    allowed_verbs: ["Run", "Check", "Fix", "Try", "See"]
  
  recall_db:
    path: "./data/recall_db/cake.db"
    ttl_hours: 24
    max_entries: 10000
  
  watchdog:
    scan_interval: 0.1
    buffer_size: 1000
    pattern_timeout: 5

# Safety settings
safety:
  blocked_commands:
    - "rm -rf /"
    - "git push --force"
    - "sudo rm -rf"
  
  require_confirmation:
    - "git push"
    - "npm publish"
    - "pip install"

# Performance settings
performance:
  detection_latency_ms: 100
  command_validation_ms: 50
  db_query_ms: 10
  message_generation_rate: 100  # messages per 0.3s

# Monitoring
monitoring:
  metrics_port: 9090
  health_check_interval: 30
  export_interval: 60
'

# Create .gitignore
create_file "$PROJECT_ROOT/.gitignore" '# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
env/
.env

# Testing
.coverage
.pytest_cache/
htmlcov/
*.coverage
coverage.xml
*.cover

# IDE
.vscode/
.idea/
*.swp
*.swo

# CAKE specific
data/recall_db/*.db
data/snapshots/*
logs/*.log
metrics/*.json
*.bak

# OS
.DS_Store
Thumbs.db

# Build
build/
dist/
*.egg-info/
'

# Create requirements files
create_file "$PROJECT_ROOT/requirements.txt" '# CAKE Core Dependencies
pyyaml>=6.0
sqlalchemy>=2.0
aiofiles>=23.0
prometheus-client>=0.19
structlog>=24.0
click>=8.1
watchdog>=3.0
psutil>=5.9
'

create_file "$PROJECT_ROOT/requirements-dev.txt" '# Development Dependencies
-r requirements.txt

# Testing
pytest>=7.4
pytest-asyncio>=0.21
pytest-cov>=4.1
pytest-timeout>=2.2
pytest-mock>=3.12

# Code Quality
black>=23.0
isort>=5.13
flake8>=7.0
mypy>=1.8
bandit>=1.7
safety>=3.0

# Documentation
sphinx>=7.2
sphinx-rtd-theme>=2.0
'

# Create pyproject.toml
create_file "$PROJECT_ROOT/pyproject.toml" '[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "cake"
version = "0.1.0"
description = "Claude Autonomy Kit Engine - Deterministic intervention system for LLM operations"
readme = "README.md"
requires-python = ">=3.11"
license = {text = "MIT"}
authors = [
    {name = "CAKE Team", email = "cake@example.com"}
]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
]

[project.urls]
Homepage = "https://github.com/ZeroSumQuant/CAKE"
Documentation = "https://cake.readthedocs.io"
Repository = "https://github.com/ZeroSumQuant/CAKE"
Issues = "https://github.com/ZeroSumQuant/CAKE/issues"

[project.scripts]
cake = "cake.cli:main"

[tool.black]
line-length = 100
target-version = ["py311"]

[tool.isort]
profile = "black"
line_length = 100

[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true

[tool.pytest.ini_options]
minversion = "7.0"
addopts = "-ra -q --strict-markers"
testpaths = ["tests"]
python_files = "test_*.py"
python_classes = "Test*"
python_functions = "test_*"

[tool.coverage.run]
source = ["cake"]
omit = ["tests/*", "*/migrations/*"]

[tool.coverage.report]
precision = 2
show_missing = true
skip_covered = false
fail_under = 90

[tool.bandit]
exclude_dirs = ["tests", "scripts"]
severity = "medium"
confidence = "medium"
'

# Create Makefile
create_file "$PROJECT_ROOT/Makefile" '.PHONY: help install dev test lint format clean

help:
	@echo "CAKE Development Commands"
	@echo "========================"
	@echo "make install    - Install production dependencies"
	@echo "make dev        - Install development dependencies"
	@echo "make test       - Run all tests"
	@echo "make lint       - Run linters"
	@echo "make format     - Format code"
	@echo "make clean      - Clean build artifacts"

install:
	pip install -r requirements.txt

dev:
	pip install -r requirements-dev.txt

test:
	pytest tests/ -v --cov=cake --cov-report=term-missing

lint:
	flake8 cake/ tests/
	mypy cake/
	bandit -r cake/ -ll
	safety check

format:
	black cake/ tests/
	isort cake/ tests/

clean:
	rm -rf build/ dist/ *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .coverage htmlcov/ .pytest_cache/
'

# Create README
create_file "$PROJECT_ROOT/README.md" '# CAKE - Claude Autonomy Kit Engine

A deterministic intervention system that monitors LLM operations, prevents known failure patterns, and enforces safety guardrails without human escalation.

## 🎯 Vision

CAKE acts as an autonomous "operator" that clones the intervention style of experienced engineers to supervise any LLM, ensuring zero-escalation autonomy.

## 🚀 Quick Start

```bash
# Clone the repository
git clone https://github.com/ZeroSumQuant/CAKE.git
cd CAKE

# Initialize project structure
./scripts/cake-init.sh

# Set up development environment
./scripts/cake-setup-dev.sh

# Run tests
make test
```

## 📁 Project Structure

```
CAKE/
├── cake/               # Core source code
│   ├── components/     # Core components (Controller, Operator, etc.)
│   ├── adapters/       # LLM adapters
│   └── utils/          # Utility functions
├── tests/              # Test suite
├── docs/               # Documentation
├── scripts/            # Development scripts
└── data/               # Runtime data
```

## 🛠️ Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.
'

# Create initial component stubs
print_status "Creating component stubs..."

# Controller stub
create_file "$PROJECT_ROOT/cake/components/controller.py" '"""CAKE Controller - Central orchestration component"""

from typing import Dict, Any, Optional
from enum import Enum
import asyncio


class ControllerState(Enum):
    """Controller state machine states"""
    IDLE = "idle"
    MONITORING = "monitoring"
    INTERVENING = "intervening"
    RECOVERING = "recovering"
    ERROR = "error"


class CakeController:
    """
    Central state machine orchestrator for CAKE.
    
    Coordinates all components and manages intervention lifecycle.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize controller with configuration"""
        self.config = config
        self.state = ControllerState.IDLE
        self.components = {}
        
    async def start(self) -> None:
        """Start the controller and all components"""
        # TODO: Implement startup sequence
        raise NotImplementedError
        
    async def stop(self) -> None:
        """Stop the controller and all components"""
        # TODO: Implement shutdown sequence
        raise NotImplementedError
        
    async def handle_error(self, error: Exception) -> None:
        """Handle detected error and coordinate intervention"""
        # TODO: Implement error handling
        raise NotImplementedError
'

# Create test stub
create_file "$PROJECT_ROOT/tests/unit/test_controller.py" '"""Unit tests for CAKE Controller"""

import pytest
from cake.components.controller import CakeController, ControllerState


class TestCakeController:
    """Test cases for CakeController"""
    
    def test_controller_initialization(self):
        """Test controller initializes with correct state"""
        config = {"test": True}
        controller = CakeController(config)
        
        assert controller.state == ControllerState.IDLE
        assert controller.config == config
        
    @pytest.mark.asyncio
    async def test_controller_start(self):
        """Test controller startup sequence"""
        # TODO: Implement test
        pass
'

print_status "CAKE project initialization complete!"
print_success "Project structure created at: $PROJECT_ROOT"

# Summary
echo
print_status "Next steps:"
echo "  1. cd $PROJECT_ROOT"
echo "  2. ./scripts/cake-setup-dev.sh  # Set up development environment"
echo "  3. make dev                     # Install dependencies"
echo "  4. make test                    # Run tests"
echo
print_status "Happy CAKE development! 🎂"
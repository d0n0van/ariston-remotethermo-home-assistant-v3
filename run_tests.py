#!/usr/bin/env python3
"""Test runner script for Ariston integration."""

import sys
import subprocess
from pathlib import Path

def main():
    """Run tests for the Ariston integration."""
    project_root = Path(__file__).parent
    
    # Install test requirements
    print("Installing test requirements...")
    subprocess.run([
        sys.executable, "-m", "pip", "install", "-r", "requirements-test.txt"
    ], cwd=project_root, check=True)
    
    # Run tests
    print("Running tests...")
    result = subprocess.run([
        sys.executable, "-m", "pytest", 
        "tests/", 
        "-v", 
        "--tb=short",
        "--cov=custom_components.ariston",
        "--cov-report=html",
        "--cov-report=term-missing"
    ], cwd=project_root)
    
    if result.returncode == 0:
        print("✅ All tests passed!")
    else:
        print("❌ Some tests failed!")
        sys.exit(result.returncode)

if __name__ == "__main__":
    main()














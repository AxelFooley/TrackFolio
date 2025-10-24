#!/usr/bin/env python3
"""
Script to check flake8 errors locally without Docker
"""

import ast
import os
from pathlib import Path

def check_imports(file_path):
    """Check for unused imports using AST analysis"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []

    # Get all imported names
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split('.')[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module.split('.')[0])

    # Get all names used in the code
    used_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used_names.add(node.id)
        elif isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name):
                used_names.add(node.value.id)

    # Find unused imports
    unused = imports - used_names
    return list(unused)

def check_file(file_path):
    """Check a single file for common linting issues"""
    issues = []

    # Check for unused imports
    unused_imports = check_imports(file_path)
    if unused_imports:
        issues.append(f"Unused imports: {', '.join(unused_imports)}")

    # Check line length
    with open(file_path, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f, 1):
            if len(line.rstrip()) > 127:
                issues.append(f"Line {i} too long: {len(line)} characters")

    return issues

def main():
    # Focus on the assets.py file we were working on
    assets_file = Path("backend/app/api/assets.py")
    if assets_file.exists():
        print(f"Checking {assets_file}")
        issues = check_file(assets_file)
        if issues:
            for issue in issues:
                print(f"  {issue}")
        else:
            print("  No issues found")
    else:
        print(f"File {assets_file} not found")

if __name__ == "__main__":
    main()
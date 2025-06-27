#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced Dependency Scanner for LittleTools.

A utility to scan a Python project directory and list its third-party dependencies.
This helps identify potentially unused packages in a `pyproject.toml` file by
providing a detailed analysis of modules that are actually imported in the code.

Features:
- AST-based parsing for accurate import detection
- Detection of conditional and function-level imports
- Detailed file-by-file breakdown
- Exclusion of standard library and local packages
- .gitignore-aware scanning

Usage:
    python requirementsBuilder.py <path_to_directory>
    python requirementsBuilder.py <path_to_directory> --detailed
"""
import sys
import argparse
import ast
from pathlib import Path
from typing import Set, List
import fnmatch

# Configuration: A set of Python standard library modules to ignore.
STANDARD_LIBRARIES = {
    'abc', 'aifc', 'argparse', 'array', 'ast', 'asyncio', 'base64', 'bdb',
    'binascii', 'bisect', 'builtins', 'bz2', 'calendar', 'cgi', 'cgitb',
    'chunk', 'cmath', 'cmd', 'code', 'codecs', 'codeop', 'collections',
    'colorsys', 'compileall', 'concurrent', 'configparser', 'contextlib',
    'contextvars', 'copy', 'copyreg', 'cProfile', 'crypt', 'csv', 'ctypes',
    'curses', 'dataclasses', 'datetime', 'dbm', 'decimal', 'difflib', 'dis',
    'distutils', 'doctest', 'email', 'encodings', 'ensurepip', 'enum',
    'errno', 'faulthandler', 'fcntl', 'filecmp', 'fileinput', 'fnmatch',
    'formatter', 'fractions', 'ftplib', 'functools', 'gc', 'getopt', 'getpass',
    'gettext', 'glob', 'graphlib', 'grp', 'gzip', 'hashlib', 'heapq', 'hmac',
    'html', 'http', 'idlelib', 'imaplib', 'imghdr', 'imp', 'importlib',
    'inspect', 'io', 'ipaddress', 'itertools', 'json', 'keyword', 'lib2to3',
    'linecache', 'locale', 'logging', 'lzma', 'macpath', 'mailbox', 'mailcap',
    'marshal', 'math', 'mimetypes', 'mmap', 'modulefinder', 'msilib', 'msvcrt',
    'multiprocessing', 'netrc', 'nis', 'nntplib', 'numbers', 'operator', 'optparse',
    'os', 'ossaudiodev', 'parser', 'pathlib', 'pdb', 'pickle', 'pickletools',
    'pipes', 'pkgutil', 'platform', 'plistlib', 'poplib', 'posix', 'pprint',
    'profile', 'pstats', 'pty', 'pwd', 'py_compile', 'pyclbr', 'pydoc', 'queue',
    'quopri', 'random', 're', 'readline', 'reprlib', 'resource', 'rlcompleter',
    'runpy', 'sched', 'secrets', 'select', 'selectors', 'shelve', 'shlex', 'shutil',
    'signal', 'site', 'smtpd', 'smtplib', 'sndhdr', 'socket', 'socketserver',
    'spwd', 'sqlite3', 'ssl', 'stat', 'statistics', 'string', 'stringprep',
    'struct', 'subprocess', 'sunau', 'symbol', 'symtable', 'sys', 'sysconfig',
    'syslog', 'tabnanny', 'tarfile', 'telnetlib', 'tempfile', 'termios', 'test',
    'textwrap', 'threading', 'time', 'timeit', 'tkinter', 'token', 'tokenize',
    'trace', 'traceback', 'tracemalloc', 'tty', 'turtle', 'turtledemo', 'types',
    'typing', 'unicodedata', 'unittest', 'urllib', 'uu', 'uuid', 'venv', 'warnings',
    'wave', 'weakref', 'webbrowser', 'winreg', 'winsound', 'wsgiref', 'xdrlib',
    'xml', 'xmlrpc', 'zipapp', 'zipfile', 'zipimport', 'zlib',
    # ! Also exclude common development/testing libraries that shouldn't be in dependencies
    'setuptools', 'distutils', 'pytest', 'unittest', 'test', 'typing_extensions',
    # ! Exclude __future__ as it's a special import, not a dependency
    '__future__'
}

# * Local package prefixes to exclude (these are internal to the project)
LOCAL_PACKAGE_PREFIXES = {
    'littletools_', 'littletools'
}

# * Common internal module names that are not dependencies
INTERNAL_MODULES = {
    'utils', 'config', 'constants', 'helpers', 'common', 'base'
}


def is_local_package(module_name: str) -> bool:
    """
    Check if a module is a local package (part of the current project).
    
    Args:
        module_name (str): The module name to check.
        
    Returns:
        bool: True if it's a local package, False otherwise.
    """
    return (any(module_name.startswith(prefix) for prefix in LOCAL_PACKAGE_PREFIXES) or
            module_name in INTERNAL_MODULES)


def find_imports_in_file_ast(file_path: Path, detailed: bool = False) -> tuple[Set[str], dict]:
    """
    Parses a Python file using AST to find all non-standard imported modules.
    
    Args:
        file_path (Path): Path to the Python file to analyze.
        detailed (bool): If True, return detailed information about import locations.

    Returns:
        tuple: (set of module names, dict with detailed info if requested)
    """
    third_party_imports = set()
    import_details = {}
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        tree = ast.parse(content, filename=str(file_path))
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module = alias.name.split('.')[0]
                    if (module and 
                        module not in STANDARD_LIBRARIES and 
                        not is_local_package(module)):
                        third_party_imports.add(module)
                        if detailed:
                            if module not in import_details:
                                import_details[module] = []
                            import_details[module].append(f"line {node.lineno}: import {alias.name}")
                            
            elif isinstance(node, ast.ImportFrom):
                # Handles 'from module import ...' but skips relative imports '.'.
                if node.module and not node.module.startswith('.'):
                    module = node.module.split('.')[0]
                    if (module and 
                        module not in STANDARD_LIBRARIES and 
                        not is_local_package(module)):
                        third_party_imports.add(module)
                        if detailed:
                            if module not in import_details:
                                import_details[module] = []
                            imported_names = ', '.join(alias.name for alias in node.names)
                            import_details[module].append(f"line {node.lineno}: from {node.module} import {imported_names}")
                            
    except (SyntaxError, UnicodeDecodeError, IOError) as e:
        print(f"Warning: Could not process {file_path}: {e}")
        
    return third_party_imports, import_details


def load_gitignore_patterns(directory: Path) -> List[str]:
    """
    Loads patterns from a .gitignore file in the project's root.
    
    Always includes '.venv' to ensure the virtual environment is ignored.
    Args:
        directory (Path): The directory to start searching for .gitignore from.

    Returns:
        List[str]: A list of glob patterns to ignore.
    """
    # Start from the scan directory and go up to find the root .gitignore
    root_dir = directory
    while root_dir.parent != root_dir: # Stop at the filesystem root
        gitignore_file = root_dir / '.gitignore'
        if gitignore_file.exists():
            break
        root_dir = root_dir.parent
    
    patterns = ['.venv'] # Always ignore virtual environments
    gitignore_file = root_dir / '.gitignore'

    if gitignore_file.exists():
        try:
            with open(gitignore_file, 'r', encoding='utf-8') as f:
                patterns.extend(line.strip() for line in f if line.strip() and not line.startswith('#'))
        except Exception as e:
            print(f"Warning: Could not read .gitignore at {gitignore_file}: {e}")
    
    return patterns


def is_ignored(file_path: Path, ignore_patterns: List[str], base_dir: Path) -> bool:
    """
    Checks if a file path matches any of the ignore patterns.
    
    Args:
        file_path (Path): Path to the file to check.
        ignore_patterns (List[str]): List of patterns to ignore.
        base_dir (Path): The base directory from which scanning started.

    Returns:
        bool: True if the file should be ignored, False otherwise.
    """
    relative_path_str = ""
    try:
        # Check against path relative to where .gitignore was found
        gitignore_root = base_dir
        while not (gitignore_root / '.gitignore').exists() and gitignore_root.parent != gitignore_root:
            gitignore_root = gitignore_root.parent

        relative_path_str = file_path.relative_to(gitignore_root).as_posix()
    except ValueError:
        # The file is outside the hierarchy of the gitignore root, don't ignore
        pass

    # Check path-based patterns (e.g., 'docs/')
    for pattern in ignore_patterns:
        if pattern.endswith('/'):
            if f"/{pattern}" in f"/{relative_path_str}/":
                return True
        elif fnmatch.fnmatch(relative_path_str, pattern):
            return True
            
    # Check directory name patterns (e.g., '.venv')
    for part in file_path.parts:
        if part in ignore_patterns:
            return True
            
    return False


def scan_directory_for_dependencies(directory: Path, detailed: bool = False):
    """
    Scans a directory for Python files, extracts their dependencies, and prints the result.
    
    Args:
        directory (Path): The directory to scan.
        detailed (bool): If True, provide detailed file-by-file breakdown.
    """
    print(f"Scanning for Python files in: {directory}\n")
    
    # Load ignore patterns relative to the project root for accurate exclusion
    ignore_patterns = load_gitignore_patterns(directory)

    # Find all python files, excluding ignored ones
    python_files = [
        f for f in directory.glob('**/*.py')
        if not is_ignored(f, ignore_patterns, directory)
    ]
    
    if not python_files:
        print("No Python files found in the specified directory.")
        return

    all_imports = set()
    file_imports = {}
    
    print("Found files to scan:")
    for file_path in python_files:
        print(f"  - {file_path.relative_to(directory)}")
        imports, details = find_imports_in_file_ast(file_path, detailed)
        all_imports.update(imports)
        if detailed and imports:
            file_imports[file_path.relative_to(directory)] = (imports, details)

    sorted_imports = sorted(all_imports)

    if detailed and file_imports:
        print("\n" + "="*60)
        print("DETAILED FILE-BY-FILE ANALYSIS")
        print("="*60)
        
        for file_path, (imports, details) in file_imports.items():
            if imports:
                print(f"\n📁 {file_path}")
                print("-" * (len(str(file_path)) + 3))
                for module in sorted(imports):
                    print(f"  • {module}")
                    if module in details:
                        for detail in details[module]:
                            print(f"    └─ {detail}")

    print("\n" + "="*60)
    print("SUMMARY: Third-Party Dependencies Found")
    print("="*60)
    if not sorted_imports:
        print("❌ No third-party imports found.")
    else:
        for i, module in enumerate(sorted_imports, 1):
            print(f"{i:2d}. {module}")
    
    print("\n" + "="*60)
    print("NEXT STEPS")
    print("="*60)
    print("1. Compare this list with your `pyproject.toml` dependencies section")
    print("2. Dependencies in pyproject.toml but NOT in this list = potentially unused")
    print("3. Dependencies in this list but NOT in pyproject.toml = missing dependencies")
    print("4. ⚠️  CAUTION: Some imports may be conditional or dynamic - review carefully!")
    
    if detailed:
        print("\n💡 TIP: Use the detailed analysis above to understand WHERE each dependency is used")
    else:
        print("\n💡 TIP: Run with --detailed flag for file-by-file breakdown")


def main() -> int:
    """
    Main function to parse CLI arguments and run the dependency scanning process.
    """
    parser = argparse.ArgumentParser(
        description="Enhanced dependency scanner for Python projects.",
        epilog="This tool helps identify unused packages by analyzing actual imports in your code.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        'directory', 
        nargs='?', 
        default='.', 
        help="The directory to scan for Python files. Defaults to the current directory."
    )
    parser.add_argument(
        '--detailed', '-d',
        action='store_true',
        help="Show detailed file-by-file breakdown of imports and their locations."
    )
    args = parser.parse_args()

    scan_dir = Path(args.directory).resolve()
    if not scan_dir.is_dir():
        print(f"❌ Error: '{scan_dir}' is not a valid directory.", file=sys.stderr)
        return 1

    try:
        scan_directory_for_dependencies(scan_dir, detailed=args.detailed)
        return 0
    except KeyboardInterrupt:
        print("\n\n⚠️  Operation cancelled by user.", file=sys.stderr)
        return 130


if __name__ == '__main__':
    sys.exit(main())
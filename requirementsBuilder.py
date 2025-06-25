#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dependency Scanner for LittleTools.

A utility to scan a Python project directory and list its third-party dependencies.
This helps identify potentially unused packages in a `pyproject.toml` file by
providing a simple list of modules that are actually imported in the code.

Usage:
    python requirementsBuilder.py <path_to_directory>
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
    'setuptools', 'distutils', 'pytest', 'unittest', 'test', 'typing_extensions'
}


def find_imports_in_file_ast(file_path: Path) -> Set[str]:
    """
    Parses a Python file using AST to find all non-standard imported modules.
    
    Args:
        file_path (Path): Path to the Python file to analyze.

    Returns:
        Set[str]: A set of top-level module names that are imported.
    """
    third_party_imports = set()
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        tree = ast.parse(content, filename=str(file_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module = alias.name.split('.')[0]
                    if module and module not in STANDARD_LIBRARIES:
                        third_party_imports.add(module)
            elif isinstance(node, ast.ImportFrom):
                # Handles 'from module import ...' but skips relative imports '.'.
                if node.module and not node.module.startswith('.'):
                    module = node.module.split('.')[0]
                    if module and module not in STANDARD_LIBRARIES:
                        third_party_imports.add(module)
    except (SyntaxError, UnicodeDecodeError, IOError) as e:
        print(f"Warning: Could not process {file_path}: {e}")
    return third_party_imports


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


def scan_directory_for_dependencies(directory: Path):
    """
    Scans a directory for Python files, extracts their dependencies, and prints the result.
    
    Args:
        directory (Path): The directory to scan.
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
    print("Found files to scan:")
    for file_path in python_files:
        print(f"  - {file_path.relative_to(directory)}")
        all_imports.update(find_imports_in_file_ast(file_path))

    sorted_imports = sorted(all_imports)

    print("\n--- Found Third-Party Dependencies ---")
    if not sorted_imports:
        print("No third-party imports found.")
    else:
        for module in sorted_imports:
            print(module)
    print("------------------------------------")
    print("\nCompare this list with your `pyproject.toml` to find unused packages.")


def main() -> int:
    """
    Main function to parse CLI arguments and run the dependency scanning process.
    """
    parser = argparse.ArgumentParser(
        description="Scan a Python project to find third-party dependencies.",
        epilog="This tool helps identify unused packages by listing all imported modules."
    )
    parser.add_argument(
        'directory', 
        nargs='?', 
        default='.', 
        help="The directory to scan for Python files. Defaults to the current directory."
    )
    args = parser.parse_args()

    scan_dir = Path(args.directory).resolve()
    if not scan_dir.is_dir():
        print(f"Error: '{scan_dir}' is not a valid directory.", file=sys.stderr)
        return 1

    try:
        scan_directory_for_dependencies(scan_dir)
        return 0
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.", file=sys.stderr)
        return 130


if __name__ == '__main__':
    sys.exit(main())
#!/usr/bin/env python3
"""
Script to generate requirements.txt by scanning Python files for imports.

Capabilities:
- Scans all Python files in the specified directory and its subdirectories.
- Detects non-standard imports, including those in conditional blocks and inside functions, using AST parsing.
- Checks installed package versions via pip to include version info in requirements.txt.
- Supports choosing the output location for the requirements file (absolute path if provided, or in the current directory).
- Offers a CLI interface and prompts whether to install packages via pip after generating the file.

Limitations:
- Dynamic imports or imports generated at runtime may not be detected.
- Analysis is static and only covers patterns parsed by Python's AST.
- Only standard libraries available in Python 3.13 and below are used.
"""

import os
import re
import sys
import subprocess
import argparse
import ast
from pathlib import Path
from typing import Set, List, Optional

# Configuration variables
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
    # Modules that might be imported from standard libraries
    'setuptools', 'distutils', 'pytest', 'unittest', 'test', 'typing_extensions'
}


def get_installed_package_version(package_name: str) -> Optional[str]:
    """
    Returns the installed version of a package using 'pip show'.
    If package is not installed, returns None.
    """
    try:
        result = subprocess.run([
            sys.executable, '-m', 'pip', 'show', package_name
        ], capture_output=True, text=True, check=True)
        for line in result.stdout.splitlines():
            if line.startswith('Version:'):
                return line.split(':', 1)[1].strip()
    except subprocess.CalledProcessError:
        return None
    return None


def get_installed_package_location(package_name: str) -> Optional[str]:
    """
    Returns the installation location of a package using 'pip show'.
    If package is not installed, returns None.
    """
    try:
        result = subprocess.run([
            sys.executable, '-m', 'pip', 'show', package_name
        ], capture_output=True, text=True, check=True)
        for line in result.stdout.splitlines():
            if line.startswith('Location:'):
                return line.split(':', 1)[1].strip()
    except subprocess.CalledProcessError:
        return None
    return None


def find_imports_in_file_ast(file_path: Path) -> Set[str]:
    """
    Parses a Python file using AST to find all non-standard imported modules.
    It catches imports in all scopes including conditional imports and within functions.
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
                # Skip relative imports
                if node.module and not node.module.startswith('.'):
                    module = node.module.split('.')[0]
                    if module and module not in STANDARD_LIBRARIES:
                        third_party_imports.add(module)
    except (SyntaxError, UnicodeDecodeError, IOError) as e:
        print(f"Warning: Could not process {file_path}: {e}")
    return third_party_imports


def find_python_files(directory: Path) -> List[Path]:
    """
    Recursively finds all Python files in the given directory.
    """
    return list(directory.glob('**/*.py'))


def generate_requirements(directory: Path, output_path: Optional[Path] = None, show_location: bool = False) -> Path:
    """
    Generates a requirements file by scanning Python files for non-standard imports.
    For each third-party import, it checks the installed package version via pip.
    If show_location is True, it will also include the installation location as a comment.

    If output_path is not provided, defaults to a file named 'requirements.txt' in the scan directory.
    The file is overwritten if it exists.
    """
    if output_path is None:
        output_path = directory / 'requirements.txt'

    python_files = find_python_files(directory)
    all_imports = set()

    print(f"Scanning {len(python_files)} Python files for imports...")

    for file_path in python_files:
        imports = find_imports_in_file_ast(file_path)
        all_imports.update(imports)

    # Sort imports alphabetically
    sorted_imports = sorted(all_imports)

    with open(output_path, 'w', encoding='utf-8') as f:
        for module in sorted_imports:
            version = get_installed_package_version(module)
            if version:
                line = f"{module}=={version}"
            else:
                line = module
            f.write(line + "\n")
            if show_location:
                location = get_installed_package_location(module)
                if location:
                    f.write(f"# installed at: {location}\n")

    print(f"Found {len(sorted_imports)} third-party module imports.")
    print(f"Requirements file generated at: {output_path}")

    return output_path


def install_requirements(requirements_path: Path) -> None:
    """
    Installs packages from the generated requirements file using pip.
    """
    try:
        subprocess.run([
            sys.executable, '-m', 'pip', 'install', '-r', str(requirements_path)
        ], check=True)
        print("Packages installed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error installing packages: {e}")


def main() -> int:
    """
    Main function to parse CLI arguments and run the requirements generation process.
    """
    parser = argparse.ArgumentParser(
        description="Generate requirements.txt by scanning Python files for imports"
    )
    parser.add_argument(
        '-d', '--dir', 
        type=str, 
        default='.', 
        help='Directory to scan for Python files (default: current directory)'
    )
    parser.add_argument(
        '-o', '--output', 
        type=str, 
        help='Output path for requirements.txt (default: requirements.txt in the scan directory)'
    )
    parser.add_argument(
        '-l', '--show-location', 
        action='store_true', 
        help='Include the installation location of the package as a comment in the requirements file'
    )

    args = parser.parse_args()

    scan_dir = Path(args.dir).resolve()
    output_path = Path(args.output).resolve() if args.output else None

    if not scan_dir.is_dir():
        print(f"Error: {scan_dir} is not a valid directory")
        return 1

    requirements_path = generate_requirements(scan_dir, output_path, args.show_location)

    while True:
        response = input("Do you want to install the requirements now? (y/n): ").lower().strip()
        if response in ['y', 'yes']:
            install_requirements(requirements_path)
            break
        elif response in ['n', 'no']:
            break
        else:
            print("Please enter 'y' or 'n'")

    return 0


if __name__ == '__main__':
    sys.exit(main())
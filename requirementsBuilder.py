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
import fnmatch

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
    Retrieves the installed version of a package using 'pip show'.

    Args:
        package_name (str): Name of the package to check.

    Returns:
        Optional[str]: Version of the package if installed, None otherwise.
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
    Retrieves the installation location of a package using 'pip show'.

    Args:
        package_name (str): Name of the package to locate.

    Returns:
        Optional[str]: Installation path of the package if installed, None otherwise.
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

    Detects imports in all scopes including conditional imports and within functions.
    Skips standard library and relative imports.

    Args:
        file_path (Path): Path to the Python file to analyze.

    Returns:
        Set[str]: Set of non-standard imported module names.

    Warns:
        Prints a warning message if the file cannot be processed.
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


def load_gitignore(directory: Path) -> List[str]:
    """
    Loads .gitignore file from the given directory.

    If .gitignore does not exist, prompts user to create one with .venv exclusion.
    Always ensures '.venv' is included in ignore patterns.

    Args:
        directory (Path): Directory to search for .gitignore file.

    Returns:
        List[str]: List of ignore patterns, always including '.venv'.

    Warns:
        Prints warning messages if .gitignore cannot be read or created.
    """
    gitignore_file = directory / '.gitignore'
    patterns = []
    patterns.append('.venv')
    if not gitignore_file.exists():
        response = input(".gitignore file not found. Do you want to create one with '.venv' exclusion (y/n)? ").strip().lower()
        if response in ['y', 'yes']:
            try:
                with open(gitignore_file, 'w', encoding='utf-8') as f:
                    f.write(".venv\n")
                print("Created .gitignore with '.venv' exclusion.")
            except Exception as e:
                print(f"Warning: Could not create .gitignore: {e}")
        else:
            print("Continuing without creating .gitignore, but '.venv' will be excluded anyway.")
    else:
        try:
            with open(gitignore_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        patterns.append(line)
        except Exception as e:
            print(f"Warning: Could not read .gitignore: {e}")
    return patterns


def is_ignored(file_path: Path, ignore_patterns: List[str], base_dir: Path) -> bool:
    """
    Checks if a file path matches any of the ignore patterns.

    Prioritizes checking if any part of the path is in ignored directories.

    Args:
        file_path (Path): Path to the file to check.
        ignore_patterns (List[str]): List of patterns to ignore.
        base_dir (Path): Base directory for relative path calculation.

    Returns:
        bool: True if the file should be ignored, False otherwise.
    """
    try:
        relative = str(file_path.relative_to(base_dir))
    except ValueError:
        relative = str(file_path)
    
    # First check if any part of the path is in ignored directories
    path_parts = Path(relative).parts
    if any(part in ignore_patterns for part in path_parts):
        return True
    
    # Then do fnmatch pattern matching
    for pattern in ignore_patterns:
        if fnmatch.fnmatch(relative, pattern):
            return True
    
    return False


def find_python_files(directory: Path) -> List[Path]:
    """
    Recursively finds all Python files in the given directory.

    Excludes files and directories that match patterns in .gitignore.

    Args:
        directory (Path): Directory to search for Python files.

    Returns:
        List[Path]: List of Python file paths that are not ignored.
    """
    ignore_patterns = load_gitignore(directory)
    all_files = list(directory.glob('**/*.py'))
    return [f for f in all_files if not is_ignored(f, ignore_patterns, directory)]


def generate_requirements(directory: Path, output_path: Optional[Path] = None, show_location: bool = False) -> Path:
    """
    Generates a requirements file by scanning Python files for non-standard imports.

    Scans all Python files, finds third-party imports, checks their installed versions,
    and optionally includes installation locations.

    Args:
        directory (Path): Directory to scan for Python files.
        output_path (Optional[Path], optional): Path to save requirements.txt. 
            Defaults to 'requirements.txt' in the scan directory.
        show_location (bool, optional): Whether to include package installation locations. 
            Defaults to False.

    Returns:
        Path: Path to the generated requirements.txt file.

    Prompts:
        Asks user whether to install the discovered requirements.
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

    print(f"Requirements file generated at: {output_path}")
    
    if sorted_imports:
        print(f"Found {len(sorted_imports)} third-party module imports.")
        while True:
                response = input("Do you want to install the requirements now? (y/n): ").lower().strip()
                if response in ['y', 'yes']:
                    install_requirements(output_path)
                    break
                elif response in ['n', 'no']:
                    break
                else:
                    print("Please enter 'y' or 'n'")
    else:
        print("No third-party modules found.")        

    return output_path


def install_requirements(requirements_path: Path) -> None:
    """
    Installs packages from the generated requirements file using pip.

    Args:
        requirements_path (Path): Path to the requirements.txt file.

    Raises:
        subprocess.CalledProcessError: If pip install fails.
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

    Handles command-line arguments for directory scanning, output path, and location display.
    Includes Ctrl+C handling.

    Returns:
        int: Exit code (0 for success, 1 for directory error, 130 for keyboard interrupt).
    """
    try:
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

        generate_requirements(scan_dir, output_path, args.show_location)

        return 0

    except KeyboardInterrupt:
        print("\nScript interrupted by user. Exiting...")
        return 130  # Standard exit code for Ctrl+C


if __name__ == '__main__':
    sys.exit(main())
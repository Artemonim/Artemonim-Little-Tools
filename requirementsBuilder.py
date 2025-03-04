#!/usr/bin/env python3
"""
Script to generate requirements.txt by scanning Python files for imports.

Capabilities:
- Scans all Python files in the specified directory and its subdirectories.
- Detects non-standard imports, including those in conditional blocks and inside functions, using AST parsing.
- Checks installed package versions via pip to include version info in requirements.txt.
- Supports choosing the output location for the requirements file (absolute path if provided, or in the current directory).
- Offers a CLI interface and prompts whether to install packages via pip after generating the file.
- Recursively generates requirements.txt for subdirectories when enabled.

Limitations:
- Dynamic imports or imports generated at runtime may not be detected.
- Analysis is static and only covers patterns parsed by Python's AST.
- Only standard libraries available in Python 3.13 and below are used.
"""

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
    'setuptools', 'distutils', 'pytest', 'unittest', 'test', 'typing_extensions'
}


def get_installed_package_version(package_name: str) -> Optional[str]:
    """
    Retrieves the installed version of a package using pip show command.

    Args:
        package_name (str): Name of the package to check.

    Returns:
        Optional[str]: Version of the package if installed, None otherwise.
    """
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'show', package_name],
            capture_output=True, text=True, check=True
        )
        for line in result.stdout.splitlines():
            if line.startswith('Version:'):
                return line.split(':', 1)[1].strip()
    except subprocess.CalledProcessError:
        return None
    return None


def get_installed_package_location(package_name: str) -> Optional[str]:
    """
    Retrieves the installation location of a package using pip show command.

    Args:
        package_name (str): Name of the package to locate.

    Returns:
        Optional[str]: Installation path of the package if installed, None otherwise.
    """
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'show', package_name],
            capture_output=True, text=True, check=True
        )
        for line in result.stdout.splitlines():
            if line.startswith('Location:'):
                return line.split(':', 1)[1].strip()
    except subprocess.CalledProcessError:
        return None
    return None


def find_imports_in_file_ast(file_path: Path) -> Set[str]:
    """
    Parses a Python file using Abstract Syntax Tree (AST) to find non-standard imported modules.

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
                if node.module and not node.module.startswith('.'):
                    module = node.module.split('.')[0]
                    if module and module not in STANDARD_LIBRARIES:
                        third_party_imports.add(module)
    except (SyntaxError, UnicodeDecodeError, IOError) as e:
        print(f"Warning: Could not process {file_path}: {e}")
    return third_party_imports


def load_gitignore(directory: Path) -> List[str]:
    """
    Loads .gitignore file from the given directory and generates ignore patterns.

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
    patterns = ['.venv']
    if not gitignore_file.exists():
        response = input(".gitignore not found. Create one with '.venv' exclusion? (y/n): ").strip().lower()
        if response in ['y', 'yes']:
            try:
                gitignore_file.write_text(".venv\n", encoding='utf-8')
                print(f"Created .gitignore in {directory}")
            except Exception as e:
                print(f"Warning: Could not create .gitignore: {e}")
    else:
        try:
            with open(gitignore_file, 'r', encoding='utf-8') as f:
                patterns.extend(line.strip() for line in f if line.strip() and not line.startswith('#'))
        except Exception as e:
            print(f"Warning: Could not read .gitignore: {e}")
    return patterns


def is_ignored(file_path: Path, ignore_patterns: List[str], base_dir: Path) -> bool:
    """
    Checks if a file path matches any of the ignore patterns.

    Determines if a file should be ignored based on its relative path and ignore patterns.

    Args:
        file_path (Path): Path to the file to check.
        ignore_patterns (List[str]): List of patterns to ignore.
        base_dir (Path): Base directory for relative path calculation.

    Returns:
        bool: True if the file should be ignored, False otherwise.
    """
    try:
        relative = file_path.relative_to(base_dir).as_posix()
    except ValueError:
        return False
    if any(fnmatch.fnmatch(relative, pattern) for pattern in ignore_patterns):
        return True
    for part in file_path.parts:
        if part in ignore_patterns:
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
    return [
        f for f in directory.glob('**/*.py')
        if not is_ignored(f, ignore_patterns, directory)
    ]


def generate_requirements(
    directory: Path,
    output_path: Optional[Path] = None,
    show_location: bool = False,
    interactive: bool = True,
    recursive: bool = False
) -> Path:
    """
    Generates a requirements.txt file by scanning Python files for non-standard imports.

    Scans all Python files, finds third-party imports, checks their installed versions,
    and optionally includes installation locations. Can process subdirectories recursively.

    Args:
        directory (Path): Directory to scan for Python files.
        output_path (Optional[Path], optional): Path to save requirements.txt. 
            Defaults to 'requirements.txt' in the scan directory.
        show_location (bool, optional): Whether to include package installation locations. 
            Defaults to False.
        interactive (bool, optional): Whether to prompt for package installation. 
            Defaults to True.
        recursive (bool, optional): Whether to process subdirectories. 
            Defaults to False.

    Returns:
        Path: Path to the generated requirements.txt file.

    Warns:
        Prints messages about file generation and potential issues.

    Prompts:
        Asks user whether to install the discovered requirements if interactive is True.
    """
    if output_path is None:
        output_path = directory / 'requirements.txt'

    python_files = find_python_files(directory)
    all_imports = set()

    print(f"Scanning {len(python_files)} Python files in {directory}...")

    for file_path in python_files:
        all_imports.update(find_imports_in_file_ast(file_path))

    sorted_imports = sorted(all_imports)

    if not sorted_imports:
        print(f"No third-party imports found in {directory}. Skipping requirements.txt.")
        if output_path.exists():
            try:
                output_path.unlink()
                print(f"Removed empty {output_path}")
            except Exception as e:
                print(f"Warning: Could not remove {output_path}: {e}")
        return output_path

    with open(output_path, 'w', encoding='utf-8') as f:
        for module in sorted_imports:
            version = get_installed_package_version(module)
            line = f"{module}=={version}" if version else module
            f.write(line + "\n")
            if show_location:
                location = get_installed_package_location(module)
                if location:
                    f.write(f"# {location}\n")

    print(f"Generated {output_path}")

    if interactive and sorted_imports:
        while True:
            choice = input("Install requirements now? (y/n): ").lower()
            if choice in ['y', 'yes']:
                install_requirements(output_path)
                break
            elif choice in ['n', 'no']:
                break

    if recursive:
        ignore_patterns = load_gitignore(directory)
        for subdir in [d for d in directory.iterdir() if d.is_dir()]:
            if not is_ignored(subdir, ignore_patterns, directory):
                generate_requirements(
                    subdir, subdir / 'requirements.txt',
                    show_location, interactive=False, recursive=True
                )

    return output_path


def install_requirements(requirements_path: Path) -> None:
    """
    Installs packages from the generated requirements file using pip.

    Args:
        requirements_path (Path): Path to the requirements.txt file.

    Warns:
        Prints error message if package installation fails.
    """
    try:
        subprocess.run(
            [sys.executable, '-m', 'pip', 'install', '-r', str(requirements_path)],
            check=True
        )
        print("Requirements installed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error installing requirements: {e}")


def main() -> int:
    """
    Main function to parse CLI arguments and run the requirements generation process.

    Handles command-line arguments for directory scanning, output path, 
    location display, and recursive processing.

    Returns:
        int: Exit code (0 for success, 1 for directory error, 130 for keyboard interrupt).

    Warns:
        Prints error message for invalid directory.

    Raises:
        KeyboardInterrupt: Handled to provide a clean exit on user interruption.
    """
    try:
        parser = argparse.ArgumentParser(description="Generate requirements.txt from Python imports")
        parser.add_argument('-d', '--dir', default='.', help="Directory to scan")
        parser.add_argument('-o', '--output', help="Output file path")
        parser.add_argument('-l', '--show-location', action='store_true', help="Show package locations")
        parser.add_argument('-r', '--recursive', action='store_true', help="Process subdirectories recursively")
        args = parser.parse_args()

        scan_dir = Path(args.dir).resolve()
        if not scan_dir.is_dir():
            print(f"Error: {scan_dir} is not a valid directory")
            return 1

        generate_requirements(
            scan_dir,
            Path(args.output) if args.output else None,
            args.show_location,
            recursive=args.recursive
        )
        return 0

    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        return 130


if __name__ == '__main__':
    sys.exit(main())
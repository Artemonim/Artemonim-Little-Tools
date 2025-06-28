#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LittleTools Code Quality Checker

Автоматизированная проверка качества кода для всего проекта LittleTools.

- Всегда выполняет автофиксы форматирования (black, isort) перед анализом.
- Использует отдельные конфиги линтеров из папки littletools_dev/.linting/
- Поддерживает проверку как всего проекта, так и отдельных файлов/директорий.
- Подходит для локальной разработки и CI/CD (через --json).

Инструменты:
    - Pyright: статический анализ типов (TypeScript-подобный)
    - Flake8: стиль и синтаксис Python
    - MyPy: строгая проверка типов
    - Black: автоформатирование Python-кода
    - isort: автоупорядочивание импортов

Примеры запуска:
    python check.py                                    # Проверить весь проект с автофиксом
    python check.py --path myfile.py                   # Проверить только myfile.py
    python check.py --path src/ tests/                 # Проверить только указанные директории
    python check.py --tool black --path myfile.py      # Проверить/отформатировать только myfile.py black'ом
    python check.py --json                             # Вывод в JSON для CI/CD

Опции:
    --tool: Запустить только указанный инструмент (pyright, flake8, mypy, black, isort)
    --path: Проверить только указанные файлы/директории
    --verbose: Подробный вывод
    --json: Вывод в JSON для CI/CD
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

# * Get the path to linting configs
def get_linting_config_path() -> str:
    """Get the path to linting configuration files."""
    # * Try littletools_dev first (new location)
    dev_linting_path = os.path.join("littletools_dev", ".linting")
    if os.path.exists(dev_linting_path):
        return dev_linting_path
    
    # * Fallback to old location for backward compatibility
    old_linting_path = ".linting"
    if os.path.exists(old_linting_path):
        return old_linting_path
    
    # * If neither exists, use the dev path (will cause appropriate errors)
    return dev_linting_path

LINTING_CONFIG_PATH = get_linting_config_path()

# * Configuration
TOOLS_CONFIG = {
    "pyright": {
        "command": ["npx", "--yes", "pyright"],
        "args": [".", "--outputjson"],
        "description": "Static type checking and analysis",
        "can_fix": False,
        "critical": True,
        "supports_single_files": True,  # now supports isolated file checks
    },
    "flake8": {
        "command": [sys.executable, "-m", "flake8"],
        "args": [f"--config={LINTING_CONFIG_PATH}/flake8.cfg"],
        "description": "Style guide enforcement and error detection",
        "can_fix": False,
        "critical": True,
        "supports_single_files": True,
    },
    "mypy": {
        "command": [sys.executable, "-m", "mypy"],
        "args": [f"--config-file={LINTING_CONFIG_PATH}/mypy.ini"],
        "description": "Advanced type checking",
        "can_fix": False,
        "critical": True,
        "supports_single_files": True,
    },
    "black": {
        "command": [sys.executable, "-m", "black"],
        "args": ["--check", "--diff", f"--config={LINTING_CONFIG_PATH}/black.toml"],
        "args_fix": [f"--config={LINTING_CONFIG_PATH}/black.toml"],
        "description": "Code formatting check",
        "can_fix": True,
        "critical": False,
        "supports_single_files": True,
    },
    "isort": {
        "command": [sys.executable, "-m", "isort"],
        "args": ["--check-only", "--diff", f"--settings-path={LINTING_CONFIG_PATH}/isort.cfg"],
        "args_fix": [f"--settings-path={LINTING_CONFIG_PATH}/isort.cfg"],
        "description": "Import sorting check",
        "can_fix": True,
        "critical": False,
        "supports_single_files": True,
    },
}

# * Target directories for analysis
TARGET_DIRS = [
    "littletools_cli",
    "littletools_core",
    "littletools_speech",
    "littletools_txt",
    "littletools_video",
]


class CodeQualityChecker:
    """Main class for running code quality checks."""

    def __init__(
        self,
        verbose: bool = False,
        json_output: bool = False,
        target_paths: Optional[List[str]] = None,
    ):
        super().__init__()  # * Ensure parent __init__ is called (for static checkers)
        self.verbose: bool = verbose
        self.json_output: bool = json_output

        # * Set target paths and validate Python files
        if target_paths:
            self.target_paths = self._validate_python_paths(target_paths)
            if not self.target_paths:
                if not json_output:
                    self.print_status(
                        "No valid Python files or directories found in specified paths",
                        "error",
                    )
                raise ValueError("No valid Python files found")
        else:
            self.target_paths = TARGET_DIRS

        self.results: Dict[str, Any] = {}
        self.start_time: float = time.time()

    def print_status(self, message: str, level: str = "info") -> None:
        """Print status message with appropriate formatting."""
        if self.json_output:
            return

        prefixes = {
            "info": "* ",
            "success": "✓ ",
            "warning": "! ",
            "error": "✗ ",
            "header": "═ ",
        }
        prefix = prefixes.get(level, "* ")
        print(f"{prefix}{message}")

    def print_separator(self, title: str = "") -> None:
        """Print a separator line."""
        if self.json_output:
            return

        if title:
            print(f"\n{'═' * 20} {title} {'═' * 20}")
        else:
            print("═" * 60)

    def _validate_python_paths(self, paths: List[str]) -> List[str]:
        """Filter paths to include only Python files and directories containing Python files."""
        valid_paths: List[str] = []
        for path in paths:
            if os.path.isfile(path):
                if path.endswith(".py"):
                    valid_paths.append(path)
                elif self.verbose:
                    self.print_status(f"Skipping non-Python file: {path}", "warning")
            elif os.path.isdir(path):
                has_python_files = False
                for root, dirs, files in os.walk(path):
                    # * Only check for .py files, do not use unused variables
                    if any(f.endswith(".py") for f in files):
                        has_python_files = True
                        break
                if has_python_files:
                    valid_paths.append(path)
                elif self.verbose:
                    self.print_status(
                        f"Directory contains no Python files: {path}", "warning"
                    )
        return valid_paths

    def run_command(
        self, command: List[str], cwd: Optional[str] = None
    ) -> Tuple[int, str, str]:
        """Run a shell command and return exit code, stdout, stderr."""
        try:
            if self.verbose:
                self.print_status(f"Running: {' '.join(command)}")

            # * Use shell=True on Windows for npm/npx commands
            use_shell = os.name == "nt" and command[0] in ["npx", "npm"]

            result = subprocess.run(
                command,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
                shell=use_shell,
            )

            return result.returncode, result.stdout, result.stderr

        except subprocess.TimeoutExpired:
            return 124, "", "Command timed out after 5 minutes"
        except FileNotFoundError:
            return 127, "", f"Command not found: {command[0]}"
        except Exception as e:
            return 1, "", f"Error running command: {e}"

    def check_tool_availability(self, tool_name: str) -> bool:
        """Check if a tool is available."""
        config: Dict[str, Any] = TOOLS_CONFIG[tool_name]
        command_base = config["command"]

        # * For Python modules, build the full command to check availability
        if (
            isinstance(command_base, list)
            and len(command_base) >= 2
            and command_base[1] == "-m"
        ):
            # * For sys.executable -m module commands, check with --version (more reliable than --help)
            command = command_base + ["--version"]
        elif isinstance(command_base, list):
            # * For other commands (like npx), check the first command with --help
            command = command_base[:1] + ["--help"]
        else:
            command = [str(command_base), "--help"]

        exit_code, _, _ = self.run_command(command)
        return exit_code == 0

    def run_tool(self, tool_name: str, fix_mode: bool = False) -> Dict[str, Any]:
        """Run a specific linting tool."""
        config: Dict[str, Any] = TOOLS_CONFIG[tool_name]
        # * Check if tool is available
        if not self.check_tool_availability(tool_name):
            return {
                "tool": tool_name,
                "available": False,
                "error": f"Tool {tool_name} is not available",
                "exit_code": 127,
            }
        # * Build command
        command_base = config["command"]
        command: List[str] = (
            list(command_base)
            if isinstance(command_base, list)
            else [str(command_base)]
        )
        if fix_mode and config["can_fix"]:
            args_fix = config.get("args_fix", [])
            if isinstance(args_fix, list):
                command.extend(args_fix)
            elif isinstance(args_fix, str):
                command.append(args_fix)
            command.extend(self.target_paths)
        else:
            args = config.get("args", [])
            if isinstance(args, list):
                command.extend(args)
            elif isinstance(args, str):
                command.append(args)
            # * For pyright, check if we're using custom paths and it supports single files
            if tool_name == "pyright":
                if self.target_paths != TARGET_DIRS:
                    # * For single files, replace the default "." with specific paths
                    command = [cmd for cmd in command if cmd != "."]
                    command.extend(self.target_paths)
                # * Always use --outputjson for consistent parsing
                if "--outputjson" not in command:
                    command.append("--outputjson")
            else:
                command.extend(self.target_paths)
        # * Run the tool
        exit_code, stdout, stderr = self.run_command(command)
        # * Parse results
        result: Dict[str, Any] = {
            "tool": tool_name,
            "description": config["description"],
            "available": True,
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr,
            "critical": config["critical"],
            "can_fix": config["can_fix"],
            "fixed": fix_mode and config["can_fix"],
        }
        # * Parse specific tool outputs
        if tool_name == "pyright" and stdout:
            try:
                pyright_data = json.loads(stdout)
                result["summary"] = pyright_data.get("summary", {})
                result["diagnostics"] = pyright_data.get("generalDiagnostics", [])
            except json.JSONDecodeError:
                result["parse_error"] = "Failed to parse pyright JSON output"
        return result

    def format_pyright_results(self, result: Dict[str, Any]) -> None:
        """Format and display pyright results."""
        if not result.get("available"):
            self.print_status(f"Pyright: {result.get('error', 'Not available')}", "error")
            return
            
        summary = result.get("summary", {})
        diagnostics = result.get("diagnostics", [])
        
        files_analyzed = summary.get("filesAnalyzed", 0)
        error_count = summary.get("errorCount", 0)
        warning_count = summary.get("warningCount", 0)
        
        # * Handle case where no files were analyzed (likely due to config exclusions)
        if files_analyzed == 0 and self.target_paths != TARGET_DIRS:
            self.print_status("No files analyzed (may be excluded by pyrightconfig.json)", "warning")
            self.print_status("Note: Check pyrightconfig.json 'exclude' patterns if analysis expected")
            return
            
        self.print_status(f"Analyzed {files_analyzed} files")
        
        if error_count == 0 and warning_count == 0:
            self.print_status("No issues found", "success")
        else:
            self.print_status(f"Found {error_count} errors, {warning_count} warnings", "warning")
            
            # * Always show detailed issues when there are problems
            if diagnostics:
                self.print_status("Detailed issues:")
                for i, diag in enumerate(diagnostics):
                    if i >= 25:  # Show first 25 issues
                        self.print_status(f"  ... and {len(diagnostics) - 25} more issues")
                        break
                        
                    file_path = diag.get("file", "").replace("g:\\GitHub\\LittleTools\\", "")
                    line = diag.get("range", {}).get("start", {}).get("line", 0) + 1
                    column = diag.get("range", {}).get("start", {}).get("character", 0) + 1
                    message = diag.get("message", "")
                    severity = diag.get("severity", "error")
                    rule = diag.get("rule", "")
                    
                    # * Format the diagnostic line
                    location = f"{file_path}:{line}:{column}"
                    rule_info = f" ({rule})" if rule else ""
                    self.print_status(f"  {location} [{severity}]{rule_info} {message}")
                    
        # * Show any stderr errors even if parsing succeeded
        if result.get("stderr"):
            self.print_status("Additional errors:")
            error_lines = result["stderr"].strip().split('\n')
            for line in error_lines[:10]:
                if line.strip():
                    self.print_status(f"  {line}")
            if len(error_lines) > 10:
                self.print_status(f"  ... and {len(error_lines) - 10} more error lines")

    def format_generic_results(self, result: Dict[str, Any]) -> None:
        """Format and display generic tool results."""
        tool_name = result["tool"]

        if not result.get("available"):
            self.print_status(
                f"{tool_name}: {result.get('error', 'Not available')}", "error"
            )
            return

        if result["exit_code"] == 0:
            if result.get("fixed"):
                self.print_status(f"{tool_name}: Issues fixed automatically", "success")
            else:
                self.print_status(f"{tool_name}: No issues found", "success")
        else:
            self.print_status(
                f"{tool_name}: Issues found (exit code: {result['exit_code']})",
                "warning",
            )

            # * Show detailed error information
            if result["stderr"]:
                self.print_status("Error details:")
                # * Show stderr with better formatting
                error_lines = result["stderr"].strip().split("\n")
                for line in error_lines[:20]:  # Show first 20 lines
                    if line.strip():
                        self.print_status(f"  {line}")
                if len(error_lines) > 20:
                    self.print_status(
                        f"  ... and {len(error_lines) - 20} more error lines"
                    )

            if result["stdout"] and result["exit_code"] != 0:
                self.print_status("Output details:")
                # * Show stdout with better formatting
                output_lines = result["stdout"].strip().split("\n")
                for line in output_lines[:15]:  # Show first 15 lines
                    if line.strip():
                        self.print_status(f"  {line}")
                if len(output_lines) > 15:
                    self.print_status(
                        f"  ... and {len(output_lines) - 15} more output lines"
                    )

        # * Always show some output in verbose mode for debugging
        if (
            self.verbose
            and result["exit_code"] == 0
            and (result["stdout"] or result["stderr"])
        ):
            if result["stdout"]:
                self.print_status("Verbose output (stdout):")
                stdout_lines = result["stdout"][:500].split("\n")
                for line in stdout_lines[:5]:
                    if line.strip():
                        self.print_status(f"  {line}")
            if result["stderr"]:
                self.print_status("Verbose output (stderr):")
                stderr_lines = result["stderr"][:500].split("\n")
                for line in stderr_lines[:5]:
                    if line.strip():
                        self.print_status(f"  {line}")

    def _install_missing_type_stubs(self, mypy_output: str) -> bool:
        """Extract and install missing type stubs suggested by mypy."""
        if not mypy_output:
            return False
            
        # * Pattern to match mypy hints for missing type stubs
        # Example: 'Hint: "python3 -m pip install types-Send2Trash"'
        pattern = r'Hint: "python3 -m pip install (types-[^"]+)"'
        matches = re.findall(pattern, mypy_output)
        
        if not matches:
            return False
            
        # * Remove duplicates and sort
        packages_to_install = sorted(set(matches))
        
        if not self.json_output:
            self.print_status(f"Found {len(packages_to_install)} missing type stub(s)")
            self.print_status("Installing missing type stubs automatically...")
            
        success = True
        for package in packages_to_install:
            if not self.json_output:
                self.print_status(f"Installing {package}...")
                
            exit_code, stdout, stderr = self.run_command([
                sys.executable, "-m", "pip", "install", package
            ])
            
            if exit_code == 0:
                if not self.json_output:
                    self.print_status(f"✓ Successfully installed {package}", "success")
            else:
                if not self.json_output:
                    self.print_status(f"✗ Failed to install {package}", "error")
                    if stderr:
                        self.print_status(f"  Error: {stderr.strip()}")
                success = False
                
        return success

    def run_all_checks(
        self, specific_tool: Optional[str] = None, fix_mode: bool = False
    ) -> Dict[str, Any]:
        """Run all code quality checks."""
        tools_to_run = [specific_tool] if specific_tool else list(TOOLS_CONFIG.keys())

        if not self.json_output:
            self.print_separator("LittleTools Code Quality Check")
            self.print_status(f"Running checks on: {', '.join(self.target_paths)}")
            if fix_mode:
                self.print_status(
                    "Fix mode enabled - will attempt to fix issues automatically"
                )
            print()

        # * Auto-fix phase: run fixable tools first to clean up code
        if not specific_tool:  # Only auto-fix when running all tools
            fixable_tools = [
                tool
                for tool in tools_to_run
                if TOOLS_CONFIG[tool].get("can_fix", False)
            ]
            if fixable_tools and not self.json_output:
                self.print_separator("AUTO-FIX PHASE")
                self.print_status("Running automatic fixes with black and isort...")

            for tool_name in fixable_tools:
                if not self.json_output:
                    self.print_status(f"Auto-fixing with {tool_name}...")
                result = self.run_tool(tool_name, fix_mode=True)
                if result["exit_code"] == 0 and not self.json_output:
                    self.print_status(f"{tool_name}: Auto-fix completed", "success")
                elif not self.json_output:
                    self.print_status(f"{tool_name}: Auto-fix had issues", "warning")
                    
            # * Auto-install missing type stubs if MyPy is going to run
            if "mypy" in tools_to_run and not self.json_output:
                self.print_status("Checking for missing type stubs...")
                # * Run mypy once to check for missing stubs
                mypy_result = self.run_tool("mypy", fix_mode=False)
                if mypy_result["exit_code"] != 0 and mypy_result.get("stdout"):
                    installed_stubs = self._install_missing_type_stubs(mypy_result["stdout"])
                    if installed_stubs:
                        self.print_status("Type stubs installed, will re-run MyPy in analysis phase", "success")
            # * Docstring generation phase: run Agent Docstrings Generator after auto-fixes
            if not self.json_output:
                self.print_separator("AGENT DOCSTRINGS GENERATOR")
                self.print_status("Running Agent Docstrings Generator...")
            cmd = [sys.executable, "-m", "agent_docstrings.cli"] + self.target_paths
            exit_code, stdout, stderr = self.run_command(cmd)
            if not self.json_output:
                if exit_code == 0:
                    self.print_status("Agent Docstrings Generator completed successfully", "success")
                else:
                    self.print_status("Agent Docstrings Generator failed", "error")
                    if stderr:
                        self.print_status(stderr)

        # * Analysis phase: run all tools for checking
        if not self.json_output and not specific_tool:
            print()
            self.print_separator("ANALYSIS PHASE")
            self.print_status("Running code quality analysis...")
            print()

        # * Run each tool
        for tool_name in tools_to_run:
            if tool_name not in TOOLS_CONFIG:
                self.print_status(f"Unknown tool: {tool_name}", "error")
                continue

            if not self.json_output:
                self.print_separator(
                    f"{tool_name.upper()} - {TOOLS_CONFIG[tool_name]['description']}"
                )

            result = self.run_tool(tool_name, fix_mode)
            self.results[tool_name] = result

            if not self.json_output:
                if tool_name == "pyright":
                    self.format_pyright_results(result)
                else:
                    self.format_generic_results(result)
                print()

        # * Generate summary
        self.results["summary"] = self._generate_summary()

        if not self.json_output:
            self._print_summary()

        return self.results

    def _generate_summary(self) -> Dict[str, Any]:
        """Generate overall summary of results."""
        total_tools = len(
            [
                r
                for r in self.results.values()
                if isinstance(r, dict) and r.get("available")
            ]
        )
        critical_failures = 0
        total_issues = 0

        for result in self.results.values():
            if not isinstance(result, dict) or not result.get("available"):
                continue

            if result["exit_code"] != 0:
                if result.get("critical"):
                    critical_failures += 1

                # * Count issues from pyright
                if result["tool"] == "pyright":
                    summary = result.get("summary", {})
                    total_issues += summary.get("errorCount", 0) + summary.get(
                        "warningCount", 0
                    )

        return {
            "total_tools_run": total_tools,
            "critical_failures": critical_failures,
            "total_issues": total_issues,
            "overall_status": "PASS" if critical_failures == 0 else "FAIL",
            "execution_time": round(time.time() - self.start_time, 2),
        }

    def _print_summary(self) -> None:
        """Print overall summary."""
        summary = self.results["summary"]

        self.print_separator("SUMMARY")
        self.print_status(f"Tools run: {summary['total_tools_run']}")
        self.print_status(f"Critical failures: {summary['critical_failures']}")
        self.print_status(f"Total issues found: {summary['total_issues']}")
        self.print_status(f"Execution time: {summary['execution_time']}s")

        if summary["overall_status"] == "PASS":
            self.print_status("Overall status: PASS", "success")
        else:
            self.print_status("Overall status: FAIL", "error")
            self.print_status(
                "Critical issues must be resolved before merging", "warning"
            )


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run comprehensive code quality checks on LittleTools project",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--tool", choices=list(TOOLS_CONFIG.keys()), help="Run only specific tool"
    )

    parser.add_argument(
        "--path",
        nargs="+",
        help="Specific files or directories to check (default: all project modules)",
    )

    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show detailed output"
    )

    parser.add_argument(
        "--json", action="store_true", help="Output results in JSON format"
    )

    args = parser.parse_args()

    # * Validate paths if provided
    target_paths = None
    if args.path:
        target_paths = []
        for path in args.path:
            if os.path.exists(path):
                target_paths.append(path)
            else:
                print(f"Error: Path '{path}' does not exist", file=sys.stderr)
                sys.exit(1)

        if not target_paths:
            print("Error: No valid paths specified", file=sys.stderr)
            sys.exit(1)

    # * Initialize checker
    try:
        checker = CodeQualityChecker(
            verbose=args.verbose, json_output=args.json, target_paths=target_paths
        )
    except ValueError as e:
        if not args.json:
            print(f"Error: {e}", file=sys.stderr)
        else:
            print(json.dumps({"error": str(e)}, indent=2))
        sys.exit(1)

    # * Run checks
    results = checker.run_all_checks(specific_tool=args.tool, fix_mode=True)

    # * Output results
    if args.json:
        print(json.dumps(results, indent=2))

    # * Exit with appropriate code
    summary = results["summary"]
    sys.exit(0 if summary["overall_status"] == "PASS" else 1)


if __name__ == "__main__":
    main()

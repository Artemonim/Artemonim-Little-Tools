#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LittleTools Code Quality Checker

This script runs comprehensive code quality checks on the LittleTools project.
It combines multiple linting tools to provide a complete analysis of code quality,
type safety, and style compliance.

Usage:
    python check.py [--fix] [--tool TOOL] [--verbose] [--json]
    
Tools used:
    - Pyright: Static type checking and comprehensive analysis
    - Flake8: Style guide enforcement and error detection  
    - MyPy: Additional type checking
    - Black: Code formatting check
    - isort: Import sorting check

Options:
    --fix: Automatically fix issues where possible (black, isort)
    --tool: Run only specific tool (pyright, flake8, mypy, black, isort)
    --verbose: Show detailed output
    --json: Output results in JSON format for CI/CD integration
"""

import argparse
import json
import os
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

# * Configuration
TOOLS_CONFIG = {
    "pyright": {
        "command": ["npx", "--yes", "pyright"],
        "args": [".", "--outputjson"],
        "description": "Static type checking and analysis",
        "can_fix": False,
        "critical": True
    },
    "flake8": {
        "command": ["python", "-m", "flake8"],
        "args": ["--config=setup.cfg"],
        "description": "Style guide enforcement and error detection",
        "can_fix": False,
        "critical": True
    },
    "mypy": {
        "command": ["python", "-m", "mypy"],
        "args": ["--config-file=setup.cfg"],
        "description": "Advanced type checking",
        "can_fix": False,
        "critical": True
    },
    "black": {
        "command": ["python", "-m", "black"],
        "args": ["--check", "--diff", "--config=pyproject.toml"],
        "args_fix": ["--config=pyproject.toml"],
        "description": "Code formatting check",
        "can_fix": True,
        "critical": False
    },
    "isort": {
        "command": ["python", "-m", "isort"],
        "args": ["--check-only", "--diff", "--settings-path=setup.cfg"],
        "args_fix": ["--settings-path=setup.cfg"],
        "description": "Import sorting check",
        "can_fix": True,
        "critical": False
    }
}

# * Target directories for analysis
TARGET_DIRS = [
    "littletools_cli",
    "littletools_core", 
    "littletools_speech",
    "littletools_txt",
    "littletools_video"
]


class CodeQualityChecker:
    """Main class for running code quality checks."""
    
    def __init__(self, verbose: bool = False, json_output: bool = False):
        self.verbose = verbose
        self.json_output = json_output
        self.results: Dict[str, Any] = {}
        self.start_time = time.time()
        
    def print_status(self, message: str, level: str = "info") -> None:
        """Print status message with appropriate formatting."""
        if self.json_output:
            return
            
        prefixes = {
            "info": "* ",
            "success": "✓ ",
            "warning": "! ",
            "error": "✗ ",
            "header": "═ "
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
    
    def run_command(self, command: List[str], cwd: Optional[str] = None) -> Tuple[int, str, str]:
        """Run a shell command and return exit code, stdout, stderr."""
        try:
            if self.verbose:
                self.print_status(f"Running: {' '.join(command)}")
                
            # * Use shell=True on Windows for npm/npx commands
            use_shell = os.name == 'nt' and command[0] in ['npx', 'npm']
            
            result = subprocess.run(
                command,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
                shell=use_shell
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
        config = TOOLS_CONFIG[tool_name]
        command = config["command"][:1] + ["--help"]  # Just check the main command
        
        exit_code, _, _ = self.run_command(command)
        return exit_code == 0
    
    def run_tool(self, tool_name: str, fix_mode: bool = False) -> Dict[str, Any]:
        """Run a specific linting tool."""
        config = TOOLS_CONFIG[tool_name]
        
        # * Check if tool is available
        if not self.check_tool_availability(tool_name):
            return {
                "tool": tool_name,
                "available": False,
                "error": f"Tool {tool_name} is not available",
                "exit_code": 127
            }
        
        # * Build command
        command: List[str] = config["command"].copy()
        
        if fix_mode and config["can_fix"]:
            command.extend(config.get("args_fix", []))
            command.extend(TARGET_DIRS)
        else:
            command.extend(config.get("args", []))
            if tool_name not in ["pyright"]:  # pyright analyzes the whole project
                command.extend(TARGET_DIRS)
        
        # * Run the tool
        exit_code, stdout, stderr = self.run_command(command)
        
        # * Parse results
        result = {
            "tool": tool_name,
            "description": config["description"],
            "available": True,
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr,
            "critical": config["critical"],
            "can_fix": config["can_fix"],
            "fixed": fix_mode and config["can_fix"]
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
        
        self.print_status(f"Analyzed {files_analyzed} files")
        
        if error_count == 0 and warning_count == 0:
            self.print_status("No issues found", "success")
        else:
            self.print_status(f"Found {error_count} errors, {warning_count} warnings", "warning")
            
        if self.verbose and diagnostics:
            self.print_status("\nDetailed issues:")
            for diag in diagnostics[:10]:  # Show first 10 issues
                file_path = diag.get("file", "").replace("g:\\GitHub\\LittleTools\\", "")
                line = diag.get("range", {}).get("start", {}).get("line", 0) + 1
                message = diag.get("message", "")
                severity = diag.get("severity", "error")
                
                self.print_status(f"  {file_path}:{line} [{severity}] {message}")
                
            if len(diagnostics) > 10:
                self.print_status(f"  ... and {len(diagnostics) - 10} more issues")
    
    def format_generic_results(self, result: Dict[str, Any]) -> None:
        """Format and display generic tool results."""
        tool_name = result["tool"]
        
        if not result.get("available"):
            self.print_status(f"{tool_name}: {result.get('error', 'Not available')}", "error")
            return
            
        if result["exit_code"] == 0:
            if result.get("fixed"):
                self.print_status(f"{tool_name}: Issues fixed automatically", "success")
            else:
                self.print_status(f"{tool_name}: No issues found", "success")
        else:
            self.print_status(f"{tool_name}: Issues found (exit code: {result['exit_code']})", "warning")
            
        if self.verbose and (result["stdout"] or result["stderr"]):
            if result["stdout"]:
                print("STDOUT:")
                print(result["stdout"][:1000])  # Limit output
            if result["stderr"]:
                print("STDERR:")
                print(result["stderr"][:1000])  # Limit output
    
    def run_all_checks(self, specific_tool: Optional[str] = None, fix_mode: bool = False) -> Dict[str, Any]:
        """Run all code quality checks."""
        tools_to_run = [specific_tool] if specific_tool else list(TOOLS_CONFIG.keys())
        
        if not self.json_output:
            self.print_separator("LittleTools Code Quality Check")
            self.print_status(f"Running checks on: {', '.join(TARGET_DIRS)}")
            if fix_mode:
                self.print_status("Fix mode enabled - will attempt to fix issues automatically")
            print()
        
        # * Run each tool
        for tool_name in tools_to_run:
            if tool_name not in TOOLS_CONFIG:
                self.print_status(f"Unknown tool: {tool_name}", "error")
                continue
                
            if not self.json_output:
                self.print_separator(f"{tool_name.upper()} - {TOOLS_CONFIG[tool_name]['description']}")
            
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
        total_tools = len([r for r in self.results.values() if isinstance(r, dict) and r.get("available")])
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
                    total_issues += summary.get("errorCount", 0) + summary.get("warningCount", 0)
        
        return {
            "total_tools_run": total_tools,
            "critical_failures": critical_failures,
            "total_issues": total_issues,
            "overall_status": "PASS" if critical_failures == 0 else "FAIL",
            "execution_time": round(time.time() - self.start_time, 2)
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
            self.print_status("Critical issues must be resolved before merging", "warning")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run comprehensive code quality checks on LittleTools project",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Automatically fix issues where possible (black, isort)"
    )
    
    parser.add_argument(
        "--tool",
        choices=list(TOOLS_CONFIG.keys()),
        help="Run only specific tool"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed output"
    )
    
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results in JSON format"
    )
    
    args = parser.parse_args()
    
    # * Initialize checker
    checker = CodeQualityChecker(verbose=args.verbose, json_output=args.json)
    
    # * Run checks
    results = checker.run_all_checks(specific_tool=args.tool, fix_mode=args.fix)
    
    # * Output results
    if args.json:
        print(json.dumps(results, indent=2))
    
    # * Exit with appropriate code
    summary = results["summary"]
    sys.exit(0 if summary["overall_status"] == "PASS" else 1)


if __name__ == "__main__":
    main() 
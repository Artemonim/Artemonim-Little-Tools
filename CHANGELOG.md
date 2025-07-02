# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2025-06-30

### Added

-   **Modular Architecture**: Restructured the entire project into a monorepo with individually versioned packages (`littletools-core`, `littletools-cli`, `littletools-dev`, `littletools-speech`, `littletools-txt`, `littletools-video`). This enhances modularity and simplifies dependency management. (#XXX)
-   **Developer Toolkit**: Introduced a new `littletools-dev` package containing essential tools for development, including a `version-bumper` script to automate version updates across all packages. (#XXX)
-   **Central Project Version**: A global project version is now defined in the root `pyproject.toml` under `[tool.littletools]` for centralized tracking. (#XXX)
-   **CLI Script Entrypoint**: The `version-bumper` tool is now accessible as a console script, configured in `littletools-dev/pyproject.toml`. (#XXX)

### Changed

-   **Major Version Bump**: All packages have been bumped to version `1.0.0`. (#XXX)
-   **Dependency Strategy**: Replaced the local, path-based `AgentDocstringsGenerator` with the published `agent-docstrings` package from PyPI, streamlining dependency handling. (#XXX)
-   **Build Scripts**: The `start.ps1` and `start.sh` environment setup scripts now use `pip-tools compile --upgrade` to ensure dependencies are always resolved to their latest compatible versions. (#XXX)
-   **Quality Check Integration**: Updated `check.py` to call `agent-docstrings` as an installed package command rather than a direct module execution. (#XXX)

### Removed

-   **Local Dependency Workaround**: Eliminated the custom logic in `start.ps1` that previously handled the installation of the local `AgentDocstringsGenerator`. (#XXX)

### CI/CD

-   **Issue Auto-Cleanup**: Implemented a GitHub Actions workflow to automatically remove empty sections from newly created bug reports, feature requests, and questions, ensuring cleaner and more concise issue tracking. (#XXX)

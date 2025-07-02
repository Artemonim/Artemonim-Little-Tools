# Contributing to LittleTools

We welcome contributions from the community! Whether you're fixing a bug, adding a new feature, or improving documentation, your help is appreciated. Please take a moment to review this document to understand how you can contribute.

## Getting Started

1.  **Fork the repository** on GitHub.
2.  **Clone your fork** to your local machine.
3.  **Follow the setup instructions** in the `README.md` to create your development environment.
4.  **Create a new branch** for your changes: `git checkout -b your-feature-name`.
5.  **Make your changes**, and ensure you follow the project's coding style and conventions.
6.  **Test your changes** thoroughly.
7.  **Commit your changes** with a clear and descriptive commit message.
8.  **Push your branch** to your fork on GitHub.
9.  **Create a pull request** from your fork to the main `LittleTools` repository.

## Versioning Policy

This project uses a hybrid versioning model where each package has its own version, and the entire project has a global version. The global version is determined by the changes in the individual packages according to the following rules:

1.  **Highest-Level Change Propagation**: When one or more packages are updated, the global project version is incremented based on the highest level of change across all updated packages.

    -   If at least one package has a **MAJOR** version bump (e.g., `1.x.x` -> `2.0.0`), the global version must also have a **MAJOR** bump.
    -   If there are no major bumps but at least one package has a **MINOR** version bump (e.g., `1.1.x` -> `1.2.0`), the global version must also have a **MINOR** bump.
    -   If all updated packages only have **PATCH** version bumps (e.g., `1.1.1` -> `1.1.2`), the global version will receive a **PATCH** bump.

2.  **Breaking Changes**: A major version increment for the global project is mandatory for any of the following breaking changes:
    -   The removal of one or more tools.
    -   A significant, backward-incompatible reorganization of the existing toolset.

## Code Style

Please adhere to the coding style guidelines enforced by the linters and formatters configured in the project (`black`, `isort`, `flake8`, `mypy`). You **must** run the quality checks using the `check.py` script before submitting your changes.

## Submitting a Pull Request

-   Provide a clear title and a detailed description of your changes.
-   If your PR addresses an existing issue, link it in the description (e.g., "Fixes #123").
-   **Update the Changelog**: Every pull request must include a brief entry in the `[Unreleased]` section of the `CHANGELOG.md` file. This entry should describe the change from a user's perspective and conclude with references to the pull request number and any associated issue numbers.
    -   **Example**: `- Fixed a critical bug in the video converter. (#123, fixes #456)`
-   **Do Not Bump Versions**: Version bumping must only be performed by project maintainers when merging the `dev` branch into `master`. Pull requests targeting the `dev` branch should not contain any version updates.
-   Ensure your code passes all automated checks.
-   Be prepared to discuss your changes and make adjustments if requested by the maintainers.

Thank you for contributing to LittleTools!

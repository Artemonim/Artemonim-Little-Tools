## GitHub Issue Synchronization Script for Cursor IDE

`ghsync.py` allows your Agent to interact with GitHub issues in your repository.

It enables reading all labels and issues, editing existing issues, and creating new ones. The script supports changing issue status but cannot delete issues.

For bulk changes, it is recommended to create a `temp.txt` file with a list of commands using a premium model and then execute it with a free model. Gemini 2.5 Flash handles it. Cursor Small and GPT-4o-mini have not been tested.

### Requirements

1.  **Python 3**: Ensure Python 3 is installed on your system.
    -   If your project does not use Python, create a local Python environment. In Crusor or VSCode just open the terminal and run `python -m venv env_py` in root, after which the IDE itself will offer to activate and use the environment.
2.  **GitHub CLI (gh)**: The [GitHub CLI](https://cli.github.com/) must be installed and authenticated (`gh auth login`).

### Setup

Add the `.cursor` folder to your repository and read the previous section.

## Usage

Use the script via the command line, typically within the context of a Cursor rule like `git-interactions.mdc`.

Example prompt for the model: `In accordance with @git-interactions.mdc perform {action}`.

Key commands supported via `ghsync.py`:

-   `-d, --download`: Fetch all labels and issues.
-   `-u, --upload`: Create a new issue.
    -   Requires: `--title <t>`
    -   Optional: `--body <b>` or `--body-from-file <filename>` (from `.cursor/Gitdata/temp_bodies`) , `--labels <l1> <l2> ...`
-   `-e, --edit <IssueNumber>`: Edit an existing issue.
    -   Optional: `-NewTitle <t>`, `-NewBody <b>` or `-NewBodyFromFile <filename>` (from `.cursor/Gitdata/temp_bodies`) , `-NewLabels <l1> <l1> ...`, `-NewState <open|closed|not_planned>`.

When using `--body-from-file` or `-NewBodyFromFile`, place the file containing the issue body in the `.cursor/Gitdata/temp_bodies` directory. The script will read the file and automatically delete it afterwards.

## Notes

-   The script and associated rule attempt to mitigate [current Cursor issues with Agent terminal output capture](https://forum.cursor.com/t/intermittent-incomplete-terminal-output-capture-issue-with-powershell-scripts/93297). **Pay close attention to execution by checking the status file (`gitsync_last_run.json`) as the Agent might occasionally fail to do so.**
-   I tried to create agent tools via the MCP server, but neither Gemini nor Claude were able to properly connect MCP to Cursor, so I gave up.
-   If you want the Agent’s actions to be shown separately from yours, create a new GitHub account for it and provide a PAT from there. Apparently, it’s also possible to use a GitHub App, but I’m too lazy for that, considering I work alone in a private repository.

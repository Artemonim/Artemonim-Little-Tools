#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LittleTools CLI - Interactive Menu

This script provides an interactive menu to run tools in the LittleTools project.
It discovers and loads all 'tool' plugins that are installed in the environment.
"""

import importlib.metadata
import time
from typing import Dict
from typing import Optional

import typer
from rich.console import Console

# * Configuration
COMMANDS_GROUP = "littletools.commands"
console = Console()


def get_command_plugins() -> Dict[str, typer.Typer]:
    """
    Discovers and loads all command plugins (Typer apps) from entry points.

    Returns:
        A dictionary mapping the command name to its loaded Typer application.
    """
    plugins = {}
    failed_plugins = []  # Track failed plugins for debugging
    try:
        # In Python 3.10+, importlib.metadata.entry_points() returns a different
        # object, and the .get() method is replaced by .select().
        eps = importlib.metadata.entry_points()
        if hasattr(eps, "select"):
            entry_points = eps.select(group=COMMANDS_GROUP)
        else:
            # Fallback for Python < 3.10
            entry_points = eps.get(
                COMMANDS_GROUP, []  # type: ignore
            )  # Fallback for older importlib.metadata

        for entry_point in entry_points:
            try:
                plugin_app = entry_point.load()
                if isinstance(plugin_app, typer.Typer):
                    plugins[entry_point.name] = plugin_app
                else:
                    failed_plugins.append(f"'{entry_point.name}': Not a Typer app")
            except Exception as e:
                failed_plugins.append(
                    f"'{entry_point.name}': {type(e).__name__}: {str(e)}"
                )

        # * Show failed plugins info if in debug mode or if plugins missing
        if failed_plugins:
            console.print(
                f"[yellow]! Debug: Failed to load {len(failed_plugins)} plugin(s):[/yellow]"
            )
            for failure in failed_plugins:
                console.print(f"  - {failure}")
            console.print("  Press any key to continue...")
            try:
                import msvcrt

                msvcrt.getch()  # Windows
            except ImportError:
                input()  # Unix/Linux

    except Exception as e:
        console.print(f"[red]! Error discovering plugins: {e}[/red]")
    return plugins


def post_execution_dialog() -> str:
    """
    Displays a menu after a command has run to decide the next action.
    Returns:
        The user's choice: 'tool_menu', 'main_menu', or 'exit'.
    """
    console.print("\n---")
    console.print("[bold]What would you like to do next?[/bold]")
    console.print("  [green]1[/green]. Return to the current tool's menu")
    console.print("  [green]2[/green]. Return to the main menu")
    console.print("  [green]0[/green]. Exit LittleTools")

    while True:
        try:
            choice = typer.prompt("Your choice", default="1")
            if choice == "1":
                return "tool_menu"
            elif choice == "2":
                return "main_menu"
            elif choice == "0":
                return "exit"
            else:
                console.print(
                    f"[red]! Invalid choice '{choice}'. Please try again.[/red]"
                )
        except (typer.Abort, KeyboardInterrupt, EOFError):
            return "exit"


def show_tool_menu(  # noqa: C901
    tool_name: str, tool_app: typer.Typer
) -> Optional[str]:
    """Displays the menu for a specific tool group."""
    # Convert the Typer app to a Click Command/Group to reliably access its commands
    click_cmd = typer.main.get_command(tool_app)

    # Determine if this is a multi-command group or a single command.
    # * In Typer ≥0.9 root apps with only one subcommand may be returned as
    #   TyperCommand (click.Command) without the ``commands`` attribute.
    is_group = hasattr(click_cmd, "commands") and bool(
        getattr(click_cmd, "commands", {})
    )

    should_continue = True
    while should_continue:
        console.clear()
        console.print(
            f"\n[bold underline]Tool: {tool_app.info.name or tool_name}[/bold underline]"
        )
        if tool_app.info.help:
            console.print(f"  [dim]{tool_app.info.help}[/dim]")

        console.print("\n[bold]Available Commands:[/bold]")

        # Build the list of available commands depending on whether we have a group.
        if is_group:
            commands = list(click_cmd.commands.values())  # type: ignore[attr-defined]
        else:
            # Treat the whole Typer app as a single command.
            commands = [click_cmd]

        for i, command in enumerate(commands, 1):
            help_text = (
                getattr(command, "help", None)
                or tool_app.info.help
                or "No description."
            )
            cmd_name = getattr(command, "name", tool_name)
            console.print(
                f"  [green]{i:2d}[/green]. [bold]{cmd_name}[/bold] - {help_text}"
            )

        console.print("\n  [bold]0[/bold]. Back to Main Menu")

        try:
            choice = input("\nEnter your choice: ").strip()
            if choice == "0":
                break

            choice_idx = int(choice)
            if 1 <= choice_idx <= len(commands):
                selected_command = commands[choice_idx - 1]

                # --- EXECUTION LOGIC ---
                console.clear()
                launch_cmd_name = getattr(selected_command, "name", tool_name)
                console.print(
                    f"\n> Launching command: [bold cyan]{tool_name} {launch_cmd_name}[/bold cyan]"
                )
                console.print("-" * 40)
                try:
                    # Invoke the selected command. For single-command apps invoke without subcommand name.
                    if is_group:
                        tool_app([selected_command.name])
                    else:
                        tool_app([])  # Runs the root Typer command directly
                except SystemExit as e:
                    # A non-zero exit code usually indicates an error or user cancellation.
                    if e.code is not None and e.code != 0:
                        console.print(
                            f"[yellow]! Command exited with code {e.code}.[/yellow]"
                        )
                except Exception as e:
                    console.print(
                        f"[bold red]! An unexpected error occurred while running command '{launch_cmd_name}':[/bold red]"
                    )
                    console.print(e)

                console.print("-" * 40)

                next_action = post_execution_dialog()
                if next_action == "exit":
                    # Propagate the exit signal up
                    return "exit"
                elif next_action == "main_menu":
                    should_continue = False  # Will exit the loop and return to main()
                # if 'tool_menu', just continue the loop
            else:
                console.print(
                    f"[red]! Invalid choice '{choice}'. Please try again.[/red]"
                )
                time.sleep(1.5)

        except ValueError:
            console.print("[red]! Invalid input. Please enter a number.[/red]")
            time.sleep(1.5)
        except (KeyboardInterrupt, EOFError):
            break
    # Implicitly return 'main_menu' when the loop is broken
    return "main_menu"


def main() -> None:
    """Main function to run the interactive menu."""
    command_plugins = get_command_plugins()

    if not command_plugins:
        console.print("[yellow]! Warning: No LittleTools plugins found.[/yellow]")
        console.print(
            "  This usually means you haven't installed any tool packages yet."
        )
        console.print("  Run the 'start.ps1' script to install all tools,")
        console.print(
            "  or install one manually (e.g., 'pip install ./littletools-video')."
        )
        return

    while True:
        console.clear()
        console.print("\n[bold cyan]=== LittleTools Interactive Menu ===[/bold cyan]")
        console.print("Select a tool group to see its commands:")

        tool_names = list(command_plugins.keys())
        for i, name in enumerate(tool_names, 1):
            help_text = command_plugins[name].info.help or "No description available."
            console.print(
                f"  [green]{i:2d}[/green]. [bold]{name.capitalize()}[/bold] - {help_text}"
            )

        console.print("\n  [bold]0[/bold]. Exit")

        try:
            choice = input("\nEnter your choice: ").strip()
            if choice == "0":
                console.print("Goodbye!")
                break

            choice_idx = int(choice)
            if 1 <= choice_idx <= len(tool_names):
                selected_name = tool_names[choice_idx - 1]
                selected_app = command_plugins[selected_name]
                # The tool menu can now signal that we need to exit the program
                if show_tool_menu(selected_name, selected_app) == "exit":
                    break
            else:
                console.print(
                    f"[red]! Invalid choice '{choice}'. Please try again.[/red]"
                )
                time.sleep(1.5)

        except ValueError:
            console.print("[red]! Invalid input. Please enter a number.[/red]")
            time.sleep(1.5)
        except (KeyboardInterrupt, EOFError):
            console.print("\nGoodbye!")
            break


if __name__ == "__main__":
    main()

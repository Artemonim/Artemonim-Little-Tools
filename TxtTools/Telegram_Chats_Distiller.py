#!/usr/bin/env python3
"""Telegram Chats Distiller

This script processes Telegram chat export JSON files by extracting and transforming messages.
It extracts text from the "text_entities" field in each message and writes a new JSON file with the transformed data.
The script gracefully handles keyboard interrupt signals (Ctrl+C).

Usage:
    python3 Telegram_Chats_Distiller.py --input <input_file> [--output <output_file>]

Args:
    -i, --input  : Path to the input Telegram chat export JSON file (required).
    -o, --output : Path to save the processed JSON file (optional).
"""
import argparse
import json
import os
import sys
from pathlib import Path

# * Import common utilities
sys.path.append(str(Path(__file__).parent.parent))
from littletools_core.utils import setup_signal_handler, print_status

# * Signal handling is now managed by little_tools_utils

def process_telegram_chat_export(input_file, output_file):
    """
    Process Telegram chat export JSON file by extracting and transforming messages.

    Args:
        input_file (str): Path to the input JSON file.
        output_file (str): Path to save the processed JSON file.

    Returns:
        bool: True if processing was successful, False otherwise.
    """
    try:
        if not os.path.exists(input_file):
            print_status(f"Input file not found: {input_file}", "error")
            return False

        with open(input_file, "r", encoding="utf-8") as file:
            data = json.load(file)

        messages = data.get("messages", [])
        if not isinstance(messages, list):
            print_status("Invalid file format. 'messages' key must contain a list.", "error")
            return False

        new_messages = []
        for message in messages:
            text_entities = message.get("text_entities", [])
            if not text_entities:
                continue

            combined_text = ""
            for entity in text_entities:
                if isinstance(entity, dict):
                    combined_text += entity.get("text", "")
                elif isinstance(entity, str):
                    combined_text += entity

            new_message = {
                "id": message.get("id"),
                "date": message.get("date"),
                "photo": message.get("photo"),
                "text_entities": combined_text
            }
            new_messages.append(new_message)

        data["messages"] = new_messages

        with open(output_file, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=4)
        
        print_status(f"Successfully processed file. Result saved to {output_file}", "success")
        return True

    except json.JSONDecodeError:
        print_status(f"Invalid JSON format in {input_file}", "error")
        return False
    except PermissionError:
        print_status(f"Permission denied when writing to {output_file}", "error")
        return False
    except Exception as e:
        print_status(f"Unexpected error occurred: {e}", "error")
        return False

def main():
    """
    Main entry point for the Telegram Chat Distillator CLI tool.
    
    Parses command-line arguments and processes Telegram chat export files.
    """
    setup_signal_handler()

    parser = argparse.ArgumentParser(
        description="Process Telegram chat export JSON files by extracting and transforming messages."
    )
    parser.add_argument(
        "-i", "--input", 
        required=True, 
        help="Path to the input Telegram chat export JSON file"
    )
    parser.add_argument(
        "-o", "--output", 
        default=None, 
        help="Path to save the processed JSON file (optional)"
    )

    args = parser.parse_args()

    input_file = os.path.abspath(args.input)
    
    if args.output:
        output_file = os.path.abspath(args.output)
    else:
        base, ext = os.path.splitext(input_file)
        output_file = f"{base}_distilled{ext}"

    success = process_telegram_chat_export(input_file, output_file)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()

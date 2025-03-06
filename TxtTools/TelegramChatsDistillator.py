#!/usr/bin/env python3
import argparse
import json
import os
import sys
import signal

def signal_handler(sig, frame):
    """
    Handle keyboard interrupt (Ctrl+C) gracefully.

    Args:
        sig (int): Signal number.
        frame (frame): Current stack frame.
    """
    print("\nOperation cancelled by user.")
    sys.exit(0)

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
            print(f"Error: Input file not found: {input_file}")
            return False

        with open(input_file, "r", encoding="utf-8") as file:
            data = json.load(file)

        messages = data.get("messages", [])
        if not isinstance(messages, list):
            print("Error: Invalid file format. 'messages' key must contain a list.")
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
        
        print(f"Successfully processed file. Result saved to {output_file}")
        return True

    except json.JSONDecodeError:
        print(f"Error: Invalid JSON format in {input_file}")
        return False
    except PermissionError:
        print(f"Error: Permission denied when writing to {output_file}")
        return False
    except Exception as e:
        print(f"Unexpected error occurred: {e}")
        return False

def main():
    """
    Main entry point for the Telegram Chat Distillator CLI tool.
    
    Parses command-line arguments and processes Telegram chat export files.
    """
    signal.signal(signal.SIGINT, signal_handler)

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

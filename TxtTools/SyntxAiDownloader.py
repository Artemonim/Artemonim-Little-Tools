#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Syntx.ai Downloader

This script downloads content from Syntx.ai llmshare or llmchat links and
saves it as a Markdown file.

It fetches the HTML from the provided URL, parses it to find all elements
with the class 'markdown-content', and concatenates their contents into
a single output file.
"""

import re
import sys
from pathlib import Path
import requests
from bs4 import BeautifulSoup

# * Add project root to path to allow importing little_tools_utils
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from little_tools_utils import (
    setup_signal_handler,
    ensure_dir_exists,
    print_status,
    print_separator,
    is_interrupted
)

# * Constants
BASE_OUTPUT_DIR = project_root / "0-OUTPUT-0"
URL_PATTERN = re.compile(r"https?://(llmshare\.syntxai\.net|llmchat\.syntxai\.net)/([a-f0-9-]+)", re.IGNORECASE)

def get_url_from_user() -> str:
    """Prompts the user to enter a valid URL."""
    while not is_interrupted():
        url = input("? Enter the Syntx.ai URL (llmshare or llmchat): ").strip()
        if URL_PATTERN.match(url):
            return url
        print_status("Invalid URL format. Please use a valid syntxai.net link.", "error")
    sys.exit(0)

def get_output_filename(url_id: str) -> str:
    """Prompts the user for an output filename, suggesting a default."""
    default_name = f"syntxai_{url_id}.md"
    filename = input(f"? Enter the output filename (or press Enter for default: {default_name}): ").strip() + ".md"
    return filename or default_name

def fetch_and_parse_content(url: str) -> str:
    """Fetches HTML from the URL and parses out the markdown content."""
    print_status(f"Fetching content from {url}...")
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        print_status(f"Failed to fetch URL: {e}", "error")
        sys.exit(1)

    print_status("Parsing HTML content...")
    soup = BeautifulSoup(response.text, 'html.parser')
    content_divs = soup.find_all('div', class_='markdown-content')

    if not content_divs:
        print_status("No 'markdown-content' divs found on the page.", "warning")
        return ""

    all_markdown = "\n\n---\n\n".join(div.get_text(separator='\n', strip=True) for div in content_divs)
    return all_markdown

def save_content_to_file(content: str, filename: str) -> None:
    """Saves the extracted content to a file."""
    output_dir = BASE_OUTPUT_DIR / "SyntxAi_Downloads"
    ensure_dir_exists(output_dir)
    output_path = output_dir / filename

    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print_status(f"Content successfully saved to:", "success")
        print(str(output_path))
    except IOError as e:
        print_status(f"Error writing to file: {e}", "error")
        sys.exit(1)

def main():
    """Main function to run the downloader."""
    setup_signal_handler()
    print_separator("═", 60)
    print(" Syntx.ai Content Downloader ".center(60, " "))
    print_separator("═", 60)

    url = get_url_from_user()
    
    match = URL_PATTERN.match(url)
    if not match:
        # This should not happen due to validation in get_url_from_user
        print_status("Could not extract ID from URL.", "error")
        sys.exit(1)
    
    url_id = match.group(2)

    filename = get_output_filename(url_id)
    
    markdown_content = fetch_and_parse_content(url)

    if markdown_content and not is_interrupted():
        save_content_to_file(markdown_content, filename)
    
    print_separator("═", 60)
    print_status("Operation finished.", "success")

if __name__ == "__main__":
    main() 
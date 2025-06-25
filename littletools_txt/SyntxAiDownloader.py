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

from littletools_core.utils import (
    ensure_dir_exists,
    is_interrupted,
    print_separator,
    print_status,
    setup_signal_handler,
)

# * Constants
BASE_OUTPUT_DIR = Path.cwd()  # Output to current working directory
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
    user_input = input(f"? Enter the output filename (or press Enter for default: {default_name}): ").strip()
    if not user_input:
        return default_name
    filename = user_input if user_input.lower().endswith(".md") else f"{user_input}.md"
    return filename

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

    all_markdown_parts = []
    
    for div in content_divs:
        markdown_text = convert_html_to_markdown(div)
        if markdown_text.strip():
            all_markdown_parts.append(markdown_text.strip())
    
    return "\n\n---\n\n".join(all_markdown_parts)

def convert_html_to_markdown(html_element) -> str:
    """Convert HTML element to properly formatted Markdown."""
    # * Replace common HTML elements with Markdown equivalents
    html_str = str(html_element)
    
    # * Process the HTML with BeautifulSoup for better structure handling
    soup = BeautifulSoup(html_str, 'html.parser')
    
    # * Convert line breaks FIRST so that paragraphs retain them
    for br in soup.find_all('br'):
        br.replace_with('\n')

    # * Convert headers
    for i in range(1, 7):
        for header in soup.find_all(f'h{i}'):
            header_text = header.get_text(strip=True)
            if header_text:
                header.replace_with(f"\n\n{'#' * i} {header_text}\n\n")

    # * Convert paragraphs (after <br> replacement to keep line breaks)
    for p in soup.find_all('p'):
        text = p.get_text(separator='\n', strip=True)
        if text:
            p.replace_with(f"\n\n{text}\n\n")
    
    # * Convert lists
    for ul in soup.find_all('ul'):
        list_items = []
        for li in ul.find_all('li', recursive=False):
            item_text = li.get_text(strip=True)
            if item_text:
                list_items.append(f"- {item_text}")
        if list_items:
            ul.replace_with('\n\n' + '\n'.join(list_items) + '\n\n')
    
    for ol in soup.find_all('ol'):
        list_items = []
        for i, li in enumerate(ol.find_all('li', recursive=False), 1):
            item_text = li.get_text(strip=True)
            if item_text:
                list_items.append(f"{i}. {item_text}")
        if list_items:
            ol.replace_with('\n\n' + '\n'.join(list_items) + '\n\n')
    
    # * Convert bold text
    for strong in soup.find_all(['strong', 'b']):
        text = strong.get_text(strip=True)
        if text:
            strong.replace_with(f"**{text}**")
    
    # * Convert italic text
    for em in soup.find_all(['em', 'i']):
        text = em.get_text(strip=True)
        if text:
            em.replace_with(f"*{text}*")
    
    # * Convert inline code
    for code in soup.find_all('code'):
        text = code.get_text(strip=True)
        if text:
            code.replace_with(f"`{text}`")
    
    # * Convert code blocks
    for pre in soup.find_all('pre'):
        code_text = pre.get_text(strip=False)
        if code_text:
            pre.replace_with(f"\n\n```\n{code_text}\n```\n\n")
    
    # * Convert blockquotes
    for blockquote in soup.find_all('blockquote'):
        quote_text = blockquote.get_text(separator='\n', strip=True)
        if quote_text:
            quoted_lines = []
            for line in quote_text.split('\n'):
                line = line.strip()
                if line:
                    quoted_lines.append(f"> {line}")
            if quoted_lines:
                blockquote.replace_with('\n\n' + '\n'.join(quoted_lines) + '\n\n')
    
    # * Convert links
    for link in soup.find_all('a'):
        href = link.get('href', '')
        text = link.get_text(strip=True)
        if text and href:
            link.replace_with(f"[{text}]({href})")
        elif text:
            link.replace_with(text)
    
    # * Get the final text
    result = soup.get_text(separator='', strip=False)
    
    # * Clean up excessive whitespace
    lines = result.split('\n')
    cleaned_lines = []
    prev_empty = False
    
    for line in lines:
        line = line.rstrip()
        is_empty = not line.strip()
        
        if is_empty:
            if not prev_empty:
                cleaned_lines.append('')
            prev_empty = True
        else:
            cleaned_lines.append(line)
            prev_empty = False
    
    # * Join lines and remove leading/trailing whitespace
    result = '\n'.join(cleaned_lines).strip()
    
    # * Ensure proper spacing around headers and lists
    result = result.replace('\n\n\n', '\n\n')
    
    return result

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

# (Removed standalone execution block reliant on __main__) 
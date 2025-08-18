#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Unit tests for SyntxAiDownloader module.

Tests URL validation, parsing logic for different link types, and error handling.
"""

import re
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
import pytest
from bs4 import BeautifulSoup
from click.exceptions import Exit

from littletools_txt.SyntxAiDownloader import (
    download_syntx_content,
    run,
    app,
)


class TestSyntxAiDownloader:
    """Test cases for SyntxAiDownloader functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.valid_share_url = "https://LLMshare.syntxai.net/8b9ae176-d674-b19c-a3c63557"
        self.valid_chat_url = "https://LLMchat.syntxai.net/115ecd6c-18ae-78ee-8d214995"
        self.valid_old_url = "https://syntx.ai/s/abc123"
        self.invalid_url = "https://example.com/invalid"

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_url_validation_patterns(self):
        """Test URL validation regex patterns."""
        # Valid patterns
        valid_urls = [
            "https://syntx.ai/s/abc123",
            "https://LLMshare.syntxai.net/8b9ae176-d674-b19c-a3c63557",
            "https://LLMchat.syntxai.net/115ecd6c-18ae-78ee-8d214995",
            "https://SYNTX.AI/S/ABC123",  # Case insensitive
            "https://llmshare.syntxai.net/test123",
            "https://llmchat.syntxai.net/test456",
        ]
        
        # Invalid patterns
        invalid_urls = [
            "https://example.com/invalid",
            "http://syntx.ai/s/abc123",  # Wrong protocol
            "https://syntx.ai/abc123",   # Missing /s/
            "https://LLMshare.syntxai.net",  # Missing ID
            "https://LLMchat.syntxai.net/",  # Missing ID
            "ftp://syntx.ai/s/abc123",   # Wrong protocol
        ]

        pattern = r"^https://(?:syntx\.ai/s/|LLM(?:share|chat)\.syntxai\.net/)\S+$"
        
        for url in valid_urls:
            assert re.match(pattern, url, re.IGNORECASE), f"URL should be valid: {url}"
        
        for url in invalid_urls:
            assert not re.match(pattern, url, re.IGNORECASE), f"URL should be invalid: {url}"

    def test_url_stripping(self):
        """Test URL stripping of whitespace and angle brackets."""
        test_cases = [
            ("<https://syntx.ai/s/abc123>", "https://syntx.ai/s/abc123"),
            ("  https://LLMshare.syntxai.net/test  ", "https://LLMshare.syntxai.net/test"),
            ("<https://LLMchat.syntxai.net/test>", "https://LLMchat.syntxai.net/test"),
            ("https://syntx.ai/s/abc123", "https://syntx.ai/s/abc123"),  # No change
        ]
        
        for input_url, expected in test_cases:
            stripped = input_url.strip().strip("<>")
            assert stripped == expected, f"Expected '{expected}', got '{stripped}'"

    @patch('littletools_txt.SyntxAiDownloader.requests.get')
    def test_download_syntx_content_share_format(self, mock_get):
        """Test downloading content from LLMshare format."""
        # Mock HTML response for share format
        mock_html = """
        <!DOCTYPE html>
        <html>
        <head><title>GPTAnswers</title></head>
        <body>
            <div class="markdown-content">
                <p>Test content from share</p>
            </div>
            <div class="footer">
                <div><b>Модель:</b> GPT-4.1 Nano</div>
                <div><b>Время:</b> 22.07.2025 00:19:00 GMT+3</div>
            </div>
        </body>
        </html>
        """
        
        mock_response = Mock()
        mock_response.text = mock_html
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        with patch('littletools_txt.SyntxAiDownloader.console.print') as mock_print:
            download_syntx_content(self.valid_share_url, self.temp_dir)
            
            # Verify success message was printed with correct filename
            mock_print.assert_called()
            call_args = mock_print.call_args[0][0]
            assert "SyntxAI Share.txt" in call_args
            assert "✓ Content saved successfully" in call_args

    @patch('littletools_txt.SyntxAiDownloader.requests.get')
    def test_download_syntx_content_chat_format(self, mock_get):
        """Test downloading content from LLMchat format."""
        # Mock HTML response for chat format
        mock_html = """
        <!DOCTYPE html>
        <html>
        <head><title>GPTConversations</title></head>
        <body>
            <section class="container mt-3">
                <div class="markdown-content">
                    <div class="message userquestion">
                        <div class="content">
                            <p>User question</p>
                            <button class="copy-message-button">Copy</button>
                        </div>
                    </div>
                    <div class="message answer">
                        <div class="content">
                            <p>Assistant answer</p>
                            <button class="copy-message-button">Copy</button>
                            <div style="opacity: 0.7; font-size: 11px;">
                                <i class="bi bi-robot"></i> GPT-4.1 Nano
                            </div>
                            <div style="opacity: 0.7; font-size: 11px;">
                                <i class="bi bi-clock-history"></i> 22.07.2025 00:19:00 GMT+3
                            </div>
                        </div>
                    </div>
                </div>
            </section>
        </body>
        </html>
        """
        
        mock_response = Mock()
        mock_response.text = mock_html
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        with patch('littletools_txt.SyntxAiDownloader.console.print') as mock_print:
            download_syntx_content(self.valid_chat_url, self.temp_dir)
            
            # Verify success message was printed with correct filename
            mock_print.assert_called()
            call_args = mock_print.call_args[0][0]
            assert "SyntxAI Chat.txt" in call_args
            assert "✓ Content saved successfully" in call_args

    @patch('littletools_txt.SyntxAiDownloader.requests.get')
    def test_download_syntx_content_old_format(self, mock_get):
        """Test downloading content from old syntx.ai format."""
        # Mock HTML response for old format
        mock_html = """
        <!DOCTYPE html>
        <html>
        <head><title>Old Format</title></head>
        <body>
            <h1 class="text-lg">Old Title</h1>
            <div class="overflow-y-auto">
                <p>Old format content</p>
            </div>
        </body>
        </html>
        """
        
        mock_response = Mock()
        mock_response.text = mock_html
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        with patch('littletools_txt.SyntxAiDownloader.console.print') as mock_print:
            download_syntx_content(self.valid_old_url, self.temp_dir)
            
            # Verify success message was printed with correct filename
            mock_print.assert_called()
            call_args = mock_print.call_args[0][0]
            assert "Old Title.txt" in call_args
            assert "✓ Content saved successfully" in call_args

    @patch('littletools_txt.SyntxAiDownloader.requests.get')
    def test_download_syntx_content_network_error(self, mock_get):
        """Test handling of network errors."""
        mock_get.side_effect = Exception("Network error")
        
        with patch('littletools_txt.SyntxAiDownloader.console.print') as mock_print:
            download_syntx_content(self.valid_share_url, self.temp_dir)
            mock_print.assert_called_with("[red]! An unexpected error occurred: Network error[/red]")

    @patch('littletools_txt.SyntxAiDownloader.requests.get')
    def test_download_syntx_content_missing_content(self, mock_get):
        """Test handling when content container is not found."""
        # Mock HTML response without content container
        mock_html = """
        <!DOCTYPE html>
        <html>
        <head><title>No Content</title></head>
        <body>
            <p>No content container here</p>
        </body>
        </html>
        """
        
        mock_response = Mock()
        mock_response.text = mock_html
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        with patch('littletools_txt.SyntxAiDownloader.console.print') as mock_print:
            download_syntx_content(self.valid_share_url, self.temp_dir)
            mock_print.assert_called_with("[red]! Could not find content container on the page.[/red]")

    @patch('littletools_txt.SyntxAiDownloader.requests.get')
    def test_download_syntx_content_requests_exception(self, mock_get):
        """Test handling of requests.RequestException."""
        from requests import RequestException
        mock_get.side_effect = RequestException("Network error")
        
        with patch('littletools_txt.SyntxAiDownloader.console.print') as mock_print:
            download_syntx_content(self.valid_share_url, self.temp_dir)
            mock_print.assert_called_with("[red]! Network or HTTP error: Network error[/red]")

    @patch('littletools_txt.SyntxAiDownloader.requests.get')
    def test_download_syntx_content_http_error(self, mock_get):
        """Test handling of HTTP errors."""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = Exception("HTTP 500 Internal Server Error")
        mock_get.return_value = mock_response
        
        with patch('littletools_txt.SyntxAiDownloader.console.print') as mock_print:
            download_syntx_content(self.valid_share_url, self.temp_dir)
            mock_print.assert_called_with("[red]! An unexpected error occurred: HTTP 500 Internal Server Error[/red]")

    @patch('littletools_txt.SyntxAiDownloader.typer.prompt')
    @patch('littletools_txt.SyntxAiDownloader.download_syntx_content')
    @patch('littletools_txt.SyntxAiDownloader.ensure_dir_exists')
    def test_run_with_valid_url(self, mock_ensure_dir, mock_download, mock_prompt):
        """Test run function with valid URL."""
        with patch('littletools_txt.SyntxAiDownloader.console.print') as mock_print:
            run(url=self.valid_share_url, output_dir=self.temp_dir)
            
            mock_ensure_dir.assert_called_once_with(self.temp_dir)
            mock_print.assert_called_with("[*] SyntxAI Content Downloader")
            mock_download.assert_called_once_with(self.valid_share_url, self.temp_dir)

    @patch('littletools_txt.SyntxAiDownloader.typer.prompt')
    @patch('littletools_txt.SyntxAiDownloader.download_syntx_content')
    @patch('littletools_txt.SyntxAiDownloader.ensure_dir_exists')
    def test_run_with_prompted_url(self, mock_ensure_dir, mock_download, mock_prompt):
        """Test run function when URL is prompted."""
        mock_prompt.return_value = self.valid_chat_url
        
        with patch('littletools_txt.SyntxAiDownloader.console.print') as mock_print:
            run(url=None, output_dir=self.temp_dir)
            
            mock_prompt.assert_called_once_with("Please enter the SyntxAI share link")
            mock_download.assert_called_once_with(self.valid_chat_url, self.temp_dir)

    @patch('littletools_txt.SyntxAiDownloader.typer.prompt')
    @patch('littletools_txt.SyntxAiDownloader.ensure_dir_exists')
    def test_run_with_invalid_url(self, mock_ensure_dir, mock_prompt):
        """Test run function with invalid URL."""
        with patch('littletools_txt.SyntxAiDownloader.console.print') as mock_print:
            with pytest.raises(Exit):
                run(url=self.invalid_url, output_dir=self.temp_dir)
            
            mock_print.assert_called_with("[red]! Invalid SyntxAI share link format.[/red]")

    @patch('littletools_txt.SyntxAiDownloader.typer.prompt')
    @patch('littletools_txt.SyntxAiDownloader.ensure_dir_exists')
    def test_run_with_url_with_angle_brackets(self, mock_ensure_dir, mock_prompt):
        """Test run function with URL wrapped in angle brackets."""
        url_with_brackets = "<https://LLMshare.syntxai.net/test123>"
        
        with patch('littletools_txt.SyntxAiDownloader.console.print') as mock_print:
            with patch('littletools_txt.SyntxAiDownloader.download_syntx_content') as mock_download:
                run(url=url_with_brackets, output_dir=self.temp_dir)
                
                # Should strip brackets and call download with clean URL
                mock_download.assert_called_once_with("https://LLMshare.syntxai.net/test123", self.temp_dir)

    def test_run_with_none_url_and_prompt(self):
        """Test run function when URL is None and prompt is used."""
        with patch('littletools_txt.SyntxAiDownloader.typer.prompt') as mock_prompt:
            mock_prompt.return_value = self.valid_share_url
            with patch('littletools_txt.SyntxAiDownloader.download_syntx_content') as mock_download:
                with patch('littletools_txt.SyntxAiDownloader.ensure_dir_exists'):
                    run(url=None, output_dir=self.temp_dir)
                    mock_prompt.assert_called_once_with("Please enter the SyntxAI share link")
                    mock_download.assert_called_once_with(self.valid_share_url, self.temp_dir)

    def test_app_creation(self):
        """Test that the Typer app is created correctly."""
        assert hasattr(app, 'info')  # Typer app has info attribute
        assert "Download content from Syntx.ai share links" in app.info.help


if __name__ == "__main__":
    pytest.main([__file__]) 
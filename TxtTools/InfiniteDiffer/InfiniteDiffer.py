#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""InfiniteDiffer: A tool for comparing multiple text files simultaneously.

This application provides a Git-like diff visualization for more than two text sources
at the same time, highlighting additions, deletions, and modifications across files.

Processing rules: (may be out of date)
    - Text that is identical across all sources is not highlighted.
    - Text added in all sources except the first one is highlighted with standard green.
    - Text removed from all sources except the first one is highlighted with standard red.
    - Text added in any specific source appears with that source's color highlighting.
        - If text is added in multiple sources, it appears once for each source.
        - Line numbers help distinguish between duplicate lines from different sources.
    - Text removed from any specific source appears underlined with that source's color.

Example:
    Run the application with:
        $ python InfiniteDiffer.py
"""

import sys
import os
import difflib
import signal
import json
import pickle
from typing import List, Dict, Tuple, Optional, Set, Any
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QTextEdit, QLabel, QFileDialog, QScrollArea,
    QSplitter, QTabWidget, QToolBar, QStatusBar, QComboBox, QMenu,
    QGridLayout, QFrame, QSizePolicy, QCheckBox, QDialogButtonBox,
    QDialog, QListWidget, QListWidgetItem, QLineEdit, QToolTip,
    QColorDialog, QInputDialog, QStackedWidget
)
from PyQt6.QtGui import (
    QTextCharFormat, QColor, QTextCursor, QPalette, 
    QAction, QIcon, QFont, QTextDocument, QPainter, QFontMetrics
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QRect, QPoint

# * Configuration variables
MAX_TEXT_SOURCES = 10  # Maximum number of text sources to compare
DEFAULT_WINDOW_WIDTH = 1200
DEFAULT_WINDOW_HEIGHT = 800
DEFAULT_FONT_FAMILY = "Consolas"
DEFAULT_FONT_SIZE = 10
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))  # Путь к директории скрипта
CACHE_FILENAME = os.path.join(SCRIPT_DIR, "infinite_differ_cache.pkl")  # Filename for workspace cache
COLORS_FILENAME = os.path.join(SCRIPT_DIR, "infinite_differ_colors.json")  # Filename for color settings
ENABLE_CACHING = False  # Whether to cache workspace state by default

# Welcome text displayed when no tabs are open
WELCOME_TEXT = """
Welcome to InfiniteDiffer!

This tool allows you to compare multiple text files simultaneously.

To get started:
1. Add files or text sources using the toolbar buttons
2. Select sources to compare
3. View the differences highlighted with colors

Use the right-click menu for additional options.
"""

# Default source tab colors - darker pastel colors (using hex values)
DEFAULT_SOURCE_COLORS = [
    QColor("#B484F0"),
    QColor("#F084F0"),
    QColor("#F0B0B4"),
    QColor("#B4F0F0"),
    QColor("#F0C8B4"),
    QColor("#C8F0B4"),
    QColor("#E6B4D2"),
    QColor("#D2D2F0"),
    QColor("#DCDCDC"),
    QColor("#C8DCC8"),
]

# * Highlight colors for diff operations
HIGHLIGHT_COLORS = {
    "addition": QColor("#4DAF4D"),
    "deletion": QColor("#FF4D4D"),
    "modification": QColor("#7C93C0"),  # Blue-ish for modifications
    "moved": QColor("#DAA520"),  # Goldenrod for moved lines
    "same": QColor("#AAAAFF"),
    "source1": QColor("#E6E666"),
    "source2": QColor("#0F8666"),
    "source3": QColor("#FF2FE6"),
    "source4": QColor("#E6FFFF"),
    "source5": QColor("#FFF0E6"),
}


class LineNumberArea(QWidget):
    """Widget for displaying line numbers in a text edit."""
    
    def __init__(self, editor):
        """Initialize the line number area.
        
        Args:
            editor: The parent text editor widget
        """
        super().__init__(editor)
        self.editor = editor
        self.setFont(QFont(DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE))
        self.setStyleSheet("background-color: #f0f0f0;")
    
    def sizeHint(self):
        """Calculate the size hint for the line number area."""
        return QSize(self.editor.line_number_area_width(), 0)
    
    def paintEvent(self, event):
        """Paint the line numbers.
        
        Args:
            event: The paint event
        """
        self.editor.line_number_area_paint_event(event)


class SearchWidget(QWidget):
    """Widget for searching text in a text edit."""
    
    def __init__(self, text_edit, parent=None):
        """Initialize the search widget.
        
        Args:
            text_edit: The text edit to search in
            parent: Parent widget
        """
        super().__init__(parent)
        self.text_edit = text_edit
        
        # Set up layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        
        # Search input
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search...")
        self.search_input.textChanged.connect(self.update_search)
        self.search_input.returnPressed.connect(self.search_down)  # Search on Enter
        layout.addWidget(self.search_input)
        
        # Up button
        self.up_button = QPushButton("🔼")
        self.up_button.setToolTip("Search up")
        self.up_button.clicked.connect(self.search_up)
        layout.addWidget(self.up_button)
        
        # Down button
        self.down_button = QPushButton("🔽")
        self.down_button.setToolTip("Search down")
        self.down_button.clicked.connect(self.search_down)
        layout.addWidget(self.down_button)
        
        # Count button
        self.count_button = QPushButton("🔢")
        self.count_button.setToolTip("Count occurrences")
        self.count_button.clicked.connect(self.count_matches)
        layout.addWidget(self.count_button)
        
        # Close button
        self.close_button = QPushButton("❌")
        self.close_button.setToolTip("Close search")
        self.close_button.clicked.connect(self.hide_search)
        layout.addWidget(self.close_button)
        
        # Set fixed size for buttons
        for button in [self.up_button, self.down_button, self.count_button, self.close_button]:
            button.setFixedSize(24, 24)
            button.setStyleSheet("padding: 0px;")
        
        # Set widget styling
        self.setStyleSheet("""
            QWidget {
                background-color: rgba(240, 240, 240, 0.9);
                border: 1px solid #aaa;
                border-radius: 3px;
            }
        """)
        
        # Store the last search position
        self.last_search_position = 0
        
        # Set initial visibility
        self.setFixedHeight(30)
        self.setVisible(False)
    
    def show_search(self):
        """Show the search widget and focus the search input."""
        self.setVisible(True)
        self.search_input.setFocus()
        self.search_input.selectAll()
    
    def hide_search(self):
        """Hide the search widget."""
        self.setVisible(False)
        self.text_edit.setFocus()
    
    def update_search(self):
        """Update the search highlighting based on current input."""
        self.text_edit.search_text(self.search_input.text())
    
    def search_up(self):
        """Search up for the current text."""
        search_text = self.search_input.text()
        if not search_text:
            return
        
        self.text_edit.find_previous()
    
    def search_down(self):
        """Search down for the current text."""
        search_text = self.search_input.text()
        if not search_text:
            return
        
        self.text_edit.find_next()
    
    def count_matches(self):
        """Count and show the number of matches."""
        search_text = self.search_input.text()
        if not search_text:
            return
        
        count = self.text_edit.count_occurrences(search_text)
        
        # Find the main window to access the status bar
        parent = self.text_edit
        while parent and not isinstance(parent, QMainWindow):
            parent = parent.parent()
        
        if parent and isinstance(parent, QMainWindow):
            parent.statusBar().showMessage(f"Found {count} occurrences of '{search_text}'", 3000)
        else:
            # Create a tooltip instead
            QToolTip.showText(
                self.mapToGlobal(QPoint(0, self.height())),
                f"Found {count} occurrences",
                self,
                QRect(),
                3000
            )


class DiffTextEdit(QTextEdit):
    """Custom text edit widget for displaying diff content with highlighting."""
    
    def __init__(self, parent=None):
        """Initialize the DiffTextEdit widget.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(QFont(DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE))
        self.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        
        # Initialize line number area
        self.line_number_area = LineNumberArea(self)
        
        # Connect signals for line number area
        self.document().blockCountChanged.connect(self.update_line_number_area_width)
        self.verticalScrollBar().valueChanged.connect(lambda val: self.update_line_number_area(None, val))
        self.textChanged.connect(lambda: self.update_line_number_area())
        self.cursorPositionChanged.connect(lambda: self.update_line_number_area())
        
        # Initialize line number area
        self.update_line_number_area_width(0)
        
        # Create search bar - embedded in the parent widget for proper display
        self.search_widget = SearchWidget(self, parent if parent else self)
        
        # Add keyboard shortcut for search
        self.search_action = QAction("Search", self)
        self.search_action.setShortcut("Ctrl+F")
        self.search_action.triggered.connect(self.toggle_search)
        self.addAction(self.search_action)
        
        # Initialize last search term
        self.last_search_term = ""
        
        # Store search highlight positions
        self.search_positions = []
        self.current_match_index = -1
        
        # Override layout on parent change to ensure search widget is shown correctly
        self.installEventFilter(self)
    
    def eventFilter(self, obj, event):
        """Filter events to handle parent changes.
        
        Args:
            obj: The object that received the event
            event: The event
            
        Returns:
            True if the event was handled, False otherwise
        """
        if obj == self and self.search_widget and self.parent():
            if event.type() == 42:  # QEvent.Polish
                # Delay positioning until parent is fully initialized
                QApplication.instance().processEvents()
                self.position_search_widget()
        return False
    
    def showEvent(self, event):
        """Handle show events to ensure search widget is positioned correctly.
        
        Args:
            event: The show event
        """
        super().showEvent(event)
        # Delay positioning until this widget is fully shown
        QApplication.instance().processEvents()
        self.position_search_widget()
    
    def position_search_widget(self):
        """Position the search widget in the parent widget."""
        if not self.search_widget or not self.parent() or not self.isVisible():
            return
        
        # Get the global position of this widget's top-right corner
        global_pos = self.mapToGlobal(QPoint(self.width() - 10, 10))
        
        # Calculate the local position in the parent widget
        local_pos = self.parent().mapFromGlobal(global_pos)
        
        # Position the search widget in the parent
        search_width = min(350, self.width() // 2)
        self.search_widget.setFixedWidth(search_width)
        self.search_widget.setParent(self.parent())
        self.search_widget.move(local_pos.x() - search_width, local_pos.y())
        
        if self.search_widget.isVisible():
            self.search_widget.raise_()
    
    def resizeEvent(self, event):
        """Handle resize events.
        
        Args:
            event: The resize event
        """
        super().resizeEvent(event)
        
        # Update line number area
        cr = self.contentsRect()
        self.line_number_area.setGeometry(QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height()))
        
        # Update search widget position
        self.position_search_widget()
    
    def toggle_search(self):
        """Toggle the visibility of the search widget."""
        if self.search_widget.isVisible():
            self.search_widget.hide_search()
        else:
            # Update position before showing
            self.position_search_widget()
            self.search_widget.raise_()
            self.search_widget.show_search()
    
    def search_text(self, search_text):
        """Search for text and highlight all occurrences.
        
        Args:
            search_text: Text to search for
        """
        self.last_search_term = search_text
        
        # Clear previous search highlights
        self.search_positions = []
        self.current_match_index = -1
        
        if not search_text:
            return
        
        # Find all occurrences
        cursor = self.textCursor()
        cursor.beginEditBlock()
        
        # Move to the beginning of the document
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        cursor.endEditBlock()
        
        self.setTextCursor(cursor)
        
        # Find the first occurrence and all subsequent ones
        found = self.find(search_text)
        
        while found:
            # Store the position
            cursor = self.textCursor()
            self.search_positions.append(cursor.position())
            
            # Find the next occurrence
            found = self.find(search_text)
        
        # Reset cursor to the beginning
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        self.setTextCursor(cursor)
        
        # If we found any matches, highlight the first one
        if self.search_positions:
            self.current_match_index = 0
            self.highlight_current_match()
    
    def highlight_current_match(self):
        """Highlight the current match."""
        if 0 <= self.current_match_index < len(self.search_positions):
            cursor = self.textCursor()
            cursor.setPosition(self.search_positions[self.current_match_index])
            cursor.movePosition(
                QTextCursor.MoveOperation.Right, 
                QTextCursor.MoveMode.KeepAnchor, 
                len(self.last_search_term)
            )
            self.setTextCursor(cursor)
            self.ensureCursorVisible()
    
    def find_next(self):
        """Find the next occurrence of the search term."""
        if not self.search_positions:
            return
        
        self.current_match_index = (self.current_match_index + 1) % len(self.search_positions)
        self.highlight_current_match()
    
    def find_previous(self):
        """Find the previous occurrence of the search term."""
        if not self.search_positions:
            return
        
        self.current_match_index = (self.current_match_index - 1) % len(self.search_positions)
        self.highlight_current_match()
    
    def count_occurrences(self, search_text):
        """Count the number of occurrences of the search text.
        
        Args:
            search_text: Text to search for
            
        Returns:
            Number of occurrences
        """
        if not search_text:
            return 0
        
        # Use the already populated search positions
        if search_text == self.last_search_term and self.search_positions:
            return len(self.search_positions)
        
        # Otherwise, perform a new search
        count = 0
        content = self.toPlainText()
        pos = 0
        
        while True:
            pos = content.find(search_text, pos)
            if pos == -1:
                break
            count += 1
            pos += len(search_text)
        
        return count
        
    def line_number_area_width(self):
        """Calculate the width of the line number area.
        
        Returns:
            Width in pixels
        """
        digits = 1
        max_num = max(1, self.document().blockCount())
        while max_num >= 10:
            max_num //= 10
            digits += 1
        
        space = 3 + self.fontMetrics().horizontalAdvance('9') * digits
        return space
    
    def update_line_number_area_width(self, _):
        """Update the width of the line number area."""
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)
    
    def update_line_number_area(self, rect=None, dy=0):
        """Update the line number area.
        
        Args:
            rect: The update rectangle
            dy: The vertical scroll value
        """
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, 0, self.line_number_area.width(), self.height())
        
        # Check if rect is a QRect object before calling isValid()
        if rect and isinstance(rect, QRect) and rect.isValid():
            self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)
        else:
            # If rect is not a valid QRect, just update the viewport margins anyway
            self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)
    
    def line_number_area_paint_event(self, event):
        """Paint the line number area.
        
        Args:
            event: The paint event
        """
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QColor("#f0f0f0"))
        
        # Get visible content bounds
        contents_rect = self.viewport().contentsRect()
        viewport_offset = self.verticalScrollBar().value()
        
        # Calculate font metrics
        fm = self.fontMetrics()
        line_spacing = fm.lineSpacing()
        
        # Get visible text block bounding rectangles
        line_count = self.document().blockCount()
        
        # Calculate how many lines are visible in the viewport
        visible_lines_count = int(contents_rect.height() / line_spacing) + 2
        
        # Calculate first visible line based on scroll position
        first_visible_line = int(viewport_offset / line_spacing) + 1
        
        # Get line numbers from the text's property, if available
        line_numbers = self.property("line_numbers")
        
        # Draw visible line numbers
        for i in range(visible_lines_count):
            line_number = first_visible_line + i
            
            if line_number > line_count:
                break
                
            top_y = int(i * line_spacing - (viewport_offset % line_spacing))
            
            # If we have custom line numbers, use them
            if line_numbers and line_number - 1 < len(line_numbers):
                display_number = line_numbers[line_number - 1]
                # Don't display numbers for folded line markers
                if display_number == -1:
                    continue
            else:
                display_number = line_number
            
            # Draw line number
            painter.setPen(QColor(100, 100, 100))
            painter.drawText(
                0, 
                top_y, 
                self.line_number_area.width() - 5, 
                line_spacing, 
                Qt.AlignmentFlag.AlignRight, 
                str(display_number)
            )
    
    def highlight_text(self, diff_lines: List[Tuple[str, str]]):
        """Highlight diff text based on status (addition, deletion, modification, moved, same).
        
        Args:
            diff_lines: List of tuples containing (line_text, status)
        """
        self.clear()
        text_cursor = self.textCursor()
        text_cursor.movePosition(QTextCursor.MoveOperation.Start)
        
        # Collect lines for folding
        all_lines = []
        for line, status in diff_lines:
            all_lines.append((line, status))
        
        # Track line numbers
        line_numbers = []
        current_line = 1
        
        # Process lines with context folding
        i = 0
        show_context = 2  # Show this many lines of context before and after changes
        
        while i < len(all_lines):
            line, status = all_lines[i]
            
            # Start of folding area
            if status == "same":
                # Check if we have a sequence of unchanged lines
                same_count = 0
                for j in range(i, len(all_lines)):
                    if all_lines[j][1] == "same":
                        same_count += 1
                    else:
                        break
                
                # If we have more than (show_context*2 + 1) unchanged lines, fold them
                if same_count > show_context * 2 + 1:
                    # Show first 'show_context' unchanged lines
                    for j in range(i, i + show_context):
                        format_text = QTextCharFormat()
                        if all_lines[j][1] in HIGHLIGHT_COLORS:
                            format_text.setBackground(HIGHLIGHT_COLORS[all_lines[j][1]])
                        format_text.setForeground(QColor(0, 0, 0))
                        text_cursor.insertText(all_lines[j][0], format_text)
                        text_cursor.insertBlock()
                        line_numbers.append(current_line)
                        current_line += 1
                    
                    # Insert folding indicator
                    fold_format = QTextCharFormat()
                    fold_format.setForeground(QColor(100, 100, 100))
                    fold_text = f"(... {same_count - show_context * 2} unchanged lines ...)"
                    text_cursor.insertText(fold_text, fold_format)
                    text_cursor.insertBlock()
                    line_numbers.append(-1)  # Special marker for folded lines
                    
                    # Skip the middle lines in line counting
                    current_line += same_count - show_context * 2
                    
                    # Show last 'show_context' unchanged lines
                    for j in range(i + same_count - show_context, i + same_count):
                        format_text = QTextCharFormat()
                        if all_lines[j][1] in HIGHLIGHT_COLORS:
                            format_text.setBackground(HIGHLIGHT_COLORS[all_lines[j][1]])
                        format_text.setForeground(QColor(0, 0, 0))
                        text_cursor.insertText(all_lines[j][0], format_text)
                        text_cursor.insertBlock()
                        line_numbers.append(current_line)
                        current_line += 1
                    
                    i += same_count
                    continue
            
            # Regular formatting
            format_text = QTextCharFormat()
            
            if status in HIGHLIGHT_COLORS:
                format_text.setBackground(HIGHLIGHT_COLORS[status])
            
            # Set text color to black
            format_text.setForeground(QColor(0, 0, 0))
            
            # Special formatting for moved lines
            if status == "moved":
                format_text.setFontItalic(True)
            
            # Special formatting for modified lines
            if status == "modification":
                format_text.setFontWeight(QFont.Weight.Bold)
            
            # Insert text with formatting
            text_cursor.insertText(line, format_text)
            text_cursor.insertBlock()
            
            # Add line number
            line_numbers.append(current_line)
            current_line += 1
            
            i += 1
        
        # Store line numbers as a property of the text edit
        self.setProperty("line_numbers", line_numbers)
        
        self.setTextCursor(text_cursor)
        
        # Force update of line number area
        self.update_line_number_area()

    def highlight_multi_diff(self, diff_data: List[Tuple[str, List[str], List[int]]]):
        """Highlight text for multi-source diff.
        
        Args:
            diff_data: List of tuples containing (line_text, statuses, source_indices)
                where statuses is a list of status strings and source_indices is a list
                of indices of sources that contain this line
        """
        self.clear()
        text_cursor = self.textCursor()
        text_cursor.movePosition(QTextCursor.MoveOperation.Start)
        
        # Collect all lines for folding
        all_lines = []
        for line, statuses, sources in diff_data:
            # Check if text is unchanged in all sources
            is_same = all(status == "same" for status in statuses)
            all_lines.append((line, statuses, sources, is_same))
        
        # Track line numbers
        line_numbers = []
        current_line = 1
        
        # Process lines with context folding
        i = 0
        show_context = 2  # * Show this many lines of context before and after changes
        
        while i < len(all_lines):
            line, statuses, sources, is_same = all_lines[i]
            
            # Start of folding area
            if is_same:
                # Check if we have a sequence of unchanged lines
                same_count = 0
                for j in range(i, len(all_lines)):
                    if all_lines[j][3]:  # Check is_same flag
                        same_count += 1
                    else:
                        break
                
                # If we have more than (show_context*2 + 1) unchanged lines, fold them
                if same_count > show_context * 2 + 1:
                    # Show first 'show_context' unchanged lines
                    for j in range(i, i + show_context):
                        format_text = QTextCharFormat()
                        # No highlighting for unchanged text
                        text_cursor.insertText(all_lines[j][0], format_text)
                        text_cursor.insertBlock()
                        line_numbers.append(current_line)
                        current_line += 1
                    
                    # Insert folding indicator
                    fold_format = QTextCharFormat()
                    fold_format.setForeground(QColor(100, 100, 100))
                    fold_text = f"(... {same_count - show_context * 2} unchanged lines ...)"
                    text_cursor.insertText(fold_text, fold_format)
                    text_cursor.insertBlock()
                    line_numbers.append(-1)  # Special marker for folded lines
                    
                    # Skip the middle lines in line counting
                    current_line += same_count - show_context * 2
                    
                    # Show last 'show_context' unchanged lines
                    for j in range(i + same_count - show_context, i + same_count):
                        format_text = QTextCharFormat()
                        # No highlighting for unchanged text
                        text_cursor.insertText(all_lines[j][0], format_text)
                        text_cursor.insertBlock()
                        line_numbers.append(current_line)
                        current_line += 1
                    
                    i += same_count
                    continue
            
            # Regular case - process the line according to its status
            line, statuses, sources = all_lines[i][0], all_lines[i][1], all_lines[i][2]
            
            # Check if text is unchanged in all sources (no highlighting)
            if all(status == "same" for status in statuses):
                format_text = QTextCharFormat()
                # No highlighting for unchanged text
                text_cursor.insertText(line, format_text)
                text_cursor.insertBlock()
                line_numbers.append(current_line)
                current_line += 1
                i += 1
                continue
            
            # Standard git diff green: added in all sources except the first
            if sources and 0 not in sources and len(sources) == len(statuses) - 1:
                format_text = QTextCharFormat()
                format_text.setBackground(HIGHLIGHT_COLORS["addition"])  # Standard green
                text_cursor.insertText(line, format_text)
                text_cursor.insertBlock()
                line_numbers.append(current_line)
                current_line += 1
                i += 1
                continue
            
            # Check if this is a line from the base source that is missing in some other sources
            if 0 in sources and len(sources) < len(statuses):
                # First show the base line as normal (not underlined)
                format_text = QTextCharFormat()
                text_cursor.insertText(line, format_text)
                text_cursor.insertBlock()
                line_numbers.append(current_line)
                current_line += 1
                
                # Now show which sources are missing this line
                missing_sources = []
                for idx in range(1, len(statuses)):  # Skip the base source
                    if idx not in [sources.index(src) for src in sources if src != 0]:
                        missing_sources.append(idx)
                
                if missing_sources:
                    format_text = QTextCharFormat()
                    format_text.setFontUnderline(True)
                    
                    # Create missing sources indicator
                    missing_text = f"[Missing in S{', S'.join([str(s + 1) for s in missing_sources])}]"
                    source_format = QTextCharFormat()
                    source_format.setForeground(QColor(100, 100, 100))  # Gray text
                    text_cursor.insertText(missing_text, source_format)
                    
                    # Insert the line with underline formatting
                    text_cursor.insertText(" " + line, format_text)
                    text_cursor.insertBlock()
                    line_numbers.append(current_line)
                    current_line += 1
                
                i += 1
                continue
            
            # For added/modified text in specific sources, show once per source with that source's color
            if len(sources) < len(statuses):
                shown = False
                
                for src_idx in sources:
                    # Skip the base source, we already handled it
                    if src_idx == 0:
                        continue
                        
                    format_text = QTextCharFormat()
                    source_color_key = f"source{src_idx + 1}" if 0 <= src_idx < 5 else "addition"
                    
                    if source_color_key in HIGHLIGHT_COLORS:
                        format_text.setBackground(HIGHLIGHT_COLORS[source_color_key])
                    
                    # Insert source indicator at the beginning
                    source_indicator = f"[S{src_idx + 1}] "
                    source_format = QTextCharFormat()
                    source_format.setForeground(QColor(100, 100, 100))  # Gray text
                    text_cursor.insertText(source_indicator, source_format)
                    
                    # Insert the line with appropriate formatting
                    text_cursor.insertText(line, format_text)
                    text_cursor.insertBlock()
                    line_numbers.append(current_line)
                    current_line += 1
                    shown = True
                
                # If we've shown this line for at least one source, continue to the next line
                if shown:
                    i += 1
                    continue
            
            # Default case: just show the line with basic formatting
            format_text = QTextCharFormat()
            if len(sources) < len(statuses):
                # Only some sources have this line
                format_text.setBackground(HIGHLIGHT_COLORS["addition"])
            text_cursor.insertText(line, format_text)
            text_cursor.insertBlock()
            line_numbers.append(current_line)
            current_line += 1
            i += 1
        
        # Store line numbers as a property of the text edit
        self.setProperty("line_numbers", line_numbers)
        
        self.setTextCursor(text_cursor)
        
        # Force update of line number area
        self.update_line_number_area()


class TextSource:
    """Class to store a text source.
    
    Represents a single text source with content, name, and color for highlighting.
    
    Attributes:
        name: Display name of the text source.
        content: String content of the text source.
        lines: List of lines parsed from the content.
        color: QColor assigned to this text source for highlighting.
    """
    
    def __init__(self, name: str = "", content: str = "", color: QColor = None):
        """Initialize a text source.
        
        Args:
            name: Display name of the text source.
            content: String content of the text source.
            color: QColor for highlighting this source. If None, a default color is used.
        """
        self.name = name
        self.content = content
        # Split content into lines for diff operations
        self.lines = content.splitlines()
        
        # Set default color if none provided
        if color is None:
            self.color = QColor(200, 200, 200)  # Light gray
        else:
            self.color = color
    
    def set_color(self, color: QColor):
        """Set the color for this text source.
        
        Args:
            color: New QColor for highlighting this source.
        """
        self.color = color
    
    def update_content(self, content: str):
        """Update the text content of this source.
        
        Args:
            content: New string content to set.
        """
        self.content = content
        self.lines = content.splitlines()


class DiffManager:
    """Manager for text sources and diff operations."""
    
    def __init__(self):
        """Initialize the diff manager."""
        self.sources = []
    
    def add_source(self, source: TextSource) -> int:
        """Add a text source to the manager.
        
        Args:
            source: The text source to add
            
        Returns:
            int: Index of the added source, or -1 if maximum sources limit reached
        """
        if len(self.sources) >= MAX_TEXT_SOURCES:
            return -1
            
        # Set the color based on the source index
        source_idx = len(self.sources)
        if source_idx < len(DEFAULT_SOURCE_COLORS):
            source.color = DEFAULT_SOURCE_COLORS[source_idx]
            
        # Update highlight colors map
        if source_idx < 5:  # We only have 5 predefined source colors
            highlight_color = source.color.lighter(130)
            HIGHLIGHT_COLORS[f"source{source_idx + 1}"] = highlight_color
            
        self.sources.append(source)
        return len(self.sources) - 1
    
    def remove_source(self, index: int) -> bool:
        """Remove a text source by index.
        
        Args:
            index: Index of the source to remove
            
        Returns:
            True if removed successfully, False otherwise
        """
        if 0 <= index < len(self.sources):
            self.sources.pop(index)
            return True
        return False
    
    def get_diff(self, base_index: int, compare_index: int) -> List[Tuple[str, str]]:
        """Calculate diff between two text sources.
        
        Uses context-aware diff algorithm to improve accuracy of matching similar lines.
        Identifies modified lines and moved lines in addition to additions and deletions.
        
        Args:
            base_index: Index of the base text source
            compare_index: Index of the text source to compare against
            
        Returns:
            List of (line, status) tuples where status is 'addition', 'deletion', 
            'modification', 'moved', or 'same'
        """
        if not (0 <= base_index < len(self.sources) and 0 <= compare_index < len(self.sources)):
            return []
        
        base = self.sources[base_index]
        compare = self.sources[compare_index]
        
        # Use SequenceMatcher for better context awareness
        matcher = difflib.SequenceMatcher(None, base.lines, compare.lines)
        
        # Get opcodes for detailed diff information
        opcodes = matcher.get_opcodes()
        
        result = []
        
        # Process opcodes (format: 'tag', i1, i2, j1, j2)
        # tag can be: 'replace', 'delete', 'insert', 'equal'
        for tag, base_start, base_end, compare_start, compare_end in opcodes:
            if tag == 'equal':
                # Unchanged lines
                for i in range(base_start, base_end):
                    result.append((base.lines[i], "same"))
            elif tag == 'replace':
                # This indicates modified lines
                # To better handle this, we'll try to match lines that are similar
                if base_end - base_start == compare_end - compare_start:
                    # Same number of lines, likely modifications
                    for i in range(base_end - base_start):
                        base_line = base.lines[base_start + i]
                        compare_line = compare.lines[compare_start + i]
                        # Calculate similarity ratio
                        line_matcher = difflib.SequenceMatcher(None, base_line, compare_line)
                        similarity = line_matcher.ratio()
                        
                        if similarity > 0.5:  # More than 50% similar
                            result.append((f"{base_line} → {compare_line}", "modification"))
                        else:
                            # If lines are too different, treat as deletion and addition
                            result.append((base_line, "deletion"))
                            result.append((compare_line, "addition"))
                else:
                    # Different number of lines
                    # Handle as separate deletion and addition
                    for i in range(base_start, base_end):
                        result.append((base.lines[i], "deletion"))
                    for i in range(compare_start, compare_end):
                        result.append((compare.lines[i], "addition"))
            elif tag == 'delete':
                # Check if these lines appear elsewhere (moved)
                for i in range(base_start, base_end):
                    base_line = base.lines[i]
                    # Check if this line appears anywhere in compare text
                    if base_line in compare.lines:
                        # It's moved, not deleted
                        result.append((base_line, "moved"))
                    else:
                        # Truly deleted
                        result.append((base_line, "deletion"))
            elif tag == 'insert':
                # Check if these lines appear elsewhere (moved)
                for i in range(compare_start, compare_end):
                    compare_line = compare.lines[i]
                    # Check if this line appears anywhere in base text
                    if compare_line in base.lines:
                        # It's moved, not added
                        # We skip it here because it was already marked as "moved" in the delete section
                        pass
                    else:
                        # Truly added
                        result.append((compare_line, "addition"))
        
        return result
    
    def get_multi_diff(self, source_indices: List[int]) -> List[Tuple[str, List[str], List[int]]]:
        """Calculate diff between multiple text sources.
        
        Uses context-aware diff algorithm to improve accuracy of matching similar lines.
        
        Args:
            source_indices: List of indices of text sources to compare
            
        Returns:
            List of tuples containing (line_text, statuses, source_indices)
                where statuses is a list of status strings and source_indices is a list
                of indices of sources that contain this line
        """
        if not source_indices or len(source_indices) < 2:
            return []
        
        # Validate all indices
        for idx in source_indices:
            if not (0 <= idx < len(self.sources)):
                return []
        
        # Get the base source (first in the list)
        base_idx = source_indices[0]
        base_lines = self.sources[base_idx].lines
        
        # Initialize result structure
        result = []
        
        # Maps to track line statuses and presence
        line_statuses = {line: [0] * len(source_indices) for line in base_lines}
        for i, line in enumerate(base_lines):
            line_statuses[line][0] = 1  # Mark as present in base source
        
        # Process each non-base source against the base
        for i, idx in enumerate(source_indices[1:], 1):
            compare_lines = self.sources[idx].lines
            
            # Use SequenceMatcher for context-aware matching
            matcher = difflib.SequenceMatcher(None, base_lines, compare_lines)
            
            # Process matching blocks
            for base_start, compare_start, size in matcher.get_matching_blocks():
                # Skip the sentinel block (0, 0, 0) at the end
                if size == 0:
                    continue
                    
                # Mark matched lines as present in current source
                for j in range(size):
                    base_line = base_lines[base_start + j]
                    line_statuses[base_line][i] = 1
            
            # Add lines unique to this source
            for j, line in enumerate(compare_lines):
                if line not in line_statuses:
                    # This line is not in the base, create a new entry
                    statuses = [0] * len(source_indices)
                    statuses[i] = 1
                    line_statuses[line] = statuses
        
        # Convert line_statuses to the expected result format
        for line, statuses in line_statuses.items():
            status_texts = []
            source_indices_with_line = []
            
            for i, present in enumerate(statuses):
                if present:
                    status_texts.append("same" if sum(statuses) == len(source_indices) else "addition")
                    source_indices_with_line.append(source_indices[i])
                else:
                    status_texts.append("deletion")
            
            result.append((line, status_texts, source_indices_with_line))
        
        # Now add lines that only exist in non-base sources
        # This preserves the context structure better than the previous implementation
        for i, idx in enumerate(source_indices[1:], 1):
            compare_lines = self.sources[idx].lines
            
            for line in compare_lines:
                # Skip lines already processed from base source
                if line in line_statuses:
                    continue
                    
                # Create status entry for this unique line
                statuses = ["deletion"] * len(source_indices)
                statuses[i] = "addition"
                
                # Add to results with correct source index
                result.append((line, statuses, [source_indices[i]]))
        
        # Sort the result by the order of lines in the base source
        # This improves readability of the diff
        base_line_order = {line: i for i, line in enumerate(base_lines)}
        
        # Custom sort function that prioritizes base lines order
        def sort_key(item):
            line = item[0]
            sources = item[2]
            # Lines in base source are sorted by their original order
            if 0 in [source_indices.index(src) for src in sources if src in source_indices]:
                return (0, base_line_order.get(line, len(base_lines)))
            # Lines not in base are sorted after all base lines
            return (1, 0)
            
        result.sort(key=sort_key)
        
        return result


class SourceSelectionDialog(QDialog):
    """Dialog for selecting multiple text sources for comparison."""
    
    def __init__(self, sources: List[TextSource], parent=None):
        """Initialize the source selection dialog.
        
        Args:
            sources: List of available text sources
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.setWindowTitle("Select Sources to Compare")
        self.resize(300, 400)
        
        # Set up layout
        layout = QVBoxLayout(self)
        
        # Add instruction label
        label = QLabel("Select at least two sources to compare:")
        layout.addWidget(label)
        
        # Add source list
        self.source_list = QListWidget()
        for i, source in enumerate(sources):
            item = QListWidgetItem(source.name)
            item.setCheckState(Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, i)  # Store source index
            self.source_list.addItem(item)
        
        layout.addWidget(self.source_list)
        
        # Add buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
    def get_selected_sources(self) -> List[int]:
        """Get the indices of selected sources.
        
        Returns:
            List of indices of selected sources
        """
        selected = []
        for i in range(self.source_list.count()):
            item = self.source_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                selected.append(item.data(Qt.ItemDataRole.UserRole))
        
        return selected


class MultiDiffView(QWidget):
    """Widget for displaying diff between multiple text sources."""
    
    def __init__(self, diff_manager: DiffManager, source_indices: List[int], parent=None):
        """Initialize the multi-diff view.
        
        Args:
            diff_manager: The diff manager instance
            source_indices: List of indices of text sources to compare
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.diff_manager = diff_manager
        self.source_indices = source_indices
        
        # Set up layout
        layout = QVBoxLayout(self)
        
        # Add source indicators
        source_layout = QHBoxLayout()
        
        for i, idx in enumerate(source_indices):
            if i < len(self.diff_manager.sources):
                source_name = self.diff_manager.sources[idx].name
                source_color = self.diff_manager.sources[idx].color
                
                indicator = QFrame()
                indicator.setFrameShape(QFrame.Shape.Box)
                indicator.setFixedSize(16, 16)
                indicator.setStyleSheet(f"background-color: {source_color.name()};")
                
                source_layout.addWidget(indicator)
                source_layout.addWidget(QLabel(f"{source_name}"))
                source_layout.addSpacing(20)
        
        source_layout.addStretch()
        layout.addLayout(source_layout)
        
        # Add diff text edit
        self.diff_edit = DiffTextEdit()
        layout.addWidget(self.diff_edit)
        
        # Calculate and display multi-diff
        self.update_diff()
    
    def update_diff(self):
        """Update the diff display with current content."""
        diff_data = self.diff_manager.get_multi_diff(self.source_indices)
        self.diff_edit.highlight_multi_diff(diff_data)
    
    def get_source_indices(self) -> List[int]:
        """Get the indices of sources being compared.
        
        Returns:
            List of source indices
        """
        return self.source_indices
    
    def get_source_names(self) -> List[str]:
        """Get the names of sources being compared.
        
        Returns:
            List of source names
        """
        names = []
        for idx in self.source_indices:
            if 0 <= idx < len(self.diff_manager.sources):
                names.append(self.diff_manager.sources[idx].name)
        return names


class ColorButton(QPushButton):
    """Custom button for color selection."""
    
    def __init__(self, color=QColor(255, 255, 255), parent=None):
        """Initialize the color button.
        
        Args:
            color: Initial color
            parent: Parent widget
        """
        super().__init__(parent)
        self.color = color
        self.setFixedSize(24, 24)
        self.setStyleSheet(f"background-color: {color.name()}; border: 1px solid #888;")
        self.clicked.connect(self.choose_color)
    
    def choose_color(self):
        """Show color picker dialog and update the button color."""
        color = QColorDialog.getColor(self.color, self, "Choose Color")
        if color.isValid():
            self.color = color
            self.setStyleSheet(f"background-color: {color.name()}; border: 1px solid #888;")
            self.color_changed.emit(self.color)
    
    def set_color(self, color):
        """Set the button color.
        
        Args:
            color: New color
        """
        self.color = color
        self.setStyleSheet(f"background-color: {color.name()}; border: 1px solid #888;")
    
    # Signal for color change
    color_changed = pyqtSignal(QColor)


class WelcomeWidget(QWidget):
    """Widget for displaying welcome message when no tabs are open."""
    
    def __init__(self, parent=None):
        """Initialize the welcome widget.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Create a rich text display for the welcome message
        welcome_label = QTextEdit()
        welcome_label.setReadOnly(True)
        welcome_label.setStyleSheet("background-color: transparent; border: none;")
        welcome_label.setHtml(f"<div style='text-align: center; font-size: 14pt;'>{WELCOME_TEXT.replace(chr(10), '<br>')}</div>")
        
        layout.addWidget(welcome_label)
        layout.addStretch()


class InfiniteDifferApp(QMainWindow):
    """Main application window for InfiniteDiffer."""
    
    def __init__(self):
        """Initialize the main window."""
        super().__init__()
        
        # Set up signal handling
        signal.signal(signal.SIGINT, self.signal_handler)
        
        # Initialize diff manager
        self.diff_manager = DiffManager()
        
        # Initialize caching flag
        self.caching_enabled = ENABLE_CACHING
        
        # Initialize UI
        self.init_ui()
        
        # Load cached workspace if available
        self.load_cached_workspace()
    
    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("InfiniteDiffer")
        self.setMinimumSize(DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)
        
        # Main widget and layout
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)
        
        # Create toolbar
        toolbar = QToolBar()
        self.addToolBar(toolbar)
        
        # Add file actions
        add_file_action = QAction("Add File", self)
        add_file_action.triggered.connect(self.add_file)
        toolbar.addAction(add_file_action)
        
        add_text_action = QAction("Add Text", self)
        add_text_action.triggered.connect(self.add_text)
        toolbar.addAction(add_text_action)
        
        toolbar.addSeparator()
        
        # Add comparison actions
        compare_action = QAction("Compare Multiple", self)
        compare_action.triggered.connect(lambda: self.create_multi_diff_tab())
        toolbar.addAction(compare_action)
        
        toolbar.addSeparator()
        
        # Add cache toggle checkbox
        cache_label = QLabel("Cache Text: ")
        toolbar.addWidget(cache_label)
        
        self.cache_checkbox = QCheckBox()
        self.cache_checkbox.setChecked(ENABLE_CACHING)  # Use global setting
        self.cache_checkbox.stateChanged.connect(self.toggle_caching)
        toolbar.addWidget(self.cache_checkbox)
        
        toolbar.addSeparator()
        
        # Add color configuration
        self.addition_color_button = ColorButton(HIGHLIGHT_COLORS["addition"])
        self.addition_color_button.color_changed.connect(self.update_addition_color)
        toolbar.addWidget(QLabel("Addition: "))
        toolbar.addWidget(self.addition_color_button)
        
        self.deletion_color_button = ColorButton(HIGHLIGHT_COLORS["deletion"])
        self.deletion_color_button.color_changed.connect(self.update_deletion_color)
        toolbar.addWidget(QLabel("Deletion: "))
        toolbar.addWidget(self.deletion_color_button)
        
        toolbar.addSeparator()
        
        # Base selector
        self.base_selector = QComboBox()
        self.base_selector.setMinimumWidth(150)
        self.base_selector.currentIndexChanged.connect(self.update_diff_view)
        toolbar.addWidget(QLabel("Base: "))
        toolbar.addWidget(self.base_selector)
        
        toolbar.addSeparator()
        
        # Diff view area
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.setMovable(True)  # Enable tab reordering
        
        # Create welcome widget
        self.welcome_widget = WelcomeWidget()
        
        # Create stack widget to show either tabs or welcome widget
        self.stack = QStackedWidget()
        self.stack.addWidget(self.welcome_widget)  # Index 0: Welcome widget
        self.stack.addWidget(self.tabs)           # Index 1: Tabs widget
        
        # Show welcome widget by default
        self.stack.setCurrentIndex(0)
        
        # Create main splitter
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self.stack)
        
        # Add source views panel at the bottom
        self.source_panel = QTabWidget()
        self.source_panel.setTabsClosable(True)
        self.source_panel.tabCloseRequested.connect(self.remove_source)
        self.source_panel.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.source_panel.customContextMenuRequested.connect(self.source_context_menu)
        splitter.addWidget(self.source_panel)
        
        # Set initial splitter sizes (70% top, 30% bottom)
        splitter.setSizes([int(DEFAULT_WINDOW_HEIGHT * 0.7), int(DEFAULT_WINDOW_HEIGHT * 0.3)])
        
        main_layout.addWidget(splitter)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
        
        self.setCentralWidget(central_widget)
        
        # Create the special first tab that shows all sources
        self.all_sources_tab_index = -1  # Will be set when created
        self.create_all_sources_tab()
    
    def create_all_sources_tab(self):
        """Create a special tab that shows all text sources and updates automatically."""
        if len(self.diff_manager.sources) < 2:
            # Can't create multi-diff with less than 2 sources
            return
            
        # Get indices of all sources
        all_indices = list(range(len(self.diff_manager.sources)))
        
        # Create the tab
        multi_diff = MultiDiffView(self.diff_manager, all_indices, self)
        multi_diff.setProperty("is_auto_sources", True)
        
        # Generate tab name
        tab_name = "All Sources"
        
        # If the all sources tab already exists, update it
        if self.all_sources_tab_index >= 0 and self.all_sources_tab_index < self.tabs.count():
            # Replace the existing tab
            self.tabs.removeTab(self.all_sources_tab_index)
            self.tabs.insertTab(self.all_sources_tab_index, multi_diff, tab_name)
            self.tabs.setCurrentIndex(self.all_sources_tab_index)
        else:
            # Add as first tab
            self.tabs.insertTab(0, multi_diff, tab_name)
            self.all_sources_tab_index = 0
            self.tabs.setCurrentIndex(0)
        
        # Make sure tabs are shown instead of welcome widget
        self.stack.setCurrentIndex(1)
    
    def update_all_sources_tab(self):
        """Update the all sources tab to include all current sources."""
        # Check if we should create or update the all sources tab
        if len(self.diff_manager.sources) >= 2:
            if self.all_sources_tab_index >= 0:
                # Update existing tab
                all_indices = list(range(len(self.diff_manager.sources)))
                tab = self.tabs.widget(self.all_sources_tab_index)
                
                # If this is a MultiDiffView, update it
                if isinstance(tab, MultiDiffView) and hasattr(tab, 'source_indices'):
                    tab.source_indices = all_indices
                    tab.update_diff()
                else:
                    # Recreate the tab if it's not a proper MultiDiffView
                    self.create_all_sources_tab()
            else:
                # Create new tab
                self.create_all_sources_tab()
        elif self.all_sources_tab_index >= 0:
            # Remove the tab if we have fewer than 2 sources
            self.tabs.removeTab(self.all_sources_tab_index)
            self.all_sources_tab_index = -1
        
        # Make sure tabs are shown instead of welcome widget
        self.stack.setCurrentIndex(1)
    
    def load_cached_workspace(self):
        """Load cached workspace data from file."""
        # Always load color settings
        self.load_color_settings()
        
        if not self.caching_enabled or not os.path.exists(CACHE_FILENAME):
            return
            
        try:
            with open(CACHE_FILENAME, 'rb') as f:
                cache_data = pickle.load(f)
            
            # Restore window position and size if available
            if 'window_geometry' in cache_data:
                geometry = cache_data['window_geometry']
                if len(geometry) == 4:  # x, y, width, height
                    self.setGeometry(*geometry)
            
            # Clear existing sources before loading
            while len(self.diff_manager.sources) > 0:
                self.remove_source_internal(0, update_ui=False)
            
            # Restore text sources
            if 'sources' in cache_data:
                for source_data in cache_data['sources']:
                    source = TextSource(
                        source_data['name'], 
                        source_data['content'],
                        QColor(source_data['color']) if 'color' in source_data else None
                    )
                    self.add_source(source)
            
            self.statusBar().showMessage("Workspace loaded from cache", 3000)
        except Exception as e:
            print(f"Error loading workspace cache: {e}")
    
    def load_color_settings(self):
        """Load color settings from file."""
        if not os.path.exists(COLORS_FILENAME):
            return
            
        try:
            with open(COLORS_FILENAME, 'r') as f:
                color_data = json.load(f)
                
            # * Restore highlight colors
            for key, value in color_data.items():
                if key in HIGHLIGHT_COLORS:
                    HIGHLIGHT_COLORS[key] = QColor(value)
                    
            # Update color buttons
            if hasattr(self, 'addition_color_button'):
                self.addition_color_button.set_color(HIGHLIGHT_COLORS["addition"])
            if hasattr(self, 'deletion_color_button'):
                self.deletion_color_button.set_color(HIGHLIGHT_COLORS["deletion"])
        except Exception as e:
            print(f"Error loading color settings: {e}")
    
    def save_cached_workspace(self):
        """Save workspace data to cache file."""
        # Always save color settings
        self.save_color_settings()
        
        if not self.caching_enabled:
            return
            
        try:
            cache_data = {
                'sources': [],
                'window_geometry': [self.x(), self.y(), self.width(), self.height()]
            }
            
            # Save text sources
            for source in self.diff_manager.sources:
                cache_data['sources'].append({
                    'name': source.name,
                    'content': source.content,
                    'color': source.color.name()
                })
            
            with open(CACHE_FILENAME, 'wb') as f:
                pickle.dump(cache_data, f)
        except Exception as e:
            print(f"Error saving workspace cache: {e}")
    
    def save_color_settings(self):
        """Save color settings to file."""
        try:
            color_data = {}
            
            # Save highlight colors
            for key, color in HIGHLIGHT_COLORS.items():
                color_data[key] = color.name()
            
            with open(COLORS_FILENAME, 'w') as f:
                json.dump(color_data, f, indent=2)
        except Exception as e:
            print(f"Error saving color settings: {e}")
    
    def closeEvent(self, event):
        """Handle window close event."""
        self.save_cached_workspace()
        event.accept()
        
    def signal_handler(self, sig, frame):
        """Handle interrupt signals (Ctrl+C).
        
        Saves the current workspace and exits the application cleanly.
        
        Args:
            sig: Signal number
            frame: Current stack frame
        """
        print("\nReceived interrupt signal. Saving workspace and exiting...")
        self.save_color_settings()  # * Always save color settings
        self.save_cached_workspace()
        QApplication.quit()
        
    def add_file(self):
        """Add a text source from a file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Text File", "", "Text Files (*.txt);;All Files (*)"
        )
        
        if not file_path:
            return
            
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
                
            file_name = os.path.basename(file_path)
            self.add_source(TextSource(file_name, content))
            self.status_bar.showMessage(f"Added file: {file_name}")
            
        except Exception as e:
            self.status_bar.showMessage(f"Error opening file: {str(e)}")
            
    def add_text(self):
        """Add a text source from manual input."""
        source_name = f"Source {len(self.diff_manager.sources) + 1}"
        source = TextSource(source_name, "")
        
        # Add empty source first
        source_index = self.add_source(source)
        
        # Create and focus the editor
        text_edit = self.source_panel.widget(source_index)
        if text_edit:
            text_edit.setFocus()
            
    def add_source(self, source: TextSource) -> int:
        """Add a new text source.
        
        Args:
            source: The text source to add
            
        Returns:
            Index of the added source
        """
        if len(self.diff_manager.sources) >= MAX_TEXT_SOURCES:
            self.status_bar.showMessage(f"Maximum of {MAX_TEXT_SOURCES} sources reached")
            return -1
            
        # Add to manager
        source_index = self.diff_manager.add_source(source)
        
        if source_index >= 0:
            # Create source view
            text_edit = QTextEdit()
            text_edit.setPlainText(source.content)
            text_edit.textChanged.connect(lambda: self.update_source_content(source_index))
            
            # Create a colored tab for the source panel
            self.source_panel.addTab(text_edit, source.name)
            
            # Set tab color in the source panel
            self.set_tab_color(self.source_panel, self.source_panel.count() - 1, source.color)
            
            # Update base selector
            self.base_selector.blockSignals(True)
            self.base_selector.addItem(source.name)
            self.base_selector.setItemData(self.base_selector.count() - 1, source_index)
            self.base_selector.blockSignals(False)
            
            # Update selectors
            self.update_selectors()
            
            # If at least 2 sources, update diffs
            if len(self.diff_manager.sources) >= 2:
                # Update the all sources tab
                self.update_all_sources_tab()
                
                # Update other existing tabs
                self.update_all_diff_views()
                
                # Make sure tabs are shown instead of welcome widget
                self.stack.setCurrentIndex(1)
            
            self.status_bar.showMessage(f"Added source: {source.name}")
            
            # Update cache
            self.save_cached_workspace()
        
        return source_index
    
    def set_tab_color(self, tab_widget: QTabWidget, tab_index: int, color: QColor):
        """Set the background color of a tab.
        
        Args:
            tab_widget: The tab widget
            tab_index: Index of the tab
            color: Color to set
        """
        if tab_index < 0 or tab_index >= tab_widget.count():
            return
        
        # Store color in tab data
        tab_widget.tabBar().setTabData(tab_index, color)
        
        # Set the tab style for all tabs
        self.update_tab_styles(tab_widget)
    
    def update_tab_styles(self, tab_widget):
        """Update styles for all tabs in a tab widget.
        
        Args:
            tab_widget: The tab widget to update
        """
        tab_bar = tab_widget.tabBar()
        style_sheet = ""
        
        # Create style for each tab
        for i in range(tab_widget.count()):
            tab_data = tab_bar.tabData(i)
            if tab_data and isinstance(tab_data, QColor):
                tab_color = tab_data
                
                # Calculate brightness for text color
                brightness = (tab_color.red() * 299 + tab_color.green() * 587 + tab_color.blue() * 114) / 1000
                text_color = "black" if brightness > 128 else "white"
                
                # Add style for this tab
                style_sheet += f"""
                QTabBar::tab:!selected:nth({i}) {{
                    background-color: {tab_color.name()};
                    color: {text_color};
                    border: 1px solid #555;
                    border-bottom: none;
                    border-top-left-radius: 4px;
                    border-top-right-radius: 4px;
                    padding: 3px;
                }}
                QTabBar::tab:selected:nth({i}) {{
                    background-color: {tab_color.name()};
                    color: {text_color};
                    border: 1px solid #555;
                    border-bottom: none;
                    border-top-left-radius: 4px;
                    border-top-right-radius: 4px;
                    font-weight: bold;
                    padding: 3px;
                }}
                """
        
        if style_sheet:
            tab_bar.setStyleSheet(style_sheet)
    
    def source_context_menu(self, point):
        """Show context menu for source tabs.
        
        Args:
            point: Click position
        """
        # Get the tab under the point
        tab_bar = self.source_panel.tabBar()
        tab_index = tab_bar.tabAt(point)
        
        if tab_index >= 0:
            # Create context menu
            menu = QMenu(self)
            
            # Add color picker action
            color_action = QAction("Change Color", self)
            color_action.triggered.connect(lambda: self.change_source_color(tab_index))
            menu.addAction(color_action)
            
            # Add rename action
            rename_action = QAction("Rename", self)
            rename_action.triggered.connect(lambda: self.rename_source(tab_index))
            menu.addAction(rename_action)
            
            # Add separator
            menu.addSeparator()
            
            # Add close action
            close_action = QAction("Close", self)
            close_action.triggered.connect(lambda: self.remove_source(tab_index))
            menu.addAction(close_action)
            
            # Show menu
            menu.exec(tab_bar.mapToGlobal(point))
    
    def change_source_color(self, source_index: int):
        """Change the color of a text source.
        
        Args:
            source_index: Index of the source
        """
        if source_index < 0 or source_index >= len(self.diff_manager.sources):
            return
            
        # Get current color
        current_color = self.diff_manager.sources[source_index].color
        
        # Show color picker dialog
        color = QColorDialog.getColor(current_color, self, "Choose Source Color")
        
        if color.isValid():
            # Update the source color
            self.diff_manager.sources[source_index].color = color
            
            # Update highlight colors map
            if source_index < 5:  # We only have 5 predefined source colors
                HIGHLIGHT_COLORS[f"source{source_index + 1}"] = color.lighter(130)
            
            # Update the tab color
            self.set_tab_color(self.source_panel, source_index, color)
            
            # Update all diff views
            self.update_all_diff_views()
            
            # Update cache
            self.save_cached_workspace()
    
    def rename_source(self, source_index: int):
        """Rename a text source.
        
        Args:
            source_index: Index of the source
        """
        if source_index < 0 or source_index >= len(self.diff_manager.sources):
            return
            
        # Get current name
        current_name = self.diff_manager.sources[source_index].name
        
        # Show input dialog
        new_name, ok = QInputDialog.getText(self, "Rename Source", "Enter new name:", text=current_name)
        
        if ok and new_name:
            # Update the source name
            self.diff_manager.sources[source_index].name = new_name
            
            # Update tab text
            self.source_panel.setTabText(source_index, new_name)
            
            # Update base selector
            self.base_selector.setItemText(source_index, new_name)
            
            # Update all diff views
            self.update_all_diff_views()
            
            # Update cache
            self.save_cached_workspace()
    
    def update_source_content(self, source_index: int):
        """Update the content of a text source when edited.
        
        Args:
            source_index: Index of the source to update
        """
        if source_index < 0 or source_index >= len(self.diff_manager.sources):
            return
            
        # Get the updated content from the text edit
        text_edit = self.source_panel.widget(source_index)
        if not text_edit:
            return
            
        new_content = text_edit.toPlainText()
        
        # Update the source
        self.diff_manager.sources[source_index].update_content(new_content)
        
        # Update all diff views
        self.update_all_diff_views()
        
        # Update cache
        self.save_cached_workspace()
    
    def update_selectors(self):
        """Update the source selectors with current sources."""
        # Remember current selection
        current_base = self.base_selector.currentIndex()
        
        # Update base selector
        self.base_selector.clear()
        for i, source in enumerate(self.diff_manager.sources):
            self.base_selector.addItem(source.name)
            self.base_selector.setItemData(self.base_selector.count() - 1, i)
            
        # Restore selection if possible
        if current_base >= 0 and current_base < self.base_selector.count():
            self.base_selector.setCurrentIndex(current_base)
        elif self.base_selector.count() > 0:
            self.base_selector.setCurrentIndex(0)
    
    def create_diff_tab(self, base_index: int, compare_index: int):
        """Create a new diff tab comparing two sources.
        
        Args:
            base_index: Index of the base source
            compare_index: Index of the source to compare against
        """
        if not (0 <= base_index < len(self.diff_manager.sources) and 
                0 <= compare_index < len(self.diff_manager.sources)):
            return
            
        base = self.diff_manager.sources[base_index]
        compare = self.diff_manager.sources[compare_index]
        
        # Create container widget and layout
        container = QWidget()
        layout = QVBoxLayout(container)
        
        # Create diff display
        diff_edit = DiffTextEdit()
        layout.addWidget(diff_edit)
        
        # Calculate and display diff
        diff_lines = self.diff_manager.get_diff(base_index, compare_index)
        diff_edit.highlight_text(diff_lines)
        
        # Add tag with indices for later reference
        container.setProperty("base_index", base_index)
        container.setProperty("compare_index", compare_index)
        container.setProperty("is_multi_diff", False)
        
        # Add to tabs
        tab_name = f"{base.name} ↔ {compare.name}"
        self.tabs.addTab(container, tab_name)
        self.tabs.setCurrentIndex(self.tabs.count() - 1)
        
        # Make sure tabs are shown instead of welcome widget
        self.stack.setCurrentIndex(1)
    
    def create_multi_diff_tab(self, source_indices=None):
        """Create a new diff tab comparing multiple sources.
        
        Args:
            source_indices: Optional list of source indices to use.
                If None, a dialog will be shown to select sources.
        """
        if len(self.diff_manager.sources) < 2:
            self.status_bar.showMessage("Need at least two sources to compare")
            return
        
        # If source indices not provided, show selection dialog
        if source_indices is None:
            # Show source selection dialog
            dialog = SourceSelectionDialog(self.diff_manager.sources, self)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
                
            # Get selected sources
            source_indices = dialog.get_selected_sources()
            
        if len(source_indices) < 2:
            self.status_bar.showMessage("Need at least two sources to compare")
            return
            
        # Create multi-diff view
        multi_diff = MultiDiffView(self.diff_manager, source_indices, self)
        
        # Generate tab name
        source_names = multi_diff.get_source_names()
        if len(source_names) <= 3:
            tab_name = " ↔ ".join(source_names)
        else:
            tab_name = f"{source_names[0]} ↔ ... ({len(source_names)} sources)"
            
        # Add to tabs
        self.tabs.addTab(multi_diff, tab_name)
        self.tabs.setCurrentIndex(self.tabs.count() - 1)
        
        # Make sure tabs are shown instead of welcome widget
        self.stack.setCurrentIndex(1)
    
    def update_diff_view(self):
        """Update the current diff view."""
        current_tab = self.tabs.currentWidget()
        if not current_tab:
            return
        
        is_multi_diff = current_tab.property("is_multi_diff")
        
        if is_multi_diff:
            # Update multi-diff view
            multi_diff = current_tab.findChild(MultiDiffView)
            if multi_diff:
                multi_diff.update_diff()
        else:
            # Update regular diff view
            base_index = current_tab.property("base_index")
            compare_index = current_tab.property("compare_index")
            
            if base_index is None or compare_index is None:
                return
                
            diff_edit = current_tab.findChild(DiffTextEdit)
            if not diff_edit:
                return
                
            diff_lines = self.diff_manager.get_diff(base_index, compare_index)
            diff_edit.highlight_text(diff_lines)
        
    def update_all_diff_views(self):
        """Update all diff views."""
        # First, handle the special "All Sources" tab
        if self.all_sources_tab_index >= 0 and self.all_sources_tab_index < self.tabs.count():
            self.update_all_sources_tab()
        
        # Update other tabs
        for i in range(self.tabs.count()):
            # Skip the "All Sources" tab as it's already updated
            if i == self.all_sources_tab_index:
                continue
                
            tab = self.tabs.widget(i)
            
            if isinstance(tab, MultiDiffView):
                tab.update_diff()
            else:
                # For regular diff tabs
                base_index = -1
                compare_index = -1
                
                # Try to get properties directly
                if hasattr(tab, 'base_index') and hasattr(tab, 'compare_index'):
                    base_index = tab.base_index
                    compare_index = tab.compare_index
                else:
                    # Fallback to widget properties
                    base_index = tab.property("base_index")
                    compare_index = tab.property("compare_index")
                
                if base_index >= 0 and compare_index >= 0:
                    # Create new diff data
                    diff_lines = self.diff_manager.get_diff(base_index, compare_index)
                    
                    # Update the diff view
                    diff_edit = tab.findChild(DiffTextEdit)
                    if diff_edit:
                        diff_edit.highlight_text(diff_lines)
        
    def close_tab(self, index: int):
        """Close a diff tab.
        
        Args:
            index: Index of the tab to close
        """
        self.tabs.removeTab(index)
        
        # If no tabs left, show welcome widget
        if self.tabs.count() == 0:
            self.stack.setCurrentIndex(0)
        
        # Update cache when tab is closed
        self.save_cached_workspace()
        
    def remove_source(self, index: int):
        """Remove a text source and update the UI.
        
        Args:
            index: Index of the source to remove
        """
        self.remove_source_internal(index, update_ui=True)
        
        # Update cache
        self.save_cached_workspace()
    
    def remove_source_internal(self, index: int, update_ui=True):
        """Remove a text source with options to update the UI.
        
        Args:
            index: Index of the source to remove
            update_ui: Whether to update the UI after removing
        """
        if index < 0 or index >= len(self.diff_manager.sources):
            return
        
        # Get the source name for messaging
        source_name = self.diff_manager.sources[index].name
        
        # Remove from manager
        if self.diff_manager.remove_source(index):
            if update_ui:
                # Remove from source panel
                self.source_panel.removeTab(index)
                
                # Update base selector
                self.base_selector.blockSignals(True)
                for i in range(self.base_selector.count()):
                    if self.base_selector.itemData(i) == index:
                        self.base_selector.removeItem(i)
                        break
                
                # Update selectors
                self.update_selectors()
                
                # Close tabs that use this source
                for i in range(self.tabs.count() - 1, -1, -1):
                    tab = self.tabs.widget(i)
                    
                    if isinstance(tab, MultiDiffView):
                        source_indices = tab.get_source_indices()
                        if index in source_indices:
                            if i == self.all_sources_tab_index:
                                # Don't remove the all sources tab, it will be updated
                                continue
                            self.tabs.removeTab(i)
                            if i < self.all_sources_tab_index:
                                self.all_sources_tab_index -= 1
                    elif hasattr(tab, 'base_index') and hasattr(tab, 'compare_index'):
                        if tab.base_index == index or tab.compare_index == index:
                            self.tabs.removeTab(i)
                            if i < self.all_sources_tab_index:
                                self.all_sources_tab_index -= 1
                
                # Update the all sources tab
                self.update_all_sources_tab()
                
                # Update other diff views
                self.update_all_diff_views()
                
                self.status_bar.showMessage(f"Removed source: {source_name}")
        
    def contextMenuEvent(self, event):
        """Handle context menu events.
        
        Args:
            event: Context menu event
        """
        context_menu = QMenu(self)
        
        add_file_action = context_menu.addAction("Add File")
        add_file_action.triggered.connect(self.add_file)
        
        add_text_action = context_menu.addAction("Add Text")
        add_text_action.triggered.connect(self.add_text)
        
        if len(self.diff_manager.sources) >= 2:
            context_menu.addSeparator()
            
            multi_compare_action = context_menu.addAction("Compare Multiple...")
            multi_compare_action.triggered.connect(self.create_multi_diff_tab)
            
            context_menu.addSeparator()
            compare_menu = context_menu.addMenu("Compare Two")
            
            for i, source1 in enumerate(self.diff_manager.sources):
                for j, source2 in enumerate(self.diff_manager.sources):
                    if i != j:
                        action = compare_menu.addAction(f"{source1.name} ↔ {source2.name}")
                        action.triggered.connect(lambda checked, s1=i, s2=j: self.create_diff_tab(s1, s2))
        
        context_menu.exec(event.globalPos())

    def update_addition_color(self, color):
        """Update the global highlight color for additions.
        
        Args:
            color: New color
        """
        HIGHLIGHT_COLORS["addition"] = color
        self.update_all_diff_views()
        self.save_color_settings()
    
    def update_deletion_color(self, color):
        """Update the global highlight color for deletions.
        
        Args:
            color: New color
        """
        HIGHLIGHT_COLORS["deletion"] = color
        self.update_all_diff_views()
        self.save_color_settings()
    
    def toggle_caching(self, state):
        """Toggle caching on/off.
        
        Args:
            state: Checkbox state
        """
        self.caching_enabled = state == Qt.CheckState.Checked.value
        
        if self.caching_enabled:
            self.save_cached_workspace()
        else:
            # ! Remove cache file if it exists
            if os.path.exists(CACHE_FILENAME):
                try:
                    os.remove(CACHE_FILENAME)
                except:
                    pass
            
            # * Still save color settings
            self.save_color_settings()


def main():
    """Main entry point for the application.
    
    Initializes the application, sets up signal handling, and starts the event loop.
    Ensures proper cleanup on application exit.
    
    Returns:
        int: Application exit code.
    """
    # Create application
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle("Fusion")
    
    # Create main window
    window = InfiniteDifferApp()
    window.show()
    
    # Set up signal handler for clean termination
    # Note: This is handled in InfiniteDifferApp.__init__
    
    # Start the event loop
    try:
        return app.exec()
    except KeyboardInterrupt:
        # Handle Ctrl+C gracefully
        print("\nExiting due to keyboard interrupt...")
        window.save_color_settings()  # Always save color settings
        window.save_cached_workspace()
        return 0


if __name__ == "__main__":
    sys.exit(main())

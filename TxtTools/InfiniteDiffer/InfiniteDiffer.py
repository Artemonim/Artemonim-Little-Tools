#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
InfiniteDiffer: A tool for comparing multiple text files simultaneously.

This application provides a Git-like diff visualization for more than two text sources
at the same time, highlighting additions, deletions, and modifications across files.
"""

import sys
import os
import difflib
import signal
from typing import List, Dict, Tuple, Optional, Set, Any
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QTextEdit, QLabel, QFileDialog, QScrollArea,
    QSplitter, QTabWidget, QToolBar, QStatusBar, QComboBox, QMenu,
    QGridLayout, QFrame, QSizePolicy, QCheckBox, QDialogButtonBox,
    QDialog, QListWidget, QListWidgetItem, QLineEdit, QToolTip
)
from PyQt6.QtGui import (
    QTextCharFormat, QColor, QTextCursor, QPalette, 
    QAction, QIcon, QFont, QTextDocument, QPainter, QFontMetrics
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QRect, QPoint

# Configuration variables
MAX_TEXT_SOURCES = 10  # Maximum number of text sources to compare
DEFAULT_WINDOW_WIDTH = 1200
DEFAULT_WINDOW_HEIGHT = 800
DEFAULT_FONT_FAMILY = "Consolas"
DEFAULT_FONT_SIZE = 10
HIGHLIGHT_COLORS = {
    "addition": QColor(205, 255, 205),  # Light green
    "deletion": QColor(255, 205, 205),  # Light red
    "modification": QColor(255, 255, 205),  # Light yellow
    "same": QColor(255, 255, 255),  # White
    "source1": QColor(230, 130, 255),  # Light blue
    "source2": QColor(255, 130, 255),  # Light purple
    "source3": QColor(255, 155, 230),  # Light yellow
    "source4": QColor(230, 155, 255),  # Light cyan
    "source5": QColor(255, 140, 230),  # Light orange
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
        
        # Search input
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search...")
        self.search_input.textChanged.connect(self.update_search)
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
        
        # Set fixed size for buttons
        for button in [self.up_button, self.down_button, self.count_button]:
            button.setFixedSize(30, 30)
        
        # Store the last search position
        self.last_search_position = 0
        
        # Set initial visibility
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
        parent = self.parent()
        while parent and not isinstance(parent, QMainWindow):
            parent = parent.parent()
        
        if parent and isinstance(parent, QMainWindow):
            parent.statusBar().showMessage(f"Found {count} occurrences of '{search_text}'", 3000)
        else:
            # If we can't find the main window, just create a temporary tooltip
            QToolTip.showText(self.count_button.mapToGlobal(QPoint(0, 30)), 
                             f"Found {count} occurrences", 
                             self.count_button, 
                             QRect(), 3000)


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
        
        # Initialize search widget
        self.search_widget = SearchWidget(self, self)
        
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
    
    def resizeEvent(self, event):
        """Handle resize events.
        
        Args:
            event: The resize event
        """
        super().resizeEvent(event)
        
        cr = self.contentsRect()
        self.line_number_area.setGeometry(QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height()))
        
        # Position search widget in top right
        self.search_widget.setGeometry(
            cr.right() - self.search_widget.sizeHint().width() - 10,
            cr.top() + 10,
            self.search_widget.sizeHint().width(),
            self.search_widget.sizeHint().height()
        )
    
    def toggle_search(self):
        """Toggle the visibility of the search widget."""
        if self.search_widget.isVisible():
            self.search_widget.hide_search()
        else:
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
        painter.fillRect(event.rect(), QColor(240, 240, 240))
        
        # Get the top and bottom y-coordinates of the visible text
        contents_rect = self.viewport().contentsRect()
        scroll_y = self.verticalScrollBar().value()
        page_bottom = scroll_y + contents_rect.height()
        
        # Initialize font metrics for measurements
        font_metrics = QFontMetrics(self.font())
        line_height = font_metrics.lineSpacing()
        
        # Calculate the first visible line number
        first_visible_line = max(1, int(scroll_y / line_height) + 1)
        
        # Calculate how many lines can fit in the viewport
        visible_lines = min(self.document().blockCount(), int(contents_rect.height() / line_height) + 2)
        
        # Draw line numbers
        top = contents_rect.top() - (scroll_y % line_height)
        for i in range(visible_lines):
            line_number = first_visible_line + i
            if line_number > self.document().blockCount():
                break
                
            painter.setPen(QColor(120, 120, 120))
            painter.drawText(0, top + i * line_height, 
                            self.line_number_area.width() - 2, 
                            line_height,
                            Qt.AlignmentFlag.AlignRight, 
                            str(line_number))
    
    def highlight_text(self, diff_lines: List[Tuple[str, str]]):
        """Highlight diff text based on status (addition, deletion, modification, same).
        
        Args:
            diff_lines: List of tuples containing (line_text, status)
        """
        self.clear()
        text_cursor = self.textCursor()
        text_cursor.movePosition(QTextCursor.MoveOperation.Start)
        
        for line, status in diff_lines:
            format_text = QTextCharFormat()
            
            if status in HIGHLIGHT_COLORS:
                format_text.setBackground(HIGHLIGHT_COLORS[status])
            
            # Set text color to black
            format_text.setForeground(QColor(0, 0, 0))
            
            # Insert text with formatting
            text_cursor.insertText(line, format_text)
            text_cursor.insertBlock()
            
        self.setTextCursor(text_cursor)

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
        
        # Process the diff data to implement the new highlighting logic
        expanded_diff_data = []
        
        for line, statuses, sources in diff_data:
            # Check if text is unchanged in all sources (no highlighting)
            if all(status == "same" for status in statuses):
                format_text = QTextCharFormat()
                # No highlighting for unchanged text
                text_cursor.insertText(line, format_text)
                text_cursor.insertBlock()
                continue
                
            # Standard git diff green: added in all sources except the first
            if sources and 0 not in sources and len(sources) == len(statuses) - 1:
                format_text = QTextCharFormat()
                format_text.setBackground(HIGHLIGHT_COLORS["addition"])  # Standard green
                text_cursor.insertText(line, format_text)
                text_cursor.insertBlock()
                continue
                
            # Standard git diff red: removed from all sources except the first
            if sources and len(sources) == 1 and 0 in sources and len(sources) < len(statuses):
                format_text = QTextCharFormat()
                format_text.setBackground(HIGHLIGHT_COLORS["deletion"])  # Standard red
                text_cursor.insertText(line, format_text)
                text_cursor.insertBlock()
                continue
                
            # For added/modified text in specific sources, show once per source with that source's color
            if len(sources) < len(statuses):
                shown = False
                
                for src_idx in sources:
                    format_text = QTextCharFormat()
                    source_color_key = f"source{src_idx + 1}" if 0 <= src_idx < 5 else "addition"
                    
                    if source_color_key in HIGHLIGHT_COLORS:
                        format_text.setBackground(HIGHLIGHT_COLORS[source_color_key])
                    
                    # If text is deleted in this source, underline it
                    if "deletion" in statuses:
                        format_text.setFontUnderline(True)
                    
                    # Insert source indicator at the beginning
                    source_indicator = f"[S{src_idx + 1}] "
                    source_format = QTextCharFormat()
                    source_format.setForeground(QColor(100, 100, 100))  # Gray text
                    text_cursor.insertText(source_indicator, source_format)
                    
                    # Insert the line with appropriate formatting
                    text_cursor.insertText(line, format_text)
                    text_cursor.insertBlock()
                    shown = True
                
                # If we've shown this line for at least one source, continue to the next line
                if shown:
                    continue
            
            # Default case: just show the line with basic formatting
            format_text = QTextCharFormat()
            if len(sources) < len(statuses):
                # Only some sources have this line
                format_text.setBackground(HIGHLIGHT_COLORS["addition"])
            text_cursor.insertText(line, format_text)
            text_cursor.insertBlock()
        
        self.setTextCursor(text_cursor)


class TextSource:
    """Represents a source of text for comparison."""
    
    def __init__(self, name: str = "", content: str = ""):
        """Initialize a text source.
        
        Args:
            name: Name or identifier for the text source
            content: Text content to compare
        """
        self.name = name
        self.content = content
        self.lines = content.splitlines() if content else []


class DiffManager:
    """Handles the diff calculations between multiple text sources."""
    
    def __init__(self):
        """Initialize the diff manager."""
        self.sources: List[TextSource] = []
        
    def add_source(self, source: TextSource) -> int:
        """Add a text source for comparison.
        
        Args:
            source: The text source to add
            
        Returns:
            Index of the added source
        """
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
        
        Args:
            base_index: Index of the base text source
            compare_index: Index of the text source to compare against
            
        Returns:
            List of (line, status) tuples where status is 'addition', 'deletion', 
            'modification', or 'same'
        """
        if not (0 <= base_index < len(self.sources) and 0 <= compare_index < len(self.sources)):
            return []
        
        base = self.sources[base_index]
        compare = self.sources[compare_index]
        
        # Use Python's difflib to calculate diff
        differ = difflib.Differ()
        diff = list(differ.compare(base.lines, compare.lines))
        result = []
        
        for line in diff:
            if line.startswith('+ '):
                result.append((line[2:], "addition"))
            elif line.startswith('- '):
                result.append((line[2:], "deletion"))
            elif line.startswith('? '):
                # Skip diff control lines
                continue
            else:
                # Line starting with '  ' is unchanged
                result.append((line[2:], "same"))
                
        return result
    
    def get_multi_diff(self, source_indices: List[int]) -> List[Tuple[str, List[str], List[int]]]:
        """Calculate diff between multiple text sources.
        
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
        
        # Get all unique lines from all sources
        all_lines = set()
        for idx in source_indices:
            all_lines.update(self.sources[idx].lines)
        
        # Create a mapping of each line to the sources it appears in
        line_sources = {}
        for line in all_lines:
            line_sources[line] = []
            for i, idx in enumerate(source_indices):
                if line in self.sources[idx].lines:
                    line_sources[line].append(i)
        
        # Create a set of all lines for each source
        source_lines = []
        for idx in source_indices:
            source_lines.append(set(self.sources[idx].lines))
        
        # Calculate multi-diff
        result = []
        
        # First, add lines from the base source
        base_idx = source_indices[0]
        base_lines = self.sources[base_idx].lines
        
        # Sort lines based on their order in the base source, then add other unique lines
        sorted_lines = list(base_lines)
        
        # Add lines that don't appear in the base source
        # This is a simple approach; for more complex diffs we'd need a more sophisticated algorithm
        for line in all_lines:
            if line not in sorted_lines:
                sorted_lines.append(line)
        
        # Generate the diff data
        for line in sorted_lines:
            sources_with_line = line_sources.get(line, [])
            
            statuses = []
            for i in range(len(source_indices)):
                if i in sources_with_line:
                    if len(sources_with_line) == len(source_indices):
                        # Line is in all sources
                        statuses.append("same")
                    else:
                        # Line is in some but not all sources
                        statuses.append("addition")
                else:
                    # Line is not in this source
                    statuses.append("deletion")
            
            # Convert source indices from local (0-based within source_indices) 
            # to global (indices in source_indices)
            global_sources = [source_indices[i] for i in sources_with_line]
            
            result.append((line, statuses, global_sources))
        
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
                color_key = f"source{i+1}"
                
                indicator = QFrame()
                indicator.setFrameShape(QFrame.Shape.Box)
                indicator.setFixedSize(16, 16)
                
                if color_key in HIGHLIGHT_COLORS:
                    indicator.setStyleSheet(f"background-color: {HIGHLIGHT_COLORS[color_key].name()};")
                
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


class InfiniteDifferApp(QMainWindow):
    """Main application window for InfiniteDiffer."""
    
    def __init__(self):
        """Initialize the main application window."""
        super().__init__()
        
        # Set up diff manager
        self.diff_manager = DiffManager()
        
        # Set up UI
        self.init_ui()
        
        # Connect signal handlers for clean exit
        signal.signal(signal.SIGINT, self.signal_handler)
        
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
        compare_action.triggered.connect(self.create_multi_diff_tab)
        toolbar.addAction(compare_action)
        
        toolbar.addSeparator()
        
        # Comparison source selector
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
        
        # Create main splitter
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self.tabs)
        
        # Add source views panel at the bottom
        self.source_panel = QTabWidget()
        self.source_panel.setTabsClosable(True)
        self.source_panel.tabCloseRequested.connect(self.remove_source)
        splitter.addWidget(self.source_panel)
        
        # Set initial splitter sizes (70% top, 30% bottom)
        splitter.setSizes([int(DEFAULT_WINDOW_HEIGHT * 0.7), int(DEFAULT_WINDOW_HEIGHT * 0.3)])
        
        main_layout.addWidget(splitter)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
        
        self.setCentralWidget(central_widget)
        
    def signal_handler(self, sig, frame):
        """Handle interrupt signals (Ctrl+C).
        
        Args:
            sig: Signal number
            frame: Current stack frame
        """
        print("\nExiting application...")
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
        """Add a text source to the application.
        
        Args:
            source: The text source to add
            
        Returns:
            Index of the added source
        """
        if len(self.diff_manager.sources) >= MAX_TEXT_SOURCES:
            self.status_bar.showMessage(f"Maximum number of sources ({MAX_TEXT_SOURCES}) reached")
            return -1
            
        source_index = self.diff_manager.add_source(source)
        
        # Create source view
        text_edit = QTextEdit()
        text_edit.setPlainText(source.content)
        text_edit.textChanged.connect(lambda: self.update_source_content(source_index))
        
        # Add to source panel
        self.source_panel.addTab(text_edit, source.name)
        
        # Update selectors
        self.update_selectors()
        
        # If this is the second source, automatically create a diff tab
        if len(self.diff_manager.sources) == 2:
            self.create_diff_tab(0, 1)
            
        return source_index
        
    def update_source_content(self, source_index: int):
        """Update the content of a text source when edited.
        
        Args:
            source_index: Index of the source to update
        """
        if not (0 <= source_index < len(self.diff_manager.sources)):
            return
            
        text_edit = self.source_panel.widget(source_index)
        if text_edit:
            self.diff_manager.sources[source_index].content = text_edit.toPlainText()
            self.diff_manager.sources[source_index].lines = text_edit.toPlainText().splitlines()
            
        # Update all diff views
        self.update_all_diff_views()
        
    def update_selectors(self):
        """Update the source selectors with current sources."""
        # Remember current selection
        current_base = self.base_selector.currentIndex()
        
        # Update base selector
        self.base_selector.clear()
        for source in self.diff_manager.sources:
            self.base_selector.addItem(source.name)
            
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
    
    def create_multi_diff_tab(self):
        """Create a new diff tab comparing multiple sources."""
        if len(self.diff_manager.sources) < 2:
            self.status_bar.showMessage("Need at least two sources to compare")
            return
            
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
        
        # Create container widget and layout
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.addWidget(multi_diff)
        
        # Add tag with source indices for later reference
        container.setProperty("source_indices", source_indices)
        container.setProperty("is_multi_diff", True)
        
        # Generate tab name
        source_names = multi_diff.get_source_names()
        if len(source_names) <= 3:
            tab_name = " ↔ ".join(source_names)
        else:
            tab_name = f"{source_names[0]} ↔ ... ↔ {source_names[-1]} ({len(source_names)})"
            
        # Add to tabs
        self.tabs.addTab(container, tab_name)
        self.tabs.setCurrentIndex(self.tabs.count() - 1)
        
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
        """Update all diff views with current content."""
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            is_multi_diff = tab.property("is_multi_diff")
            
            if is_multi_diff:
                # Update multi-diff view
                multi_diff = tab.findChild(MultiDiffView)
                if multi_diff:
                    multi_diff.update_diff()
                    
                    # Update tab name if source names have changed
                    source_names = multi_diff.get_source_names()
                    if len(source_names) <= 3:
                        tab_name = " ↔ ".join(source_names)
                    else:
                        tab_name = f"{source_names[0]} ↔ ... ↔ {source_names[-1]} ({len(source_names)})"
                    
                    self.tabs.setTabText(i, tab_name)
            else:
                # Update regular diff view
                base_index = tab.property("base_index")
                compare_index = tab.property("compare_index")
                
                if base_index is None or compare_index is None:
                    continue
                    
                diff_edit = tab.findChild(DiffTextEdit)
                if not diff_edit:
                    continue
                    
                diff_lines = self.diff_manager.get_diff(base_index, compare_index)
                diff_edit.highlight_text(diff_lines)
                
                # Update tab name if source names have changed
                if (0 <= base_index < len(self.diff_manager.sources) and 
                    0 <= compare_index < len(self.diff_manager.sources)):
                    base = self.diff_manager.sources[base_index]
                    compare = self.diff_manager.sources[compare_index]
                    tab_name = f"{base.name} ↔ {compare.name}"
                    self.tabs.setTabText(i, tab_name)
        
    def close_tab(self, index: int):
        """Close a diff tab.
        
        Args:
            index: Index of the tab to close
        """
        self.tabs.removeTab(index)
        
    def remove_source(self, index: int):
        """Remove a text source.
        
        Args:
            index: Index of the source to remove
        """
        if not (0 <= index < len(self.diff_manager.sources)):
            return
            
        # Remove source
        self.diff_manager.remove_source(index)
        self.source_panel.removeTab(index)
        
        # Update selectors
        self.update_selectors()
        
        # Remove any diff tabs using this source
        for i in range(self.tabs.count() - 1, -1, -1):
            tab = self.tabs.widget(i)
            is_multi_diff = tab.property("is_multi_diff")
            
            if is_multi_diff:
                # Check if multi-diff uses this source
                source_indices = tab.property("source_indices")
                if source_indices and index in source_indices:
                    self.tabs.removeTab(i)
                else:
                    # Update source indices if needed
                    new_indices = [idx if idx < index else idx - 1 for idx in source_indices if idx != index]
                    tab.setProperty("source_indices", new_indices)
                    
                    # Update the multi-diff view
                    multi_diff = tab.findChild(MultiDiffView)
                    if multi_diff:
                        multi_diff.source_indices = new_indices
                        multi_diff.update_diff()
            else:
                # Check regular diff
                base_index = tab.property("base_index")
                compare_index = tab.property("compare_index")
                
                if base_index == index or compare_index == index:
                    self.tabs.removeTab(i)
                elif base_index > index:
                    tab.setProperty("base_index", base_index - 1)
                elif compare_index > index:
                    tab.setProperty("compare_index", compare_index - 1)
                
        # Update all diff views
        self.update_all_diff_views()
        
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


def main():
    """Main entry point for the application."""
    # Create application
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle("Fusion")
    
    # Create and show main window
    window = InfiniteDifferApp()
    window.show()
    
    # Start event loop
    try:
        sys.exit(app.exec())
    except KeyboardInterrupt:
        print("\nExiting application...")
        sys.exit(0)


if __name__ == "__main__":
    main()

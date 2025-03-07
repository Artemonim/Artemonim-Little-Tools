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
from typing import List, Dict, Tuple, Optional, Set
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QTextEdit, QLabel, QFileDialog, QScrollArea,
    QSplitter, QTabWidget, QToolBar, QStatusBar, QComboBox, QMenu,
    QGridLayout, QFrame, QSizePolicy
)
from PyQt6.QtGui import (
    QTextCharFormat, QColor, QTextCursor, QPalette, 
    QAction, QIcon, QFont, QTextDocument
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal

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
    "same": QColor(255, 255, 255)  # White
}


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
        
        # Add to tabs
        tab_name = f"{base.name} ↔ {compare.name}"
        self.tabs.addTab(container, tab_name)
        self.tabs.setCurrentIndex(self.tabs.count() - 1)
        
    def update_diff_view(self):
        """Update the current diff view."""
        current_tab = self.tabs.currentWidget()
        if not current_tab:
            return
            
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
            compare_menu = context_menu.addMenu("Compare")
            
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

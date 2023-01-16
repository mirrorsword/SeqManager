"""
A simple PyQt program that can rename, copy, and delete file sequences.

This is a simple PyQt program to rename file sequences. The window is like a file browser in that it shows files and
directories, but when it finds a sequence of files it displays them as one entry using pound signs (#) for the file
number. you can rename, copy, or delete a sequence by right-clicking on it and choosing the desired command. if you
choose to rename or copy you will need to enter a new name. This name needs to contain at least one pound sign, which
will be replaced with the file number. multiple pound signs in a row can be used to specify the padding for the numbers.
"""

__author__ = 'JamesLittlejohn'

import argparse
import glob
import os
import re
import shutil
import sys
from functools import total_ordering

from PyQt6 import QtGui, QtCore, QtWidgets
from PyQt6.QtCore import Qt


def main(path=None):
    app = QtWidgets.QApplication(sys.argv)
    # dialog = QtGui.QFileDialog()
    main_window = SeqManagerDialog(path)

    main_window.show()

    sys.exit(app.exec())


class SeqManagerDialog(QtWidgets.QMainWindow):
    """
    Main Window for SeqManager
    """

    def __init__(self, initial_directory=None):
        super(SeqManagerDialog, self).__init__()

        self.setWindowTitle("Sequence Manager")

        self.fileArea = FileArea(initial_directory)
        self.resize(500, 500)
        self.setup_ui()

    def setup_ui(self):
        self.setCentralWidget(self.fileArea)

        # main_menu = self.menuBar()
        # edit_menu = main_menu.addMenu("&Edit")
        # edit_menu.addAction("Copy", self.fileArea.copyAction)
        # edit_menu.addAction("Rename", self.fileArea.renameAction)
        # edit_menu.addAction("Delete", self.fileArea.deleteAction)

        tool_bar = QtWidgets.QToolBar()
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, tool_bar)
        tool_bar.addAction("Copy", self.fileArea.copy_action)
        tool_bar.addAction("Rename", self.fileArea.rename_action)
        tool_bar.addAction("Delete", self.fileArea.delete_action)


def warning_message(text):
    print("Warning: ", text)
    warning_message_box = QtWidgets.QMessageBox()
    warning_message_box.setText(text)
    warning_message_box.setIcon(QtWidgets.QMessageBox.Icon.Warning)
    warning_message_box.exec()


class FileArea(QtWidgets.QWidget):
    def __init__(self, initial_directory=None):
        super(FileArea, self).__init__()

        self.currentItem = None
        self.currentDirectoryWidget = None
        print(initial_directory)
        if initial_directory is None or not os.path.isdir(initial_directory):
            initial_directory = os.getcwd()

        self.currentQDir = QtCore.QDir(initial_directory)
        filters = self.currentQDir.filter()

        self.currentQDir.setFilter(filters | QtCore.QDir.Filter.NoDotAndDotDot)

        # ui items
        self.upButton = QtWidgets.QPushButton("Up")
        self.fileTableWidget = QtWidgets.QTableWidget()

        self.setup_ui()

        self.update_dir_widget()

        self.update_files()

    def setup_ui(self):
        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)
        top_layout = QtWidgets.QHBoxLayout()
        layout.addLayout(top_layout)
        # Directory Bar
        self.currentDirectoryWidget = QtWidgets.QLineEdit()
        dir_completer = QtWidgets.QCompleter(self)
        file_system_model = QtGui.QFileSystemModel(parent=dir_completer)
        file_system_model.setRootPath(self.currentQDir.absolutePath())
        dir_completer.setModel(file_system_model)
        self.currentDirectoryWidget.setCompleter(dir_completer)

        top_layout.addWidget(self.currentDirectoryWidget)
        top_layout.addWidget(self.upButton)
        # File List
        layout.addWidget(self.fileTableWidget)
        # COLUMN COUNT
        self.fileTableWidget.setColumnCount(1)
        h_header = self.fileTableWidget.horizontalHeader()
        v_header = self.fileTableWidget.verticalHeader()
        assert isinstance(h_header, QtWidgets.QHeaderView)
        assert isinstance(v_header, QtWidgets.QHeaderView)
        v_header.hide()
        h_header.setStretchLastSection(True)
        self.fileTableWidget.setHorizontalHeaderLabels(("Name", "Date"))
        self.fileTableWidget.setSelectionBehavior(QtWidgets.QTableWidget.SelectionBehavior.SelectRows)
        self.fileTableWidget.setSelectionMode(QtWidgets.QTableWidget.SelectionMode.SingleSelection)
        self.fileTableWidget.setColumnWidth(0, 300)
        self.fileTableWidget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        # Signals
        self.fileTableWidget.customContextMenuRequested.connect(self.show_item_context_menu)
        self.currentDirectoryWidget.editingFinished.connect(self.cur_dir_editing_finished)
        self.fileTableWidget.doubleClicked.connect(self.on_double_click)
        self.upButton.clicked.connect(self.on_up_button_clicked)

    def rename_action(self):
        self.seq_edit_action("Rename", rename_sequence)

    def copy_action(self):
        self.seq_edit_action("Copy", copy_sequence)

    def delete_action(self):
        cur_sq_info = self.selected_file_sq_info()
        if not (cur_sq_info and cur_sq_info.is_sequence()):
            warning_message("Please Select a file sequence.")
            return
        pattern = cur_sq_info.get_label()
        directory = cur_sq_info.directory
        pattern_path = os.path.join(directory, pattern)
        delete_sequence(pattern_path)
        self.update_files()

    def seq_edit_action(self, title, function):
        cur_sq_info = self.selected_file_sq_info()
        if not (cur_sq_info and cur_sq_info.is_sequence()):
            warning_message("Please Select a file sequence.")
            return
        source_pattern = cur_sq_info.get_label()
        directory = cur_sq_info.directory
        new_pattern, successful = self.get_new_pattern_dialog(title, source_pattern)  # Query user for new pattern
        if not successful:
            return
        original_pattern_path = os.path.join(directory, source_pattern)
        new_pattern_path = os.path.join(directory, new_pattern)
        function(original_pattern_path, new_pattern_path)
        self.update_files()

    def get_new_pattern_dialog(self, title, original_pattern):
        """Query user for new pattern"""
        new_pattern = None
        finished = False
        while finished is False:
            new_pattern, successful = QtWidgets.QInputDialog.getText(self, title, "Enter New Name",
                                                                     text=original_pattern)
            if successful:
                if "*" not in new_pattern and "#" not in new_pattern:
                    warning = 'Please enter a valid filename pattern with "*" or "#"'
                    QtWidgets.QMessageBox.critical(self, "Invalid Name", warning)
                else:
                    finished = True
            else:
                return "", False  # Operation was aborted
        return new_pattern, True

    def on_up_button_clicked(self):
        self.currentQDir.cdUp()
        self.update_dir_widget()

    def selected_file_item(self):
        selected_items = self.fileTableWidget.selectedItems()
        if len(selected_items) == 0:
            return None
        row = selected_items[0].row()
        file_item = self.fileTableWidget.item(row, 0)
        return file_item

    def selected_file_sq_info(self):
        item = self.selected_file_item()
        if item is None:
            return None
        assert isinstance(item, FileNameTreeWidgetItem)
        return item.fileSqInfo

    def show_item_context_menu(self, qpoint):

        current_file_info = self.selected_file_sq_info()
        if current_file_info and current_file_info.is_sequence():
            menu = QtWidgets.QMenu()
            menu.addAction("Rename", self.rename_action)
            menu.addAction("Copy", self.copy_action)
            menu.addAction("Delete", self.delete_action)
            global_pos = self.fileTableWidget.mapToGlobal(qpoint)
            menu.exec(global_pos)

    def change_dir(self, directory):
        if os.path.isdir(directory):
            self.currentQDir.setPath(directory)
            self.update_dir_widget()

    def update_dir_widget(self):
        """Updates Directory Widget to match self.currentQDir and updates the file list"""
        self.currentDirectoryWidget.setText(QtCore.QDir.toNativeSeparators(self.currentQDir.absolutePath()))
        self.update_files()

    def on_double_click(self, model_index):
        row = model_index.row()
        item = self.fileTableWidget.item(row, 0)
        assert isinstance(item, FileNameTreeWidgetItem)
        if item.fileSqInfo.is_directory():
            self.change_dir(item.fileSqInfo.path)
        elif item.fileSqInfo.is_sequence():
            self.rename_action()

    def cur_dir_editing_finished(self):
        text = self.currentDirectoryWidget.text()
        if os.path.isdir(text):
            self.change_dir(text)
        else:
            self.update_dir_widget()

    def update_files(self):
        self.currentQDir.refresh()
        file_info_list = self.currentQDir.entryInfoList()
        seqs = self.collapse_sequences(file_info_list)
        self.fileTableWidget.setRowCount(len(seqs))
        for i, fileSqInfo in enumerate(seqs):
            item = FileNameTreeWidgetItem(fileSqInfo)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self.fileTableWidget.setItem(i, 0, item)

    def collapse_sequences(self, file_info_list):
        # RE expressions keyed based on what index they are at when the file name is split by periods
        pattern_by_location = {}
        # dict where the key is the pattern and the value is a list of files that match the pattern.
        files_for_patterns = {}
        filename_list = []
        for fileInfo in file_info_list:
            assert isinstance(fileInfo, QtCore.QFileInfo)
            filename_list.append(fileInfo.fileName())

        for filename in filename_list:
            if os.path.isdir(filename):
                continue
            filename_parts = filename.split(".")
            for i, part in reversed(list(enumerate(filename_parts))):
                match = re.match(r"(.*?)(\d+)(.*?)", part)
                if match:
                    prefix, number, postfix = match.groups()
                    if i not in pattern_by_location:  # add list
                        pattern_by_location[i] = set()
                    pattern_parts = filename_parts[:i] + [prefix + "*" + postfix] + filename_parts[i + 1:]
                    pattern = ".".join(pattern_parts)
                    if pattern not in files_for_patterns:
                        files_for_patterns[pattern] = []
                    files_for_patterns[pattern].append((filename, number))
                    pattern_by_location[i].add(pattern)
                    # we only want to match the farthest left pattern so if we find one
                    # then we break out of the loop.
                    break

        sq_info_by_pattern = {}
        directory = self.currentQDir.absolutePath()
        keys = sorted(pattern_by_location.keys())
        for position in keys:
            for pattern in pattern_by_location[position]:
                # Skip patterns with a single file
                if len(files_for_patterns[pattern]) <= 1:
                    continue
                if pattern not in sq_info_by_pattern:
                    sq_info = FileSqInfo(os.path.join(directory, pattern))
                    sq_info_by_pattern[pattern] = sq_info
                else:
                    sq_info = sq_info_by_pattern[pattern]
                for filename, number in files_for_patterns[pattern]:
                    if filename in filename_list:
                        filename_list.remove(filename)  # file will be consolidated, so we can remove it from the list
                    sq_info.add_file(os.path.join(directory, filename), number)

        individual_files = [FileSqInfo(os.path.join(directory, x)) for x in filename_list]
        sequences = list(sq_info_by_pattern.values()) + individual_files
        sequences.sort()
        return sequences


def copy_sequence(old_pattern, new_pattern):
    edit_sequence(copy_file, old_pattern, new_pattern)


def rename_sequence(old_pattern, new_pattern):
    edit_sequence(rename_file, old_pattern, new_pattern)


def edit_sequence(function, old_pattern, new_pattern):
    # normcase makes the paths lowercase, so it is not good in this case
    # oldPattern = os.path.normcase(oldPattern)
    # newPattern = os.path.normcase(newPattern)
    # Get Source Files
    confirmed_files = get_files_for_sequence(old_pattern)
    if len(confirmed_files) == 0:
        warning_message("No Files to Edit")
    for filename, number in confirmed_files:
        destination = format_pattern_with_number(new_pattern, number)
        print("Processing:", os.path.basename(filename), " : ", os.path.basename(destination))
        function(filename, destination)  # rename or copy file


def get_files_for_sequence(pattern):
    # Get Source Files
    pattern = os.path.normcase(pattern)
    pattern_glob = re.sub(r"#+", "*", pattern)

    # patternGlob = pattern.replace("#", "?")
    pattern_glob = os.path.normcase(pattern_glob)
    potential_files = glob.glob(pattern_glob)
    pattern_re = pattern_to_re(pattern)
    confirmed_files = []
    for filepath in potential_files:
        filepath = os.path.normcase(filepath)
        match = re.match(pattern_re, filepath)
        if match:
            number = match.group(1)
            confirmed_files.append((filepath, number))
    return confirmed_files


def delete_sequence(pattern):
    files = get_files_for_sequence(pattern)
    for f, number in files:
        print("removing: ", f)
        os.remove(f)


def rename_file(source, destination):
    # Check if it is the same file
    if os.path.normcase(os.path.normpath(source)) == os.path.normcase(os.path.normpath(destination)):
        return  # Same name, no action needed
    if os.path.isfile(destination):
        os.remove(destination)
    os.rename(source, destination)


def copy_file(source, destination):
    shutil.copy(source, destination)


def format_pattern_with_number(pattern, number):
    """Takes a seq pattern and a number and formats it into a correct filename."""
    if "*" in pattern:
        new_pattern = pattern.replace("*", number)
    elif "#" in pattern:
        match = re.match("(.*?)(#+)(.*)", pattern)
        start, wildcard, end = match.groups()
        length = len(wildcard)  # determine correct padding
        number_text = str(int(number)).zfill(length)  # convert number to correct padding
        new_pattern = pattern.replace(wildcard, number_text)
    else:
        raise ValueError("pattern is invalid")
    return new_pattern


def pattern_to_re(pattern):
    pattern_parts = re.split("#+", pattern)
    re_pattern = re.escape(pattern_parts[0]) + r"(\d+)" + re.escape(pattern_parts[1])

    return re_pattern


@total_ordering
class FileSqInfo(object):
    def __init__(self, path):
        self.path = path
        self.filename = os.path.basename(path)
        self.directory = os.path.dirname(path)

        self.files = []

        # number of digits in the file sequences' numbers.
        self.padWidth = None

        if os.path.isdir(path):
            self.type = "directory"
        elif "*" in self.filename:
            self.type = "sequence"
        elif os.path.isfile(path):
            self.type = "file"
        else:
            raise ValueError("path is not a directory, file sequence, or individual file")

    def is_directory(self):
        return self.type == "directory"

    def is_sequence(self):
        return self.type == "sequence"

    def is_single_file(self):
        return self.type == "file"

    def add_file(self, path, number):
        self.files.append(path)
        if self.padWidth is None or len(number) < self.padWidth:
            self.padWidth = len(number)

    def get_label(self):
        if not self.is_sequence():
            return self.filename
        else:
            if self.padWidth:
                # TODO: enable assert again
                # assert self.padWidth is not None, "Pattern {0} has no files".format(self.filename)
                wildcard = "#" * self.padWidth
                return self.filename.replace("*", wildcard)
            else:
                return self.filename

    def __lt__(self, other):
        return self.filename < other.filename

    def __eq__(self, other):
        return self.filename == other.filename


# class RenameDialog(QtGui.QDialogButtonBox)


class FileNameTreeWidgetItem(QtWidgets.QTableWidgetItem):
    def __init__(self, file_sq_info):
        name = file_sq_info.get_label()
        self.fileSqInfo = file_sq_info
        if self.fileSqInfo.is_directory():
            name += os.sep
        super(FileNameTreeWidgetItem, self).__init__(name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='GUI for renaming or copying file sequences')
    parser.add_argument('path', default=None, nargs="?")
    args = parser.parse_args()
    main(args.path)

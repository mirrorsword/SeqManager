"""
A simple PyQt program that can rename, copy, and delete file sequences.

This is a simple PyQt program to rename file sequences. The window is like a file browser in that it shows files and
directories, but when it finds a sequence of files it displays them as one entry using pound signs (#) for the file
number. you can rename, copy, or delete a sequence by right clicking on it and choosing the desired command. if you
choose to rename or copy you will need to enter a new name. This name needs to contain at least one pound sign, which
will be replaced with the file number. multiple pound signs in a row can be used to specify the padding for the numbers.
"""

__author__ = 'JamesLittlejohn'

import sys
import os
import re
import glob
import shutil
from functools import total_ordering
import argparse

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
    Main Window for SeqMangager
    """

    def __init__(self, initial_directory=None):
        super(SeqManagerDialog, self).__init__()

        self.setWindowTitle("Sequence Manager")

        self.fileArea = FileArea(initial_directory)
        self.resize(500, 500)
        self.setupUI()

    def setupUI(self):
        self.setCentralWidget(self.fileArea)

        # main_menu = self.menuBar()
        # edit_menu = main_menu.addMenu("&Edit")
        # edit_menu.addAction("Copy", self.fileArea.copyAction)
        # edit_menu.addAction("Rename", self.fileArea.renameAction)
        # edit_menu.addAction("Delete", self.fileArea.deleteAction)

        tool_bar = QtWidgets.QToolBar()
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, tool_bar)
        tool_bar.addAction("Copy", self.fileArea.copyAction)
        tool_bar.addAction("Rename", self.fileArea.renameAction)
        tool_bar.addAction("Delete", self.fileArea.deleteAction)


# noinspection PyArgumentList
class FileArea(QtWidgets.QWidget):
    def __init__(self, initialDirectory=None):
        super(FileArea, self).__init__()

        self.currentItem = None
        self.currentDirectoryWidget = None
        print (initialDirectory)
        if initialDirectory is None or not os.path.isdir(initialDirectory):
            initialDirectory = os.getcwd()

        self.currentQDir = QtCore.QDir(initialDirectory)
        filters = self.currentQDir.filter()

        self.currentQDir.setFilter(filters | QtCore.QDir.Filter.NoDotAndDotDot)

        self.setupUI()

        self.updateDirWidget()

        self.updateFiles()

    def setupUI(self):
        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)
        topLayout = QtWidgets.QHBoxLayout()
        layout.addLayout(topLayout)
        # Directory Bar
        self.currentDirectoryWidget = QtWidgets.QLineEdit()
        dirCompleter = QtWidgets.QCompleter(self)
        fileSystemModel = QtGui.QFileSystemModel(parent=dirCompleter)
        fileSystemModel.setRootPath(self.currentQDir.absolutePath())
        dirCompleter.setModel(fileSystemModel)
        self.currentDirectoryWidget.setCompleter(dirCompleter)

        topLayout.addWidget(self.currentDirectoryWidget)
        self.upButton = QtWidgets.QPushButton("Up")
        topLayout.addWidget(self.upButton)
        # File List
        self.fileTableWidget = QtWidgets.QTableWidget()
        layout.addWidget(self.fileTableWidget)
        # COLUMN COUNT
        self.fileTableWidget.setColumnCount(1)
        hHeader = self.fileTableWidget.horizontalHeader()
        vHeader = self.fileTableWidget.verticalHeader()
        assert isinstance(hHeader, QtWidgets.QHeaderView)
        assert isinstance(vHeader, QtWidgets.QHeaderView)
        vHeader.hide()
        hHeader.setStretchLastSection(True)
        self.fileTableWidget.setHorizontalHeaderLabels(("Name", "Date"))
        self.fileTableWidget.setSelectionBehavior(QtWidgets.QTableWidget.SelectionBehavior.SelectRows)
        self.fileTableWidget.setSelectionMode(QtWidgets.QTableWidget.SelectionMode.SingleSelection)
        self.fileTableWidget.setColumnWidth(0, 300)
        self.fileTableWidget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        # Signals
        self.fileTableWidget.customContextMenuRequested.connect(self.showItemContextMenu)
        self.currentDirectoryWidget.editingFinished.connect(self.curDirEditingFinished)
        self.fileTableWidget.doubleClicked.connect(self.onDoubleClick)
        self.upButton.clicked.connect(self.onUpButtonClicked)

    def renameAction(self):
        self.seqEditAction("Rename", renameSequence)

    def copyAction(self):
        self.seqEditAction("Copy", copySequence)

    def deleteAction(self):
        curSqInfo = self.selectedFileSqInfo()
        if not (curSqInfo and curSqInfo.isSequence()):
            self.warning_message("Please Select a file sequence.")
            return
        pattern = curSqInfo.getLabel()
        directory = curSqInfo.directory
        patternPath = os.path.join(directory, pattern)
        deleteSequence(patternPath)
        self.updateFiles()

    def seqEditAction(self, title, function):
        curSqInfo = self.selectedFileSqInfo()
        if not (curSqInfo and curSqInfo.isSequence()):
            self.warning_message("Please Select a file sequence.")
            return
        sourcePattern = curSqInfo.getLabel()
        directory = curSqInfo.directory
        newPattern, successful = self.getNewPatternDialog(title, sourcePattern)  # Query user for new pattern
        if not successful:
            return
        originalPatternPath = os.path.join(directory, sourcePattern)
        newPatternPath = os.path.join(directory, newPattern)
        function(originalPatternPath, newPatternPath)
        self.updateFiles()

    def warning_message(self, text):
        warning_message_box = QtWidgets.QMessageBox()
        warning_message_box.setText(text)
        warning_message_box.setIcon(QtWidgets.QMessageBox.Icon.Warning)
        warning_message_box.exec()

    def getNewPatternDialog(self, title, originalPattern):
        """Query user for new pattern"""
        newPattern = None
        finished = False
        while finished is False:
            newPattern, successful = QtWidgets.QInputDialog.getText(self, title, "Enter New Name", text=originalPattern)
            if successful:
                if "*" not in newPattern and "#" not in newPattern:
                    warning = 'Please enter a valid filename pattern with "*" or "#"'
                    QtWidgets.QMessageBox.critical(self, "Invalid Name", warning)
                else:
                    finished = True
            else:
                return "", False  # Operation was aborted
        return newPattern, True

    def onUpButtonClicked(self):
        self.currentQDir.cdUp()
        self.updateDirWidget()

    def selectedFileItem(self):
        selectedItems = self.fileTableWidget.selectedItems()
        if len(selectedItems) == 0:
            return None
        row = selectedItems[0].row()
        fileItem = self.fileTableWidget.item(row, 0)
        return fileItem

    def selectedFileSqInfo(self):
        item = self.selectedFileItem()
        if item is None:
            return None
        assert isinstance(item, FileNameTreeWidgetItem)
        return item.fileSqInfo

    def showItemContextMenu(self, qpoint):

        currnetFileInfo = self.selectedFileSqInfo()
        if currnetFileInfo and currnetFileInfo.isSequence():
            menu = QtWidgets.QMenu()
            menu.addAction("Rename", self.renameAction)
            menu.addAction("Copy", self.copyAction)
            menu.addAction("Delete", self.deleteAction)
            global_pos = self.fileTableWidget.mapToGlobal(qpoint)
            menu.exec(global_pos)


    def changeDir(self, dir):
        if os.path.isdir(dir):
            self.currentQDir.setPath(dir)
            self.updateDirWidget()

    def updateDirWidget(self):
        """Updates Directory Widget to match self.currentQDir and updates the file list"""
        self.currentDirectoryWidget.setText(QtCore.QDir.toNativeSeparators(self.currentQDir.absolutePath()))
        self.updateFiles()

    def onDoubleClick(self, modelIndex):
        row = modelIndex.row()
        item = self.fileTableWidget.item(row, 0)
        assert isinstance(item, FileNameTreeWidgetItem)
        if item.fileSqInfo.isDirectory():
            self.changeDir(item.fileSqInfo.path)
        elif item.fileSqInfo.isSequence():
            self.renameAction()

    def curDirEditingFinished(self):
        text = self.currentDirectoryWidget.text()
        if os.path.isdir(text):
            self.changeDir(text)
        else:
            self.updateDirWidget()

    def updateFiles(self):
        self.currentQDir.refresh()
        fileInfoList = self.currentQDir.entryInfoList()
        seqs = self.collapseSequences(fileInfoList)
        self.fileTableWidget.setRowCount(len(seqs))
        for i, fileSqInfo in enumerate(seqs):
            item = FileNameTreeWidgetItem(fileSqInfo)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self.fileTableWidget.setItem(i, 0, item)

    def collapseSequences(self, fileInfoList):
        #RE expressions keyed based on what index they are at when the file name is split by periods
        patternByLocation = {}
        # dict where the key is the pattern and the value is a list of files that match the pattern.
        filesForPatterns = {}
        filenameList = []
        for fileInfo in fileInfoList:
            assert isinstance(fileInfo, QtCore.QFileInfo)
            filenameList.append(fileInfo.fileName())

        for filename in filenameList:
            if os.path.isdir(filename):
                continue
            filenameParts = filename.split(".")
            for i, part in reversed(list(enumerate(filenameParts))):
                match = re.match(r"(.*?)(\d+)(.*?)", part)
                if match:
                    prefix, number, postfix = match.groups()
                    if i not in patternByLocation:  # add list
                        patternByLocation[i] = set()
                    patternParts = filenameParts[:i] + [prefix + "*" + postfix] + filenameParts[i + 1:]
                    pattern = ".".join(patternParts)
                    if pattern not in filesForPatterns:
                        filesForPatterns[pattern] = []
                    filesForPatterns[pattern].append((filename, number))
                    patternByLocation[i].add(pattern)
                    # we only want to match the farthest left pattern so if we find one
                    # then we break out of the loop.
                    break

        sq_infos_by_pattern = {}
        dir = self.currentQDir.absolutePath()
        keys = sorted(patternByLocation.keys())
        for position in keys:
            for pattern in patternByLocation[position]:
                # Skip patterns with a single file
                if len(filesForPatterns[pattern]) <= 1:
                    continue
                if pattern not in sq_infos_by_pattern:
                    sqInfo = FileSqInfo(os.path.join(dir, pattern))
                    sq_infos_by_pattern[pattern] = sqInfo
                else:
                    sqInfo = sq_infos_by_pattern[pattern]
                for filename, number in filesForPatterns[pattern]:
                    if filename in filenameList:
                        filenameList.remove(filename)  # file will be consolidated so we can remove it from the list
                    sqInfo.addFile(os.path.join(dir, filename), number)

        individualFiles = [FileSqInfo(os.path.join(dir, x)) for x in filenameList]
        sequences = list(sq_infos_by_pattern.values()) + individualFiles
        sequences.sort()
        return sequences


def copySequence(oldPattern, newPattern):
    editSequence(copyFile, oldPattern, newPattern)


def renameSequence(oldPattern, newPattern):
    editSequence(renameFile, oldPattern, newPattern)


def editSequence(function, oldPattern, newPattern):
    #normcase makes the paths lowercase so it is not good in this case
    #oldPattern = os.path.normcase(oldPattern)
    #newPattern = os.path.normcase(newPattern)
    # Get Source Files
    confirmedFiles = getFilesForSequence(oldPattern)
    if len(confirmedFiles) == 0:
        print("No Files To Edit")
    for filename, number in confirmedFiles:
        destination = formatPatternWithNumber(newPattern, number)
        print("Processing:", os.path.basename(filename), " : ", os.path.basename(destination))
        function(filename, destination)  # rename or copy file


def getFilesForSequence(pattern):
    # Get Source Files
    pattern = os.path.normcase(pattern)
    patternGlob = re.sub(r"#+", "*", pattern)
    print("PatternGlob: ", patternGlob)

    #patternGlob = pattern.replace("#", "?")
    patternGlob = os.path.normcase(patternGlob)
    potentialFiles = glob.glob(patternGlob)
    patternRE = patternToRE(pattern)
    confirmedFiles = []
    for filepath in potentialFiles:
        filepath = os.path.normcase(filepath)
        match = re.match(patternRE, filepath)
        #print(repr(patternRE), repr(filepath), match is not None)
        if match:
            number = match.group(1)
            confirmedFiles.append((filepath, number))
    return confirmedFiles


def deleteSequence(pattern):
    files = getFilesForSequence(pattern)
    for f, number in files:
        print("removing: ", f)
        os.remove(f)


def renameFile(source, destination):
    # Check if it is the same file
    if os.path.normcase(os.path.normpath(source)) == os.path.normcase(os.path.normpath(destination)):
        return  # Same name, no action needed
    if os.path.isfile(destination):
        os.remove(destination)
    os.rename(source, destination)


def copyFile(source, destination):
    shutil.copy(source, destination)


def formatPatternWithNumber(pattern, number):
    """Takes a seq pattern and a number and formats it into a correct filename."""
    if "*" in pattern:
        newPattern = pattern.replace("*", number)
    elif "#" in pattern:
        match = re.match("(.*?)(#+)(.*)", pattern)
        start, wildcard, end = match.groups()
        # print("Parts:", start, wildcard, end)
        length = len(wildcard)  # determine correct padding
        numberText = str(int(number)).zfill(length)  # convert number to correct padding
        # print wildcard, number, numberText
        newPattern = pattern.replace(wildcard, numberText)
    else:
        raise ValueError("pattern is invalid")
    return newPattern


def patternToRE(pattern):
    pattern_parts = re.split("#+", pattern)
    re_pattern = re.escape(pattern_parts[0]) + r"(\d+)" + re.escape(pattern_parts[1]);

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

    def isDirectory(self):
        return self.type == "directory"

    def isSequence(self):
        return self.type == "sequence"

    def isSingleFile(self):
        return self.type == "file"

    def addFile(self, path, number):
        self.files.append(path)
        if self.padWidth is None or len(number) < self.padWidth:
            self.padWidth = len(number)

    def getLabel(self):
        if not self.isSequence():
            return self.filename
        else:
            if self.padWidth:
                #TODO: enable assert again
                #assert self.padWidth is not None, "Pattern {0} has no files".format(self.filename)
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
    def __init__(self, fileSqInfo):
        name = fileSqInfo.getLabel()
        self.fileSqInfo = fileSqInfo
        if self.fileSqInfo.isDirectory():
            name += os.sep
        super(FileNameTreeWidgetItem, self).__init__(name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='GUI for renaming or copying file sequences')
    parser.add_argument('path', default=None, nargs="?")
    args = parser.parse_args()
    main(args.path)

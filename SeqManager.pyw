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

import sip

sip.setapi("QString", 2)
from PyQt4 import QtGui, QtCore
from PyQt4.QtCore import Qt


def main(path=None):
    app = QtGui.QApplication(sys.argv)
    # dialog = QtGui.QFileDialog()
    mainWindow = SeqManagerDialog(path)

    mainWindow.show()

    sys.exit(app.exec_())


class SeqManagerDialog(QtGui.QMainWindow):
    """
    Main Window for SeqMangager
    """

    def __init__(self, initialDirectory=None):
        super(SeqManagerDialog, self).__init__()

        self.setWindowTitle("Sequence Manager")

        self.fileArea = FileArea(initialDirectory)
        self.resize(500, 500)
        self.setupUI()

    def setupUI(self):
        self.setCentralWidget(self.fileArea)
        mainMenu = self.menuBar()
        editMenu = mainMenu.addMenu("&Edit")
        editMenu.addAction("Copy", self.fileArea.copyAction)
        editMenu.addAction("Rename", self.fileArea.renameAction)
        editMenu.addAction("Delete", self.fileArea.deleteAction)
        # toolBar = QtGui.QToolBar()
        # self.addToolBar(Qt.BottomToolBarArea, toolBar)
        # toolBar.addAction("Copy", self.fileArea.copyAction)


# noinspection PyArgumentList
class FileArea(QtGui.QWidget):
    def __init__(self, initialDirectory=None):
        super(FileArea, self).__init__()

        self.currentItem = None
        self.currentDirectoryWidget = None
        print initialDirectory
        if initialDirectory is None or not os.path.isdir(initialDirectory):
            initialDirectory = os.getcwd()

        self.currentQDir = QtCore.QDir(initialDirectory)
        filters = self.currentQDir.filter()
        self.currentQDir.setFilter(filters | QtCore.QDir.NoDotAndDotDot)

        self.setupUI()

        self.updateDirWidget()

        self.updateFiles()

    def setupUI(self):
        layout = QtGui.QVBoxLayout()
        self.setLayout(layout)
        topLayout = QtGui.QHBoxLayout()
        layout.addLayout(topLayout)
        # Directory Bar
        self.currentDirectoryWidget = QtGui.QLineEdit()
        dirCompleter = QtGui.QCompleter(self)
        fileSystemModel = QtGui.QFileSystemModel(parent=dirCompleter)
        fileSystemModel.setRootPath(self.currentQDir.absolutePath())
        dirCompleter.setModel(fileSystemModel)
        self.currentDirectoryWidget.setCompleter(dirCompleter)

        topLayout.addWidget(self.currentDirectoryWidget)
        self.upButton = QtGui.QPushButton("Up")
        topLayout.addWidget(self.upButton)
        # File List
        self.fileTableWidget = QtGui.QTableWidget()
        layout.addWidget(self.fileTableWidget)
        # COLUMN COUNT
        self.fileTableWidget.setColumnCount(1)
        hHeader = self.fileTableWidget.horizontalHeader()
        vHeader = self.fileTableWidget.verticalHeader()
        assert isinstance(hHeader, QtGui.QHeaderView)
        assert isinstance(vHeader, QtGui.QHeaderView)
        vHeader.hide()
        hHeader.setStretchLastSection(True)
        self.fileTableWidget.setHorizontalHeaderLabels(("Name", "Date"))
        self.fileTableWidget.setSelectionBehavior(QtGui.QTableWidget.SelectRows)
        self.fileTableWidget.setSelectionMode(QtGui.QTableWidget.SingleSelection)
        self.fileTableWidget.setColumnWidth(0, 300)
        self.fileTableWidget.setContextMenuPolicy(Qt.CustomContextMenu)

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
        if not curSqInfo.isSequence():
            return
        pattern = curSqInfo.getLabel()
        directory = curSqInfo.directory
        patternPath = os.path.join(directory, pattern)
        deleteSequence(patternPath)
        self.updateFiles()

    def seqEditAction(self, title, function):
        curSqInfo = self.selectedFileSqInfo()
        if not curSqInfo.isSequence():
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

    def getNewPatternDialog(self, title, originalPattern):
        """Query user for new pattern"""
        newPattern = None
        finished = False
        while finished is False:
            newPattern, successful = QtGui.QInputDialog.getText(self, title, "Enter New Name", text=originalPattern)
            if successful:
                if "*" not in newPattern and "#" not in newPattern:
                    warning = 'Please enter a valid filename pattern with "*" or "#"'
                    QtGui.QMessageBox.critical(self, "Invalid Name", warning)
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
        if not currnetFileInfo.isSequence():
            return
        menu = QtGui.QMenu()
        menu.addAction("Rename", self.renameAction)
        menu.addAction("Copy", self.copyAction)
        menu.addAction("Delete", self.deleteAction)
        globalPos = self.fileTableWidget.mapToGlobal(qpoint)
        menu.exec_(globalPos)

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
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.fileTableWidget.setItem(i, 0, item)

    def collapseSequences(self, fileInfoList):
        patternByLocation = {}
        filesForPatterns = {}
        filenameList = []
        for fileInfo in fileInfoList:
            assert isinstance(fileInfo, QtCore.QFileInfo)
            filenameList.append(fileInfo.fileName())

        for filename in filenameList:
            if os.path.isdir(filename):
                continue
            filenameParts = filename.split(".")
            for i, part in enumerate(filenameParts):

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

        sqInfos = {}
        dir = self.currentQDir.absolutePath()
        keys = sorted(patternByLocation.keys())
        for position in keys:
            for pattern in patternByLocation[position]:
                # Skip patterns with a single file
                if len(filesForPatterns[pattern]) <= 1:
                    continue
                if pattern not in sqInfos:
                    sqInfo = FileSqInfo(os.path.join(dir, pattern))
                    sqInfos[pattern] = sqInfo
                else:
                    sqInfo = sqInfos[pattern]
                for filename, number in filesForPatterns[pattern]:
                    if filename in filenameList:
                        filenameList.remove(filename)  # file will be consolidated so we can remove it from the list
                        sqInfo.addFile(os.path.join(dir, filename), number)

        individualFiles = [FileSqInfo(os.path.join(dir, x)) for x in filenameList]
        sequences = sqInfos.values() + individualFiles
        sequences.sort()
        return sequences


def copySequence(oldPattern, newPattern):
    editSequence(copyFile, oldPattern, newPattern)


def renameSequence(oldPattern, newPattern):
    editSequence(renameFile, oldPattern, newPattern)


def editSequence(function, oldPattern, newPattern):
    # Get Source Files
    oldPattern = os.path.normcase(oldPattern)
    newPattern = os.path.normcase(newPattern)
    confirmedFiles = getFilesForSequence(oldPattern)
    if len(confirmedFiles) == 0:
        print "No Files To Edit"
    for filename, number in confirmedFiles:
        destination = formatPatternWithNumber(newPattern, number)
        print "Files:", os.path.basename(filename), os.path.basename(destination)
        function(filename, destination)  # rename or copy file


def getFilesForSequence(pattern):
    # Get Source Files
    pattern = os.path.normcase(pattern)
    patternGlob = pattern.replace("#", "?")
    patternGlob = os.path.normcase(patternGlob)
    potentialFiles = glob.glob(patternGlob)
    patternRE = patternToRE(pattern)
    confirmedFiles = []
    for filepath in potentialFiles:
        filepath = os.path.normcase(filepath)
        match = re.match(patternRE, filepath)
        print repr(patternRE), repr(filepath), match is not None
        if match:
            number = match.group(1)
            confirmedFiles.append((filepath, number))
    return confirmedFiles


def deleteSequence(pattern):
    files = getFilesForSequence(pattern)
    print files
    for f, number in files:
        print "removing: ", f
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
        print "Parts:", start, wildcard, end
        length = len(wildcard)  # determine correct padding
        numberText = str(int(number)).zfill(length)  # convert number to correct padding
        # print wildcard, number, numberText
        newPattern = pattern.replace(wildcard, numberText)
    else:
        raise ValueError("pattern is invalid")
    return newPattern


def patternToRE(pattern):
    pattern = re.escape(pattern)
    print pattern
    # pattern = pattern.replace(r"\*", r"(\d+)")
    # match = re.match(r"(.*?)\\")
    pattern = re.sub(r"((?:\\#)+)", r"(\d+)", pattern)
    print pattern
    return pattern


@total_ordering
class FileSqInfo(object):
    def __init__(self, path):
        self.path = path
        self.filename = os.path.basename(path)
        self.directory = os.path.dirname(path)

        self.files = []

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
            assert self.padWidth is not None, "Pattern {0} has no files".format(self.filename)
            wildcard = "#" * self.padWidth
            return self.filename.replace("*", wildcard)

    def __lt__(self, other):
        return self.filename < other.filename

    def __eq__(self, other):
        return self.filename == other.filename


# class RenameDialog(QtGui.QDialogButtonBox)


class FileNameTreeWidgetItem(QtGui.QTableWidgetItem):
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

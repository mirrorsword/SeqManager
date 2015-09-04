__author__ = 'JamesLittlejohn'

import sys
import os
import re
import glob
import shutil
from functools import total_ordering

import sip

sip.setapi("QString", 2)
from PyQt4 import QtGui, QtCore
from PyQt4.QtCore import Qt


def main():
    app = QtGui.QApplication(sys.argv)
    # dialog = QtGui.QFileDialog()
    mainWindow = QtGui.QMainWindow()

    table = QtGui.QTreeView()

    mainWindow.setCentralWidget(table)

    fileSystem = QtGui.QFileSystemModel()
    fileSystem.setRootPath("C:\\Users")
    table.setModel(fileSystem)

    mainWindow.show()

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()

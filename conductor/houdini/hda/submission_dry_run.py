import json
from PySide2 import QtWidgets, QtGui, QtCore


class SubmissionDryRun(QtWidgets.QWidget):

    def __init__(self, parent=None):
        QtWidgets.QWidget.__init__(self, parent)
        hbox = QtWidgets.QHBoxLayout()
        hbox.setContentsMargins(0, 0, 0, 0)
        self._console = QtWidgets.QTextEdit()
        self._console.setReadOnly(False)
        self._console.setWordWrapMode(QtGui.QTextOption.NoWrap)
        hbox.addWidget(self._console)
        self.setLayout(hbox)

    def populate(self, json):
        self._console.setText(json)
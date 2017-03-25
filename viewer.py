#!/usr/bin/env python3

'''
[x] auto rotate
[x] sorting
[x] center image
[x] aspect ratio
[x] read path on command line
[x] react on SPACE/BACK
[ ] nice dark theme style

* research: open directory dialog
* restore layout after fullscreen
* research qt dark theme style
* research: capture key press / parent / handle
'''


import sys
import os
import signal
import logging
from PyQt5 import QtWidgets, QtGui, QtCore, uic

import viewer_core

LOG = logging.getLogger('viewer_ui')

class Picks(QtWidgets.QMainWindow):

    def __init__(self):
        super().__init__()

        self.setMouseTracking(True)
        self._directory = os.path.dirname(os.path.realpath(__file__))
        uic.loadUi(os.path.join(self._directory, 'viewer.ui'), self)

        self.lst_files.itemClicked.connect(self.list_item_clicked)
        self.txt_filter.textChanged.connect(self.filter_changed)
        self.lst_files.keyPressEvent = self.other_widgets_keypress_event

        if len(sys.argv) > 1:
            os.chdir(sys.argv[1])

        self.list_files(pattern='')

        self.show()

        self.goto(0)

    def other_widgets_keypress_event(self, event):
        self.keyPressEvent(event)

    def list_files(self, pattern: str):
        self.lst_files.clear()
        p_lower = pattern.lower()
        for f in viewer_core.list_pics():
            if p_lower not in f.lower():
                continue
            self.lst_files.addItem(f)

    def filter_changed(self, text):
        self.list_files(pattern=text)

    def list_item_clicked(self, _):
        self.goto(self.lst_files.currentRow())

    def jump(self, items: int):
        next_index = self.lst_files.currentRow() + items
        self.goto(
            0 if next_index < 0 else
            self.lst_files.count() - 1 if next_index >= self.lst_files.count() else
            next_index)

    def goto(self, index: int):
        self.lst_files.setCurrentRow(
            self.lst_files.count() - 1 if index < 0 else index)
        filename = self.lst_files.currentItem().text()
        print('show file %d: %s' % (self.lst_files.currentRow(), filename))
        self.set_image(filename)

    def set_image(self, filename: str):
        self.setWindowTitle('Picks - %s' % filename)
        tags = viewer_core.get_tags(filename)
        pixmap = QtGui.QPixmap(filename)
        self.lbl_viewer.setPixmap(
            pixmap.transformed(
                QtGui.QTransform().rotate(
                    viewer_core.get_orientation(tags))).scaled(
                        self.lbl_viewer.width(), self.lbl_viewer.height(),
                        QtCore.Qt.KeepAspectRatio))
        self.lbl_viewer.setMask(pixmap.mask())

    def on_clicked_pb_start_p1(self):
        pass

    def mouseReleaseEvent(self, event):
        pass

    def handle_signal(self, _: int) -> None:
        self.close()

    def copy_current_file(self):
        print('copy')

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.frm_filelist.setVisible(True)
            self.txt_filter.setEnabled(True)
            self.showNormal()
#            self.restoreGeometry(self._geometry)
        else:
#            self._geometry = self.saveGeometry()
            self.frm_filelist.setVisible(False)
            self.txt_filter.setEnabled(False)
            self.showFullScreen()

    def void(self):
        print('void')

    def keyPressEvent(self, event):
        try:
            {
                QtCore.Qt.Key_F7:        self.copy_current_file,
                QtCore.Qt.Key_F11:       self.toggle_fullscreen,
                QtCore.Qt.Key_Backspace: lambda: self.jump(-1),
                QtCore.Qt.Key_Left:      lambda: self.jump(-1),
                QtCore.Qt.Key_Up:        lambda: self.jump(-1),
                QtCore.Qt.Key_Space:     lambda: self.jump(1),
                QtCore.Qt.Key_Right:     lambda: self.jump(1),
                QtCore.Qt.Key_Down:      lambda: self.jump(1),
                QtCore.Qt.Key_PageUp:    lambda: self.jump(-10),
                QtCore.Qt.Key_PageDown:  lambda: self.jump(10),
                QtCore.Qt.Key_Home:      lambda: self.goto(0),
                QtCore.Qt.Key_End:       lambda: self.goto(-1),
             }[event.key()]()
        except KeyError:
            print('unknown key', event.key())


def main():
    logging.basicConfig(level=logging.INFO)

    LOG.info(sys.executable)
    LOG.info('.'.join((str(e) for e in sys.version_info)))

    app = QtWidgets.QApplication(sys.argv)
    ex = Picks()

    for s in (signal.SIGABRT, signal.SIGINT, signal.SIGSEGV, signal.SIGTERM):
        signal.signal(s, lambda signal, frame: ex.handle_signal(signal))

    # catch the interpreter every now and then to be able to catch signals
    timer = QtCore.QTimer()
    timer.start(200)
    timer.timeout.connect(lambda: None)

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()


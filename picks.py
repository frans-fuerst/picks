#!/usr/bin/env python3

'''

* research: copy file: from shutil import copyfile copyfile(src, dst)
* research: exif dates
* research: open directory dialog
* restore layout after fullscreen
* research qt dark theme style
* research: capture key press / parent / handle

* more sophisticated resizing:
    http://stackoverflow.com/questions/21041941
'''


import sys
import os
import signal
import logging
import shutil
from PyQt5 import QtWidgets, QtGui, QtCore, uic

import viewer_core

LOG = logging.getLogger('picks')
STYLESHEET = 'qdarkstyle.qss'
APP_DIR = os.path.dirname(os.path.realpath(__file__))
SELECTED_DIR_NAME = "SELECTED_PICKS"


class Picks(QtWidgets.QMainWindow):

    def __init__(self):
        super().__init__()

        uic.loadUi(os.path.join(APP_DIR, 'picks.ui'), self)

        self.setMouseTracking(True)

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
        filename = self.selected_filename()
        print('show file %d: %s' % (self.lst_files.currentRow(), filename))
        self.set_image(filename)

    def selected_filename(self) -> str:
        return self.lst_files.currentItem().text()

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

    def mouseReleaseEvent(self, event):
        pass

    def handle_signal(self, _: int) -> None:
        self.close()

    def copy_current_file(self):
        try:
            os.makedirs(SELECTED_DIR_NAME)
        except FileExistsError:
            pass
        filename = self.selected_filename()
        LOG.info('copy file "%s" to "%s" folder' % (SELECTED_DIR_NAME, filename))
        shutil.copyfile(filename, os.path.join(SELECTED_DIR_NAME, filename))

    def delete_current_file(self):
        print('delete')

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.frm_filelist.setVisible(True)
            self.txt_filter.setEnabled(True)
            self.showNormal()
        else:
            self.frm_filelist.setVisible(False)
            self.txt_filter.setEnabled(False)
            self.showFullScreen()

    def resizeEvent(self, event: QtGui.QResizeEvent):
        try:
            self.set_image(self.selected_filename())
        except AttributeError:
            pass

    def void(self):
        print('void')

    def keyPressEvent(self, event):
        try:
            {
                # F2: rename
                # F3: edit
                # F5: slideshow
                QtCore.Qt.Key_F7:        self.copy_current_file,
                QtCore.Qt.Key_Delete:    self.delete_current_file,
                # F8: link
                # F9: move
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

    with open(os.path.join(APP_DIR, STYLESHEET)) as f:
        app.setStyleSheet(f.read())

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

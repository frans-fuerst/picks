#!/usr/bin/env python3

'''
[x] auto rotate
[x] sorting
[ ] center image
[x] aspect ratio
[ ] read path on command line
[ ] react on SPACE/BACK
'''


import sys
import os
import signal
import glob
import logging
import exifread
from abc import ABCMeta, abstractmethod
from PyQt5 import QtWidgets, QtGui, QtCore, uic

import viewer_core

LOG = logging.getLogger('viewer_ui')

class Viewer(QtWidgets.QMainWindow):
    _colors = [
        QtCore.Qt.green,
        QtCore.Qt.blue,
        QtCore.Qt.red,
        QtCore.Qt.cyan,
        QtCore.Qt.magenta,
        QtCore.Qt.darkBlue,
        QtCore.Qt.darkCyan,
        QtCore.Qt.darkGray,
        QtCore.Qt.darkGreen,
        QtCore.Qt.darkMagenta,
        QtCore.Qt.darkRed,
        QtCore.Qt.darkYellow,
        QtCore.Qt.lightGray,
        QtCore.Qt.gray,
        QtCore.Qt.white,
        QtCore.Qt.black,
        QtCore.Qt.yellow]

    def __init__(self):
        super().__init__()

        self.setMouseTracking(True)
        self._directory = os.path.dirname(os.path.realpath(__file__))
        uic.loadUi(os.path.join(self._directory, 'viewer.ui'), self)

        if len(sys.argv) > 1:
            os.chdir(sys.argv[1])

        self.list_files(pattern='')

        self.show()

        #self.pb_start_p1.clicked.connect(self.on_clicked_pb_start_p1)
        self.lst_files.itemClicked.connect(self.item_click)
        self.txt_filter.textChanged.connect(self.filter_changed)

    def list_files(self, pattern: str):
        self.lst_files.clear()
        p_lower = pattern.lower()
        for f in viewer_core.list_pics():
            if p_lower not in f.lower():
                continue
            print (f)
            self.lst_files.addItem(f)

    def filter_changed(self, text):
        self.list_files(pattern=text)

    def item_click(self, item):
        self.set_image(str(item.text()))

    def set_image(self, filename: str):
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

    def handle_signal(self, signal:int) -> None:
        self.close()

    def keyPressEvent(self, event):
        try:
            key = {16777235: 0,
                   16777237: 1,
                   16777234: 2,
                   16777236: 3}[event.key()]
#            self._world.handle_key_press(key)
#            self._update_field()
        except KeyError:
            print('unknown key', event.key())
#        logger.log_i() << "keyPressEvent '" << k->key();
#        switch (k->key()) {
#    case Qt::Key_Back:
#    case Qt::Key_Escape:
#       if (m_txt_note->isVisible()) {
#            m_lst_search_result->clearSelection();
#        } else if (m_frm_status->isVisible()) {
#             m_frm_status->setVisible(false);
#        } else if (k->key() == Qt::Key_Back) {
#            close();


def main():
    logging.basicConfig(level=logging.INFO)

    LOG.info(sys.executable)
    LOG.info('.'.join((str(e) for e in sys.version_info)))

    app = QtWidgets.QApplication(sys.argv)
    ex = Viewer()

    for s in (signal.SIGABRT, signal.SIGINT, signal.SIGSEGV, signal.SIGTERM):
        signal.signal(s, lambda signal, frame: ex.handle_signal(signal))

    # catch the interpreter every now and then to be able to catch signals
    timer = QtCore.QTimer()
    timer.start(200)
    timer.timeout.connect(lambda: None)

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()


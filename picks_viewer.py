#!/usr/bin/env python3

'''
'''


import sys
import os
import signal
import logging
import shutil
import ast
import json
import time
from PyQt5 import QtWidgets, QtGui, QtCore, uic

import picks_core

LOG = logging.getLogger('picks')
STYLESHEET = 'QTDark.stylesheet'
APP_DIR = os.path.dirname(os.path.realpath(__file__))
SELECTED_DIR_NAME = "SELECTED_PICKS"
DELETED_DIR_NAME = ".picks.deleted"
CONFIG_FILE = os.path.expanduser('~/.picks/config')

class Picks(QtWidgets.QMainWindow):

    def __init__(self, args: dict):
        super().__init__()

        uic.loadUi(os.path.join(APP_DIR, 'picks.ui'), self)

        self._config = self._read_config(CONFIG_FILE)
        self._image_cache = {}

        self.lbl_notification = QtWidgets.QLabel(self.lbl_viewer)
        self.setMouseTracking(True)

        self.frm_tags.setVisible(False)

        self.lst_files.itemClicked.connect(self.list_item_clicked)
        self.txt_filter.textChanged.connect(self.filter_changed)
        self.lst_files.keyPressEvent = self.other_widgets_keypress_event

        os.chdir(args.directory)

        self.le_directory.setText(os.getcwd())
        self.list_files()

        self.show()

        self.goto(0)

    def _set_config_value(self, name: str, value) -> None:
        self._config[name] = value
        self._write_config(CONFIG_FILE, self._config)

    @staticmethod
    def _read_config(filename: str) -> dict:
        try:
            with open(filename) as f:
                return ast.literal_eval(f.read())
        except FileNotFoundError:
            return {}

    @staticmethod
    def _write_config(filename: str, data: dict) -> None:
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, 'w') as f:
            json.dump(data, f)

    def update_file_list(self):
        ''' '''

    def update_tag_list(self, filenames):
        new_tags = self._config['tags'] if 'tags' in self._config else []
        for t in picks_core.get_all_tags(filenames):
            if not t in new_tags:
                new_tags.append(t)
        self._config['tags'] = new_tags

    def other_widgets_keypress_event(self, event):
        self.keyPressEvent(event)

    def list_files(self):
        current_index = self.selected_index()
        self.lst_files.clear()
        p_lower = self.txt_filter.text().lower()
        filenames = picks_core.list_pics()
        for f in filenames:
            if p_lower not in f.lower():
                continue
            self.lst_files.addItem(f)
        # don't jump to last viewed image if none was selected
        if current_index >= 0:
            self.goto(current_index)

    def filter_changed(self, text):
        self.list_files()

    def list_item_clicked(self, _):
        self.goto(self.lst_files.currentRow())

    def jump(self, items: int):
        next_index = self.selected_index() + items
        self.goto(
            0 if next_index < 0 else
            self.lst_files.count() - 1 if next_index >= self.lst_files.count() else
            next_index)

    def goto(self, index: int):
        self.lst_files.setCurrentRow(
            self.lst_files.count() - 1 if index < 0 else index)
        filename = self.selected_filename()
        print('show file %d: %s' % (self.selected_index(), filename))
        self.set_image(filename)
        self.repaint()
        QtCore.QMetaObject.invokeMethod(
            self, "preload", QtCore.Qt.QueuedConnection)

    @QtCore.pyqtSlot()
    def preload(self):
        try:
            self.fetch_image_data(
                self.lst_files.item(self.selected_index() + 1).text())
        except AttributeError:
            # ignore index overflow
            pass

    def selected_filename(self) -> str:
        return self.lst_files.currentItem().text()

    def selected_index(self) -> int:
        return self.lst_files.currentRow()

    def fetch_image_data(self, filename: str) -> list:
        def load_image(filename: str) -> list:
            t1 = time.time()
            tags = picks_core.get_tags(filename)
            t2 = time.time()
            pixmap = QtGui.QPixmap(filename)
            t3 = time.time()
            print('tot: %.2f tags: %.2f pic: %.2f' %
                  (t3 - t1, t2 - t1, t3 - t2))
            return [pixmap, tags]

        def clean_cache():
            print(len(self._image_cache))
            if len(self._image_cache) > 20:
                self._image_cache = {}

        clean_cache()

        abs_file = os.path.abspath(filename)
        if not abs_file in self._image_cache:
            self._image_cache[abs_file] = load_image(filename)
            self._image_cache[abs_file].append(0.0)

        self._image_cache[abs_file][2] = time.time()

        return self._image_cache[abs_file][:2]

    def set_image(self, filename: str):

        pixmap, tags = self.fetch_image_data(filename)
        self.setWindowTitle('Picks - %s' % filename)
        self.lbl_viewer.setPixmap(
            pixmap.transformed(
                QtGui.QTransform().rotate(
                    picks_core.get_orientation(tags))).scaled(
                        self.lbl_viewer.width(), self.lbl_viewer.height(),
                        QtCore.Qt.KeepAspectRatio))
        self.lbl_viewer.setMask(pixmap.mask())

    def mouseReleaseEvent(self, event):
        pass

    def handle_signal(self, _: int) -> None:
        self.close()

    def show_tag_dialog(self):
        self.frm_tags.setVisible(not self.frm_tags.isVisible())

    def copy_current_file(self):
        os.makedirs(SELECTED_DIR_NAME, exist_ok=True)
        filename = self.selected_filename()
        shutil.copyfile(filename, os.path.join(SELECTED_DIR_NAME, filename))
        self.show_notification('Added to selected pictures: %s' % filename)

    def show_notification(self, msg: str):
        LOG.info(msg)
        self.lbl_notification.setText(msg)
        new_width = self.lbl_notification.fontMetrics().width(msg) + 50
        self.lbl_notification.setAlignment(QtCore.Qt.AlignCenter)
        self.lbl_notification.setGeometry(
            QtCore.QRect((self.lbl_viewer.width() - new_width) / 2,
                         (self.lbl_viewer.height() - 50) / 2,
                         new_width, 50))
        self.lbl_notification.setVisible(True)
        QtCore.QTimer.singleShot(
            1500, lambda: self.lbl_notification.setVisible(False))

    def delete_current_file(self):
        os.makedirs(DELETED_DIR_NAME, exist_ok=True)
        filename = self.selected_filename()
        shutil.move(filename, os.path.join(DELETED_DIR_NAME, filename))
        self.list_files()
        self.show_notification('Marked as deleted: %s' % filename)

    def enter_fullscreen(self):
        self.frm_filelist.setVisible(False)
        self.le_directory.setVisible(False)
        self.txt_filter.setEnabled(False)
        self.showFullScreen()

    def leave_fullscreen(self):
        self.frm_filelist.setVisible(True)
        self.le_directory.setVisible(True)
        self.txt_filter.setEnabled(True)
        self.showNormal()

    def escape(self):
        if self.isFullScreen():
            self.leave_fullscreen()

    def new(self):
        print(self.frm_tags.isVisible())
        if self.frm_tags.isVisible():
            print('new')

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.leave_fullscreen()
        else:
            self.enter_fullscreen()

    def resizeEvent(self, event: QtGui.QResizeEvent):
        try:
            self.set_image(self.selected_filename())
        except AttributeError:
            pass

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
                QtCore.Qt.Key_T:         self.show_tag_dialog,
                QtCore.Qt.Key_F11:       self.toggle_fullscreen,
                QtCore.Qt.Key_Escape:    self.escape,
                QtCore.Qt.Key_N:         self.new,
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


def main(args: dict):
    logging.basicConfig(level=logging.INFO)

    LOG.info(sys.executable)
    LOG.info('.'.join((str(e) for e in sys.version_info)))

    app = QtWidgets.QApplication(sys.argv)

    with open(os.path.join(APP_DIR, STYLESHEET)) as f:
        app.setStyleSheet(f.read())

    ex = Picks(args)

    for s in (signal.SIGABRT, signal.SIGINT, signal.SIGSEGV, signal.SIGTERM):
        signal.signal(s, lambda signal, frame: ex.handle_signal(signal))

    # catch the interpreter every now and then to be able to catch signals
    timer = QtCore.QTimer()
    timer.start(200)
    timer.timeout.connect(lambda: None)

    sys.exit(app.exec_())


if __name__ == '__main__':
    class Args:
        pass
    args = Args()
    args.directory = '.' if len(sys.argv) < 2 else sys.argv[1]
    main(args)

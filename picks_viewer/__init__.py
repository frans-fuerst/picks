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

        self._buttons = {}
        for _, c, bl in (
            ('rename',     lambda: None, {QtCore.Qt.Key_F2}),
            ('edit',       lambda: None, {QtCore.Qt.Key_F3}),
            ('slideshow',  lambda: None, {QtCore.Qt.Key_F5}),
            ('copy',       self.copy_current_file, {QtCore.Qt.Key_F7}),
            ('copy',       self.move_current_file, {QtCore.Qt.Key_F6}),
            ('copy',       self.delete_current_file, {QtCore.Qt.Key_Delete}),
            ('link',       lambda: None, {QtCore.Qt.Key_F8}),
            ('tag-dialog', self.toggle_tag_dialog, {QtCore.Qt.Key_T}),
            ('find',       self.txt_file_filter.setFocus, {QtCore.Qt.Key_F}),
            ('fullscreen', self.toggle_fullscreen, {QtCore.Qt.Key_F11}),
            ('escape',     self.escape, {QtCore.Qt.Key_Escape}),
            ('previous',   lambda: self.jump(-1), {QtCore.Qt.Key_Backspace, QtCore.Qt.Key_Left, QtCore.Qt.Key_Up}),
            ('next',       lambda: self.jump(1), {QtCore.Qt.Key_Space, QtCore.Qt.Key_Right, QtCore.Qt.Key_Down}),
            ('jump-back',       lambda: self.jump(-10), {QtCore.Qt.Key_PageUp}),
            ('jump',       lambda: self.jump(10), {QtCore.Qt.Key_PageDown}),
            ('first',       lambda: self.goto(0), {QtCore.Qt.Key_Home}),
            ('last',       lambda: self.goto(-1), {QtCore.Qt.Key_End}),
            ('none',       lambda: None, {QtCore.Qt.Key_Return, QtCore.Qt.Key_Alt}),
            ('help',       self.help, {QtCore.Qt.Key_F1, QtCore.Qt.Key_H}),
            ('clear-cache',       self._clean_cache, {QtCore.Qt.Key_C}),
        ):
            for b in bl:
                self._buttons[b] = c

        self._config = self._read_config(CONFIG_FILE)
        if not 'tags' in self._config:
            self._config['tags'] = []
        self._image_cache = {}

        self.lbl_notification = QtWidgets.QLabel(self.lbl_viewer)
        self.setMouseTracking(True)

        self.frm_tags.setVisible(False)

        self.lst_files.itemClicked.connect(self.list_item_clicked)
        self.txt_file_filter.textChanged.connect(self.filter_changed)
        self.txt_tag_filter.textChanged.connect(self.tag_filter_changed)
        self.txt_tag_filter.returnPressed.connect(self.tag_filter_return_pressed)

        self.lst_files.keyPressEvent = self.other_widgets_keypress_event

        if os.path.isfile(args.directory):
            filename = os.path.basename(args.directory)
            os.chdir(os.path.dirname(args.directory))
        else:
            directory = os.path.abspath(args.directory)
            filename = self._config.setdefault('recent_files', {}).setdefault(directory, None)
            os.chdir(directory)

        self.le_directory.setText(os.getcwd())
        self.update_tag_list(picks_core.list_pics())
        self.list_files()

        self.show()

        self.goto(self.get_index(filename))

    def _set_config_value(self, key, value) -> None:
        if isinstance(key, str):
            *path, name = key.split('/')
        elif isinstance(key, tuple):
            *path, name = key

        subtree = self._config
        for e in path:
            if not e in subtree:
                subtree[e] = {}
            subtree = subtree[e]

        subtree[name] = value

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
        current_filename = self.selected_filename()
        current_index = max(self.selected_index(), 0)
        self.lst_files.clear()
        p_lower = self.txt_file_filter.text().lower()
        filenames = picks_core.list_pics()
        for f in filenames:
            if p_lower not in f.lower():
                continue
            self.lst_files.addItem(f)
            if f == current_filename:
                current_filename = self.lst_files.count()

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
        if not self.lst_files.count():
            return
        self.lst_files.setCurrentRow(
            self.lst_files.count() - 1 if index < 0 else index)
        filename = self.selected_filename()
        LOG.info('show file %d: %s', self.selected_index(), filename)
        self.set_image(filename)
        self.repaint()
        QtCore.QMetaObject.invokeMethod(
            self, "preload", QtCore.Qt.QueuedConnection)

    @QtCore.pyqtSlot()
    def preload(self):
        for i in range(-1, 3):
            try:
                self.fetch_image_data(
                    self.lst_files.item(self.selected_index() + i).text())
            except AttributeError:
                # ignore index overflow
                pass

    def selected_filename(self) -> str:
        try:
            return self.lst_files.currentItem().text()
        except AttributeError:
            return None

    def selected_index(self) -> int:
        return self.lst_files.currentRow()

    def get_index(self, filename: str) -> int:
        for i in range(self.lst_files.count()):
            if self.lst_files.item(i).text() == filename:
                return i
        return 0

    def _clean_cache(self):
        if len(self._image_cache) > 40:
            self._image_cache = {}

    def fetch_image_data(self, filename: str) -> list:
        def load_image(filename: str) -> list:
            sizeObject = QtWidgets.QDesktopWidget().screenGeometry(-1)
            screenw, screenh = sizeObject.width(), sizeObject.height()
            t1 = time.time()
            tags = picks_core.get_tags(filename)
            t2 = time.time()

            pixmap = QtGui.QPixmap(filename).transformed(
                 QtGui.QTransform().rotate(
                     picks_core.get_orientation(tags))).scaled(
                         screenw, screenh,
                         QtCore.Qt.KeepAspectRatio,
                         QtCore.Qt.SmoothTransformation
                     )
            t3 = time.time()
            LOG.info('tot: %.2f tags: %.2f pic: %.2f',
                     t3 - t1, t2 - t1, t3 - t2)
            return [pixmap, tags]

        self._clean_cache()

        abs_file = os.path.abspath(filename)
        if not abs_file in self._image_cache:
            self._image_cache[abs_file] = load_image(filename)
            self._image_cache[abs_file].append(0.0)

        self._image_cache[abs_file][2] = time.time()

        return self._image_cache[abs_file]

    def set_image(self, filename: str):
        pixmap, *_ = self.fetch_image_data(filename)
        self.setWindowTitle('Picks - %s' % filename)
        self.lbl_viewer.setPixmap(pixmap.scaled(
            self.lbl_viewer.width(), self.lbl_viewer.height(),
            QtCore.Qt.KeepAspectRatio,
            QtCore.Qt.SmoothTransformation
        ))
        self.lbl_viewer.setMask(pixmap.mask())
        self._set_config_value(('recent_files', os.getcwd()), filename)

    def tag_filter_changed(self, text):
        self.lst_tags.clear()
        for t in self._config['tags']:
            if text in t:
                self.lst_tags.addItem(t)

    def tag_filter_return_pressed(self):
        # todo: restrict allowed characters in lineEdit
        if QtWidgets.QApplication.queryKeyboardModifiers() == QtCore.Qt.ShiftModifier:
            tag = self.txt_tag_filter.text().lower()
            if not picks_core.is_valid_tag(tag) or tag in self._config['tags']:
                return
            self.show_notification('added new tag "%s"' % tag)
            self._config['tags'].append(tag)
            self.txt_tag_filter.setText('')
            self._write_config(CONFIG_FILE, self._config)
        else:
            if self.lst_tags.count() == 1:
                self.apply_tag_to_current_file(self.lst_tags.item(0).text())
                self.txt_tag_filter.setText('')

    def apply_tag_to_current_file(self, tag: str):
        picks_core.add_tag_to_file(self.selected_filename(), tag)
        self.show_notification('Added tag: %s' % tag)
        self.list_files()

    def mouseReleaseEvent(self, event):
        pass

    def handle_signal(self, _: int) -> None:
        self.close()

    def copy_current_file(self):
        os.makedirs(SELECTED_DIR_NAME, exist_ok=True)
        src_filename = self.selected_filename()
        dst_filename = os.path.join(SELECTED_DIR_NAME, src_filename)
        if os.path.exists(dst_filename):
            self.show_notification('File already selected: %s' % src_filename)
        else:
            shutil.copyfile(src_filename, dst_filename)
            self.show_notification('Added to selected pictures: %s' % src_filename)

    def move_current_file(self):
        os.makedirs(SELECTED_DIR_NAME, exist_ok=True)
        filename = self.selected_filename()
        shutil.move(filename, os.path.join(SELECTED_DIR_NAME, filename))
        self.list_files()
        self.show_notification('Moved to selected pictures: %s' % filename)

    def delete_current_file(self):
        os.makedirs(DELETED_DIR_NAME, exist_ok=True)
        filename = self.selected_filename()
        shutil.move(filename, os.path.join(DELETED_DIR_NAME, filename))
        self.list_files()
        self.show_notification('Marked as deleted: %s' % filename)

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

    def toggle_tag_dialog(self):
        if not self.frm_tags.isVisible():
            self.enter_tag_dialog()
        else:
            self.leave_tag_dialog()

    def enter_tag_dialog(self):
        self.frm_tags.setVisible(True)
        self.tag_filter_changed('')
        self.txt_tag_filter.setFocus()

    def leave_tag_dialog(self):
        self.frm_tags.setVisible(False)
        self.txt_file_filter.setFocus()

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.leave_fullscreen()
        else:
            self.enter_fullscreen()

    def enter_fullscreen(self):
        self.frm_filelist.setVisible(False)
        self.le_directory.setVisible(False)
        self.txt_file_filter.setEnabled(False)
        self.showFullScreen()

    def leave_fullscreen(self):
        self.frm_filelist.setVisible(True)
        self.le_directory.setVisible(True)
        self.txt_file_filter.setEnabled(True)
        self.showNormal()

    def escape(self):
        if self.frm_tags.isVisible():
            self.leave_tag_dialog()
        elif self.isFullScreen():
            self.leave_fullscreen()
        else:
            self.lst_files.setFocus()

    def help(self):
        QtWidgets.QMessageBox.question(
            self, 'Keys',
            'F2: rename\n'
            'F6: move\n'
            'F7: copy\n'
            'DEL: delete\n'
            'T: show tag dialog\n'
            'F: find\n'
            'F11: toggle fullscreen\n'
            'ESC: back\n'
            'BACK/Left/Up: previous\n'
            'Space/Right/Down: next\n'
            'PG_UP: jump+10\n'
            'PG_DOWN: jump-10\n'
            'HOME: jump to first\n'
            'END: jump to last\n'
            'F1/H: this help',
            QtWidgets.QMessageBox.Ok)

    def resizeEvent(self, event: QtGui.QResizeEvent):
        try:
            self.set_image(self.selected_filename())
        except AttributeError:
            pass

    def keyPressEvent(self, event):
        try:
            self._buttons[event.key()]()
        except KeyError:
            LOG.warning('unknown key %d', event.key())


def main(args: dict):
    class Args:
        pass
    args = Args()
    args.directory = '.' if len(sys.argv) < 2 else sys.argv[1]

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
    main(args)

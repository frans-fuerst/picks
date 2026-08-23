#!/usr/bin/env python3
# Copyright (c) 2017-2026 Frans Fürst
"""PyQt6 image viewer for picks."""

import ast
import json
import logging
import os
import shutil
import signal
import subprocess
import sys
import time
from contextlib import suppress
from pathlib import Path

from PyQt6 import QtCore, QtGui, QtWidgets, uic

from picks.application import picks_core
from picks.application.picks_viewer.photoframe import PhotoFrameDialog

LOG = logging.getLogger("picks")
STYLESHEET = "QTDark.stylesheet"
APP_DIR = str(Path(__file__).resolve().parent)
SELECTED_DIR_NAME = "_PICKS"
DELETED_DIR_NAME = ".picks.deleted"
CONFIG_FILE = str(Path("~/.picks/config").expanduser())
SIMILAR_EXTENSIONS = {".PNG", ".JPG", ".CR2"}
CACHE_SIZE_LIMIT = 40
MIN_ARGV_LENGTH = 2


class Args:
    """CLI arguments for the viewer."""

    def __init__(self) -> None:
        """Read the target directory from argv (default '.')."""
        self.directory: str = (
            "." if len(sys.argv) < MIN_ARGV_LENGTH else sys.argv[1]
        )


class Picks(QtWidgets.QMainWindow):
    """Main viewer window."""

    def __init__(self, args: Args) -> None:
        """Build the UI and bind keyboard shortcuts."""
        super().__init__()
        uic.loadUi(str(Path(APP_DIR) / "picks.ui"), self)

        self._buttons: dict[int, object] = {}
        for _name, c, bl in (
            ("rename", self.rename_current_file, {QtCore.Qt.Key.Key_F2}),
            (
                "edit",
                lambda: self.edit_current_file("shotwell"),
                {QtCore.Qt.Key.Key_F3},
            ),
            (
                "gimp",
                lambda: self.edit_current_file("gimp"),
                {QtCore.Qt.Key.Key_G},
            ),
            ("photoframe", self.send_to_photoframe, {QtCore.Qt.Key.Key_F4}),
            ("slideshow", lambda: None, {QtCore.Qt.Key.Key_F5}),
            ("move", self.move_current_file, {QtCore.Qt.Key.Key_F6}),
            ("copy", self.copy_current_file, {QtCore.Qt.Key.Key_F7}),
            ("delete", self.delete_current_file, {QtCore.Qt.Key.Key_Delete}),
            ("link", lambda: None, {QtCore.Qt.Key.Key_F8}),
            ("tag-dialog", self.toggle_tag_dialog, {QtCore.Qt.Key.Key_T}),
            ("find", self.txt_file_filter.setFocus, {QtCore.Qt.Key.Key_F}),
            ("fullscreen", self.toggle_fullscreen, {QtCore.Qt.Key.Key_F11}),
            ("zoom", self.toggle_zoom, {QtCore.Qt.Key.Key_F12}),
            ("escape", self.escape, {QtCore.Qt.Key.Key_Escape}),
            (
                "previous",
                lambda: self.jump(-1),
                {
                    QtCore.Qt.Key.Key_Backspace,
                    QtCore.Qt.Key.Key_Left,
                    QtCore.Qt.Key.Key_Up,
                },
            ),
            (
                "next",
                lambda: self.jump(1),
                {
                    QtCore.Qt.Key.Key_Space,
                    QtCore.Qt.Key.Key_Right,
                    QtCore.Qt.Key.Key_Down,
                },
            ),
            ("jump-back", lambda: self.jump(-10), {QtCore.Qt.Key.Key_PageUp}),
            ("jump", lambda: self.jump(10), {QtCore.Qt.Key.Key_PageDown}),
            ("first", lambda: self.goto(0), {QtCore.Qt.Key.Key_Home}),
            ("last", lambda: self.goto(-1), {QtCore.Qt.Key.Key_End}),
            (
                "none",
                lambda: None,
                {QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Alt},
            ),
            ("help", self.help, {QtCore.Qt.Key.Key_F1, QtCore.Qt.Key.Key_H}),
            (
                "clear-cache",
                lambda: self._clean_cache(force=True),
                {QtCore.Qt.Key.Key_C},
            ),
        ):
            for b in bl:
                self._buttons[b] = c

        self._config: dict[str, object] = self._read_config(CONFIG_FILE)
        if "tags" not in self._config:
            self._config["tags"] = []
        self._image_cache: dict[str, list[object]] = {}
        self._zoomed = False

        self.lbl_notification = QtWidgets.QLabel(self.lbl_viewer)
        self.setMouseTracking(True)

        self.frm_tags.setVisible(False)

        self.lst_files.itemClicked.connect(self.list_item_clicked)
        self.txt_file_filter.textChanged.connect(self.filter_changed)
        self.txt_tag_filter.textChanged.connect(self.tag_filter_changed)
        self.txt_tag_filter.returnPressed.connect(
            self.tag_filter_return_pressed,
        )

        self.lst_files.keyPressEvent = self.other_widgets_keypress_event

        directory_path = Path(args.directory)
        if directory_path.is_file():
            filename = directory_path.name
            os.chdir(str(directory_path.parent))
        else:
            directory = str(directory_path.resolve())
            filename = self._config.setdefault("recent_files", {}).setdefault(  # type: ignore[union-attr]
                directory, None,
            )
            os.chdir(directory)

        self.le_directory.setText(str(Path.cwd()))
        self.update_tag_list(picks_core.list_pics())
        self.list_files()

        self.show()

        self.goto(self.get_index(filename))

    def _set_config_value(
        self,
        key: str | tuple[str, ...],
        value: object,
    ) -> None:
        """Set a (possibly nested) config value and persist it."""
        if isinstance(key, str):
            *path, name = key.split("/")
        elif isinstance(key, tuple):
            *path, name = key
        else:
            msg = f"unsupported key type: {type(key)}"
            raise TypeError(msg)

        subtree: dict[str, object] = self._config  # type: ignore[assignment]
        for e in path:
            if e not in subtree:
                subtree[e] = {}
            subtree = subtree[e]  # type: ignore[assignment]

        subtree[name] = value

        self._write_config(CONFIG_FILE, self._config)

    @staticmethod
    def _read_config(filename: str) -> dict[str, object]:
        """Read the JSON config file; return {} if missing."""
        try:
            with Path(filename).open() as f:
                return ast.literal_eval(f.read())  # type: ignore[return-value]
        except FileNotFoundError:
            return {}

    @staticmethod
    def _write_config(filename: str, data: dict[str, object]) -> None:
        """Write the config file, creating parent dirs as needed."""
        p = Path(filename)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w") as f:
            json.dump(data, f)

    def update_file_list(self) -> None:
        """Refresh the file list (currently a no-op hook)."""

    def update_tag_list(self, filenames: list[str]) -> None:
        """Merge tags found in filenames into the stored tag list."""
        new_tags = self._config.get("tags", [])  # type: ignore[assignment]
        for t in picks_core.get_all_tags(filenames):
            if t not in new_tags:
                new_tags.append(t)
        self._config["tags"] = new_tags

    def other_widgets_keypress_event(self, event: QtGui.QKeyEvent) -> None:
        """Forward key presses from child widgets to the main handler."""
        self.keyPressEvent(event)

    def list_files(self) -> None:
        """Repopulate the file list widget from disk."""
        current_index = max(self.selected_index(), 0)
        self.lst_files.clear()
        p_lower = self.txt_file_filter.text().lower()
        filenames = picks_core.list_pics()
        for f in filenames:
            if p_lower not in f.lower():
                continue
            self.lst_files.addItem(f)

        self.goto(current_index)

    def filter_changed(self, _text: str) -> None:
        """React to the file filter text changing."""
        self.list_files()

    def list_item_clicked(self, _item: object) -> None:
        """Jump to the clicked list item."""
        self.goto(self.lst_files.currentRow())

    def jump(self, items: int) -> None:
        """Move the selection by a number of items, clamped to bounds."""
        next_index = self.selected_index() + items
        self.goto(
            0
            if next_index < 0
            else self.lst_files.count() - 1
            if next_index >= self.lst_files.count()
            else next_index,
        )

    def goto(self, index: int) -> None:
        """Select and show the file at the given index."""
        if not self.lst_files.count():
            return
        self.lst_files.setCurrentRow(
            self.lst_files.count() - 1 if index < 0 else index,
        )
        filename = self.selected_filename()
        LOG.info("show file %d: %s", self.selected_index(), filename)
        self.set_image(filename)
        self.repaint()
        QtCore.QMetaObject.invokeMethod(
            self,
            "preload",
            QtCore.Qt.ConnectionType.QueuedConnection,
        )

    @QtCore.pyqtSlot()
    def preload(self) -> None:
        """Preload images around the current selection."""
        for i in range(-1, 3):
            with suppress(AttributeError):
                # ignore index overflow
                self.fetch_image_data(
                    self.lst_files.item(self.selected_index() + i).text(),
                )

    def selected_filename(self) -> str | None:
        """Return the currently selected filename, or None."""
        try:
            return self.lst_files.currentItem().text()
        except AttributeError:
            return None

    def selected_index(self) -> int:
        """Return the row index of the current selection."""
        return self.lst_files.currentRow()

    def get_index(self, filename: str) -> int:
        """Find the list index of a filename; 0 if absent."""
        for i in range(self.lst_files.count()):
            if self.lst_files.item(i).text() == filename:
                return i
        return 0

    def _clean_cache(self, *, force: bool = False) -> None:
        """Clear the image cache if forced or over the size limit."""
        if force or len(self._image_cache) > CACHE_SIZE_LIMIT:
            self._image_cache = {}

    def fetch_image_data(self, filename: str) -> list[object]:
        """Load (and cache) a scaled pixmap and its EXIF tags."""

        def load_image(fname: str) -> list[object]:
            screen = QtWidgets.QApplication.primaryScreen()
            if screen is not None:
                size_object = screen.geometry()
            else:
                size_object = QtCore.QRect(0, 0, 1920, 1080)
            screenw, screenh = size_object.width(), size_object.height()
            t1 = time.time()
            tags = picks_core.get_tags(fname)
            t2 = time.time()

            raw_pixmap = QtGui.QPixmap(fname)
            pixmap = raw_pixmap.transformed(
                QtGui.QTransform().rotate(picks_core.get_orientation(tags)),
            ).scaled(
                screenw,
                screenh,
                QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation,
            )
            t3 = time.time()
            LOG.info(
                "tot: %.2f tags: %.2f pic: %.2f",
                t3 - t1,
                t2 - t1,
                t3 - t2,
            )
            LOG.info("%dx%d", raw_pixmap.width(), raw_pixmap.height())
            return [pixmap, tags]

        self._clean_cache()

        abs_file = str(Path(filename).resolve())
        if abs_file not in self._image_cache:
            self._image_cache[abs_file] = load_image(filename)
            self._image_cache[abs_file].append(0.0)

        self._image_cache[abs_file][2] = time.time()

        return self._image_cache[abs_file]

    def set_image(self, filename: str | None) -> None:
        """Display an image and its EXIF-derived info."""
        if filename is None:
            self.lbl_viewer.setPixmap(QtGui.QPixmap())
            return

        pixmap, tags, _ = self.fetch_image_data(filename)  # type: ignore[misc]
        self.setWindowTitle(f"Picks - {filename}")
        image_data: list[str] = []
        with suppress(KeyError):
            image_data.append(tags["EXIF DateTimeOriginal"].printable)  # type: ignore[union-attr]
        with suppress(KeyError):
            image_data.append(
                f"{tags['EXIF FocalLength'].printable}mm "  # type: ignore[union-attr]
                f"({tags['EXIF LensModel'].printable})",  # type: ignore[union-attr]
            )
        with suppress(KeyError):
            image_data.append(
                f"{tags['EXIF ExifImageLength'].printable}"  # type: ignore[union-attr]
                f"x{tags['EXIF ExifImageWidth'].printable}",  # type: ignore[union-attr]
            )

        self.lbl_file_info.setText("\n".join(image_data))
        if self._zoomed:
            self.lbl_viewer.setPixmap(
                pixmap.transformed(QtGui.QTransform().translate(500, 500)),  # type: ignore[union-attr]
            )
        else:
            self.lbl_viewer.setPixmap(
                pixmap.scaled(  # type: ignore[union-attr]
                    self.lbl_viewer.width(),
                    self.lbl_viewer.height(),
                    QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                    QtCore.Qt.TransformationMode.SmoothTransformation,
                ),
            )
        self.lbl_viewer.setMask(pixmap.mask())  # type: ignore[union-attr]
        self._set_config_value(("recent_files", str(Path.cwd())), filename)

    def tag_filter_changed(self, text: str) -> None:
        """Filter the tag list widget by the given text."""
        self.lst_tags.clear()
        for t in self._config["tags"]:  # type: ignore[union-attr]
            if text in t:
                self.lst_tags.addItem(t)

    def tag_filter_return_pressed(self) -> None:
        """Handle Enter in the tag filter: add a new tag or apply one."""
        if (
            QtWidgets.QApplication.queryKeyboardModifiers()
            == QtCore.Qt.KeyboardModifier.ShiftModifier
        ):
            tag = self.txt_tag_filter.text().lower()
            if not picks_core.is_valid_tag(tag) or tag in self._config["tags"]:  # type: ignore[operator]
                return
            self.show_notification(f'added new tag "{tag}"')
            self._config["tags"].append(tag)  # type: ignore[union-attr]
            self.txt_tag_filter.setText("")
            self._write_config(CONFIG_FILE, self._config)
        elif self.lst_tags.count() == 1:
            self.apply_tag_to_current_file(self.lst_tags.item(0).text())
            self.txt_tag_filter.setText("")

    def apply_tag_to_current_file(self, tag: str) -> None:
        """Apply a tag to the selected file and refresh the list."""
        picks_core.add_tag_to_file(self.selected_filename(), tag)  # type: ignore[arg-type]
        self.show_notification(f"Added tag: {tag}")
        self.list_files()

    def mouseReleaseEvent(self, _event: QtGui.QMouseEvent) -> None:  # noqa: N802
        """Mouse release handler (currently a no-op)."""

    def handle_signal(self, _: int) -> None:
        """Close the window on a caught signal."""
        self.close()

    def rename_current_file(self) -> None:
        """Rename the current file (not yet implemented)."""

    def edit_current_file(self, tool: str = "shotwell") -> None:
        """Open the selected file in an external editor."""
        filename = str(Path(self.selected_filename()).resolve())  # type: ignore[arg-type]
        subprocess.Popen(args=[tool, filename])  # noqa: S603

    def send_to_photoframe(self) -> None:
        """Open the photo frame upload dialog for the current image."""
        filename = self.selected_filename()
        if filename is None:
            return
        dialog = PhotoFrameDialog(str(Path(filename).resolve()), self)
        dialog.exec()

    def copy_current_file(self) -> None:
        """Copy the selected file (and similar ones) to the selection dir."""
        Path(SELECTED_DIR_NAME).mkdir(exist_ok=True)
        src_filename = self.selected_filename()
        if src_filename is None:
            return
        if Path(SELECTED_DIR_NAME, src_filename).exists():
            self.show_notification(f"File already selected: {src_filename}")
            return
        to_be_copied = self.similar_files(src_filename)
        for fname in to_be_copied:
            shutil.copyfile(fname, str(Path(SELECTED_DIR_NAME) / fname))

        self.show_notification(
            "Added to selected pictures: \n" + "\n".join(to_be_copied),
        )

    def move_current_file(self) -> None:
        """Move the selected file into the selection directory."""
        Path(SELECTED_DIR_NAME).mkdir(exist_ok=True)
        filename = self.selected_filename()
        if filename is None:
            return
        shutil.move(filename, str(Path(SELECTED_DIR_NAME) / filename))
        self.list_files()
        self.show_notification(f"Moved to selected pictures: {filename}")

    @staticmethod
    def similar_files(filename: str) -> list[str]:
        """Return files sharing the same base name and an image extension."""
        p = Path(filename)
        prefix = str(p.with_suffix(""))
        return [
            f.name
            for f in Path.cwd().glob(f"{prefix}*")
            if f.suffix.upper() in SIMILAR_EXTENSIONS
        ]

    def delete_current_file(self) -> None:
        """Move the selected file (and similar ones) to the deleted dir."""
        Path(DELETED_DIR_NAME).mkdir(exist_ok=True)
        src = self.selected_filename()
        if src is None:
            return
        to_be_deleted = self.similar_files(src)
        for fname in to_be_deleted:
            shutil.move(fname, str(Path(DELETED_DIR_NAME) / fname))

        self.list_files()
        self.show_notification(
            "Marked as deleted: \n" + "\n".join(to_be_deleted),
        )

    def show_notification(self, msg: str) -> None:
        """Show a transient notification over the image area."""
        LOG.info(msg)
        self.lbl_notification.setText(msg)
        new_width = (
            self.lbl_notification.fontMetrics().horizontalAdvance(msg) + 50
        )
        self.lbl_notification.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.lbl_notification.setGeometry(
            QtCore.QRect(
                (self.lbl_viewer.width() - new_width) // 2,
                (self.lbl_viewer.height() - 50) // 2,
                new_width,
                50,
            ),
        )
        self.lbl_notification.setVisible(True)
        QtCore.QTimer.singleShot(
            1500,
            lambda: self.lbl_notification.setVisible(False),
        )

    def toggle_tag_dialog(self) -> None:
        """Toggle the tag dialog visibility."""
        if not self.frm_tags.isVisible():
            self.enter_tag_dialog()
        else:
            self.leave_tag_dialog()

    def enter_tag_dialog(self) -> None:
        """Show and focus the tag dialog."""
        self.frm_tags.setVisible(True)
        self.tag_filter_changed("")
        self.txt_tag_filter.setFocus()

    def leave_tag_dialog(self) -> None:
        """Hide the tag dialog and refocus the file filter."""
        self.frm_tags.setVisible(False)
        self.txt_file_filter.setFocus()

    def toggle_fullscreen(self) -> None:
        """Toggle fullscreen mode."""
        if self.isFullScreen():
            self.leave_fullscreen()
        else:
            self.enter_fullscreen()

    def enter_fullscreen(self) -> None:
        """Hide the chrome and go fullscreen."""
        self.frm_filelist.setVisible(False)
        self.le_directory.setVisible(False)
        self.txt_file_filter.setEnabled(False)
        self.showFullScreen()

    def leave_fullscreen(self) -> None:
        """Restore the chrome and normal window size."""
        self.frm_filelist.setVisible(True)
        self.le_directory.setVisible(True)
        self.txt_file_filter.setEnabled(True)
        self.showNormal()

    def escape(self) -> None:
        """Handle Escape: close dialog, exit fullscreen, or focus list."""
        if self.frm_tags.isVisible():
            self.leave_tag_dialog()
        elif self.isFullScreen():
            self.leave_fullscreen()
        else:
            self.lst_files.setFocus()

    def help(self) -> None:
        """Show the key bindings help dialog."""
        QtWidgets.QMessageBox.question(
            self,
            "Keys",
            "F2: rename\n"
            "F4: send to photoframe\n"
            "F6: move\n"
            "F7: copy\n"
            "DEL: delete\n"
            "T: show tag dialog\n"
            "F: find\n"
            "F11: toggle fullscreen\n"
            "ESC: back\n"
            "BACK/Left/Up: previous\n"
            "Space/Right/Down: next\n"
            "PG_UP: jump+10\n"
            "PG_DOWN: jump-10\n"
            "HOME: jump to first\n"
            "END: jump to last\n"
            "F1/H: this help",
            QtWidgets.QMessageBox.StandardButton.Ok,
        )

    def toggle_zoom(self) -> None:
        """Toggle zoom and re-render the current image."""
        self._zoomed = not self._zoomed
        self.set_image(self.selected_filename())

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802, ARG002
        """Re-render the image when the window is resized."""
        with suppress(AttributeError):
            self.set_image(self.selected_filename())

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:  # noqa: N802
        """Dispatch a key press to its bound action, if any."""
        try:
            self._buttons[event.key()]()  # type: ignore[operator]
        except KeyError:
            LOG.warning("unknown key %d", event.key())


def main(_args: Args | None = None) -> None:
    """Create the QApplication and run the viewer."""
    args = Args()

    logging.basicConfig(level=logging.INFO)

    LOG.info(sys.executable)
    LOG.info(".".join(str(e) for e in sys.version_info))

    app = QtWidgets.QApplication(sys.argv)

    with Path(APP_DIR, STYLESHEET).open() as f:
        app.setStyleSheet(f.read())

    ex = Picks(args)

    for s in (signal.SIGABRT, signal.SIGINT, signal.SIGSEGV, signal.SIGTERM):
        signal.signal(s, lambda signum, _frame: ex.handle_signal(signum))

    # catch the interpreter every now and then to be able to catch signals
    timer = QtCore.QTimer()
    timer.start(200)
    timer.timeout.connect(lambda: None)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

# Copyright (c) 2017-2026 Frans Fürst
"""Photo frame upload dialog: convert and send image to ESP32 photo frame."""

import io
import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import requests
from PIL import Image, ImageOps
from PyQt6 import QtCore, QtGui, QtWidgets

LOG = logging.getLogger("picks")

PHOTOFRAME_HOST = "photoframe.local"
THUMBNAIL_MAX_DIM = 400
REQUEST_TIMEOUT = 10

# sRGB gamma conversion constants
_SRGB_GAMMA_THRESHOLD = 0.04045
_SRGB_LINEAR_THRESHOLD = 0.0031308
_EPSILON = 1e-6


@dataclass
class DeviceInfo:
    """Device display and processing info."""

    width: int
    height: int
    palette: dict[str, tuple[int, int, int]]
    processing: dict[str, object]


# Theoretical palette (what goes into the output PNG for firmware compat)
# Index order matches firmware: 0=black, 1=white, 2=yellow, 3=red, 4=reserved,
# 5=blue, 6=green
SPECTRA6_THEORETICAL = np.array(
    [
        [0, 0, 0],       # black
        [255, 255, 255],  # white
        [255, 255, 0],   # yellow
        [255, 0, 0],     # red
        [0, 0, 0],       # reserved (skip)
        [0, 0, 255],     # blue
        [0, 255, 0],     # green
    ],
    dtype=np.float64,
)

# Floyd-Steinberg error diffusion weights (numerator / denominator)
_FS_RIGHT = 7.0 / 16.0
_FS_BELOW_LEFT = 3.0 / 16.0
_FS_BELOW = 5.0 / 16.0
_FS_BELOW_RIGHT = 1.0 / 16.0


def _srgb_to_linear(v: float) -> float:
    """Convert sRGB [0..1] to linear light."""
    if v <= _SRGB_GAMMA_THRESHOLD:
        return v / 12.92
    return float(((v + 0.055) / 1.055) ** 2.4)


def _linear_to_srgb(v: float) -> int:
    """Convert linear light [0..1] to sRGB byte."""
    if v <= 0.0:
        return 0
    if v >= 1.0:
        return 255
    if v <= _SRGB_LINEAR_THRESHOLD:
        s = 12.92 * v
    else:
        s = 1.055 * v ** (1.0 / 2.4) - 0.055
    return max(0, min(255, round(s * 255)))


def _compute_cdr_range(
    palette: dict[str, tuple[int, int, int]],
) -> tuple[float, float]:
    """Compute CDR black/white luminance range from measured palette."""
    black = palette.get("black", (0, 0, 0))
    white = palette.get("white", (255, 255, 255))

    def luminance(rgb: tuple[int, int, int]) -> float:
        r = _srgb_to_linear(rgb[0] / 255.0)
        g = _srgb_to_linear(rgb[1] / 255.0)
        b = _srgb_to_linear(rgb[2] / 255.0)
        return 0.2126729 * r + 0.7151522 * g + 0.0721750 * b

    black_y = luminance(black)
    white_y = luminance(white)
    return black_y, white_y - black_y


def _apply_cdr(
    img_array: np.ndarray,
    black_y: float,
    range_y: float,
) -> np.ndarray:
    """Apply Compressed Dynamic Range to an RGB image array (uint8)."""
    # Convert to linear float [0..1]
    srgb = img_array.astype(np.float64) / 255.0
    lin = np.where(
        srgb <= _SRGB_GAMMA_THRESHOLD,
        srgb / 12.92,
        ((srgb + 0.055) / 1.055) ** 2.4,
    )

    # Compute luminance per pixel
    y = (
        0.2126729 * lin[:, :, 0]
        + 0.7151522 * lin[:, :, 1]
        + 0.0721750 * lin[:, :, 2]
    )

    # Compressed luminance mapped to [black_y, white_y]
    compressed_y = black_y + y * range_y

    # Scale RGB channels proportionally
    scale = np.where(
        y > _EPSILON,
        compressed_y / np.maximum(y, _EPSILON),
        0.0,
    )
    lin_out = lin * scale[:, :, np.newaxis]

    # Convert back to sRGB bytes
    srgb_out = np.where(
        lin_out <= _SRGB_LINEAR_THRESHOLD,
        12.92 * lin_out,
        1.055 * np.power(np.maximum(lin_out, 0), 1.0 / 2.4) - 0.055,
    )
    return np.clip(srgb_out * 255.0, 0, 255).astype(np.uint8)


def _floyd_steinberg_dither(
    img_array: np.ndarray,
    measured_palette: np.ndarray,
    theoretical_palette: np.ndarray,
) -> np.ndarray:
    """Apply Floyd-Steinberg dithering in sRGB space.

    Matches the firmware's dither_row(): works in sRGB [0..255], matches
    against measured palette, outputs theoretical palette colors, diffuses
    error relative to measured palette values.
    """
    h, w, _ = img_array.shape
    work = img_array.astype(np.float64)

    meas = np.delete(measured_palette, 4, axis=0)
    theo = np.delete(theoretical_palette, 4, axis=0)

    curr_errors = np.zeros((w, 3), dtype=np.float64)
    next_errors = np.zeros((w, 3), dtype=np.float64)

    for y in range(h):
        row = work[y].copy()
        for x in range(w):
            pv = row[x] + curr_errors[x]
            pv = np.clip(pv, 0.0, 255.0)

            dists = np.sum((meas - pv) ** 2, axis=1)
            idx = int(np.argmin(dists))

            work[y, x] = theo[idx]
            err = pv - meas[idx]

            if x + 1 < w:
                curr_errors[x + 1] += err * _FS_RIGHT
            if x - 1 >= 0:
                next_errors[x - 1] += err * _FS_BELOW_LEFT
            next_errors[x] += err * _FS_BELOW
            if x + 1 < w:
                next_errors[x + 1] += err * _FS_BELOW_RIGHT

        curr_errors, next_errors = next_errors, curr_errors
        next_errors[:] = 0.0

    return work.astype(np.uint8)


def convert_for_photoframe(
    filepath: str,
    display_w: int,
    display_h: int,
    palette: dict[str, tuple[int, int, int]],
) -> Image.Image:
    """Convert an image to 6-color Spectra format for the photo frame.

    Pipeline: load, EXIF orient, cover-scale, CDR, FS dither.
    """
    img: Image.Image = Image.open(filepath)
    img = ImageOps.exif_transpose(img)
    if img.mode != "RGB":
        img = img.convert("RGB")

    # Cover-scale to display dimensions (center crop)
    img = ImageOps.fit(img, (display_w, display_h), Image.Resampling.LANCZOS)

    # Build measured palette array in firmware order
    color_names = ["black", "white", "yellow", "red", None, "blue", "green"]
    measured = np.zeros((7, 3), dtype=np.float64)
    for i, name in enumerate(color_names):
        if name is not None:
            rgb = palette.get(name, (0, 0, 0))
            measured[i] = rgb

    # CDR
    black_y, range_y = _compute_cdr_range(palette)
    img_array = np.array(img, dtype=np.uint8)
    img_array = _apply_cdr(img_array, black_y, range_y)

    # Dither
    result = _floyd_steinberg_dither(
        img_array, measured, SPECTRA6_THEORETICAL,
    )

    return Image.fromarray(result, mode="RGB")


def make_thumbnail(filepath: str, max_dim: int = THUMBNAIL_MAX_DIM) -> bytes:
    """Create a JPEG thumbnail of the original image (same as CLI)."""
    img: Image.Image = Image.open(filepath)
    img = ImageOps.exif_transpose(img)
    if img.mode != "RGB":
        img = img.convert("RGB")
    img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return buf.getvalue()


def fetch_device_info(host: str = PHOTOFRAME_HOST) -> DeviceInfo:
    """Fetch display resolution, palette, and processing settings."""
    base = f"http://{host}"

    resp = requests.get(f"{base}/api/system-info", timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    info = resp.json()

    resp = requests.get(
        f"{base}/api/settings/palette", timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    palette_raw = resp.json()
    palette: dict[str, tuple[int, int, int]] = {
        k: (v["r"], v["g"], v["b"]) for k, v in palette_raw.items()
    }

    resp = requests.get(
        f"{base}/api/settings/processing", timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    processing = resp.json()

    return DeviceInfo(
        width=info["width"],
        height=info["height"],
        palette=palette,
        processing=processing,
    )


def upload_to_photoframe(
    image_data: bytes,
    thumbnail_data: bytes,
    host: str = PHOTOFRAME_HOST,
) -> None:
    """Upload and display an image via POST /api/display-image."""
    files = {
        "image": (
            "image.png",
            image_data,
            "image/png",
        ),
        "thumbnail": (
            "thumbnail.jpg",
            thumbnail_data,
            "image/jpeg",
        ),
    }
    resp = requests.post(
        f"http://{host}/api/display-image",
        files=files,
        timeout=60,
    )
    resp.raise_for_status()


class PhotoFrameDialog(QtWidgets.QDialog):
    """Dialog to preview and upload the current image to the photo frame."""

    def __init__(
        self, filepath: str, parent: QtWidgets.QWidget | None = None,
    ) -> None:
        """Build the dialog UI and start background conversion."""
        super().__init__(parent)
        self._filepath = filepath
        self._converted: Image.Image | None = None
        self._thumbnail_data: bytes | None = None

        self.setWindowTitle(f"Send to PhotoFrame - {Path(filepath).name}")
        self.setMinimumSize(640, 480)

        layout = QtWidgets.QVBoxLayout(self)

        self.lbl_status = QtWidgets.QLabel("Converting...")
        self.lbl_status.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_status)

        self.lbl_preview = QtWidgets.QLabel()
        self.lbl_preview.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignCenter,
        )
        self.lbl_preview.setMinimumSize(480, 288)
        self.lbl_preview.setStyleSheet("background-color: #111;")
        layout.addWidget(self.lbl_preview, stretch=1)

        btn_layout = QtWidgets.QHBoxLayout()
        self.btn_upload = QtWidgets.QPushButton("Upload to PhotoFrame (Enter)")
        self.btn_upload.setEnabled(False)
        self.btn_close = QtWidgets.QPushButton("Close (Esc)")
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_upload)
        btn_layout.addWidget(self.btn_close)
        layout.addLayout(btn_layout)

        self.btn_upload.clicked.connect(self._do_upload)
        self.btn_close.clicked.connect(self.reject)

        # Run conversion in a thread to not block the UI
        self._worker = _ConvertWorker(filepath)
        self._worker.finished.connect(self._on_converted)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_converted(
        self,
        image: Image.Image,
        thumbnail: bytes,
        info: DeviceInfo,
    ) -> None:
        self._converted = image
        self._thumbnail_data = thumbnail

        # Show preview
        qimg = _pil_to_qimage(image)
        pixmap = QtGui.QPixmap.fromImage(qimg).scaled(
            self.lbl_preview.width(),
            self.lbl_preview.height(),
            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            QtCore.Qt.TransformationMode.SmoothTransformation,
        )
        self.lbl_preview.setPixmap(pixmap)

        self.lbl_status.setText(
            f"Ready ({info.width}x{info.height}, "
            f"{len(info.palette)} colors)",
        )
        self.btn_upload.setEnabled(True)

    def _on_error(self, msg: str) -> None:
        self.lbl_status.setText(f"Error: {msg}")
        LOG.error("photoframe conversion failed: %s", msg)

    def _do_upload(self) -> None:
        if self._converted is None or self._thumbnail_data is None:
            return

        self.btn_upload.setEnabled(False)
        self.lbl_status.setText("Uploading...")

        worker = _UploadWorker(
            self._converted, self._thumbnail_data,
        )
        worker.finished.connect(self._on_upload_done)
        worker.error.connect(self._on_upload_error)
        worker.start()

    def _on_upload_done(self) -> None:
        self.lbl_status.setText("Uploaded successfully!")
        QtCore.QTimer.singleShot(1500, self.accept)

    def _on_upload_error(self, msg: str) -> None:
        self.lbl_status.setText(f"Upload failed: {msg}")
        self.btn_upload.setEnabled(True)
        LOG.error("photoframe upload failed: %s", msg)

    def keyPressEvent(  # noqa: N802
        self, event: QtGui.QKeyEvent | None,
    ) -> None:
        """Handle Enter to upload, Esc to close."""
        if event is None:
            return
        if (
            event.key() == QtCore.Qt.Key.Key_Return
            and self.btn_upload.isEnabled()
        ):
            self._do_upload()
        elif event.key() == QtCore.Qt.Key.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)


def _pil_to_qimage(img: Image.Image) -> QtGui.QImage:
    """Convert a PIL RGB image to a QImage."""
    data = img.tobytes("raw", "RGB")
    qimg = QtGui.QImage(
        data,
        img.width,
        img.height,
        QtGui.QImage.Format.Format_RGB888,
    )
    return qimg.copy()


class _ConvertWorker(QtCore.QThread):
    """Background thread: fetch device info + convert image."""

    finished = QtCore.pyqtSignal(object, bytes, object)
    error = QtCore.pyqtSignal(str)

    def __init__(self, filepath: str) -> None:
        super().__init__()
        self._filepath = filepath

    def run(self) -> None:
        try:
            info = fetch_device_info()
            image = convert_for_photoframe(
                self._filepath,
                info.width,
                info.height,
                info.palette,
            )
            thumb = make_thumbnail(self._filepath)
            self.finished.emit(image, thumb, info)
        except requests.ConnectionError:
            self.error.emit(f"Cannot reach photoframe at {PHOTOFRAME_HOST}")
        except Exception as e:  # noqa: BLE001
            self.error.emit(str(e))


class _UploadWorker(QtCore.QThread):
    """Background thread: upload image to photo frame."""

    finished = QtCore.pyqtSignal()
    error = QtCore.pyqtSignal(str)

    def __init__(
        self,
        image: Image.Image,
        thumbnail: bytes,
    ) -> None:
        super().__init__()
        self._image = image
        self._thumbnail = thumbnail

    def run(self) -> None:
        try:
            buf = io.BytesIO()
            self._image.save(buf, format="PNG")
            upload_to_photoframe(buf.getvalue(), self._thumbnail)
            self.finished.emit()
        except requests.ConnectionError:
            self.error.emit(f"Cannot reach photoframe at {PHOTOFRAME_HOST}")
        except Exception as e:  # noqa: BLE001
            self.error.emit(str(e))

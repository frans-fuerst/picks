#!/usr/bin/env python3
# Copyright (c) 2017-2026 Frans Fürst
"""Core filename composition, tag handling and EXIF helpers for picks."""

import datetime
import logging
import sys
import types
from pathlib import Path

import exifread

LOG = logging.getLogger("viewer_core")
IMAGE_PATTERN = ("*.jpg", "*.jpeg", "*.png", "*.bmp")
DATE_FORMAT = "%Y%m%d.%H%M%S"
ALLOWED_TAG_CHARACTERS = "abcdefghijklmnopqrstuvwxyz_"
MIN_TAG_LENGTH = 3


class CompFilename(types.SimpleNamespace):
    """A composite filename: date, tag list, base and extension."""

    def __init__(
        self,
        date: object,
        tags: list[str],
        base: str,
        ext: str,
    ) -> None:
        """Store the decomposed filename components."""
        super().__init__()
        self.date = date
        self.tags = tags
        self.base = base
        self.ext = ext

    def __hash__(self) -> int:
        """Hash the filename components."""
        return hash((str(self.date), tuple(self.tags), self.base, self.ext))

    def __eq__(self, other: object) -> bool:
        """Compare two composite filenames for equality."""
        return (
            isinstance(other, self.__class__)
            and self._date == other._date
            and tuple(self.tags) == tuple(other.tags)
            and self.base == other.base
            and self.ext == other.ext
        )

    @staticmethod
    def from_str(composite: str) -> "CompFilename":
        """Split a composite filename into date, base and tag list."""
        date = None
        tags: list[str] = []
        new_base: list[str] = []
        p = Path(composite)
        base, ext = str(p.with_suffix("")), p.suffix
        for c in base.split("-"):
            if not date:
                try:
                    date = datetime.datetime.strptime(c, DATE_FORMAT)  # noqa: DTZ007
                    continue
                except ValueError:
                    pass
            try:
                tags += to_tags(c)
                continue
            except ValueError:
                pass
            new_base.append(c)
        return CompFilename(date, tags, ".".join(new_base), ext)

    @property
    def date(self) -> datetime.datetime | None:
        """Return the parsed date component."""
        return self._date

    @date.setter
    def date(self, value: object) -> None:
        """Set the date, parsing a DATE_FORMAT string if needed."""
        if value is not None and not isinstance(value, datetime.datetime):
            value = datetime.datetime.strptime(str(value), DATE_FORMAT)  # noqa: DTZ007
        self._date = value

    def add_tag(self, tag: str) -> "CompFilename":
        """Append a tag if not already present; return self."""
        if tag not in self.tags:
            self.tags.append(tag)
        return self

    def __repr__(self) -> str:
        """Return the SimpleNamespace repr."""
        return super().__repr__()

    def __str__(self) -> str:
        """Synthesize the composite filename string."""
        return (
            "-".join(
                x
                for x in (
                    self._date.strftime(DATE_FORMAT) if self._date else None,
                    self.base,
                    ".".join(self.tags),
                )
                if x
            )
            + self.ext
        )


def list_pics() -> list[str]:
    """Return sorted image filenames in the current directory."""

    def insensitive_glob(pattern: str) -> list[str]:
        def either(c: str) -> str:
            return f"[{c.lower()}{c.upper()}]" if c.isalpha() else c

        return [str(p) for p in Path().glob("".join(map(either, pattern)))]

    result: list[str] = []
    for p in IMAGE_PATTERN:
        result += insensitive_glob(p)
    return sorted(result)


def get_all_tags(filenames: list[str]) -> list[str]:
    """Collect the unique tags present across the given filenames."""
    result: list[str] = []
    for f in filenames:
        for t in CompFilename.from_str(f).tags:
            if t not in result:
                result.append(t)
    return result


def add_tag_to_file(filename: str, tag: str) -> str:
    """Rename a file to include the given tag; return the new name."""
    new_filename = str(CompFilename.from_str(filename).add_tag(tag))
    Path(filename).rename(new_filename)
    return new_filename


def is_valid_tag(name: str) -> bool:
    """Return True if the name is a valid tag (length and characters)."""
    return len(name) >= MIN_TAG_LENGTH and all(
        c in ALLOWED_TAG_CHARACTERS for c in name
    )


def get_date(tags: dict[str, object]) -> datetime.datetime | None:
    """Return the EXIF DateTimeOriginal, or None if absent."""
    try:
        date_tag = tags["EXIF DateTimeOriginal"]
    except KeyError:
        return None
    assert hasattr(date_tag, "values"), "unexpected tag type"  # noqa: S101
    return datetime.datetime.strptime(  # noqa: DTZ007
        str(date_tag.values),
        "%Y:%m:%d %H:%M:%S",
    )


def get_orientation(tags: dict[str, object]) -> int:
    """Return the rotation in degrees implied by the EXIF orientation tag."""
    try:
        orientation_tag = tags["Image Orientation"]
    except KeyError:
        LOG.warning('orientation: cannot find "Image Orientation" tag')
        return 0

    assert hasattr(orientation_tag, "values"), "unexpected tag type"  # noqa: S101
    # http://jpegclub.org/exif_orientation.html
    value = orientation_tag.values[0]  # type: ignore[index]
    try:
        return {
            1: 0,
            2: 0,  # should be flipped
            3: 180,
            4: 180,  # should be flipped
            5: 90,  # should be flipped
            6: 90,
            7: 270,  # should be flipped
            8: 270,
        }[value]
    except KeyError as e:
        LOG.exception("orientation: cannot handle value %d", value)
        raise TypeError from e


def get_tags(filename: str) -> dict[str, object]:
    """Return the EXIF tags of an image file."""
    # for PNG
    #  https://blender.stackexchange.com/questions/35504/read-image-metadata-from-python

    with Path(filename).open("rb") as f:
        return exifread.process_file(f)  # type: ignore[return-value]


def to_tags(tags: str) -> tuple[str, ...]:
    """Split a dotted tag string into a tuple of valid tags."""
    for c in tags.lower().replace(".", ""):
        if c not in ALLOWED_TAG_CHARACTERS:
            msg = f"character not allowed: {c}"
            raise ValueError(msg)
    return tuple(tags.split("."))


def test_filename_decomposer() -> None:
    """Exercise CompFilename.from_str on a few sample names."""
    assert CompFilename(  # noqa: S101
        date="20170330.172531",
        tags=[],
        base="img_123",
        ext=".jpg",
    ) == CompFilename(
        date="20170330.172531",
        tags=(),
        base="img_123",
        ext=".jpg",
    )
    LOG.info("%s", CompFilename.from_str("img_1234.jpg"))

    LOG.info("%s", CompFilename.from_str("img_1234"))
    LOG.info("%s", CompFilename.from_str("20170330.172531-img_1234.png"))
    LOG.info(
        "%s",
        CompFilename.from_str("20170330.172531-img_1234-tagA.tagB.png"),
    )


def test_filename_synthesizer() -> None:
    """Exercise CompFilename string synthesis."""
    LOG.info(
        "%s",
        str(
            CompFilename(
                "20171116.213412",
                ("tagA", "tagB"),
                "img_1234",
                ".jpg",
            ),
        ),
    )


def main() -> None:
    """Run the filename decomposer/synthesizer self-tests."""
    logging.basicConfig(level=logging.INFO)

    LOG.info(sys.executable)
    LOG.info(".".join(str(e) for e in sys.version_info))

    test_filename_decomposer()
    test_filename_synthesizer()


if __name__ == "__main__":
    main()

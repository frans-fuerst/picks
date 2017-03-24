#!/usr/bin/env python3

import sys
import os
import signal
import glob
import logging
import exifread
from abc import ABCMeta, abstractmethod
from PyQt5 import QtWidgets, QtGui, QtCore, uic

LOG = logging.getLogger('viewer_core')
IMAGE_PATTERN = ('*.jpg', '*.jpeg', '*.png', '*.bmp')


def list_pics() -> list:
    def insensitive_glob(pattern):
        def either(c):
            return '[%s%s]'%(c.lower(),c.upper()) if c.isalpha() else c
        return glob.glob(''.join(map(either, pattern)))
    return sorted(sum([insensitive_glob(p) for p in IMAGE_PATTERN], []))


def get_orientation(tags: dict) -> int:
    try:
        orientation_tag = tags['Image Orientation']
    except KeyError:
        print('orientation: cannot find "Image Orientation" tag')
        return 0

    try:
        return {1: 0,
                6: 90,
                8: 270,
                }[orientation_tag.values[0]]
    except KeyError:
        print('orientation: cannot handle value %d' %
              orientation_tag.values[0])
        raise


def get_tags(filename: str) -> dict:
    with open(filename, 'rb') as f:
        return exifread.process_file(f)


def main():
    logging.basicConfig(level=logging.INFO)

    LOG.info(sys.executable)
    LOG.info('.'.join((str(e) for e in sys.version_info)))

    if len(sys.argv) > 1:
        os.chdir(sys.argv[1])

    for f in list_pics():
        o = get_orientation(get_tags(f))
        if o not in (270,0):
            print(o, f)


if __name__ == '__main__':
    main()

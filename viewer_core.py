#!/usr/bin/env python3

import sys
import os
import glob
import logging
import exifread
import datetime
from collections import namedtuple

LOG = logging.getLogger('viewer_core')
IMAGE_PATTERN = ('*.jpg', '*.jpeg', '*.png', '*.bmp')
DATE_FORMAT = '%Y%m%d.%H%M%S'
ALLOWED_TAG_CHARACTERS = 'abcdefghijklmnopqrstuvwxyz_'

class CompFilename(namedtuple(
    'CompFilename', ['date', 'tags', 'base', 'ext'])):
    def __eq__(self, other):
        return (isinstance(other, self.__class__) and
                self.date == other.date and
                tuple(self.tags) == tuple(other.tags) and
                self.base == other.base and
                self.ext == other.ext)

    @staticmethod
    def from_str(composite: str):
        ''' turns a filename into a tuple containing
            a date, an origninal file basename and a list
            of tags
        '''
        date = None
        tags = []
        new_base = []
        base, ext = os.path.splitext(composite)
        for c in base.split('-'):
            if not date:
                try:
                    date = datetime.datetime.strptime(c, DATE_FORMAT)
                    continue
                except ValueError:
                    pass
            try:
                tags += to_tags(c)
                continue
            except ValueError:
                pass
            new_base.append(c)
        return CompFilename(date, tags, '.'.join(new_base), ext)

    def __repr__(self) -> str:
        return super().__repr__()

    def __str__(self) -> str:
        return '-'.join(x for x in (
            self.date.strftime(DATE_FORMAT) if self.date else None,
            self.base,
            '.'.join(self.tags)) if x) + self.ext

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

def to_tags(tags: str) -> tuple:
    for c in tags.lower().replace('.', ''):
        if c not in ALLOWED_TAG_CHARACTERS:
            raise ValueError('character not allowed: %s' % c)
    return tags.split('.')

def test_filename_decomposer():
    assert(
        CompFilename(date='t', tags=[], base='img_123', ext='.jpg') ==
        CompFilename(date='t', tags=(), base='img_123', ext='.jpg'))
    print(CompFilename.from_str('img_1234.jpg'))

    print(CompFilename.from_str('img_1234'))
    print(CompFilename.from_str('20170330.172531-img_1234.png'))
    print(CompFilename.from_str('20170330.172531-img_1234-tagA.tagB.png'))

def test_filename_synthesizer():
    print(str(CompFilename(
        '20171116.213412',
        ('tagA', 'tagB'),
        'img_1234',
        '.jpg')))

def read_orientation():
    for f in list_pics():
        o = get_orientation(get_tags(f))
        if o not in (270, 0):
            print(o, f)

def main():
    logging.basicConfig(level=logging.INFO)

    LOG.info(sys.executable)
    LOG.info('.'.join((str(e) for e in sys.version_info)))

    if len(sys.argv) > 1:
        os.chdir(sys.argv[1])

    test_filename_decomposer()
    test_filename_synthesizer()

if __name__ == '__main__':
    main()


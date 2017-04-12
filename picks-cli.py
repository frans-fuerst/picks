#!/usr/bin/env python3

import sys
import os
import logging
import argparse

import picks_core

LOG = logging.getLogger('viewer_cli')

def run_viewer(args: dict):
    import picks_viewer
    picks_viewer.main(args)

def read_orientation(args: dict):
    for f in list_pics():
        o = get_orientation(get_tags(f))
        if o not in (270, 0):
            print(o, f)

def setup_filenames(args: dict):
    os.chdir(args.directory)
    for f in picks_core.list_pics():
        comp = picks_core.CompFilename.from_str(f)
        synth = str(comp)
        print('%s %s, %s, %r' % ('! ' if f != synth else '  ', f, synth, comp) )

def main():
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-i", "--initialize", action="store_true")
    parser.add_argument("directory", nargs='?', type=str, default='.')
    args = parser.parse_args()
    print(args)

    LOG.info(sys.executable)
    LOG.info('.'.join((str(e) for e in sys.version_info)))

    if args.initialize:
        setup_filenames(args)
    else:
        run_viewer(args)

if __name__ == '__main__':
    main()


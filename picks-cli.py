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


def print_info(args: dict):
    for f in picks_core.list_pics():
        orientation = picks_core.get_orientation(picks_core.get_tags(f))
        print(orientation, f)


def setup_filenames(args: dict):
    os.chdir(args.directory)
    for f in picks_core.list_pics():
        comp = picks_core.CompFilename.from_str(f)
        if not comp.date:
            comp.date = picks_core.get_date(picks_core.get_tags(f))
        synth = str(comp)
        print('%s %s, %s, %r' % ('! ' if f != synth else '  ', f, synth, comp))
        os.rename(f, synth)


def main():
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-n", "--initialize", action="store_true")
    group.add_argument("-i", "--info", action="store_true")
    parser.add_argument("directory", nargs='?', type=str, default='.')
    args = parser.parse_args()
    print(args)

    LOG.info(sys.executable)
    LOG.info('.'.join((str(e) for e in sys.version_info)))

    if args.initialize:
        setup_filenames(args)
    elif args.info:
        print_info(args)
    else:
        run_viewer(args)


if __name__ == '__main__':
    main()

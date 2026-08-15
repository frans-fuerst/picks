#!/usr/bin/env python3
# Copyright (c) 2017-2026 Frans Fürst
"""Command line entry point for picks."""

import argparse
import logging
import os
import sys
from pathlib import Path

from picks.application import picks_core

LOG = logging.getLogger("viewer_cli")


def run_viewer(args: argparse.Namespace) -> None:
    """Launch the PyQt viewer (imported lazily to avoid a hard dep)."""
    from picks.application import picks_viewer  # noqa: PLC0415

    picks_viewer.main(args)


def print_info(_args: argparse.Namespace) -> None:
    """Print the orientation of every image in the target directory."""
    for f in picks_core.list_pics():
        orientation = picks_core.get_orientation(picks_core.get_tags(f))
        print(orientation, f)


def setup_filenames(args: argparse.Namespace) -> None:
    """Rename images to their synthesized composite filenames."""
    os.chdir(args.directory)
    for f in picks_core.list_pics():
        comp = picks_core.CompFilename.from_str(f)
        if not comp.date:
            comp.date = picks_core.get_date(picks_core.get_tags(f))
        synth = str(comp)
        LOG.info("%s %s, %s, %r", "! " if f != synth else "  ", f, synth, comp)
        Path(f).rename(synth)


def main() -> None:
    """Parse arguments and dispatch to the selected sub-command."""
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-n", "--initialize", action="store_true")
    group.add_argument("-i", "--info", action="store_true")
    parser.add_argument("directory", nargs="?", type=str, default=".")
    args = parser.parse_args()
    LOG.info("%s", args)

    LOG.info(sys.executable)
    LOG.info(".".join(str(e) for e in sys.version_info))

    if args.initialize:
        setup_filenames(args)
    elif args.info:
        print_info(args)
    else:
        run_viewer(args)


if __name__ == "__main__":
    main()

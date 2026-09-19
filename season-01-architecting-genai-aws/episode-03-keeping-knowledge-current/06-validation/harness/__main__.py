"""Learner lab entry point: python3 -m harness lab-<verb> (run from 06-validation/)."""
import argparse
import sys

from harness import lab


def main():
    parser = argparse.ArgumentParser(prog="python3 -m harness",
                                     description="Episode 03 learner lab. Start a part first with "
                                                 "python3 scripts/tla_ops.py lab-up <part> from 05-implementation/.")
    sub = parser.add_subparsers(dest="command", required=True)
    lab.add_cli(sub)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

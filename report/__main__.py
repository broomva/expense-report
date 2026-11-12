"""python3 -m report <file.csv> [--currency CODE]"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from report.expenses import ReportError, filter_currency, read_expenses, summary


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python3 -m report")
    parser.add_argument("file", type=Path, metavar="file.csv")
    parser.add_argument("--currency", metavar="CODE", help="count only expenses in this currency")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        expenses = read_expenses(args.file)
    except (OSError, ReportError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if args.currency is not None:
        expenses = filter_currency(expenses, args.currency)
    print(summary(expenses))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

"""python3 -m report [--by-month] <file.csv>"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

from report.expenses import ReportError, read_expenses, summary, totals_by_month

MONTH_FLAG = "--by-month"


def by_month_text(totals: dict[str, dict[str, Decimal]]) -> str:
    if not totals:
        return "No expenses."
    lines: list[str] = []
    for month, by_currency in totals.items():
        lines.append(month)
        lines.extend(f"  {code} {amount}" for code, amount in sorted(by_currency.items()))
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    by_month = MONTH_FLAG in argv
    files = [arg for arg in argv if arg != MONTH_FLAG]
    if len(files) != 1:
        print("usage: python3 -m report [--by-month] <file.csv>", file=sys.stderr)
        return 2
    try:
        expenses = read_expenses(Path(files[0]))
    except (OSError, ReportError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(by_month_text(totals_by_month(expenses)) if by_month else summary(expenses))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

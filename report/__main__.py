"""python3 -m report <file.csv>"""

from __future__ import annotations

import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from report.expenses import Expense, ReportError, read_expenses, summary, totals_by_currency

CENT = Decimal("0.01")


def currency_lines(expenses: list[Expense]) -> list[str]:
    totals = totals_by_currency(expenses)
    return [f"{code} {totals[code].quantize(CENT, ROUND_HALF_UP)}" for code in sorted(totals)]


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: python3 -m report <file.csv>", file=sys.stderr)
        return 2
    try:
        expenses = read_expenses(Path(argv[0]))
    except (OSError, ReportError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(summary(expenses))
    for line in currency_lines(expenses):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

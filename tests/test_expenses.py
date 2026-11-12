import subprocess
import sys
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from report.__main__ import currency_lines
from report.expenses import Expense, ReportError, parse_row, read_expenses, summary, totals_by_currency

ROW = {"date": "2026-10-03", "description": "Taxi", "amount": "12.50", "currency": "usd"}


def write_csv(text: str) -> Path:
    f = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8")
    f.write(text)
    f.close()
    return Path(f.name)


class ParseRow(unittest.TestCase):
    def test_reads_a_row(self) -> None:
        self.assertEqual(parse_row(ROW, 2), Expense(date(2026, 10, 3), "Taxi", Decimal("12.50"), "USD"))

    def test_bad_date_names_the_line(self) -> None:
        with self.assertRaisesRegex(ReportError, "line 7"):
            parse_row({**ROW, "date": "03/10/2026"}, 7)

    def test_bad_amount(self) -> None:
        with self.assertRaises(ReportError):
            parse_row({**ROW, "amount": "twelve"}, 2)

    def test_bad_currency(self) -> None:
        with self.assertRaisesRegex(ReportError, "3-letter"):
            parse_row({**ROW, "currency": "dollars"}, 2)

    def test_rejects_non_finite_amounts_and_names_the_line(self) -> None:
        for value in ["NaN", "sNaN", "Infinity", "-Infinity"]:
            with self.subTest(value=value), self.assertRaisesRegex(ReportError, "line 4"):
                parse_row({**ROW, "amount": value}, 4)


class ReadAndSummarise(unittest.TestCase):
    def test_reads_a_file(self) -> None:
        path = write_csv("date,description,amount,currency\n2026-10-03,Taxi,12.50,USD\n2026-10-05,Lunch,9,EUR\n")
        self.assertEqual([e.currency for e in read_expenses(path)], ["USD", "EUR"])

    def test_error_line_counts_the_header(self) -> None:
        path = write_csv("date,description,amount,currency\n2026-10-03,Taxi,x,USD\n")
        with self.assertRaisesRegex(ReportError, "line 2"):
            read_expenses(path)

    def test_summary(self) -> None:
        expenses = [parse_row(ROW, 2), parse_row({**ROW, "date": "2026-09-30"}, 3)]
        self.assertEqual(summary(expenses), "2 expenses from 2026-09-30 to 2026-10-03")

    def test_summary_of_nothing(self) -> None:
        self.assertEqual(summary([]), "No expenses.")

    def test_totals_by_currency_sums_per_currency(self) -> None:
        expenses = [
            parse_row({**ROW, "amount": "10.50", "currency": "EUR"}, 2),
            parse_row({**ROW, "amount": "2.25", "currency": "EUR"}, 3),
            parse_row({**ROW, "amount": "3", "currency": "USD"}, 4),
        ]
        self.assertEqual(totals_by_currency(expenses), {"EUR": Decimal("12.75"), "USD": Decimal("3")})

    def test_currency_lines_sort_by_code_and_use_two_decimals(self) -> None:
        expenses = read_expenses(Path("data/sample.csv"))
        self.assertEqual(currency_lines(expenses), ["EUR 141.90", "GBP 210.00", "USD 485.00"])

    def test_currency_lines_round_half_up_to_the_cent(self) -> None:
        expenses = [parse_row({**ROW, "amount": "1.005", "currency": "EUR"}, 2)]
        self.assertEqual(currency_lines(expenses), ["EUR 1.01"])

    def test_currency_lines_of_nothing_is_empty(self) -> None:
        self.assertEqual(currency_lines([]), [])


class Cli(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, "-m", "report", *args], capture_output=True, text=True)

    def test_prints_the_summary(self) -> None:
        out = self.run_cli("data/sample.csv")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("expenses from", out.stdout)

    def test_prints_the_currency_lines_after_the_summary(self) -> None:
        out = self.run_cli("data/sample.csv")
        self.assertEqual(out.returncode, 0, out.stderr)
        lines = out.stdout.splitlines()
        self.assertEqual(lines[1:], ["EUR 141.90", "GBP 210.00", "USD 485.00"])
        self.assertIn("expenses from", lines[0])

    def test_bad_file_exits_1(self) -> None:
        self.assertEqual(self.run_cli("missing.csv").returncode, 1)


if __name__ == "__main__":
    unittest.main()

import subprocess
import sys
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from report.expenses import Expense, ReportError, filter_currency, parse_row, read_expenses, summary

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


class FilterCurrency(unittest.TestCase):
    def setUp(self) -> None:
        self.expenses = [
            parse_row({**ROW, "currency": "USD"}, 2),
            parse_row({**ROW, "currency": "EUR", "date": "2026-09-30"}, 3),
            parse_row({**ROW, "currency": "USD", "date": "2026-10-01"}, 4),
            parse_row({**ROW, "currency": "EUR", "date": "2026-10-02"}, 5),
        ]

    def test_keeps_only_matching_expenses_in_order(self) -> None:
        self.assertEqual(filter_currency(self.expenses, "EUR"), [self.expenses[1], self.expenses[3]])

    def test_is_case_insensitive_and_ignores_spaces(self) -> None:
        expected = filter_currency(self.expenses, "EUR")
        self.assertEqual(filter_currency(self.expenses, "eur"), expected)
        self.assertEqual(filter_currency(self.expenses, " eur "), expected)

    def test_unknown_code_matches_nothing(self) -> None:
        self.assertEqual(filter_currency(self.expenses, "XYZ"), [])
        self.assertEqual(summary(filter_currency(self.expenses, "XYZ")), "No expenses.")


class Cli(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, "-m", "report", *args], capture_output=True, text=True)

    def test_prints_the_summary(self) -> None:
        out = self.run_cli("data/sample.csv")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("expenses from", out.stdout)

    def test_without_flag_output_is_unchanged(self) -> None:
        out = self.run_cli("data/sample.csv")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(out.stdout.strip(), "8 expenses from 2026-09-02 to 2026-10-19")

    def test_currency_flag_before_path(self) -> None:
        out = self.run_cli("--currency", "EUR", "data/sample.csv")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(out.stdout.strip(), "4 expenses from 2026-09-02 to 2026-10-03")

    def test_currency_lower_case_matches(self) -> None:
        out = self.run_cli("--currency", "usd", "data/sample.csv")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(out.stdout.strip(), "3 expenses from 2026-09-15 to 2026-10-07")

    def test_currency_equals_form_after_path(self) -> None:
        out = self.run_cli("data/sample.csv", "--currency=usd")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(out.stdout.strip(), "3 expenses from 2026-09-15 to 2026-10-07")

    def test_unknown_currency_prints_no_expenses(self) -> None:
        out = self.run_cli("--currency", "XYZ", "data/sample.csv")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(out.stdout.strip(), "No expenses.")

    def test_bad_row_still_fails_under_a_filter(self) -> None:
        path = write_csv("date,description,amount,currency\n2026-10-03,Taxi,x,USD\n2026-09-02,Train,4.20,EUR\n")
        out = self.run_cli("--currency", "EUR", str(path))
        self.assertEqual(out.returncode, 1)
        self.assertIn("line 2", out.stderr)

    def test_bad_file_exits_1(self) -> None:
        self.assertEqual(self.run_cli("missing.csv").returncode, 1)


if __name__ == "__main__":
    unittest.main()

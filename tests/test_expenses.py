import subprocess
import sys
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from report.__main__ import by_month_text
from report.expenses import Expense, ReportError, parse_row, read_expenses, summary, totals_by_month

ROW ={"date": "2026-10-03", "description": "Taxi", "amount": "12.50", "currency": "usd"}


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


def exp(day: str, amount: str, currency: str) -> Expense:
    return Expense(date.fromisoformat(day), "x", Decimal(amount), currency)


class TotalsByMonth(unittest.TestCase):
    def test_groups_by_month_in_ascending_order(self) -> None:
        expenses = [exp("2026-10-03", "1", "USD"), exp("2026-09-15", "1", "USD"), exp("2026-09-02", "1", "USD")]
        self.assertEqual(list(totals_by_month(expenses)), ["2026-09", "2026-10"])

    def test_sums_per_currency_inside_a_month(self) -> None:
        expenses = [exp("2026-09-02", "4.20", "EUR"), exp("2026-09-02", "6.80", "EUR"), exp("2026-09-15", "120.00", "USD")]
        self.assertEqual(
            totals_by_month(expenses)["2026-09"], {"EUR": Decimal("11.00"), "USD": Decimal("120.00")}
        )

    def test_keeps_months_separate(self) -> None:
        expenses = [exp("2026-09-02", "5", "EUR"), exp("2026-10-01", "7", "EUR")]
        totals = totals_by_month(expenses)
        self.assertEqual(totals["2026-09"], {"EUR": Decimal("5")})
        self.assertEqual(totals["2026-10"], {"EUR": Decimal("7")})

    def test_empty_input(self) -> None:
        self.assertEqual(totals_by_month([]), {})


class ByMonthText(unittest.TestCase):
    def test_block_output_in_month_order_with_sorted_currencies(self) -> None:
        totals = {
            "2026-09": {"USD": Decimal("120.00"), "EUR": Decimal("11.00")},
            "2026-10": {"EUR": Decimal("130.90")},
        }
        self.assertEqual(
            by_month_text(totals),
            "2026-09\n  EUR 11.00\n  USD 120.00\n2026-10\n  EUR 130.90",
        )

    def test_empty_totals_print_no_expenses(self) -> None:
        self.assertEqual(by_month_text({}), "No expenses.")


class Cli(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, "-m", "report", *args], capture_output=True, text=True)

    def test_prints_the_summary(self) -> None:
        out = self.run_cli("data/sample.csv")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("expenses from", out.stdout)

    def test_bad_file_exits_1(self) -> None:
        self.assertEqual(self.run_cli("missing.csv").returncode, 1)

    def test_by_month_flag_before_the_path(self) -> None:
        out = self.run_cli("--by-month", "data/sample.csv")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertLess(out.stdout.index("2026-09"), out.stdout.index("2026-10"))
        self.assertIn("EUR 11.00", out.stdout)

    def test_by_month_flag_after_the_path(self) -> None:
        after = self.run_cli("data/sample.csv", "--by-month")
        before = self.run_cli("--by-month", "data/sample.csv")
        self.assertEqual(after.returncode, 0, after.stderr)
        self.assertEqual(after.stdout, before.stdout)

    def test_by_month_flag_without_a_file_is_usage_error(self) -> None:
        self.assertEqual(self.run_cli("--by-month").returncode, 2)

    def test_by_month_empty_file_prints_no_expenses(self) -> None:
        path = write_csv("date,description,amount,currency\n")
        out = self.run_cli("--by-month", str(path))
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(out.stdout, "No expenses.\n")

    def test_by_month_bad_row_exits_1_and_names_the_line(self) -> None:
        path = write_csv("date,description,amount,currency\n2026-10-03,Taxi,x,USD\n")
        out = self.run_cli("--by-month", str(path))
        self.assertEqual(out.returncode, 1)
        self.assertIn("line 2", out.stderr)


if __name__ == "__main__":
    unittest.main()

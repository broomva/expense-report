import subprocess
import sys
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from report.expenses import Expense, ReportError, parse_row, read_expenses, summary

ROW = {"date": "2026-10-03", "description": "Taxi", "amount": "12.50", "currency": "usd"}


def write_file(text: str, suffix: str) -> Path:
    f = tempfile.NamedTemporaryFile("w", suffix=suffix, delete=False, encoding="utf-8")
    f.write(text)
    f.close()
    return Path(f.name)


def write_csv(text: str) -> Path:
    return write_file(text, ".csv")


CSV_TEXT = "date,description,amount,currency\n2026-10-03,Taxi,12.50,usd\n2026-10-05,Lunch,9,EUR\n"
JSON_TEXT = (
    '[{"date": "2026-10-03", "description": "Taxi", "amount": "12.50", "currency": "usd"},'
    ' {"date": "2026-10-05", "description": "Lunch", "amount": 9, "currency": "EUR"}]'
)
XML_OK = (
    "<expense><date>2026-10-03</date><description>Taxi</description>"
    "<amount>12.50</amount><currency>usd</currency></expense>"
)
XML_LUNCH = (
    "<expense><date>2026-10-05</date><description>Lunch</description>"
    "<amount>9</amount><currency>EUR</currency></expense>"
)
XML_NO_AMOUNT = "<expense><date>2026-10-05</date><description>Lunch</description><currency>EUR</currency></expense>"


def run_report(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-m", "report", *args], capture_output=True, text=True)


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


class Cli(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, "-m", "report", *args], capture_output=True, text=True)

    def test_prints_the_summary(self) -> None:
        out = self.run_cli("data/sample.csv")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("expenses from", out.stdout)

    def test_bad_file_exits_1(self) -> None:
        self.assertEqual(self.run_cli("missing.csv").returncode, 1)


class FiniteAmounts(unittest.TestCase):
    def test_non_finite_amounts_name_the_line(self) -> None:
        for amount in ["NaN", "sNaN", "Infinity", "-Infinity"]:
            with self.subTest(amount=amount), self.assertRaisesRegex(ReportError, "line 4"):
                parse_row({**ROW, "amount": amount}, 4)


class Formats(unittest.TestCase):
    def test_json_matches_csv(self) -> None:
        self.assertEqual(read_expenses(write_file(JSON_TEXT, ".json")), read_expenses(write_csv(CSV_TEXT)))

    def test_upper_case_extension_is_json(self) -> None:
        self.assertEqual(len(read_expenses(write_file(JSON_TEXT, ".JSON"))), 2)

    def test_json_null_description_is_empty(self) -> None:
        text = '[{"date": "2026-10-03", "description": null, "amount": "1", "currency": "USD"}]'
        self.assertEqual(read_expenses(write_file(text, ".json"))[0].description, "")

    def test_json_top_level_object_is_refused(self) -> None:
        with self.assertRaises(ReportError):
            read_expenses(write_file('{"date": "2026-10-03"}', ".json"))

    def test_invalid_json_names_the_line(self) -> None:
        with self.assertRaisesRegex(ReportError, "line 2: not valid JSON"):
            read_expenses(write_file('[\n  {"date": x}\n]', ".json"))

    def test_xml_matches_csv(self) -> None:
        xml = write_file(f"<expenses>{XML_OK}{XML_LUNCH}</expenses>", ".xml")
        self.assertEqual(read_expenses(xml), read_expenses(write_csv(CSV_TEXT)))

    def test_malformed_xml_names_a_line(self) -> None:
        with self.assertRaisesRegex(ReportError, r"line 3: not valid XML"):
            read_expenses(write_file("<expenses>\n<expense>\n</expenses>", ".xml"))

    def test_xml_with_doctype_is_refused(self) -> None:
        text = f'<!DOCTYPE expenses [<!ENTITY e "x">]><expenses>{XML_OK}</expenses>'
        with self.assertRaisesRegex(ReportError, "DOCTYPE"):
            read_expenses(write_file(text, ".xml"))

    def test_xml_missing_column_names_the_entry(self) -> None:
        with self.assertRaisesRegex(ReportError, "line 2"):
            read_expenses(write_file(f"<expenses>{XML_OK}{XML_NO_AMOUNT}</expenses>", ".xml"))

    def test_excel_is_refused(self) -> None:
        for suffix in (".xlsx", ".xls"):
            with self.subTest(suffix=suffix), self.assertRaises(ReportError) as ctx:
                read_expenses(Path(f"x{suffix}"))
            self.assertIn(suffix, str(ctx.exception))
            self.assertIn("export to CSV", str(ctx.exception))

    def test_unknown_extension_is_read_as_csv(self) -> None:
        self.assertEqual(len(read_expenses(write_file(CSV_TEXT, ".txt"))), 2)


class CliFormats(unittest.TestCase):
    def test_json_file_prints_the_summary(self) -> None:
        out = run_report(str(write_file(JSON_TEXT, ".json")))
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("expenses from", out.stdout)

    def test_excel_file_exits_1_with_the_message(self) -> None:
        out = run_report(str(write_file("", ".xlsx")))
        self.assertEqual(out.returncode, 1)
        self.assertIn("export to CSV", out.stderr)


if __name__ == "__main__":
    unittest.main()

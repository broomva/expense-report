"""Read expenses from CSV, JSON or XML files (date,description,amount,currency) and summarise them."""

from __future__ import annotations

import csv
import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path


@dataclass(frozen=True)
class Expense:
    day: date
    description: str
    amount: Decimal
    currency: str


class ReportError(ValueError):
    """A row the report cannot use; the message names its line in the file."""


def parse_row(row: dict[str, str], line: int) -> Expense:
    try:
        day = date.fromisoformat(row["date"].strip())
        amount = Decimal(row["amount"].strip())
    except (KeyError, AttributeError, ValueError, InvalidOperation) as exc:
        raise ReportError(f"line {line}: cannot read date or amount ({exc})") from exc
    if not amount.is_finite():
        raise ReportError(f"line {line}: amount must be a finite number, got {amount}")
    currency = (row.get("currency") or "").strip().upper()
    if len(currency) != 3 or not currency.isalpha():
        raise ReportError(f"line {line}: currency must be a 3-letter code, got {currency!r}")
    return Expense(day, (row.get("description") or "").strip(), amount, currency)


EXCEL_SUFFIXES = (".xlsx", ".xls")


def read_expenses(path: Path) -> list[Expense]:
    suffix = path.suffix.lower()
    if suffix in EXCEL_SUFFIXES:
        raise ReportError(f"{suffix} files are not supported; export to CSV and run the report again")
    if suffix == ".json":
        return read_json(path)
    if suffix == ".xml":
        return read_xml(path)
    return read_csv(path)


def read_csv(path: Path) -> list[Expense]:
    with path.open(newline="", encoding="utf-8") as f:
        return [parse_row(row, n) for n, row in enumerate(csv.DictReader(f), start=2)]


def _json_row(entry: object, line: int) -> dict[str, str]:
    if not isinstance(entry, dict):
        raise ReportError(f"line {line}: expected an object with date, description, amount and currency")
    return {key: "" if value is None else str(value) for key, value in entry.items()}


def read_json(path: Path) -> list[Expense]:
    with path.open(encoding="utf-8") as f:
        try:
            entries = json.load(f)
        except json.JSONDecodeError as exc:
            raise ReportError(f"line {exc.lineno}: not valid JSON ({exc.msg})") from exc
    if not isinstance(entries, list):
        raise ReportError("JSON expense file must hold a list of expense objects")
    return [parse_row(_json_row(entry, n), n) for n, entry in enumerate(entries, start=1)]


def read_xml(path: Path) -> list[Expense]:
    text = path.read_text(encoding="utf-8")
    if "<!DOCTYPE" in text:
        raise ReportError("XML files with a DOCTYPE are refused; remove it and run the report again")
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise ReportError(f"line {exc.position[0]}: not valid XML ({exc.code})") from exc
    entries = root.findall("expense")
    return [parse_row({child.tag: child.text or "" for child in e}, n) for n, e in enumerate(entries, start=1)]


def summary(expenses: list[Expense]) -> str:
    if not expenses:
        return "No expenses."
    days = sorted(e.day for e in expenses)
    return f"{len(expenses)} expenses from {days[0].isoformat()} to {days[-1].isoformat()}"

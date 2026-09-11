import csv
from collections import defaultdict
from pathlib import Path

from .models import Expense


def top_categories(expenses: list[Expense], limit: int = 3) -> list[tuple[str, int]]:
    totals: dict[str, int] = defaultdict(int)
    for expense in expenses:
        totals[expense.category] += expense.amount
    return sorted(totals.items(), key=lambda item: (-item[1], item[0]))[:limit]


def export_csv(expenses: list[Expense], output: Path, month: str | None = None) -> int:
    selected = [e for e in expenses if month is None or e.date.startswith(month)]
    with output.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=["date", "category", "amount", "memo"])
        writer.writeheader()
        writer.writerows(e.to_dict() for e in selected)
    return len(selected)


def import_csv(expenses: list[Expense], source: Path) -> tuple[list[Expense], int, int]:
    imported: list[Expense] = []
    skipped = 0
    with source.open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        required = {"date", "category", "amount"}
        if not required.issubset(reader.fieldnames or set()):
            raise ValueError("CSV 헤더에는 date, category, amount가 필요합니다.")
        for row in reader:
            try:
                imported.append(Expense(row["date"].strip(), row["category"].strip(), int(row["amount"]), (row.get("memo") or "").strip()))
            except (ValueError, TypeError, KeyError):
                skipped += 1
    return expenses + imported, len(imported), skipped

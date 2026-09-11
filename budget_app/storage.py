import json
from pathlib import Path

from .models import Expense


DEFAULT_DB = Path(".budget_data.json")


def load(path: Path = DEFAULT_DB) -> list[Expense]:
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return [Expense(str(item["date"]), str(item["category"]), int(item["amount"]), str(item.get("memo", ""))) for item in raw]
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"저장 파일을 읽을 수 없습니다: {path}") from exc


def save(expenses: list[Expense], path: Path = DEFAULT_DB) -> None:
    try:
        path.write_text(json.dumps([expense.to_dict() for expense in expenses], ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"저장 파일을 쓸 수 없습니다: {path}") from exc

import json
import os
import tempfile
from collections.abc import Callable, Iterator
from pathlib import Path

from .models import Transaction

DEFAULT_DATA_DIR = Path("data")
DEFAULT_CATEGORIES = ("food", "transport", "rent", "salary")


def _read_jsonl(path: Path) -> Iterator[dict[str, object]]:
    if not path.exists():
        return
    try:
        with path.open(encoding="utf-8") as file:
            for line in file:
                if line.strip():
                    yield json.loads(line)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"저장 파일을 읽을 수 없습니다: {path}") from exc


def _atomic_write(path: Path, rows: Iterator[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = -1
    temp_name = ""
    try:
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent, text=True)
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            fd = -1
            for row in rows:
                file.write(json.dumps(row, ensure_ascii=False) + "\n")
        os.replace(temp_name, path)
    except OSError as exc:
        if fd >= 0:
            os.close(fd)
        if temp_name:
            Path(temp_name).unlink(missing_ok=True)
        raise RuntimeError(f"저장 파일을 쓸 수 없습니다: {path}") from exc
    except BaseException:
        if fd >= 0:
            os.close(fd)
        if temp_name:
            Path(temp_name).unlink(missing_ok=True)
        raise


class TransactionRepository:
    def __init__(self, data_dir: Path) -> None:
        self.path = data_dir / "transactions.jsonl"

    def stream(self) -> Iterator[Transaction]:
        for row in _read_jsonl(self.path):
            yield Transaction.from_dict(row)

    def replace(self, transactions: Iterator[Transaction]) -> None:
        _atomic_write(self.path, (transaction.to_dict() for transaction in transactions))

    def rewrite(self, transform: Callable[[Transaction], Transaction | None]) -> bool:
        """모든 행을 스트리밍으로 임시 파일에 옮기며 transform을 적용한다."""
        found = False

        def rows() -> Iterator[Transaction]:
            nonlocal found
            for transaction in self.stream():
                transformed = transform(transaction)
                if transformed is None:
                    found = True
                else:
                    if transformed is not transaction:
                        found = True
                    yield transformed

        _atomic_write(self.path, (transaction.to_dict() for transaction in rows()))
        return found

    def append(self, transaction: Transaction) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(transaction.to_dict(), ensure_ascii=False) + "\n")


class CategoryRepository:
    def __init__(self, data_dir: Path) -> None:
        self.path = data_dir / "categories.jsonl"
        if not self.path.exists():
            self.replace(DEFAULT_CATEGORIES)

    def list(self) -> list[str]:
        return [str(row["name"]) for row in _read_jsonl(self.path)]

    def replace(self, categories: Iterator[str] | tuple[str, ...] | list[str]) -> None:
        _atomic_write(self.path, ({"name": name} for name in categories))


class BudgetRepository:
    def __init__(self, data_dir: Path) -> None:
        self.path = data_dir / "budgets.jsonl"

    def get(self, month: str) -> int | None:
        return next((int(row["amount"]) for row in _read_jsonl(self.path) if row.get("month") == month), None)

    def set(self, month: str, amount: int) -> None:
        budgets = {str(row["month"]): int(row["amount"]) for row in _read_jsonl(self.path)}
        budgets[month] = amount
        _atomic_write(self.path, ({"month": key, "amount": value} for key, value in sorted(budgets.items())))

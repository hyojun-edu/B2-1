import csv
import heapq
import json
import logging
import os
import shutil
import tempfile
import time
import uuid
from collections import defaultdict
from collections.abc import Callable, Iterator
from functools import wraps
from pathlib import Path
from typing import ParamSpec, TypeVar

from calendar import monthrange
from .models import RecurringTransaction, Transaction
from .repositories import BudgetRepository, CategoryRepository, RecurringRepository, TransactionRepository

P = ParamSpec("P")
R = TypeVar("R")


def logged_timed(func: Callable[P, R]) -> Callable[P, R]:
    """서비스 실행 시간과 예외를 공통으로 기록하는 데코레이터."""
    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        started = time.perf_counter()
        try:
            return func(*args, **kwargs)
        except Exception:
            logging.exception("서비스 오류: %s", func.__name__)
            raise
        finally:
            logging.info("%s 실행 시간: %.3f초", func.__name__, time.perf_counter() - started)
    return wrapper


def validate_month(month: str) -> None:
    if len(month) != 7 or month[4] != "-" or not month[:4].isdigit() or not month[5:].isdigit():
        raise ValueError("월 형식이 올바르지 않습니다 (YYYY-MM).")


def new_id() -> str:
    return f"TX-{uuid.uuid4().hex[:12].upper()}"


class BudgetService:
    def __init__(
        self,
        transaction_repository: TransactionRepository,
        category_repository: CategoryRepository,
        budget_repository: BudgetRepository,
        recurring_repository: RecurringRepository,
    ) -> None:
        self.transaction_repository = transaction_repository
        self.category_repository = category_repository
        self.budget_repository = budget_repository
        self.recurring_repository = recurring_repository

    @logged_timed
    def add(self, transaction: Transaction) -> None:
        if transaction.category not in self.category_repository.list():
            raise ValueError(f"등록되지 않은 카테고리입니다: {transaction.category}")
        if any(row.id == transaction.id for row in self.transaction_repository.stream()):
            raise ValueError("중복된 거래 id입니다.")
        self.transaction_repository.append(transaction)

    def stream(self, **filters: str | None) -> Iterator[Transaction]:
        """조건에 맞는 거래를 최신순으로, 제한된 메모리만 사용해 반환한다."""
        chunk_size = 1024
        with tempfile.TemporaryDirectory(prefix="budget-sort-") as temp_dir:
            chunk_paths: list[Path] = []
            chunk: list[Transaction] = []

            def write_chunk() -> None:
                if not chunk:
                    return
                chunk.sort(key=lambda row: (row.date, row.id), reverse=True)
                path = Path(temp_dir) / f"chunk-{len(chunk_paths)}.jsonl"
                with path.open("w", encoding="utf-8") as file:
                    for row in chunk:
                        file.write(json.dumps(row.to_dict(), ensure_ascii=False) + "\n")
                chunk_paths.append(path)
                chunk.clear()

            for row in self.transaction_repository.stream():
                if self._matches(row, filters):
                    chunk.append(row)
                    if len(chunk) >= chunk_size:
                        write_chunk()
            write_chunk()

            def read_chunk(path: Path) -> Iterator[Transaction]:
                with path.open(encoding="utf-8") as file:
                    for line in file:
                        yield Transaction.from_dict(json.loads(line))

            yield from heapq.merge(
                *(read_chunk(path) for path in chunk_paths),
                key=lambda row: (row.date, row.id),
                reverse=True,
            )

    @staticmethod
    def _matches(row: Transaction, filters: dict[str, str | None]) -> bool:
        return (
            (not filters.get("from") or row.date >= filters["from"])
            and (not filters.get("to") or row.date <= filters["to"])
            and (not filters.get("category") or row.category == filters["category"])
            and (not filters.get("type") or row.type == filters["type"])
            and (not filters.get("q") or filters["q"].lower() in row.memo.lower())
            and (not filters.get("tag") or filters["tag"] in row.tags)
        )

    @logged_timed
    def update(self, transaction_id: str, changes: dict[str, object]) -> bool:
        def transform(row: Transaction) -> Transaction:
            if row.id != transaction_id:
                return row
            data = row.to_dict()
            data.update(changes)
            data["id"] = row.id
            updated = Transaction.from_dict(data)
            if updated.category not in self.category_repository.list():
                raise ValueError(f"등록되지 않은 카테고리입니다: {updated.category}")
            return updated

        return self.transaction_repository.rewrite(transform)

    @logged_timed
    def delete(self, transaction_id: str) -> bool:
        return self.transaction_repository.rewrite(
            lambda row: None if row.id == transaction_id else row
        )

    def summary(self, month: str) -> tuple[int, int, list[tuple[str, int]]]:
        validate_month(month)
        income = expense = 0
        totals: dict[str, int] = defaultdict(int)
        for row in self.transaction_repository.stream():
            if not row.date.startswith(month):
                continue
            if row.type == "income":
                income += row.amount
            else:
                expense += row.amount
                totals[row.category] += row.amount
        ranking = sorted(totals.items(), key=lambda item: (-item[1], item[0]))
        return income, expense, ranking

    def set_budget(self, month: str, amount: int) -> None:
        validate_month(month)
        if amount <= 0:
            raise ValueError("예산은 0보다 커야 합니다.")
        self.budget_repository.set(month, amount)

    def add_category(self, name: str) -> None:
        name = name.strip()
        if not name:
            raise ValueError("카테고리명을 입력해야 합니다.")
        categories = self.category_repository.list()
        if name in categories:
            raise ValueError("이미 존재하는 카테고리입니다.")
        self.category_repository.replace(categories + [name])

    def remove_category(self, name: str) -> None:
        if any(row.category == name for row in self.transaction_repository.stream()):
            raise ValueError("사용 중인 카테고리는 삭제할 수 없습니다.")
        categories = self.category_repository.list()
        if name not in categories:
            raise ValueError("존재하지 않는 카테고리입니다.")
        self.category_repository.replace([category for category in categories if category != name])

    def export_csv(self, output: Path, **filters: str | None) -> int:
        count = 0
        output.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=f".{output.name}.", dir=output.parent, text=True)
        os.close(fd)
        staged = Path(temp_name)
        try:
            with staged.open("w", newline="", encoding="utf-8-sig") as file:
                writer = csv.DictWriter(file, fieldnames=["id", "date", "type", "category", "amount", "memo", "tags"])
                writer.writeheader()
                for row in self.stream(**filters):
                    data = row.to_dict()
                    data["tags"] = ",".join(row.tags)
                    writer.writerow(data)
                    count += 1
            os.replace(staged, output)
            return count
        finally:
            staged.unlink(missing_ok=True)

    def import_csv(self, source: Path) -> tuple[int, int]:
        """CSV 전체를 staging 파일에 반영한 뒤 성공 시에만 원자적으로 교체한다."""
        path = self.transaction_repository.path
        categories = set(self.category_repository.list())
        existing_ids = {row.id for row in self.transaction_repository.stream()}
        imported = 0
        staged_path: Path | None = None

        try:
            fd, temp_name = tempfile.mkstemp(
                prefix=f".{path.name}.import-", dir=path.parent, text=True
            )
            staged_path = Path(temp_name)
            os.close(fd)
            shutil.copy2(path, staged_path)

            with source.open(newline="", encoding="utf-8-sig") as file, staged_path.open(
                "a", encoding="utf-8"
            ) as staged:
                reader = csv.DictReader(file)
                required = {"date", "type", "category", "amount"}
                if not required.issubset(reader.fieldnames or set()):
                    raise ValueError("CSV 헤더에는 date, type, category, amount가 필요합니다.")

                for row_number, row in enumerate(reader, start=2):
                    try:
                        transaction = Transaction(
                            row.get("id") or new_id(), row["type"].strip(), row["date"].strip(),
                            int(row["amount"]), row["category"].strip(), row.get("memo", "").strip(),
                            tuple(tag.strip() for tag in row.get("tags", "").split(",") if tag.strip()),
                        )
                        if transaction.category not in categories:
                            raise ValueError(f"등록되지 않은 카테고리입니다: {transaction.category}")
                        if transaction.id in existing_ids:
                            raise ValueError(f"중복된 거래 id입니다: {transaction.id}")
                    except (ValueError, KeyError, TypeError) as exc:
                        raise ValueError(f"CSV {row_number}행이 올바르지 않습니다: {exc}") from exc

                    staged.write(json.dumps(transaction.to_dict(), ensure_ascii=False) + "\n")
                    existing_ids.add(transaction.id)
                    imported += 1

            os.replace(staged_path, path)
            staged_path = None
            return imported, 0
        finally:
            if staged_path is not None:
                staged_path.unlink(missing_ok=True)

    def add_recurring(self, recurring: RecurringTransaction) -> None:
        if recurring.category not in self.category_repository.list():
            raise ValueError(f"등록되지 않은 카테고리입니다: {recurring.category}")
        self.recurring_repository.append(recurring)

    def generate_recurring(self, month: str) -> int:
        validate_month(month)
        last_day = monthrange(int(month[:4]), int(month[5:]))[1]
        generated_rows: list[Transaction] = []
        existing_generated = {
            (row.recurring_id, row.date)
            for row in self.transaction_repository.stream()
            if row.recurring_id is not None
        }
        for recurring in self.recurring_repository.stream():
            day = min(recurring.day, last_day)
            transaction_date = f"{month}-{day:02d}"
            if (recurring.id, transaction_date) in existing_generated:
                continue
            generated_rows.append(Transaction(new_id(), recurring.type, transaction_date, recurring.amount, recurring.category, recurring.memo, recurring.tags, recurring.id))
            existing_generated.add((recurring.id, transaction_date))

        if not generated_rows:
            return 0

        def rows() -> Iterator[Transaction]:
            yield from self.transaction_repository.stream()
            yield from generated_rows

        self.transaction_repository.replace(rows())
        return len(generated_rows)

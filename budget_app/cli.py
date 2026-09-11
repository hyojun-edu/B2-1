import argparse
from datetime import date
from pathlib import Path

from .models import Expense
from .service import export_csv, import_csv, top_categories
from .storage import DEFAULT_DB, load, save


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="간단한 지출 관리 프로그램")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="저장 파일 경로")
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add", help="지출 추가")
    add.add_argument("--date", dest="expense_date")
    add.add_argument("--category")
    add.add_argument("--amount", type=int)
    add.add_argument("--memo", default="")

    sub.add_parser("top", help="지출 금액 TOP 3")
    export = sub.add_parser("export", help="CSV로 내보내기")
    export.add_argument("--out", required=True, type=Path)
    export.add_argument("--month", help="YYYY-MM 형식의 월 필터")
    imp = sub.add_parser("import", help="CSV 가져오기")
    imp.add_argument("--from", dest="source", required=True, type=Path)
    return parser


def _prompt(value: str | None, label: str) -> str:
    return value if value is not None else input(label).strip()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        expenses = load(args.db)
        if args.command == "add":
            expense = Expense(_prompt(args.expense_date, "날짜(YYYY-MM-DD): "), _prompt(args.category, "카테고리: "), int(_prompt(str(args.amount) if args.amount is not None else None, "금액: ")), args.memo)
            save(expenses + [expense], args.db)
            print(f"[완료] 지출이 추가되었습니다: {expense.date} / {expense.category} / {expense.amount}원")
        elif args.command == "top":
            for index, (category, amount) in enumerate(top_categories(expenses), 1):
                print(f"{index}) {category} {amount}원")
        elif args.command == "export":
            if args.month and (len(args.month) != 7 or args.month[4] != "-"):
                raise ValueError("월 형식이 올바르지 않습니다 (YYYY-MM).")
            count = export_csv(expenses, args.out, args.month)
            print(f"[완료] {args.out} ({count} records)")
        elif args.command == "import":
            updated, imported, skipped = import_csv(expenses, args.source)
            save(updated, args.db)
            print(f"[완료] imported={imported}, skipped={skipped}")
        return 0
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"[오류] {exc}")
        if args.command == "add" and "날짜" in str(exc):
            print("[힌트] 예: 2024-01-15")
        return 1

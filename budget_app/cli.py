import argparse
import logging
from pathlib import Path

from .models import RecurringTransaction, Transaction
from .service import BudgetService, new_id, validate_month
from .repositories import BudgetRepository, CategoryRepository, RecurringRepository, TransactionRepository, backup


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="파일 기반 콘솔 가계부")
    parser.add_argument("--data-dir", type=Path, default=Path("data"), help="저장 폴더 (기본값: ./data)")
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("add", help="거래 추가"); add.add_argument("--date"); add.add_argument("--type", choices=["income", "expense"]); add.add_argument("--category"); add.add_argument("--amount", type=int); add.add_argument("--memo", default=None); add.add_argument("--tags", default=None)
    listing = sub.add_parser("list", help="거래 목록"); add_filters(listing); listing.add_argument("--limit", type=int, default=20)
    search = sub.add_parser("search", help="거래 검색"); add_filters(search)
    summary = sub.add_parser("summary", help="월별 요약"); summary.add_argument("--month", required=True); summary.add_argument("--top", type=int, default=3)
    budget = sub.add_parser("budget", help="예산 관리"); budget_sub = budget.add_subparsers(dest="budget_command", required=True); set_budget = budget_sub.add_parser("set"); set_budget.add_argument("--month", required=True); set_budget.add_argument("--amount", required=True, type=int)
    category = sub.add_parser("category", help="카테고리 관리"); category_sub = category.add_subparsers(dest="category_command", required=True); category_sub.add_parser("list"); cat_add = category_sub.add_parser("add"); cat_add.add_argument("--name"); cat_remove = category_sub.add_parser("remove"); cat_remove.add_argument("--name")
    update = sub.add_parser("update", help="거래 수정 (옵션 방식)"); update.add_argument("--id", required=True); update.add_argument("--date"); update.add_argument("--type", choices=["income", "expense"]); update.add_argument("--category"); update.add_argument("--amount", type=int); update.add_argument("--memo"); update.add_argument("--tags")
    delete = sub.add_parser("delete", help="거래 삭제"); delete.add_argument("--id", required=True)
    export = sub.add_parser("export", help="CSV 내보내기"); export.add_argument("--out", required=True, type=Path); add_filters(export); export.add_argument("--month")
    imp = sub.add_parser("import", help="CSV 가져오기"); imp.add_argument("--from", dest="source", required=True, type=Path)
    recurring = sub.add_parser("recurring", help="반복 내역 관리")
    recurring_sub = recurring.add_subparsers(dest="recurring_command", required=True)
    recurring_add = recurring_sub.add_parser("add", help="반복 내역 추가"); recurring_add.add_argument("--day", required=True, type=int); recurring_add.add_argument("--type", required=True, choices=["income", "expense"]); recurring_add.add_argument("--category", required=True); recurring_add.add_argument("--amount", required=True, type=int); recurring_add.add_argument("--memo", default=""); recurring_add.add_argument("--tags", default="")
    recurring_generate = recurring_sub.add_parser("generate", help="특정 월의 반복 내역 생성"); recurring_generate.add_argument("--month", required=True)
    sub.add_parser("backup", help="저장 파일 백업")
    return parser


def add_filters(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--from", dest="date_from"); parser.add_argument("--to", dest="date_to"); parser.add_argument("--category"); parser.add_argument("--type", choices=["income", "expense"]); parser.add_argument("--q"); parser.add_argument("--tag")


def prompt(value: str | None, label: str) -> str:
    return value if value is not None else input(label).strip()


def make_service(data_dir: Path) -> BudgetService:
    return BudgetService(
        transaction_repository=TransactionRepository(data_dir),
        category_repository=CategoryRepository(data_dir),
        budget_repository=BudgetRepository(data_dir),
        recurring_repository=RecurringRepository(data_dir),
    )


def print_transaction(row: Transaction) -> None:
    print(f"{row.id:<16} | {row.date} | {row.type:<7} | {row.category:<12} | {row.amount:>10} | {row.memo:<20} | {','.join(row.tags)}")


def print_table_header() -> None:
    print("id               | date       | type    | category     |      amount | memo                 | tags")
    print("-" * 105)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="[로그] %(message)s")
    args = build_parser().parse_args(argv)
    try:
        service = make_service(args.data_dir)
        if args.command == "add":
            transaction_date = prompt(args.date, "날짜(YYYY-MM-DD): ")
            transaction_type = prompt(args.type, "타입(income/expense): ")
            category_name = prompt(args.category, "카테고리: ")
            amount = int(prompt(str(args.amount) if args.amount is not None else None, "금액: "))
            memo = prompt(args.memo, "메모(선택): ")
            tags = tuple(tag.strip() for tag in prompt(args.tags, "태그(쉼표 구분): ").split(",") if tag.strip())
            transaction = Transaction(new_id(), transaction_type, transaction_date, amount, category_name, memo, tags)
            service.add(transaction); print(f"[저장 완료] id={transaction.id}")
        elif args.command in {"list", "search"}:
            print_table_header()
            limit = args.limit if args.command == "list" else None
            for index, row in enumerate(service.stream(**filters(args))):
                if limit is not None and index >= limit:
                    break
                print_transaction(row)
        elif args.command == "summary":
            validate_month(args.month); income, expense, ranking = service.summary(args.month)
            if income == expense == 0: print("데이터 없음"); return 0
            print(f"총 수입: {income}원\n총 지출: {expense}원\n잔액: {income - expense}원")
            budget = service.budget_repository.get(args.month)
            if budget is not None:
                rate = expense / budget * 100; print(f"예산: {budget}원 (사용률 {rate:.1f}%)"); print("[경고] 예산을 초과했습니다.") if expense > budget else None
            print(f"지출 TOP {args.top}"); [print(f"{i}) {cat} {amount}원") for i, (cat, amount) in enumerate(ranking[:args.top], 1)]
        elif args.command == "budget":
            service.set_budget(args.month, args.amount); print(f"[저장 완료] {args.month} 예산 {args.amount}원")
        elif args.command == "category":
            if args.category_command == "list": print("\n".join(f"- {name}" for name in service.category_repository.list()))
            elif args.category_command == "add": service.add_category(prompt(args.name, "카테고리명: ")); print("[저장 완료]")
            else: service.remove_category(prompt(args.name, "카테고리명: ")); print("[삭제 완료]")
        elif args.command == "update":
            changes = {key: value for key, value in {"date": args.date, "type": args.type, "category": args.category, "amount": args.amount, "memo": args.memo, "tags": tuple(x.strip() for x in args.tags.split(",") if x.strip()) if args.tags is not None else None}.items() if value is not None}
            if not changes: raise ValueError("수정할 옵션을 하나 이상 입력하세요.")
            if not service.update(args.id, changes): raise ValueError("없는 거래 id입니다.")
            print("[수정 완료]")
        elif args.command == "delete":
            if not service.delete(args.id): raise ValueError("없는 거래 id입니다.")
            print("[삭제 완료]")
        elif args.command == "export":
            if not args.month and not (args.date_from or args.date_to): raise ValueError("export에는 --month 또는 --from/--to가 필요합니다.")
            selected = filters(args); selected["month"] = args.month
            if args.month: validate_month(args.month); selected["from"] = f"{args.month}-01"; selected["to"] = f"{args.month}-31"
            count = service.export_csv(args.out, **selected); print(f"[완료] {args.out} ({count} records)")
        elif args.command == "import":
            imported, invalid_rows, report_path = service.import_csv(args.source)
            if invalid_rows:
                print(f"[실패] imported=0, invalid_rows={invalid_rows} (전체 반영 취소)")
                print(f"[안내] 불량 행 리포트를 확인하세요: {report_path}")
                return 1
            print(f"[완료] imported={imported}, invalid_rows=0")
        elif args.command == "recurring":
            if args.recurring_command == "add":
                recurring = RecurringTransaction(new_id(), args.day, args.type, args.amount, args.category, args.memo, tuple(tag.strip() for tag in args.tags.split(",") if tag.strip()))
                service.add_recurring(recurring); print(f"[저장 완료] recurring_id={recurring.id}")
            else:
                generated = service.generate_recurring(args.month); print(f"[완료] generated={generated}")
        elif args.command == "backup":
            print(f"[백업 완료] {backup(args.data_dir)}")
        return 0
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"[오류] {exc}\n[힌트] 입력값과 저장 경로를 확인하세요.")
        return 1


def filters(args: argparse.Namespace) -> dict[str, str | None]:
    return {"from": args.date_from, "to": args.date_to, "category": args.category, "type": args.type, "q": args.q, "tag": args.tag}

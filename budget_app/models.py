from dataclasses import asdict, dataclass
from datetime import date


@dataclass(frozen=True)
class Expense:
    date: str
    category: str
    amount: int
    memo: str = ""

    def __post_init__(self) -> None:
        try:
            date.fromisoformat(self.date)
        except (TypeError, ValueError) as exc:
            raise ValueError("날짜 형식이 올바르지 않습니다 (YYYY-MM-DD).") from exc
        if not self.category.strip():
            raise ValueError("카테고리를 입력해야 합니다.")
        if self.amount <= 0:
            raise ValueError("금액은 0보다 커야 합니다.")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

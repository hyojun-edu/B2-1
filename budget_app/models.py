from dataclasses import asdict, dataclass
from datetime import date


@dataclass(frozen=True)
class Transaction:
    id: str
    type: str
    date: str
    amount: int
    category: str
    memo: str = ""
    tags: tuple[str, ...] = ()
    recurring_id: str | None = None

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("거래 id가 필요합니다.")
        try:
            parsed = date.fromisoformat(self.date)
        except (TypeError, ValueError) as exc:
            raise ValueError("날짜 형식이 올바르지 않습니다 (YYYY-MM-DD).") from exc
        if parsed.isoformat() != self.date:
            raise ValueError("날짜 형식이 올바르지 않습니다 (YYYY-MM-DD).")
        if self.type not in {"income", "expense"}:
            raise ValueError("type은 income 또는 expense여야 합니다.")
        if self.amount <= 0:
            raise ValueError("금액은 0보다 커야 합니다.")
        if not self.category.strip():
            raise ValueError("카테고리를 입력해야 합니다.")

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["tags"] = list(self.tags)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "Transaction":
        raw_tags = data.get("tags", [])
        tags = tuple(str(raw_tags).split(",")) if isinstance(raw_tags, str) else tuple(str(tag) for tag in (raw_tags or []))
        return cls(str(data["id"]), str(data["type"]), str(data["date"]), int(data["amount"]), str(data["category"]), str(data.get("memo", "")), tags, str(data["recurring_id"]) if data.get("recurring_id") else None)


@dataclass(frozen=True)
class RecurringTransaction:
    id: str
    day: int
    type: str
    amount: int
    category: str
    memo: str = ""
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not 1 <= self.day <= 31:
            raise ValueError("반복 날짜는 1에서 31 사이여야 합니다.")
        if self.type not in {"income", "expense"}:
            raise ValueError("type은 income 또는 expense여야 합니다.")
        if self.amount <= 0:
            raise ValueError("금액은 0보다 커야 합니다.")
        if not self.category.strip():
            raise ValueError("카테고리를 입력해야 합니다.")

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["tags"] = list(self.tags)
        return data

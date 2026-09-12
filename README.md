# Budget App

Python 표준 라이브러리만 사용하는 파일 기반 콘솔 가계부입니다. 거래 CRUD, 검색, 월별 요약, 예산, 카테고리 관리, CSV 가져오기·내보내기를 제공합니다. Python 3.10 이상이 필요합니다.

## 실행

```bash
python3 -m budget_app --help
python3 -m budget_app add
```

모든 명령은 `--help`를 지원합니다. 저장 폴더는 기본적으로 `./data`이며, `--data-dir 다른폴더`로 바꿀 수 있습니다. 최초 실행 시 `categories.jsonl`에 `food`, `transport`, `rent`, `salary`가 자동 생성됩니다.

## 명령어

```bash
python3 -m budget_app add
python3 -m budget_app list --limit 10
python3 -m budget_app search --from 2024-01-01 --to 2024-01-31 --type expense --tag meal
python3 -m budget_app summary --month 2024-01 --top 3
python3 -m budget_app budget set --month 2024-01 --amount 500000
python3 -m budget_app category add --name health
python3 -m budget_app category list
python3 -m budget_app category remove --name health
python3 -m budget_app update --id TX-ABC123 --amount 20000 --memo 수정
python3 -m budget_app delete --id TX-ABC123
python3 -m budget_app export --out export.csv --month 2024-01
python3 -m budget_app import --from import.csv
```

`add`는 기본적으로 날짜, 타입, 카테고리, 금액, 메모, 태그를 순서대로 대화형 입력받습니다. `update`는 옵션 방식으로 고정했으며 `--id`와 수정할 필드를 함께 입력합니다. 목록과 검색 결과는 최신순입니다. 사용 중인 카테고리는 삭제할 수 없습니다.

## 저장 형식

데이터는 한 번에 모두 읽지 않아도 되는 JSONL로 세 파일에 나누어 저장합니다.

| 파일 | 내용 |
| --- | --- |
| `data/transactions.jsonl` | 거래의 `id`, `type`, `date`, `amount`, `category`, `memo`, `tags` |
| `data/categories.jsonl` | 카테고리의 `name` |
| `data/budgets.jsonl` | 월별 `month`, `amount` 예산 |

수정·삭제·카테고리 변경·예산 변경은 임시 파일에 기록한 뒤 원자적으로 교체하여 중간 상태가 남을 가능성을 줄입니다. 거래 수정·삭제도 JSONL 전체를 리스트로 로드하지 않고 한 행씩 임시 파일에 재작성합니다. 거래 추가는 JSONL 끝에 한 줄을 추가합니다.

## CSV 스키마

`export`와 `import`는 UTF-8 BOM, 헤더 포함 형식을 사용합니다. `export`는 `--month YYYY-MM` 또는 `--from YYYY-MM-DD`/`--to YYYY-MM-DD` 조건을 하나 이상 요구합니다.

BOM(Byte Order Mark)은 파일 맨 앞에 추가되는 특수한 바이트 표시입니다. 이 프로그램은 CSV를 `UTF-8-sig` 인코딩으로 저장하여 BOM을 포함합니다. Excel이 이 표시를 보고 파일을 UTF-8로 인식하므로, CSV를 Excel에서 열 때 한글이 깨지는 문제를 줄일 수 있습니다. 일반 UTF-8 파일과 데이터 내용은 같고 파일 시작 부분에 표시가 하나 추가된 형태입니다.

| column | 필수 | 설명 |
| --- | --- | --- |
| `id` | 아니오 | 없으면 import 시 자동 생성 |
| `date` | 예 | `YYYY-MM-DD` |
| `type` | 예 | `income` 또는 `expense` |
| `category` | 예 | 등록된 카테고리 |
| `amount` | 예 | 0보다 큰 정수 |
| `memo` | 아니오 | 문자열 |
| `tags` | 아니오 | 쉼표로 구분한 문자열 |

예시:

```csv
id,date,type,category,amount,memo,tags
TX-001,2024-01-15,expense,food,15000,점심,"meal,weekday"
TX-002,2024-01-25,income,salary,3000000,월급,
```

## 구조와 학습 포인트

| 계층 | 파일 | 책임 |
| --- | --- | --- |
| 모델 | `models.py` | `Transaction` 데이터 구조와 날짜·타입·금액 기본 검증 |
| 저장소 | `repositories.py` | 거래·카테고리·예산 JSONL의 스트리밍 읽기와 안전한 파일 쓰기 |
| 서비스 | `service.py` | CRUD, 검색, 요약, 예산, CSV 업무 규칙 |
| CLI | `cli.py` | 명령행 옵션·대화형 입력·출력·종료 코드 |

CLI는 입력을 해석하고 서비스에 요청하며, 서비스는 저장소를 통해 데이터를 다룹니다. 이 분리 덕분에 화면 출력 방식을 바꾸어도 거래 검증과 계산 규칙을 함께 수정할 필요가 없습니다. `Transaction`, `TransactionRepository`, `CategoryRepository`, `BudgetRepository`, `BudgetService`처럼 여러 클래스로 책임을 나누고 함수마다 타입 힌트를 적용했습니다.

`Transaction`은 `@dataclass(frozen=True)`로 정의했습니다. `frozen=True`는 객체를 생성한 뒤 필드 값을 바꿀 수 없게 합니다. 따라서 저장된 거래의 날짜·금액·카테고리가 실수로 변경되는 일을 줄일 수 있습니다.

```python
transaction = Transaction("TX-001", "expense", "2024-01-15", 15000, "food")
transaction.amount = 20000  # FrozenInstanceError 발생
```

거래를 변경해야 할 때는 기존 객체를 직접 수정하지 않고 새로운 `Transaction` 객체를 생성합니다. 또한 `tags`를 변경 가능한 `list` 대신 `tuple`로 저장해 태그 내부 내용도 함부로 바뀌지 않도록 했습니다. `frozen=True`는 객체 내부의 리스트나 딕셔너리까지 자동으로 불변으로 만들지는 않기 때문에, 컬렉션 필드의 자료형도 함께 선택해야 합니다.

`TransactionRepository.stream()`과 JSONL 읽기 함수는 `yield` 기반 제너레이터입니다. 반복할 때 한 행씩 `Transaction`을 생성하므로 대용량 파일도 전체 내용을 리스트로 만든 뒤 처리하지 않아 메모리 사용량을 줄일 수 있습니다. 수정·삭제도 같은 방식으로 한 행씩 읽어 임시 파일에 기록합니다. 최신순 정렬이 필요한 목록·검색은 최대 1,024개씩 정렬한 임시 청크 파일을 만든 뒤 병합하므로, 전체 거래를 메모리에 올리지 않고 순서를 유지합니다.

`service.py`의 `@logged_timed` 데코레이터는 서비스 함수의 예외 로그와 실행 시간 측정을 공통 처리합니다. 핵심 업무 함수마다 로그 코드를 복사하지 않아도 되고, CLI는 사용자에게 원인과 힌트를 출력하는 역할에 집중할 수 있습니다.

타입 힌트는 함수의 입출력 계약을 코드에 기록합니다. 예를 들어 다음 선언은 `Transaction` 목록과 선택적 정수 제한을 받아 카테고리·금액 튜플 목록을 반환한다는 뜻을 IDE와 정적 검사 도구에 전달합니다.

```python
def summary(
    self, month: str
) -> tuple[int, int, list[tuple[str, int]]]:
    ...
```

실제 서비스의 `stream() -> Iterator[Transaction]`, `summary() -> tuple[int, int, list[tuple[str, int]]]` 같은 선언도 함수 사이의 데이터 계약을 명확하게 하여 자동 완성, 코드 리뷰, 변경 영향 확인에 도움을 줍니다.

오류는 스택트레이스 대신 `[오류]` 원인과 `[힌트]` 해결 방향으로 출력되며, 정상 종료는 0, 오류 종료는 1을 반환합니다.

# Budget App

간단한 지출을 기록하고, 카테고리별 합계와 CSV 입출력을 제공하는 Python CLI 프로그램입니다. 외부 패키지 없이 Python 3.10 이상에서 동작합니다.

## 1. 실행

```bash
python -m budget_app --help
python -m budget_app add
```

지출은 기본적으로 현재 폴더의 `.budget_data.json`에 저장됩니다. `--db 다른파일.json`을 앞에 붙여 저장 위치를 바꿀 수 있습니다.

## 2. 명령어

```bash
python -m budget_app add --date 2024-01-15 --category rent --amount 150000 --memo 월세
python -m budget_app top
python -m budget_app export --out export.csv --month 2024-01
python -m budget_app import --from import.csv
```

`add`에서 인자를 생략하면 대화형으로 입력합니다. CSV는 `date,category,amount,memo` 헤더를 사용하며, 가져오기 중 형식이 잘못된 행은 건너뛰고 결과를 표시합니다.

## 프로젝트 구조

- `budget_app/__init__.py`: `budget_app`을 Python 패키지로 인식시키고 패키지 버전을 정의합니다.
- `budget_app/__main__.py`: `python -m budget_app` 실행 시 호출되며, `cli.py`의 `main()` 함수를 시작합니다.

실행 흐름은 다음과 같습니다.

```text
python -m budget_app
        ↓
budget_app/__main__.py
        ↓
budget_app/cli.py의 main()
```

## 3. 과제목표

### 1) 지출 TOP 3

`top` 명령은 모든 지출을 카테고리별로 합산한 뒤 금액이 큰 순서로 최대 3개를 출력합니다. 금액이 같으면 카테고리 이름순으로 정렬하여 결과가 항상 재현되도록 했습니다.

예시:

```text
1) rent 150000원
2) food 45000원
3) transport 20000원
```

### 2) export / import (CSV 내보내기/가져오기)

`export`는 전체 지출 또는 `--month YYYY-MM`으로 선택한 월의 지출을 CSV로 저장합니다. `import`는 CSV의 유효한 행을 저장소에 추가하고, 잘못된 날짜·금액·필수값이 있는 행은 `skipped`로 집계합니다. UTF-8 BOM을 사용해 Excel에서도 한글이 깨지지 않도록 했습니다.

### 3) 오류 출력

날짜는 실제 달력 날짜인 `YYYY-MM-DD`인지 검증합니다. 예를 들어 `2024-13-40`을 입력하면 저장하지 않고 `[오류] 날짜 형식이 올바르지 않습니다 (YYYY-MM-DD).`와 올바른 입력 예시를 출력합니다. 금액, 카테고리, CSV 헤더와 파일 접근 오류도 같은 방식으로 안내합니다.

## 4. CSV 형식

```csv
date,category,amount,memo
2024-01-15,rent,150000,월세
2024-01-20,food,45000,식비
```

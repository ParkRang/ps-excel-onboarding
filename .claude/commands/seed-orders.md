---
description: orders 테이블에 테스트 행 N개를 시드 (generate_series, 기본 10000)
argument-hint: [N]
allowed-tools: Bash
---
orders 테이블에 테스트 행을 시드한다. 개수: $ARGUMENTS (비어 있으면 10000).

다음을 실행할 것:
`cd backend && .venv/bin/python scripts/seed_orders.py $ARGUMENTS`

동작/주의:
- 전제: 로컬 Postgres가 5432에 떠 있어야 한다.
- 삽입 전/후 orders 행수를 사용자에게 보고할 것.
- 이 데이터는 export 원본이라 **자동 삭제되지 않는다**는 점을 알릴 것(정리하려면 별도 요청).

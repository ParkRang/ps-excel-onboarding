---
description: 로컬 Postgres에 붙어 Excel export를 실제로 실행·검증(웹훅 스텁, 자동 정리)
allowed-tools: Bash
---
로컬 Postgres 컨테이너에 붙어 `create_excel`을 실제로 돌려 end-to-end 검증한다.

다음을 실행할 것:
`cd backend && .venv/bin/python scripts/verify_export.py`

동작/주의:
- 전제: 로컬 Postgres(orders/jobs)가 5432에 떠 있어야 한다. 연결 실패면 먼저 사용자에게 알릴 것.
- 스크립트가 임시 Job을 만들어 export를 실행하고, 생성된 .xlsx를 다시 열어 행수/헤더를 검증한 뒤
  Job 행과 파일을 정리한다(웹훅/SSE는 스텁이라 실제 Discord 발송 없음).
- 결과(PASS/FAIL, 소요시간, duration)를 사용자에게 요약 보고할 것. FAIL이면 실패한 체크를 그대로 전달.

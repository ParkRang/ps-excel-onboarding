#!/usr/bin/env python
"""orders 테이블에 테스트 행을 시드한다.

사용:  cd backend && INFRA_MODE=local .venv/bin/python scripts/seed_orders.py [N]
       N 생략 시 10000. 로컬 Postgres가 떠 있어야 한다.
generate_series로 빠르게 삽입한다. (원본 데이터라 자동 삭제하지 않음)
"""
import os
import sys

# backend/ 를 import 경로에 추가 (scripts/ 에서 실행해도 절대 import 되도록)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from db.database import engine


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10000
    with engine.begin() as c:
        before = c.execute(text("select count(*) from orders")).scalar()
        c.execute(
            text(
                """
                insert into orders(user_name, product_name, category, amount, status, order_date)
                select 'user'||g, 'product', 'cat', (g %% 1000), 'PAID', now()
                from generate_series(1, :n) g
                """
            ),
            {"n": n},
        )
        after = c.execute(text("select count(*) from orders")).scalar()
    print(f"seeded {n} orders: {before} -> {after}")


if __name__ == "__main__":
    main()

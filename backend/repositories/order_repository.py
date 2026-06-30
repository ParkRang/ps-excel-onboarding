from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.order import Order


class OrderRepository:

    def find_all(self, db: Session) -> list[Order]:
        stmt = (
            select(Order)
            .order_by(Order.id)
        )

        return list(
            db.execute(stmt).scalars().all()
        )
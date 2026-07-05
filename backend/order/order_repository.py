from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from order.order import Order


class OrderRepository:

    # def find_all(self, db: Session) -> list[Order]:
    #     stmt = (
    #         select(Order)
    #         .order_by(Order.id)
    #     )

    #     return list(
    #         db.execute(stmt).scalars().all()
    #     )

    async def find_chunk_by_last_id(db: AsyncSession, last_id: int, size: int = 1000):
        stmt = (
            select(Order)
            .where(Order.id > last_id)
            .order_by(Order.id)
            .limit(size)
        )

        result = await db.execute(stmt)
        return result.scalars().all()
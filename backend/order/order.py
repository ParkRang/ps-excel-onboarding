from datetime import datetime

from sqlalchemy import Integer, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from db.database import Base
from common.utils.now import now


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    user_name: Mapped[str] = mapped_column(String(100))

    product_name: Mapped[str] = mapped_column(String(200))

    category: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    amount: Mapped[int] = mapped_column(Integer)

    status: Mapped[str] = mapped_column(String(30))

    order_date: Mapped[datetime] = mapped_column(DateTime)
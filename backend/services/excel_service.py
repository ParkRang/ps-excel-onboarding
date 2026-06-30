import os

from openpyxl import Workbook

from backend.models.job import Job
from backend.models.order import Order


class ExcelService:

    def create_excel(
        self,
        orders: list[Order],
        job: Job
    ) -> str:

        workbook = Workbook()

        sheet = workbook.active
        sheet.title = "Orders"

        sheet.append([
            "주문번호",
            "주문자",
            "상품명",
            "카테고리",
            "금액",
            "상태",
            "주문일"
        ])

        total = len(orders)

        for order in orders:

            sheet.append([
                order.id,
                order.user_name,
                order.product_name,
                order.category,
                order.amount,
                order.status,
                order.order_date.strftime("%Y-%m-%d %H:%M:%S")
            ])

        os.makedirs("exports", exist_ok=True)

        file_path = f"exports/job_{job.id}.xlsx"

        workbook.save(file_path)

        return file_path
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font


class ExcelReportBuilder:
    """Builds an Excel workbook for the invitations report."""

    def __init__(self, headers: list[str], sheet_name: str = "Invitations"):
        self.headers = headers
        self.sheet_name = sheet_name

    def build_from_rows(self, rows: list[list[str]]) -> bytes:  # noqa: WPS210
        """Build an Excel workbook in memory and return its raw bytes."""
        wb = Workbook()
        ws = wb.active
        if ws.title == "Sheet":
            ws.title = self.sheet_name

        header_font = Font(bold=True)
        for col, header in enumerate(self.headers, start=1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = header_font

        for row_idx, row_data in enumerate(rows, start=2):
            for col_idx, cell_value in enumerate(row_data, start=1):
                ws.cell(row=row_idx, column=col_idx, value=cell_value)

        ws.auto_filter.ref = ws.dimensions

        buffer = BytesIO()
        wb.save(buffer)
        return buffer.getvalue()

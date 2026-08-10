"""Tidy up a Collated BOM Exporter spreadsheet for reading and ordering.

InvenTree writes plain data, so the nice-to-haves live here. Run this on an
exported .xlsx and it will:

  - drop the IPN column,
  - move Description to the far right so the numbers read first,
  - colour "Enough In Stock" green for Yes, red for No,
  - format Unit Price and Line Total as currency,
  - rebuild a bold TOTAL row (total quantity, order qty and total cost),
  - bold the header, freeze it, add a filter, and size the columns.

Usage:
    python format_bom_excel.py "path/to/export.xlsx"
    python format_bom_excel.py "path/to/export.xlsx" "path/to/output.xlsx"

If no output path is given, it writes "<name> (formatted).xlsx" alongside the
input.
"""

import sys
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


# --- Styling constants ------------------------------------------------------
CURRENCY_FORMAT = "$#,##0.00"
DROP_COLUMNS = ["IPN"]
DESCRIPTION_COLUMN = "Description"
STOCK_FLAG_COLUMN = "Enough In Stock"
CURRENCY_COLUMNS = ["Unit Price", "Line Total"]
# Columns to sum on the TOTAL row.
SUM_COLUMNS = ["Total Quantity Required", "Order Qty", "Line Total"]
TOTAL_LABEL = "TOTAL"

HEADER_FILL = PatternFill("solid", fgColor="1F2A37")   # dark slate
HEADER_FONT = Font(bold=True, color="FFFFFF")
GREEN_FILL = PatternFill("solid", fgColor="C6EFCE")
GREEN_FONT = Font(color="006100")
RED_FILL = PatternFill("solid", fgColor="FFC7CE")
RED_FONT = Font(color="9C0006")
TOTAL_FONT = Font(bold=True)
TOP_BORDER = Border(top=Side(style="thin", color="9AA0A6"))

YES_VALUES = {"yes", "y", "true", "1"}
NO_VALUES = {"no", "n", "false", "0"}


def _to_number(value):
    """Return a float for numeric-looking values, else None."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(",", "").replace("$", "").strip())
    except (ValueError, AttributeError):
        return None


def format_workbook(input_path: Path, output_path: Path) -> None:
    wb = openpyxl.load_workbook(input_path, data_only=True)
    ws = wb.active

    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        raise SystemExit("Spreadsheet is empty.")

    header = list(rows[0])
    data = [list(r) for r in rows[1:]]

    # Drop any pre-existing TOTAL row so we do not double count.
    if data and str(data[-1][0]).strip().upper() == TOTAL_LABEL:
        data.pop()

    # Work out the new column order: drop unwanted columns, push Description
    # to the far right.
    kept = [h for h in header if h not in DROP_COLUMNS]
    if DESCRIPTION_COLUMN in kept:
        kept.remove(DESCRIPTION_COLUMN)
        kept.append(DESCRIPTION_COLUMN)

    src_index = {name: i for i, name in enumerate(header)}

    def cell(row, name):
        i = src_index.get(name)
        return row[i] if i is not None and i < len(row) else None

    # Build a fresh sheet in the new order.
    out = openpyxl.Workbook()
    sheet = out.active
    sheet.title = "Collated BOM"

    sheet.append(kept)

    for row in data:
        sheet.append([cell(row, name) for name in kept])

    # TOTAL row.
    totals = {}
    for name in SUM_COLUMNS:
        if name in kept:
            total = sum(
                n for n in (_to_number(cell(r, name)) for r in data) if n is not None
            )
            totals[name] = total

    total_row = []
    for i, name in enumerate(kept):
        if i == 0:
            total_row.append(TOTAL_LABEL)
        elif name in totals:
            total_row.append(round(totals[name], 4))
        else:
            total_row.append(None)
    sheet.append(total_row)

    _apply_styles(sheet, kept)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.save(output_path)


def _apply_styles(sheet, header) -> None:
    col_index = {name: i + 1 for i, name in enumerate(header)}
    last_row = sheet.max_row
    total_row_idx = last_row

    # Header styling.
    for c in range(1, len(header) + 1):
        hc = sheet.cell(row=1, column=c)
        hc.fill = HEADER_FILL
        hc.font = HEADER_FONT
        hc.alignment = Alignment(vertical="center")

    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = f"A1:{get_column_letter(len(header))}1"

    # Currency columns.
    for name in CURRENCY_COLUMNS:
        c = col_index.get(name)
        if not c:
            continue
        for r in range(2, last_row + 1):
            sheet.cell(row=r, column=c).number_format = CURRENCY_FORMAT

    # Colour the stock flag (data rows only, not the TOTAL row).
    flag_c = col_index.get(STOCK_FLAG_COLUMN)
    if flag_c:
        for r in range(2, total_row_idx):
            cellv = sheet.cell(row=r, column=flag_c)
            token = str(cellv.value).strip().lower() if cellv.value is not None else ""
            if token in YES_VALUES:
                cellv.fill, cellv.font = GREEN_FILL, GREEN_FONT
            elif token in NO_VALUES:
                cellv.fill, cellv.font = RED_FILL, RED_FONT

    # TOTAL row styling.
    for c in range(1, len(header) + 1):
        tc = sheet.cell(row=total_row_idx, column=c)
        tc.font = TOTAL_FONT
        tc.border = TOP_BORDER
        if header[c - 1] in CURRENCY_COLUMNS:
            tc.number_format = CURRENCY_FORMAT

    # Column widths, capped so long descriptions do not blow out the sheet.
    for c, name in enumerate(header, start=1):
        longest = len(str(name))
        for r in range(2, last_row + 1):
            val = sheet.cell(row=r, column=c).value
            if val is not None:
                longest = max(longest, len(str(val)))
        width = min(max(longest + 2, 10), 60)
        sheet.column_dimensions[get_column_letter(c)].width = width
        if name == DESCRIPTION_COLUMN:
            for r in range(2, last_row + 1):
                sheet.cell(row=r, column=c).alignment = Alignment(wrap_text=True, vertical="top")


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python format_bom_excel.py <input.xlsx> [output.xlsx]")

    input_path = Path(sys.argv[1])
    if not input_path.exists():
        raise SystemExit(f"File not found: {input_path}")

    if len(sys.argv) >= 3:
        output_path = Path(sys.argv[2])
    else:
        output_path = input_path.with_name(f"{input_path.stem} (formatted).xlsx")

    format_workbook(input_path, output_path)
    print(f"Written: {output_path}")


if __name__ == "__main__":
    main()

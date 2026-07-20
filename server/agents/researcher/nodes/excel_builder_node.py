import os
import logging
import time
import xlsxwriter
from langchain_core.messages import AIMessage
from agents.researcher.state import ResearcherState

logger = logging.getLogger(__name__)

TMP_DIR = "/tmp"


def excel_builder_node(state: ResearcherState) -> dict:
    """
    Ingests structured_products from state and writes them to an .xlsx file
    using XlsxWriter. Returns the filename and a download-ready flag.
    """
    products: list[dict] = state.get("structured_products") or []
    query: str = state.get("query") or "products"

    if not products:
        return {
            "messages": [AIMessage(content="⚠️ No product data to export. The search may not have returned usable results.")],
            "download_ready": False,
            "excel_filename": None,
        }

    # --- Build the .xlsx file ---
    timestamp = int(time.time())
    safe_query = "".join(c if c.isalnum() else "_" for c in query)[:30]
    filename = f"products_{safe_query}_{timestamp}.xlsx"
    filepath = os.path.join(TMP_DIR, filename)

    workbook = xlsxwriter.Workbook(filepath)
    worksheet = workbook.add_worksheet("Products")

    # ── Styles ──────────────────────────────────────────────────────────────
    header_fmt = workbook.add_format({
        "bold": True,
        "font_color": "#FFFFFF",
        "bg_color": "#1E40AF",   # deep blue
        "border": 1,
        "align": "center",
        "valign": "vcenter",
        "font_size": 12,
    })
    cell_fmt = workbook.add_format({
        "border": 1,
        "align": "left",
        "valign": "vcenter",
        "font_size": 11,
        "text_wrap": True,
    })
    url_fmt = workbook.add_format({
        "border": 1,
        "font_color": "#3B82F6",
        "underline": True,
        "align": "left",
        "valign": "vcenter",
        "font_size": 11,
    })
    alt_fmt = workbook.add_format({
        "border": 1,
        "align": "left",
        "valign": "vcenter",
        "font_size": 11,
        "bg_color": "#F1F5F9",
        "text_wrap": True,
    })
    alt_url_fmt = workbook.add_format({
        "border": 1,
        "font_color": "#3B82F6",
        "underline": True,
        "align": "left",
        "valign": "vcenter",
        "font_size": 11,
        "bg_color": "#F1F5F9",
    })

    # ── Column widths ────────────────────────────────────────────────────────
    worksheet.set_column(0, 0, 40)   # Name
    worksheet.set_column(1, 1, 55)   # Source
    worksheet.set_column(2, 2, 18)   # Price
    worksheet.set_row(0, 28)

    # ── Header row ───────────────────────────────────────────────────────────
    headers = ["Product Name", "Source URL", "Price"]
    for col, h in enumerate(headers):
        worksheet.write(0, col, h, header_fmt)

    # ── Data rows ────────────────────────────────────────────────────────────
    for row_idx, product in enumerate(products, start=1):
        row_num = row_idx  # 0-indexed for xlsxwriter
        is_alt = row_idx % 2 == 0
        text_f = alt_fmt if is_alt else cell_fmt
        link_f = alt_url_fmt if is_alt else url_fmt

        worksheet.set_row(row_num, 22)

        name = product.get("name") or "Unknown"
        source = product.get("source") or ""
        price = product.get("price") or "N/A"

        worksheet.write(row_num, 0, name, text_f)

        if source:
            worksheet.write_url(row_num, 1, source, link_f, source[:80])
        else:
            worksheet.write(row_num, 1, "N/A", text_f)

        worksheet.write(row_num, 2, price, text_f)

    workbook.close()
    logger.info(f"excel_builder_node: wrote {filepath} with {len(products)} rows")

    return {
        "messages": [
            AIMessage(
                content=(
                    f"📊 Your Excel report is ready with **{len(products)}** products!\n\n"
                    f"Tap the **Download Excel** button below to save it to your device."
                )
            )
        ],
        "excel_filename": filename,
        "download_ready": True,
    }

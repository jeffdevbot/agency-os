import os
import tempfile
import itertools
import time

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.responses import FileResponse

from ..auth import require_user
from ..config import settings
from ..usage_logging import usage_logger
from ..services.npat import (
    read_backview_path,
    calculate_asin_metrics,
    derive_category,
    build_npat_workbook,
)
from openpyxl import load_workbook
import xlsxwriter

router = APIRouter(prefix="/npat", tags=["npat"])


@router.get("/healthz")
def health():
    """Health check endpoint."""
    return {"ok": True}


MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "40"))


@router.post("/process", response_class=FileResponse)
async def process_report(
    file: UploadFile = File(...),
    user=Depends(require_user),
):
    """
    Generate N-PAT workbook from Search Term Report.

    Filters to ONLY ASINs, groups by campaign, calculates metrics,
    and generates Excel with H10 integration zones.
    """
    started = time.time()
    total = 0
    chunk_size = 2 * 1024 * 1024

    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp_path = tmp.name
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_UPLOAD_MB * 1024 * 1024:
                await file.close()
                os.unlink(tmp_path)
                raise HTTPException(status_code=413, detail="File too large")
            tmp.write(chunk)
    await file.close()

    try:
        df = read_backview_path(tmp_path, file.filename)
    except Exception as exc:
        os.unlink(tmp_path)
        raise HTTPException(status_code=400, detail=f"Parse error: {exc}") from exc

    os.unlink(tmp_path)

    if df.empty:
        raise HTTPException(
            status_code=400,
            detail="No ASINs found in uploaded file. N-PAT requires ASIN data (10-character alphanumeric codes like B08XYZ123)."
        )

    campaign_items = []
    for camp, sub in df.groupby("Campaign Name"):
        cname = str(camp)
        # Exclude campaigns with "Ex.", "SDI", or "SDV" in name
        if any(x in cname for x in ["Ex.", "SDI", "SDV"]):
            continue

        category_raw, category_key, cat_notes = derive_category(cname)

        # Calculate ASIN metrics
        asins = calculate_asin_metrics(sub)

        notes = list(cat_notes)
        if asins.empty:
            notes.append("No ASINs found for this campaign.")

        campaign_items.append(
            {
                "campaign_name": cname,
                "category_raw": category_raw,
                "category_key": category_key,
                "asins": asins,
                "notes": notes,
            }
        )

    if not campaign_items:
        raise HTTPException(status_code=400, detail="No eligible campaigns after filters (Ex./SD*).")

    workbook_path = build_npat_workbook(campaign_items, settings.app_version)
    dl_name = (
        os.path.splitext(file.filename)[0].replace(" ", "_")
        + "_npat.xlsx"
    )

    # Calculate total ASINs across all campaigns
    total_asins = sum(len(item["asins"]) for item in campaign_items)

    usage_logger.log(
        {
            "user_id": user.get("sub"),
            "user_email": user.get("email"),
            "file_name": file.filename,
            "file_size_bytes": total,
            "rows_processed": int(df.shape[0]),
            "campaigns": len(campaign_items),
            "total_asins": total_asins,
            "status": "success",
            "duration_ms": int((time.time() - started) * 1000),
            "app_version": settings.app_version,
        }
    )

    return FileResponse(
        workbook_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=dl_name,
    )


@router.post("/collect", response_class=FileResponse)
async def collect_negatives(
    file: UploadFile = File(...),
    user=Depends(require_user),
):
    """
    Extract negatives summary from filled N-PAT workbook.

    Reads ASINs marked "NE" in column AB, extracts enrichment data
    from columns W-AA, and generates formatted negatives summary.
    """
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        tmp_path = tmp.name
        tmp.write(await file.read())
    await file.close()

    try:
        wb = load_workbook(tmp_path, data_only=True)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Unable to read workbook: {exc}") from exc
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    # Per-campaign negative ASINs with enrichment
    per_campaign: dict[str, list[dict]] = {}

    def _last_non_empty(sheet, col: str, start_row: int) -> int:
        """Find last non-empty row in column."""
        max_row = sheet.max_row
        for i in range(max_row, start_row - 1, -1):
            val = sheet[f"{col}{i}"].value
            if val not in (None, ""):
                return i
        return start_row - 1

    for sheet in wb.worksheets:
        if sheet.title in {"Summary"}:
            continue

        # Get campaign name from cell B1
        campaign_name = sheet["B1"].value or sheet.title

        # Find last row with data in NE/NP column (AB)
        last_ne_row = _last_non_empty(sheet, "AB", 6)

        negatives = []
        # Read ASINs marked "NE" in column AB
        for i in range(6, last_ne_row + 1):
            flag = sheet[f"AB{i}"].value
            if (flag or "").strip().upper() == "NE":
                asin = sheet[f"A{i}"].value
                if asin in (None, ""):
                    continue

                # Read original metrics (columns B-J)
                impression = sheet[f"B{i}"].value or 0
                click = sheet[f"C{i}"].value or 0
                spend = sheet[f"D{i}"].value or 0
                order_14d = sheet[f"E{i}"].value or 0
                sales_14d = sheet[f"F{i}"].value or 0
                ctr = sheet[f"G{i}"].value or 0
                cvr = sheet[f"H{i}"].value or 0
                cpc = sheet[f"I{i}"].value or 0
                acos = sheet[f"J{i}"].value or 0

                # Read enrichment data (columns W-AA)
                title = sheet[f"W{i}"].value or ""
                brand = sheet[f"X{i}"].value or ""
                price = sheet[f"Y{i}"].value or ""
                rating = sheet[f"Z{i}"].value or ""
                reviews = sheet[f"AA{i}"].value or ""

                negatives.append({
                    "asin": str(asin),
                    "title": str(title),
                    "brand": str(brand),
                    "impression": impression,
                    "click": click,
                    "spend": spend,
                    "order_14d": order_14d,
                    "sales_14d": sales_14d,
                    "ctr": ctr,
                    "cvr": cvr,
                    "cpc": cpc,
                    "acos": acos,
                })

        if negatives:
            per_campaign[str(campaign_name)] = negatives

    if not per_campaign:
        raise HTTPException(status_code=400, detail="No NE markings found. Please mark ASINs as 'NE' in column AB before uploading.")

    # Generate negatives summary Excel
    rows_out = [[
        "Campaign",
        "ASIN",
        "Product Title",
        "Brand",
        "Impression",
        "Click",
        "Spend",
        "Order 14d",
        "Sales 14d",
        "CTR",
        "CVR",
        "CPC",
        "ACOS",
    ]]

    for campaign_name, negatives in per_campaign.items():
        for neg in negatives:
            rows_out.append([
                campaign_name,
                neg["asin"],
                neg["title"],
                neg["brand"],
                neg["impression"],
                neg["click"],
                neg["spend"],
                neg["order_14d"],
                neg["sales_14d"],
                neg["ctr"],
                neg["cvr"],
                neg["cpc"],
                neg["acos"],
            ])

    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as out_tmp:
        out_path = out_tmp.name

    workbook = xlsxwriter.Workbook(out_path)
    ws = workbook.add_worksheet("NE Summary")

    # Define formats
    header_fmt = workbook.add_format(
        {"bold": True, "bg_color": "#0066CC", "font_color": "#FFFFFF", "border": 1, "align": "center", "valign": "vcenter"}
    )
    border_fmt = workbook.add_format({"border": 1})
    zebra_fmt = workbook.add_format({"bg_color": "#F2F2F2", "border": 1})
    number_fmt = workbook.add_format({"border": 1, "num_format": "#,##0", "align": "center"})
    zebra_number_fmt = workbook.add_format({"bg_color": "#F2F2F2", "border": 1, "num_format": "#,##0", "align": "center"})
    currency_fmt = workbook.add_format({"border": 1, "num_format": "$#,##0.00"})
    zebra_currency_fmt = workbook.add_format({"bg_color": "#F2F2F2", "border": 1, "num_format": "$#,##0.00"})
    pct_fmt = workbook.add_format({"border": 1, "num_format": "0.00%"})
    zebra_pct_fmt = workbook.add_format({"bg_color": "#F2F2F2", "border": 1, "num_format": "0.00%"})

    # Write headers
    for j, col_name in enumerate(rows_out[0]):
        ws.write_string(0, j, col_name, header_fmt)

    # Write data rows
    for r, row_vals in enumerate(rows_out[1:], start=1):
        is_zebra = r % 2 == 0
        base_fmt = zebra_fmt if is_zebra else border_fmt

        # Campaign, ASIN, Title, Brand (text)
        for c in range(4):
            ws.write(r, c, row_vals[c], base_fmt)

        # Impression, Click (numbers)
        ws.write_number(r, 4, float(row_vals[4] or 0), zebra_number_fmt if is_zebra else number_fmt)
        ws.write_number(r, 5, float(row_vals[5] or 0), zebra_number_fmt if is_zebra else number_fmt)

        # Spend (currency)
        ws.write_number(r, 6, float(row_vals[6] or 0), zebra_currency_fmt if is_zebra else currency_fmt)

        # Order 14d (number)
        ws.write_number(r, 7, float(row_vals[7] or 0), zebra_number_fmt if is_zebra else number_fmt)

        # Sales 14d (currency)
        ws.write_number(r, 8, float(row_vals[8] or 0), zebra_currency_fmt if is_zebra else currency_fmt)

        # CTR, CVR (percentage)
        ws.write_number(r, 9, float(row_vals[9] or 0), zebra_pct_fmt if is_zebra else pct_fmt)
        ws.write_number(r, 10, float(row_vals[10] or 0), zebra_pct_fmt if is_zebra else pct_fmt)

        # CPC (currency)
        ws.write_number(r, 11, float(row_vals[11] or 0), zebra_currency_fmt if is_zebra else currency_fmt)

        # ACOS (percentage)
        ws.write_number(r, 12, float(row_vals[12] or 0), zebra_pct_fmt if is_zebra else pct_fmt)

    # Set column widths
    ws.set_column("A:A", 50)  # Campaign
    ws.set_column("B:B", 15)  # ASIN
    ws.set_column("C:C", 60)  # Product Title
    ws.set_column("D:D", 20)  # Brand
    ws.set_column("E:F", 12)  # Impression, Click
    ws.set_column("G:G", 12)  # Spend
    ws.set_column("H:H", 12)  # Order 14d
    ws.set_column("I:I", 12)  # Sales 14d
    ws.set_column("J:M", 10)  # CTR, CVR, CPC, ACOS

    ws.freeze_panes(1, 0)
    workbook.close()

    usage_logger.log(
        {
            "user_id": user.get("sub"),
            "user_email": user.get("email"),
            "file_name": file.filename,
            "status": "success",
            "rows_emitted": len(rows_out) - 1,
            "app_version": settings.app_version,
        }
    )

    return FileResponse(
        out_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"{os.path.splitext(file.filename)[0]}_negatives.xlsx",
    )

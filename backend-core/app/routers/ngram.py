import os
import tempfile
import time

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.responses import FileResponse

import tempfile

from ..auth import require_user
from ..config import settings
from ..usage_logging import usage_logger
from ..services.ngram import (
    read_backview_path,
    build_ngram,
    derive_category,
    build_workbook,
)
from openpyxl import load_workbook
import xlsxwriter

router = APIRouter(prefix="/ngram", tags=["ngram"])


@router.get("/healthz")
def health():
    return {"ok": True}


MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "40"))


@router.post("/process", response_class=FileResponse)
async def process_report(
    file: UploadFile = File(...),
    user=Depends(require_user),
):
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

    campaign_items = []
    for camp, sub in df.groupby("Campaign Name"):
        cname = str(camp)
        if any(x in cname for x in ["Ex.", "SDI", "SDV"]):
            continue

        category_raw, category_key, cat_notes = derive_category(cname)

        mono = build_ngram(sub, 1)
        bi = build_ngram(sub, 2)
        tri = build_ngram(sub, 3)

        raw = sub.rename(columns={"Query": "Search Term"})[
            ["Search Term", "Impression", "Click", "Spend", "Order 14d", "Sales 14d"]
        ].copy()
        raw["NE/NP"] = ""
        raw["Comments"] = ""
        raw = raw.sort_values(["Click", "Sales 14d"], ascending=[False, False]).reset_index(drop=True)

        notes = list(cat_notes)
        if mono.empty:
            notes.append("Monogram table has no rows.")
        if bi.empty:
            notes.append("Bigram table has no rows.")
        if tri.empty:
            notes.append("Trigram table has no rows.")
        if raw.empty:
            notes.append("Search Term table has no rows.")

        campaign_items.append(
            {
                "campaign_name": cname,
                "category_raw": category_raw,
                "category_key": category_key,
                "mono": mono,
                "bi": bi,
                "tri": tri,
                "raw": raw,
                "notes": notes,
            }
        )

    if not campaign_items:
        raise HTTPException(status_code=400, detail="No eligible campaigns after filters (Ex./SD*).")

    workbook_path = build_workbook(campaign_items, settings.app_version)
    dl_name = (
        os.path.splitext(file.filename)[0].replace(" ", "_")
        + "_ngrams.xlsx"
    )

    usage_logger.log(
        {
            "user_id": user.get("sub"),
            "user_email": user.get("email"),
            "file_name": file.filename,
            "file_size_bytes": total,
            "rows_processed": int(df.shape[0]),
            "campaigns": len(campaign_items),
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
    # Parse a filled workbook and extract NE keywords plus scratchpad mono/bi/tri
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

    rows_out = [["Campaign", "NE Keywords", "Monogram", "Bigram", "Trigram"]]

    def _last_non_empty(sheet, col: str, start_row: int) -> int:
        max_row = sheet.max_row
        for i in range(max_row, start_row - 1, -1):
            val = sheet[f"{col}{i}"].value
            if val not in (None, ""):
                return i
        return start_row - 1

    for sheet in wb.worksheets:
        if sheet.title in {"Summary", "NE Summary"}:
            continue
        campaign_name = sheet["B1"].value or sheet.title
        last_ne_row = _last_non_empty(sheet, "AT", 6)
        last_sp_row = max(
            _last_non_empty(sheet, "AX", 7),
            _last_non_empty(sheet, "AY", 7),
            _last_non_empty(sheet, "AZ", 7),
        )
        # NE keywords from search term table (AN with AT = "NE")
        for i in range(6, last_ne_row + 1):
            flag = sheet[f"AT{i}"].value
            term = sheet[f"AN{i}"].value
            if (flag or "").strip().upper() == "NE" and term not in (None, ""):
                rows_out.append([campaign_name, str(term), "", "", ""])
        # Scratchpad mono/bi/tri
        for i in range(7, last_sp_row + 1):
            mono = sheet[f"AX{i}"].value
            bi = sheet[f"AY{i}"].value
            tri = sheet[f"AZ{i}"].value
            if mono not in (None, "") or bi not in (None, "") or tri not in (None, ""):
                rows_out.append(
                    [
                        campaign_name,
                        "",
                        str(mono) if mono not in (None, "") else "",
                        str(bi) if bi not in (None, "") else "",
                        str(tri) if tri not in (None, "") else "",
                    ]
                )

    if len(rows_out) == 1:
        raise HTTPException(status_code=400, detail="No NE or scratchpad entries found.")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as out_tmp:
        out_path = out_tmp.name

    workbook = xlsxwriter.Workbook(out_path)
    ws = workbook.add_worksheet("NE Summary")
    header_fmt = workbook.add_format(
        {"bold": True, "bg_color": "#0066CC", "font_color": "#FFFFFF", "border": 1, "align": "center", "valign": "vcenter"}
    )
    zebra_fmt = workbook.add_format({"bg_color": "#F2F2F2"})
    border_fmt = workbook.add_format({"border": 1})

    for j, col_name in enumerate(rows_out[0]):
        ws.write_string(0, j, col_name, header_fmt)

    for r, row_vals in enumerate(rows_out[1:], start=1):
        fmt = zebra_fmt if r % 2 == 0 else border_fmt
        for c, val in enumerate(row_vals):
            ws.write(r, c, val, fmt)

    ws.set_column("A:A", 50)
    ws.set_column("B:B", 60)
    ws.set_column("C:E", 30)
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

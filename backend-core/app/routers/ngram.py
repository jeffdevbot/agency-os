import os
import tempfile
import itertools
import time
from datetime import date

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from supabase import Client, create_client

import tempfile

from ..auth import require_user
from ..config import settings
from ..usage_logging import usage_logger
from ..services.ngram import (
    read_backview_path,
    build_campaign_items,
    build_workbook,
    NativeNgramWorkbookService,
)
from openpyxl import load_workbook
import xlsxwriter

router = APIRouter(prefix="/ngram", tags=["ngram"])


@router.get("/healthz")
def health():
    return {"ok": True}


MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "40"))


def _get_supabase() -> Client:
    if not settings.supabase_url or not settings.supabase_service_role:
        raise HTTPException(status_code=500, detail="Supabase credentials not configured")
    try:
        return create_client(settings.supabase_url, settings.supabase_service_role)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to initialize Supabase client") from exc


def _get_native_service() -> NativeNgramWorkbookService:
    return NativeNgramWorkbookService(_get_supabase())


class NativeWorkbookRequest(BaseModel):
    profile_id: str = Field(..., min_length=1)
    ad_product: str = Field(..., min_length=1)
    date_from: date
    date_to: date
    respect_legacy_exclusions: bool = True


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

    build_result = build_campaign_items(df, respect_legacy_exclusions=True)
    campaign_items = build_result.campaign_items

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
            "tool": "ngram",
            "action": "process",
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


@router.post("/native-workbook", response_class=FileResponse)
async def build_native_workbook(
    request: NativeWorkbookRequest,
    service: NativeNgramWorkbookService = Depends(_get_native_service),
    user=Depends(require_user),
):
    if request.date_from > request.date_to:
        raise HTTPException(status_code=400, detail="date_from must be on or before date_to")

    started = time.time()

    try:
        result = service.build_workbook_from_search_term_facts(
            profile_id=request.profile_id,
            ad_product=request.ad_product,
            date_from=request.date_from,
            date_to=request.date_to,
            respect_legacy_exclusions=request.respect_legacy_exclusions,
            app_version=settings.app_version,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to generate native N-Gram workbook") from exc

    usage_logger.log(
        {
            "user_id": user.get("sub"),
            "user_email": user.get("email"),
            "tool": "ngram",
            "action": "native_workbook",
            "profile_id": request.profile_id,
            "ad_product": result.ad_product,
            "date_from": request.date_from.isoformat(),
            "date_to": request.date_to.isoformat(),
            "rows_processed": result.rows_processed,
            "campaigns": result.campaigns_included,
            "campaigns_skipped": result.campaigns_skipped,
            "status": "success",
            "duration_ms": int((time.time() - started) * 1000),
            "app_version": settings.app_version,
        }
    )

    return FileResponse(
        result.workbook_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=result.filename,
    )


@router.post("/native-summary")
async def build_native_summary(
    request: NativeWorkbookRequest,
    service: NativeNgramWorkbookService = Depends(_get_native_service),
    user=Depends(require_user),
):
    if request.date_from > request.date_to:
        raise HTTPException(status_code=400, detail="date_from must be on or before date_to")

    started = time.time()

    try:
        result = service.build_summary_from_search_term_facts(
            profile_id=request.profile_id,
            ad_product=request.ad_product,
            date_from=request.date_from,
            date_to=request.date_to,
            respect_legacy_exclusions=request.respect_legacy_exclusions,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to build native N-Gram summary") from exc

    usage_logger.log(
        {
            "user_id": user.get("sub"),
            "user_email": user.get("email"),
            "tool": "ngram",
            "action": "native_summary",
            "profile_id": request.profile_id,
            "ad_product": result.ad_product,
            "date_from": request.date_from.isoformat(),
            "date_to": request.date_to.isoformat(),
            "rows_processed": result.eligible_rows,
            "campaigns": result.campaigns_included,
            "campaigns_skipped": result.campaigns_skipped,
            "status": "success",
            "duration_ms": int((time.time() - started) * 1000),
            "app_version": settings.app_version,
        }
    )

    return {
        "ok": True,
        "summary": {
            "ad_product": result.ad_product,
            "profile_id": result.profile_id,
            "profile_display_name": result.profile_display_name,
            "marketplace_code": result.marketplace_code,
            "date_from": result.date_from,
            "date_to": result.date_to,
            "raw_rows": result.raw_rows,
            "eligible_rows": result.eligible_rows,
            "excluded_asin_rows": result.excluded_asin_rows,
            "excluded_incomplete_rows": result.excluded_incomplete_rows,
            "unique_campaigns": result.unique_campaigns,
            "unique_search_terms": result.unique_search_terms,
            "campaigns_included": result.campaigns_included,
            "campaigns_skipped": result.campaigns_skipped,
            "report_dates_present": result.report_dates_present,
            "coverage_start": result.coverage_start,
            "coverage_end": result.coverage_end,
            "imported_totals": {
                "impressions": result.imported_totals.impressions,
                "clicks": result.imported_totals.clicks,
                "spend": result.imported_totals.spend,
                "orders": result.imported_totals.orders,
                "sales": result.imported_totals.sales,
            },
            "workbook_input_totals": {
                "impressions": result.workbook_input_totals.impressions,
                "clicks": result.workbook_input_totals.clicks,
                "spend": result.workbook_input_totals.spend,
                "orders": result.workbook_input_totals.orders,
                "sales": result.workbook_input_totals.sales,
            },
            "warnings": result.warnings,
        },
    }


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

    per_campaign: dict[str, dict[str, list[str]]] = {}

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
        bucket = per_campaign.setdefault(
            str(campaign_name),
            {"ne": [], "mono": [], "bi": [], "tri": []},
        )
        last_ne_row = _last_non_empty(sheet, "AT", 2)
        last_mono_row = _last_non_empty(sheet, "K", 7)  # Monogram NE/NP column
        last_bi_row = _last_non_empty(sheet, "X", 7)   # Bigram NE/NP column
        last_tri_row = _last_non_empty(sheet, "AK", 7)  # Trigram NE/NP column
        # NE keywords from search term table (AN with AT = "NE")
        for i in range(2, last_ne_row + 1):
            flag = sheet[f"AT{i}"].value
            term = sheet[f"AN{i}"].value
            if (flag or "").strip().upper() == "NE" and term not in (None, ""):
                bucket["ne"].append(str(term))
        # Monogram/Bigram/Trigram NE/NP column flags
        for i in range(7, last_mono_row + 1):
            flag = sheet[f"K{i}"].value
            gram = sheet[f"A{i}"].value
            if (flag or "").strip().upper() in {"NE", "NP"} and gram not in (None, ""):
                bucket["mono"].append(str(gram))
        for i in range(7, last_bi_row + 1):
            flag = sheet[f"X{i}"].value
            gram = sheet[f"N{i}"].value
            if (flag or "").strip().upper() in {"NE", "NP"} and gram not in (None, ""):
                bucket["bi"].append(str(gram))
        for i in range(7, last_tri_row + 1):
            flag = sheet[f"AK{i}"].value
            gram = sheet[f"AA{i}"].value
            if (flag or "").strip().upper() in {"NE", "NP"} and gram not in (None, ""):
                bucket["tri"].append(str(gram))

    rows_out = [["Campaign", "NE Keywords", "Monogram", "Bigram", "Trigram"]]
    for campaign_name, data in per_campaign.items():
        if not (data["ne"] or data["mono"] or data["bi"] or data["tri"]):
            continue
        for ne, mono, bi, tri in itertools.zip_longest(
            data["ne"], data["mono"], data["bi"], data["tri"], fillvalue=""
        ):
            rows_out.append([campaign_name, ne, mono, bi, tri])

    if len(rows_out) == 1:
        raise HTTPException(status_code=400, detail="No NE or scratchpad entries found.")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as out_tmp:
        out_path = out_tmp.name

    workbook = xlsxwriter.Workbook(out_path)
    ws = workbook.add_worksheet("NE Summary")
    header_fmt = workbook.add_format(
        {"bold": True, "bg_color": "#0066CC", "font_color": "#FFFFFF", "border": 1, "align": "center", "valign": "vcenter"}
    )
    border_fmt = workbook.add_format({"border": 1})
    zebra_fmt = workbook.add_format({"bg_color": "#F2F2F2", "border": 1})

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
            "tool": "ngram",
            "action": "collect",
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

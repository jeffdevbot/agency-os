"""Root Keyword Analysis router."""
import os
import tempfile
import time
from datetime import datetime

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.responses import FileResponse

from ..auth import require_user
from ..config import settings
from ..usage_logging import usage_logger
from ..services.root import (
    read_campaign_report_path,
    calculate_week_buckets,
    aggregate_hierarchy,
    get_stats,
    build_root_workbook,
)

router = APIRouter(prefix="/root", tags=["root"])


@router.get("/healthz")
def health():
    """Health check endpoint."""
    return {"ok": True}


MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "40"))


@router.post("/process", response_class=FileResponse)
async def process_campaign_report(
    file: UploadFile = File(...),
    user=Depends(require_user),
):
    """
    Process Campaign Report and generate Root Keyword Analysis workbook.

    This is a single-step tool - no /collect endpoint needed.
    """
    started = time.time()
    total = 0
    chunk_size = 2 * 1024 * 1024  # 2MB chunks

    # Stream upload to temp file with size validation
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

    # Parse Campaign Report
    try:
        df, currency_symbol = read_campaign_report_path(tmp_path, file.filename)
    except ValueError as exc:
        os.unlink(tmp_path)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        os.unlink(tmp_path)
        raise HTTPException(status_code=400, detail=f"Parse error: {exc}") from exc

    os.unlink(tmp_path)

    rows_processed = len(df)

    # Calculate 4-week Sunday-Saturday buckets
    if df.empty or df["Time"].isna().all():
        raise HTTPException(status_code=400, detail="No valid date data in file")

    max_date = df["Time"].max()
    week_buckets = calculate_week_buckets(max_date)

    # Aggregate into hierarchical structure
    try:
        nodes = aggregate_hierarchy(df, week_buckets)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not nodes:
        raise HTTPException(status_code=400, detail="No data after aggregation")

    # Get statistics for logging
    stats = get_stats(nodes)

    # Build workbook
    try:
        workbook_path = build_root_workbook(nodes, week_buckets, currency_symbol)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Workbook generation failed: {exc}") from exc

    # Generate download filename
    dl_name = (
        os.path.splitext(file.filename)[0].replace(" ", "_")
        + "_root_keywords.xlsx"
    )

    # Calculate weeks covered for logging
    weeks_covered = [
        f"{bucket.start_label} - {bucket.end_label}"
        for bucket in week_buckets
    ]

    # Log usage
    usage_logger.log(
        {
            "user_id": user.get("sub"),
            "user_email": user.get("email"),
            "file_name": file.filename,
            "file_size_bytes": total,
            "rows_processed": rows_processed,
            "profiles_count": stats["profiles_count"],
            "portfolios_count": stats["portfolios_count"],
            "campaigns_parsed": stats["campaigns_parsed"],
            "status": "success",
            "duration_ms": int((time.time() - started) * 1000),
            "app_version": settings.app_version,
            "weeks_covered": weeks_covered,
            "generated_at": datetime.utcnow().isoformat(),
        }
    )

    return FileResponse(
        workbook_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=dl_name,
    )

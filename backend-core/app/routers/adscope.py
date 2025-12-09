"""AdScope audit router."""
import os
import tempfile
import time
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse

from ..auth import require_user
from ..config import settings
from ..usage_logging import usage_logger
from ..services.adscope import parse_str_file, parse_bulk_file, compute_all_views

import pandas as pd


router = APIRouter(prefix="/adscope", tags=["adscope"])


@router.get("/healthz")
def health():
    """Health check endpoint."""
    return {"ok": True}


MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "40"))
MEMORY_LIMIT_MB = 512


@router.post("/audit")
async def run_audit(
    bulk_file: UploadFile = File(...),
    str_file: UploadFile = File(...),
    brand_keywords: str = Form(default=""),
    user=Depends(require_user),
):
    """
    Run AdScope audit on Bulk + STR files.

    Returns JSON with all precomputed views.
    """
    started = time.time()
    bulk_size = 0
    str_size = 0
    chunk_size = 2 * 1024 * 1024  # 2MB chunks

    bulk_tmp_path = None
    str_tmp_path = None

    try:
        # Upload bulk file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
            bulk_tmp_path = tmp.name
            while True:
                chunk = await bulk_file.read(chunk_size)
                if not chunk:
                    break
                bulk_size += len(chunk)
                if bulk_size > MAX_UPLOAD_MB * 1024 * 1024:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Bulk file too large (max {MAX_UPLOAD_MB}MB)"
                    )
                tmp.write(chunk)
        await bulk_file.close()

        # Upload STR file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
            str_tmp_path = tmp.name
            while True:
                chunk = await str_file.read(chunk_size)
                if not chunk:
                    break
                str_size += len(chunk)
                if str_size > MAX_UPLOAD_MB * 1024 * 1024:
                    raise HTTPException(
                        status_code=413,
                        detail=f"STR file too large (max {MAX_UPLOAD_MB}MB)"
                    )
                tmp.write(chunk)
        await str_file.close()

        # Parse brand keywords
        brand_kw_list = [kw.strip() for kw in brand_keywords.split(",") if kw.strip()] if brand_keywords else []

        # Parse Bulk file
        try:
            bulk_excel = pd.ExcelFile(bulk_tmp_path)
            bulk_df, bulk_metadata = parse_bulk_file(bulk_excel)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Bulk file parse error: {exc}"
            ) from exc

        # Parse STR file
        try:
            # Try Excel first, fall back to CSV
            if str_file.filename.lower().endswith(('.xlsx', '.xls')):
                str_df_raw = pd.read_excel(str_tmp_path)
            else:
                str_df_raw = pd.read_csv(str_tmp_path)

            str_df, str_metadata = parse_str_file(str_df_raw, brand_kw_list)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail=f"STR file parse error: {exc}"
            ) from exc

        # Memory guard
        bulk_mem = bulk_df.memory_usage(deep=True).sum() / (1024 * 1024)  # MB
        str_mem = str_df.memory_usage(deep=True).sum() / (1024 * 1024)  # MB
        total_mem = bulk_mem + str_mem

        if total_mem > MEMORY_LIMIT_MB:
            raise HTTPException(
                status_code=413,
                detail=f"File too large in memory ({total_mem:.0f}MB > {MEMORY_LIMIT_MB}MB). "
                       f"Reduce date range to 30 days or less."
            )

        # Merge metadata
        metadata = {**bulk_metadata, **str_metadata}

        # Date range validation
        date_range_mismatch = False
        if "bulk_start_date" in metadata and "str_start_date" in metadata:
            bulk_start = metadata["bulk_start_date"]
            str_start = metadata["str_start_date"]
            bulk_end = metadata.get("bulk_end_date")
            str_end = metadata.get("str_end_date")

            if all(pd.notna(d) for d in [bulk_start, str_start, bulk_end, str_end]):
                # Check if ranges differ by more than 24 hours
                start_diff = abs((bulk_start - str_start).total_seconds())
                end_diff = abs((bulk_end - str_end).total_seconds())

                if start_diff > 86400 or end_diff > 86400:  # 24 hours in seconds
                    date_range_mismatch = True
                    if "warnings" not in metadata:
                        metadata["warnings"] = []
                    metadata["warnings"].append(
                        "File date ranges do not match. Analysis may be skewed."
                    )

        # Compute all views
        try:
            views = compute_all_views(bulk_df, str_df, metadata)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"View computation failed: {exc}"
            ) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"View computation failed: {exc}"
            ) from exc

        # Build response
        response = {
            "currency_code": metadata.get("currency_code", "USD"),
            "date_range_mismatch": date_range_mismatch,
            "warnings": metadata.get("warnings", []),
            "views": views,
        }

        # Log usage
        duration_ms = int((time.time() - started) * 1000)

        usage_logger.log(
            {
                "user_id": user.get("sub"),
                "user_email": user.get("email"),
                "tool": "adscope",
                "bulk_file_name": bulk_file.filename,
                "str_file_name": str_file.filename,
                "bulk_file_size_bytes": bulk_size,
                "str_file_size_bytes": str_size,
                "bulk_rows_processed": len(bulk_df),
                "str_rows_processed": len(str_df),
                "total_memory_mb": total_mem,
                "brand_keywords_count": len(brand_kw_list),
                "status": "success",
                "duration_ms": duration_ms,
                "app_version": settings.app_version,
                "generated_at": datetime.utcnow().isoformat(),
            }
        )

        return JSONResponse(content=response)

    except HTTPException:
        raise
    except Exception as exc:
        # Log error
        usage_logger.log(
            {
                "user_id": user.get("sub"),
                "user_email": user.get("email"),
                "tool": "adscope",
                "status": "error",
                "error": str(exc),
                "duration_ms": int((time.time() - started) * 1000),
                "app_version": settings.app_version,
                "generated_at": datetime.utcnow().isoformat(),
            }
        )
        raise HTTPException(status_code=500, detail=f"Audit failed: {exc}") from exc

    finally:
        # Clean up temp files
        if bulk_tmp_path and os.path.exists(bulk_tmp_path):
            try:
                os.unlink(bulk_tmp_path)
            except Exception:
                pass
        if str_tmp_path and os.path.exists(str_tmp_path):
            try:
                os.unlink(str_tmp_path)
            except Exception:
                pass

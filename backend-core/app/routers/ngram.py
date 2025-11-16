import os
import tempfile
import time

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.responses import FileResponse

from ..auth import require_user
from ..config import settings
from ..usage_logging import usage_logger
from ..services.ngram import (
    read_backview_path,
    build_ngram,
    derive_category,
    build_workbook,
)

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

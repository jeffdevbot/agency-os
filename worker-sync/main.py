from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from supabase import create_client

ROOT = Path(__file__).resolve().parents[1]
BACKEND_CORE = ROOT / "backend-core"
if str(BACKEND_CORE) not in sys.path:
    sys.path.insert(0, str(BACKEND_CORE))

from app.services.wbr.nightly_sync import WBRNightlySyncService  # noqa: E402


def _env_int(name: str, default: int, *, minimum: int | None = None) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError:
        value = default
    if minimum is not None:
        value = max(value, minimum)
    return value


def _create_supabase_client():
    url = os.getenv("SUPABASE_URL", "").strip()
    key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE") or "").strip()
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be configured for worker-sync")
    return create_client(url, key)


async def _run_forever() -> None:
    poll_seconds = _env_int("WBR_WORKER_POLL_SECONDS", 60, minimum=30)
    timezone_name = os.getenv("WBR_WORKER_TIMEZONE", "America/Toronto").strip() or "America/Toronto"
    run_hour = _env_int("WBR_WORKER_RUN_HOUR", 2)
    run_minute = _env_int("WBR_WORKER_RUN_MINUTE", 0)
    worker_user_id = os.getenv("WBR_WORKER_USER_ID", "").strip() or None

    db = _create_supabase_client()
    service = WBRNightlySyncService(
        db,
        timezone_name=timezone_name,
        run_hour=run_hour,
        run_minute=run_minute,
        worker_user_id=worker_user_id,
    )

    print(
        f"[worker-sync] starting WBR nightly sync loop "
        f"(tz={timezone_name}, run_at={run_hour:02d}:{run_minute:02d}, poll={poll_seconds}s)"
    )

    while True:
        try:
            summary = await service.run_pending()
            print(f"[worker-sync] {summary}")
        except Exception as exc:  # noqa: BLE001
            print(f"[worker-sync] error: {exc}")
        await asyncio.sleep(poll_seconds)


def main() -> None:
    asyncio.run(_run_forever())


if __name__ == "__main__":
    main()

import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import httpx



from supabase import Client

class SlackError(Exception):
    pass


class SlackConfigurationError(SlackError):
    pass


class SlackAuthError(SlackError):
    pass


class SlackAPIError(SlackError):
    pass


class SlackReceiptService:
    def __init__(self, db: Client):
        self.db = db

    def attempt_insert_dedupe(
        self,
        *,
        event_key: str,
        event_source: str,
        slack_event_id: str = "",
        event_type: str = "",
        payload: dict[str, Any] | None = None,
    ) -> bool:
        """
        Attempt to insert a new receipt record atomically.
        Returns True if new (inserted), False if already exists (duplicate).
        """
        row = {
            "event_key": event_key,
            "event_source": event_source,
            "slack_event_id": slack_event_id,
            "event_type": event_type,
            "request_payload": payload or {},
            "status": "processing",
        }
        try:
            # Supabase/PostgREST 'ignore_duplicates' behavior on insert is usually achieved 
            # by `on_conflict` arg in newer SDKs, or checking exception.
            # Using count='exact' to see if rows were inserted. 
            # Note: supabase-py v2 `upsert` with ignore_duplicates might be safer via `on_conflict`? 
            # But here we want INSERT ... ON CONFLICT DO NOTHING.
            # Since strict 'do nothing' via pure SDK can be tricky, we'll try insert and catch error 
            # OR use upsert with `on_conflict="event_key"` and `ignore_duplicates=True`.
            
            res = self.db.table("slack_event_receipts").upsert(
                row, on_conflict="event_key", ignore_duplicates=True
            ).execute()
            
            # If ignore_duplicates=True, effective response data is [] if conflict occurred (no insert),
            # or data=[row] if inserted.
            if not res.data:
                return False
            return True
        except Exception:
            # Fallback for older SDKs or unexpected constraint errors
            return False

    def update_status(self, event_key: str, status: str, payload: dict[str, Any] | None = None) -> None:
        """Update receipt status (e.g., processed, failed)."""
        # Keep status values aligned with DB constraint:
        # ('processing', 'processed', 'ignored', 'failed', 'duplicate')
        if status not in {"processing", "processed", "ignored", "failed", "duplicate"}:
            status = "failed"

        updates: dict[str, Any] = {"status": status}
        if status in {"processed", "ignored", "failed", "duplicate"}:
            updates["processed_at"] = datetime.now(timezone.utc).isoformat()
        if payload is not None:
            updates["response_payload"] = payload
        
        try:
            self.db.table("slack_event_receipts").update(updates).eq("event_key", event_key).execute()
        except Exception:
            pass



def verify_slack_signature(
    signing_secret: str,
    timestamp: str,
    body: bytes,
    signature: str,
) -> bool:
    """
    Verify request came from Slack.

    Slack signs requests using:
      basestring = "v0:{timestamp}:{raw_body}"
      signature = "v0=" + HMAC_SHA256(signing_secret, basestring).hexdigest()
    """
    signing_secret = (signing_secret or "").strip()
    if not signing_secret:
        return False

    try:
        ts = int(timestamp)
    except (TypeError, ValueError):
        return False

    # Reject requests older than 5 minutes (replay protection)
    if abs(time.time() - ts) > 60 * 5:
        return False

    if not signature or not signature.startswith("v0="):
        return False

    try:
        body_str = body.decode("utf-8")
    except UnicodeDecodeError:
        return False

    sig_basestring = f"v0:{timestamp}:{body_str}"
    digest = hmac.new(
        signing_secret.encode("utf-8"),
        sig_basestring.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    expected = f"v0={digest}"
    return hmac.compare_digest(expected, signature)


@dataclass(frozen=True)
class SlackMessageResponse:
    ok: bool
    ts: Optional[str] = None
    channel: Optional[str] = None
    raw: Optional[dict[str, Any]] = None


class SlackService:
    def __init__(self, bot_token: str) -> None:
        self.bot_token = (bot_token or "").strip()
        if not self.bot_token:
            raise SlackConfigurationError("SLACK_BOT_TOKEN not set")

        self._client = httpx.AsyncClient(
            base_url="https://slack.com/api",
            headers={"Authorization": f"Bearer {self.bot_token}"},
            timeout=httpx.Timeout(10.0),
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def post_message(
        self,
        *,
        channel: str,
        text: str,
        blocks: Optional[list[dict[str, Any]]] = None,
    ) -> SlackMessageResponse:
        channel = (channel or "").strip()
        if not channel:
            raise SlackAPIError("Slack post_message missing channel")

        payload: dict[str, Any] = {"channel": channel, "text": text}
        if blocks:
            payload["blocks"] = blocks

        response = await self._client.post(
            "/chat.postMessage",
            json=payload,
        )

        if response.status_code == 401:
            raise SlackAuthError("Slack auth failed (401). Check SLACK_BOT_TOKEN.")

        if response.status_code < 200 or response.status_code >= 300:
            raise SlackAPIError(f"Slack API error ({response.status_code}): {response.text}")

        try:
            data = response.json()
        except json.JSONDecodeError as exc:
            raise SlackAPIError(f"Slack API returned invalid JSON: {exc}") from exc

        if not data.get("ok"):
            error = data.get("error")
            raise SlackAPIError(f"Slack API error: {error or 'unknown_error'}")

        return SlackMessageResponse(
            ok=True,
            ts=str(data.get("ts")) if data.get("ts") else None,
            channel=str(data.get("channel")) if data.get("channel") else None,
            raw=data,
        )

    async def update_message(
        self,
        *,
        channel: str,
        ts: str,
        text: str,
        blocks: Optional[list[dict[str, Any]]] = None,
    ) -> SlackMessageResponse:
        channel = (channel or "").strip()
        ts = (ts or "").strip()
        if not channel or not ts:
            raise SlackAPIError("Slack update_message missing channel/ts")

        payload: dict[str, Any] = {"channel": channel, "ts": ts, "text": text}
        if blocks:
            payload["blocks"] = blocks

        response = await self._client.post("/chat.update", json=payload)
        if response.status_code == 401:
            raise SlackAuthError("Slack auth failed (401). Check SLACK_BOT_TOKEN.")
        if response.status_code < 200 or response.status_code >= 300:
            raise SlackAPIError(f"Slack API error ({response.status_code}): {response.text}")

        try:
            data = response.json()
        except json.JSONDecodeError as exc:
            raise SlackAPIError(f"Slack API returned invalid JSON: {exc}") from exc

        if not data.get("ok"):
            error = data.get("error")
            raise SlackAPIError(f"Slack API error: {error or 'unknown_error'}")

        return SlackMessageResponse(
            ok=True,
            ts=str(data.get("ts")) if data.get("ts") else None,
            channel=str(data.get("channel")) if data.get("channel") else None,
            raw=data,
        )


def get_slack_signing_secret() -> str:
    return os.environ.get("SLACK_SIGNING_SECRET", "")


def get_slack_service() -> SlackService:
    return SlackService(bot_token=os.environ.get("SLACK_BOT_TOKEN", ""))

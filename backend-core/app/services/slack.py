import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from typing import Any, Optional

import httpx


class SlackError(Exception):
    pass


class SlackConfigurationError(SlackError):
    pass


class SlackAuthError(SlackError):
    pass


class SlackAPIError(SlackError):
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

    async def post_message(self, *, channel: str, text: str) -> SlackMessageResponse:
        channel = (channel or "").strip()
        if not channel:
            raise SlackAPIError("Slack post_message missing channel")

        response = await self._client.post(
            "/chat.postMessage",
            json={"channel": channel, "text": text},
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


def get_slack_signing_secret() -> str:
    return os.environ.get("SLACK_SIGNING_SECRET", "")


def get_slack_service() -> SlackService:
    return SlackService(bot_token=os.environ.get("SLACK_BOT_TOKEN", ""))

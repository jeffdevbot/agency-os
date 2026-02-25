"""Pure helper functions for The Claw Slack route handling."""

from __future__ import annotations

import json
from urllib.parse import parse_qs

from fastapi import HTTPException, Request

from ..slack import verify_slack_signature


def parse_json_payload(body: bytes) -> dict:
    try:
        value = json.loads(body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    return value


def verify_request_or_401(*, signing_secret: str, request: Request, body: bytes) -> None:
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")
    if not verify_slack_signature(signing_secret, timestamp, body, signature):
        raise HTTPException(status_code=401, detail="Invalid Slack signature")


def parse_interaction_payload(raw_body: bytes) -> dict:
    try:
        form = parse_qs(raw_body.decode("utf-8"), keep_blank_values=True)
    except UnicodeDecodeError:
        return {}

    payload_str = (form.get("payload") or [""])[0]
    if not payload_str:
        return {}

    try:
        payload = json.loads(payload_str)
    except json.JSONDecodeError:
        return {}

    return payload if isinstance(payload, dict) else {}

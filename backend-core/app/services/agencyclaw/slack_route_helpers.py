"""Shared pure/request helpers for Slack route wiring."""

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


def build_client_picker_blocks(clients: list[dict]) -> list[dict]:
    top = clients[:10]
    blocks: list[dict] = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "Which client are you working on today?"},
        }
    ]

    for i in range(0, len(top), 5):
        chunk = top[i : i + 5]
        blocks.append(
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": str(client.get("name", "Client"))},
                        "action_id": f"select_client_{client.get('id')}",
                        "value": str(client.get("id")),
                    }
                    for client in chunk
                ],
            }
        )

    return blocks


def build_brand_picker_blocks(brands: list[dict], client_name: str) -> list[dict]:
    top = brands[:10]
    blocks: list[dict] = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"Which brand under *{client_name}*?"},
        }
    ]
    for i in range(0, len(top), 5):
        chunk = top[i : i + 5]
        blocks.append(
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": str(b.get("name", "Brand"))},
                        "action_id": f"select_brand_{b.get('id')}",
                        "value": str(b.get("id")),
                    }
                    for b in chunk
                ],
            }
        )
    return blocks


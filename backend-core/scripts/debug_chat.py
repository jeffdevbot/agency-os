#!/usr/bin/env python3
"""Terminal REPL for testing AgencyClaw against a deployed instance.

Usage:
    export DEBUG_CHAT_TOKEN="your-token-here"
    python backend-core/scripts/debug_chat.py https://your-app.onrender.com

    # Or with a custom user ID:
    python backend-core/scripts/debug_chat.py https://your-app.onrender.com --user U_CUSTOM_ID
"""

from __future__ import annotations

import argparse
import os
import sys

import requests


def main() -> None:
    parser = argparse.ArgumentParser(description="AgencyClaw debug chat REPL")
    parser.add_argument("base_url", help="Deployed backend URL (e.g. https://your-app.onrender.com)")
    parser.add_argument("--user", default="U_DEBUG_TERMINAL", help="User ID for the session")
    parser.add_argument("--token", default=None, help="Debug chat token (or set DEBUG_CHAT_TOKEN env var)")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    token = args.token or os.environ.get("DEBUG_CHAT_TOKEN", "")
    user_id = args.user

    if not token:
        print("Error: Set DEBUG_CHAT_TOKEN env var or pass --token", file=sys.stderr)
        sys.exit(1)

    endpoint = f"{base_url}/api/slack/debug/chat"
    headers = {"X-Debug-Token": token, "Content-Type": "application/json"}

    print(f"Connected to {base_url}")
    print(f"Session user: {user_id}")
    print("Type messages to send to AgencyClaw. Ctrl+C to quit.\n")

    try:
        while True:
            try:
                text = input("you> ").strip()
            except EOFError:
                break
            if not text:
                continue

            try:
                resp = requests.post(
                    endpoint,
                    json={"text": text, "user_id": user_id},
                    headers=headers,
                    timeout=60,
                )
            except requests.ConnectionError:
                print(f"  [error] Could not connect to {base_url}")
                continue
            except requests.Timeout:
                print("  [error] Request timed out (60s)")
                continue

            if resp.status_code == 404:
                print("  [error] Debug chat not enabled on this instance")
                print("  Set AGENCYCLAW_DEBUG_CHAT_ENABLED=true on the server")
                sys.exit(1)
            if resp.status_code == 401:
                print("  [error] Invalid debug token")
                sys.exit(1)
            if resp.status_code != 200:
                print(f"  [error] HTTP {resp.status_code}: {resp.text}")
                continue

            data = resp.json()
            messages = data.get("messages", [])
            if not messages:
                print("  [no response]")
            for msg in messages:
                text_out = msg.get("text", "")
                prefix = "claw (update)>" if msg.get("update") else "claw>"
                print(f"{prefix} {text_out}\n")

    except KeyboardInterrupt:
        print("\nBye!")


if __name__ == "__main__":
    main()

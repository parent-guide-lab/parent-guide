#!/usr/bin/env python3
"""Send the daily tip card to Feishu as an interactive card via webhook.

Adapted from lose-fat-zyc/skills/daily-tips/feishu_card.py (2026-10-20),
simplified for parent-guide's single-card tip format: title from the `#`
heading becomes the card header, the rest becomes one lark_md element.
Webhook URL is read lazily at send time so --dry-run (and tests) work
without local config.

Usage:
  feishu-tip.py <md_file> [--title TITLE] [--dry-run]

Exit code: nonzero on failure (caller decides whether to block; the daily
flow treats push failure as non-blocking -- tip was already delivered).
"""
import argparse
import json
import os
import re
import sys
import urllib.request

WEBHOOK_FILE = os.path.expanduser("~/.config/feishu/webhook_url")
HEADER_COLOR = "blue"


def load_webhook():
    try:
        with open(WEBHOOK_FILE) as f:
            return f.read().strip()
    except FileNotFoundError:
        sys.exit(f"FAIL: feishu webhook config missing: {WEBHOOK_FILE}")


def send_card(title, md_content, dry_run=False):
    body = re.sub(r"^#\s+.*\n", "", md_content).strip()
    card = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": title},
                "template": HEADER_COLOR,
            },
            "elements": [{"tag": "markdown", "content": body}] if body else [],
        },
    }
    payload = json.dumps(card, ensure_ascii=False).encode("utf-8")
    if dry_run:
        print(json.dumps(card, ensure_ascii=False, indent=2))
        return {"ok": True, "mode": "dry_run"}
    req = urllib.request.Request(
        load_webhook(), data=payload, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    ap = argparse.ArgumentParser(description="Send daily tip card to Feishu")
    ap.add_argument("file", help="Markdown file of the tip card")
    ap.add_argument("--title", default=None,
                    help="Card title (default: first # heading, else 今日贴士)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print card JSON without sending (no webhook needed)")
    args = ap.parse_args()

    with open(args.file, encoding="utf-8") as f:
        content = f.read()
    title = args.title
    if not title:
        m = re.match(r"^#\s+(.+)", content)
        title = m.group(1).strip() if m else "今日贴士"
    result = send_card(title, content, dry_run=args.dry_run)
    print(json.dumps(result, ensure_ascii=False))
    if not args.dry_run and result.get("code") not in (None, 0):
        sys.exit(f"FAIL: feishu rejected: {result}")


if __name__ == "__main__":
    main()

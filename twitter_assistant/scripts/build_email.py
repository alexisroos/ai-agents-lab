#!/usr/bin/env python3
"""Render the daily digest email from the template + report data."""

from __future__ import annotations

import argparse
import json
import re
import textwrap
from datetime import datetime
from pathlib import Path
from typing import List


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build digest email body from report + template")
    parser.add_argument("date", help="Target date (YYYY-MM-DD)")
    parser.add_argument(
        "--workspace",
        default=Path("twitter_assistant"),
        type=Path,
        help="Workspace root containing reports/, templates/, config/",
    )
    return parser.parse_args()


def friendly_date(date_str: str) -> str:
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return dt.strftime("%A, %B %d, %Y").replace(" 0", " ")


def load_json(path: Path):
    with path.open() as f:
        return json.load(f)


def extract_summary_block(report_path: Path) -> str:
    text = report_path.read_text()
    lines = text.splitlines()
    start = None
    end = None
    for idx, line in enumerate(lines):
        if line.strip() == "## Summaries":
            start = idx + 1
        elif line.strip().startswith("## Raw Feed") and start is not None:
            end = idx
            break
    if start is None:
        return "- _No summaries added yet._"
    snippet = lines[start:end] if end is not None else lines[start:]
    snippet = "\n".join(line.rstrip() for line in snippet).strip()
    return snippet or "- _No summaries added yet._"


def extract_tweet_body(text: str, handle: str) -> str:
    """Strip accessibility-tree prefix (Name Verified account @handle TIMESTAMP)
    and trailing engagement stats from full_text."""
    # Remove prefix up through the timestamp after @handle
    prefix_re = re.compile(
        r'^.*?@' + re.escape(handle) +
        r'\s+(?:\d+\s+(?:minutes?|hours?|days?)\s+ago'
        r'|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d+'
        r'|\d+[mhd])\s+',
        re.IGNORECASE
    )
    body = prefix_re.sub('', text, count=1)
    # Remove trailing engagement stats: "N replies, N reposts, N likes..."
    body = re.sub(r'\s*\d[\d,]*\s+repl(?:y|ies).*$', '', body, flags=re.IGNORECASE | re.DOTALL)
    # Remove trailing media noise like "Embedded video", "Image", "Play Video"
    body = re.sub(r'\s*(Embedded video[^"]*|Image|Play Video)\s*$', '', body, flags=re.IGNORECASE)
    return body.strip() or text.strip()


def build_top_block(top_tweets: List[dict]) -> str:
    blocks = []
    for item in top_tweets:
        body = extract_tweet_body(item['text'], item['author_handle'])
        # Wrap body at 80 chars for readable email lines
        wrapped = textwrap.fill(body, width=80)
        block = (
            f"**@{item['author_handle']}**  "
            f"💬 {item['replies']:,} · 🔁 {item['reposts']:,} · ❤️ {item['likes']:,}  "
            f"_{item['posted_pt']}_\n"
            f"{wrapped}\n"
            f"{item['permalink']}"
        )
        blocks.append(block)
    return "\n\n".join(blocks)


def main() -> None:
    args = parse_args()
    workspace = args.workspace
    date = args.date

    template_path = workspace / "templates" / "email.md"
    template = template_path.read_text()

    settings_path = workspace / "config" / "settings.json"
    settings = load_json(settings_path)

    top_path = workspace / "reports" / f"{date}-top.json"
    report_path = workspace / "reports" / f"{date}.md"
    email_path = workspace / "reports" / f"{date}-email.txt"

    top_data = load_json(top_path)
    top_block = build_top_block(top_data["top_tweets"])
    summary_block = extract_summary_block(report_path)

    friendly = friendly_date(date)
    subject = f"{settings['subject_prefix']} – {friendly}"

    body = (
        template
        .replace("{{subject}}", subject)
        .replace("{{recipient_name}}", settings.get("recipient_name", "there"))
        .replace("{{date}}", friendly)
        .replace("{{top_tweets}}", top_block)
        .replace("{{link_summaries}}", summary_block)
    )

    email_path.write_text(body)
    print(f"Email body written to {email_path}")


if __name__ == "__main__":
    main()

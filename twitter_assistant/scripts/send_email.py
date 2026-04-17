#!/usr/bin/env python3
"""Send the compiled digest email via gog, using config/settings.json."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path


def friendly_date(date_str: str) -> str:
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return dt.strftime("%A, %B %d, %Y").replace(" 0", " ")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send digest email via gog gmail send")
    parser.add_argument("date", help="Target date (YYYY-MM-DD)")
    parser.add_argument(
        "--workspace",
        default=Path("twitter_assistant"),
        type=Path,
        help="Workspace root containing config/ and reports/",
    )
    parser.add_argument(
        "--subject-suffix",
        default="",
        help="Optional text appended to the computed subject (e.g., '(Tech Filter)')",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the gog command instead of executing it",
    )
    return parser.parse_args()


def load_json(path: Path):
    with path.open() as f:
        return json.load(f)


def main() -> None:
    args = parse_args()
    workspace = args.workspace
    settings = load_json(workspace / "config" / "settings.json")
    template_subject = f"{settings['subject_prefix']} – {friendly_date(args.date)}"
    subject = template_subject + (f" {args.subject_suffix}" if args.subject_suffix else "")

    email_path = workspace / "reports" / f"{args.date}-email.txt"
    if not email_path.exists():
        raise SystemExit(f"Email file not found: {email_path}. Run build_email.py first.")

    cmd = [
        "gog",
        "gmail",
        "send",
        "--account",
        settings["gmail_account"],
        "--to",
        settings["digest_recipient"],
        "--subject",
        subject,
        "--body-file",
        str(email_path),
    ]

    if args.dry_run:
        print("Dry run:", " ".join(cmd))
        return

    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()

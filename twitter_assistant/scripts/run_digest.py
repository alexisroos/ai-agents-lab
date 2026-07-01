#!/usr/bin/env python3
"""Build Twitter digest artifacts (report + top JSON) with optional topic filters."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any, Dict, List

PT = ZoneInfo("America/Los_Angeles")


def load_json(path: Path) -> Any:
    with path.open() as f:
        return json.load(f)


def load_filter_config(path: Path | None) -> Dict[str, Any]:
    template = {
        "blocked_keywords": [],
        "blocked_handles": [],
        "allowed_keywords": [],
        "allowed_handles": [],
        "require_allowed_keyword": False,
    }
    if path is None or not path.exists():
        return template
    data = load_json(path)
    template.update({k: data.get(k, template[k]) for k in template})
    # Normalize to lowercase for comparisons.
    template["blocked_keywords"] = [kw.lower() for kw in template["blocked_keywords"]]
    template["blocked_handles"] = [h.lower() for h in template["blocked_handles"]]
    template["allowed_keywords"] = [kw.lower() for kw in template["allowed_keywords"]]
    template["allowed_handles"] = [h.lower() for h in template["allowed_handles"]]
    template["require_allowed_keyword"] = bool(template["require_allowed_keyword"])
    return template


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate digest artifacts from a capture file.")
    parser.add_argument("date", help="Target date (YYYY-MM-DD)")
    parser.add_argument(
        "--workspace",
        default=Path("twitter_assistant"),
        type=Path,
        help="Workspace root containing captures/, reports/, templates/, etc.",
    )
    parser.add_argument(
        "--filter-config",
        default=None,
        type=Path,
        help="Optional path to filters JSON (defaults to workspace/config/filters.json if present).",
    )
    return parser.parse_args()


def parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def clean_text(text: str) -> str:
    return text.replace("\r", "").replace("\n", "  ").strip()


def format_metrics(tweet: Dict[str, Any]) -> str:
    return f"(💬 {tweet.get('replies', 0):,} · 🔁 {tweet.get('reposts', 0):,} · ❤️ {tweet.get('likes', 0):,})"


def should_drop(tweet: Dict[str, Any], config: Dict[str, Any], stats: Dict[str, int]) -> bool:
    text_parts = [tweet.get("full_text", ""), tweet.get("author_name", ""), tweet.get("author_handle", "")]
    for url in tweet.get("urls", []) or []:
        text_parts.append(url.get("display", ""))
        text_parts.append(url.get("expanded_url", ""))
    haystack = " ".join(text_parts).lower()
    handle = (tweet.get("author_handle") or "").lower()

    if handle in config["blocked_handles"]:
        stats["blocked_handle"] += 1
        return True
    if any(kw and kw in haystack for kw in config["blocked_keywords"]):
        stats["blocked_keyword"] += 1
        return True

    require_allowed = config.get("require_allowed_keyword", False)
    if not config["allowed_keywords"] and not config["allowed_handles"]:
        require_allowed = False

    if require_allowed:
        allowed = False
        if handle in config["allowed_handles"]:
            allowed = True
        elif any(kw and kw in haystack for kw in config["allowed_keywords"]):
            allowed = True
        if not allowed:
            stats["allowed_miss"] += 1
            return True
    return False


def main() -> None:
    args = parse_args()
    target_date = args.date
    workspace = args.workspace
    capture_path = workspace / "captures" / f"{target_date}.json"
    meta_path = workspace / "captures" / f"{target_date}.meta.json"
    report_path = workspace / "reports" / f"{target_date}.md"
    top_path = workspace / "reports" / f"{target_date}-top.json"

    if not capture_path.exists():
        raise SystemExit(f"Capture file not found: {capture_path}")

    if args.filter_config:
        filter_config_path = args.filter_config
    else:
        filter_config_path = workspace / "config" / "filters.json"
    filter_config = load_filter_config(filter_config_path if filter_config_path and filter_config_path.exists() else None)

    tweets = load_json(capture_path)
    meta = load_json(meta_path) if meta_path.exists() else {}

    for tweet in tweets:
        ts = parse_ts(tweet["timestamp_iso"])
        tweet["_dt_pt"] = ts.astimezone(PT)
        tweet["score"] = tweet.get("replies", 0) * 3 + tweet.get("reposts", 0) * 2 + tweet.get("likes", 0)

    filter_stats = {"blocked_keyword": 0, "blocked_handle": 0, "allowed_miss": 0}
    filtered_tweets: List[Dict[str, Any]] = []
    for tweet in tweets:
        if should_drop(tweet, filter_config, filter_stats):
            continue
        filtered_tweets.append(tweet)

    if not filtered_tweets:
        raise SystemExit("All tweets were filtered out; adjust your filters.")

    # Sorts
    filtered_tweets.sort(key=lambda t: (t["score"], t["_dt_pt"]), reverse=True)

    # Limit Elon Musk to his single top tweet
    elon_handle = "elonmusk"
    elon_tweets = [t for t in filtered_tweets if (t.get("author_handle") or "").lower() == elon_handle]
    other_tweets = [t for t in filtered_tweets if (t.get("author_handle") or "").lower() != elon_handle]
    if elon_tweets:
        top_elon = [elon_tweets[0]]
        remaining_slots = 9
        top_tweets = top_elon + other_tweets[:remaining_slots]
    else:
        top_tweets = other_tweets[:10]

    # Ensure we still have up to 10 and re-sort by original score for display stability
    top_tweets.sort(key=lambda t: (t["score"], t["_dt_pt"]), reverse=True)
    raw_feed = sorted(filtered_tweets, key=lambda t: t["_dt_pt"])

    captured_at = meta.get("collected_at")
    captured_at_pt = parse_ts(captured_at).astimezone(PT) if captured_at else None
    now_pt = datetime.now(PT)

    lines: List[str] = []
    lines.append(f"# Twitter Digest — {target_date}")
    lines.append("")
    if captured_at_pt:
        lines.append(f"Captured at: {captured_at_pt.strftime('%Y-%m-%d %I:%M %p PDT')}")
    if meta:
        lines.append(
            f"Scrolled: {meta.get('tweets_scrolled', 'n/a')} | In window: {meta.get('tweets_in_window', 'n/a')} | "
            f"Skipped (GenAI): {meta.get('tweets_skipped_genai', 'n/a')} | Saved: {meta.get('tweets_found', 'n/a')} | "
            f"Scroll passes: {meta.get('scroll_passes', 'n/a')}"
        )
    lines.append(f"Report generated: {now_pt.strftime('%Y-%m-%d %I:%M %p PDT')}")
    filtered_total = sum(filter_stats.values())
    lines.append(
        "Kept after filters: {kept} | Filtered out: {removed} "
        "(keywords: {kw}, handles: {handles}, non-tech: {allowed})".format(
            kept=len(filtered_tweets),
            removed=filtered_total,
            kw=filter_stats["blocked_keyword"],
            handles=filter_stats["blocked_handle"],
            allowed=filter_stats["allowed_miss"],
        )
    )
    lines.append("")
    lines.append("## Top Tweets")
    lines.append("")
    for idx, tweet in enumerate(top_tweets, start=1):
        lines.append(f"{idx}. **{tweet['author_name']} ({tweet['author_handle']})** — {clean_text(tweet['full_text'])}")
        lines.append(f"   - Score: {tweet['score']:,} {format_metrics(tweet)}")
        lines.append(f"   - Posted: {tweet['_dt_pt'].strftime('%Y-%m-%d %I:%M %p PDT')}")
        lines.append(f"   - Link: {tweet['permalink']}")
        lines.append("")

    lines.append("## Summaries")
    lines.append("")
    lines.append("_(Add link summaries here.)_")
    lines.append("")
    lines.append("## Raw Feed")
    lines.append("")
    for tweet in raw_feed:
        lines.append(
            f"- {tweet['_dt_pt'].strftime('%Y-%m-%d %I:%M %p PDT')} — **{tweet['author_handle']}**: "
            f"{clean_text(tweet['full_text'])} ({tweet['permalink']})"
        )

    report_path.write_text("\n".join(lines))

    top_payload = {
        "date": target_date,
        "generated_pt": now_pt.isoformat(),
        "filter_stats": filter_stats,
        "kept": len(filtered_tweets),
        "top_tweets": [
            {
                "rank": idx,
                "author_handle": tweet["author_handle"],
                "author_name": tweet["author_name"],
                "text": clean_text(tweet["full_text"]),
                "score": tweet["score"],
                "replies": tweet.get("replies", 0),
                "reposts": tweet.get("reposts", 0),
                "likes": tweet.get("likes", 0),
                "posted_pt": tweet["_dt_pt"].strftime("%Y-%m-%d %I:%M %p PDT"),
                "permalink": tweet["permalink"],
                "urls": tweet.get("urls", []),
                "photo_urls": tweet.get("photo_urls", []),
            }
            for idx, tweet in enumerate(top_tweets, start=1)
        ],
    }
    top_path.write_text(json.dumps(top_payload, indent=2))

    print(f"Report written to {report_path}")
    print(f"Top list written to {top_path}")
    print(
        f"Kept {len(filtered_tweets)} tweets (filtered out {filtered_total}). "
        f"Top sample: {[t['author_handle'] for t in top_tweets]}"
    )


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Twitter Following feed capture script.
Scrolls the browser, takes snapshots, parses tweets deterministically.
No LLM loop needed — shell executes the scroll, Python parses the output.
"""
import subprocess, re, json, sys, time
from datetime import datetime, timezone
import zoneinfo

PT = zoneinfo.ZoneInfo("America/Los_Angeles")
NOW = datetime.now(PT)
YESTERDAY = NOW.date().replace(day=NOW.day - 1) if NOW.day > 1 else None

WS = "/Users/alx6/.openclaw/workspace/twitter_assistant"
DATE_STR = (NOW.date().isoformat() if NOW.hour < 6
            else datetime(NOW.year, NOW.month, NOW.day, tzinfo=PT).date().isoformat())

# "yesterday" = today minus 1 day
import datetime as dt
yesterday = (dt.date.today() - dt.timedelta(days=1))
DATE_STR = yesterday.isoformat()

OUT_JSON = f"{WS}/captures/{DATE_STR}.json"
OUT_META = f"{WS}/captures/{DATE_STR}.meta.json"


def run(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout


def snapshot():
    return run(["openclaw", "browser", "snapshot"])


def press_pagedown():
    run(["openclaw", "browser", "press", "PageDown"])


def wait_ms(ms):
    time.sleep(ms / 1000)


def setup_browser():
    """Focus existing Twitter tab or navigate to it."""
    tabs_out = run(["openclaw", "browser", "tabs", "--json"])
    try:
        tabs = json.loads(tabs_out)
        for tab in tabs:
            url = tab.get("url", "")
            if "x.com" in url or "twitter.com" in url:
                run(["openclaw", "browser", "focus", tab["id"]])
                print(f"Focused existing tab: {url}", flush=True)
                return
    except Exception:
        pass
    run(["openclaw", "browser", "navigate", "https://x.com/home"])
    print("Navigated to x.com/home", flush=True)
    wait_ms(3000)


def click_following_tab(snap_text):
    """Find and click the Following tab."""
    m = re.search(r'tab "Following"[^[]*\[ref=(e\d+)\]', snap_text)
    if m:
        run(["openclaw", "browser", "click", m.group(1)])
        print("Clicked Following tab", flush=True)
        wait_ms(2000)
        return True
    return False


def parse_tweets(snap_text):
    """
    Extract tweets from a full accessibility-tree snapshot.
    Returns list of dicts.
    """
    tweets = []

    # Each tweet is an <article> element whose label contains the full text.
    # Pattern: - article "CONTENT" [ref=eN]:
    #   (followed by nested elements including timestamp link with /status/ URL)
    article_re = re.compile(
        r'- article "(.*?)" \[ref=(e\d+)\]',
        re.DOTALL
    )
    # Engagement buttons inside an article block
    replies_re  = re.compile(r'(\d[\d,.]*[KMBkmb]?) Repl')
    reposts_re  = re.compile(r'(\d[\d,.]*[KMBkmb]?) repost')
    likes_re    = re.compile(r'(\d[\d,.]*[KMBkmb]?) Like')
    views_re    = re.compile(r'(\d[\d,.]*[KMBkmb]?) view')
    bookmarks_re= re.compile(r'(\d[\d,.]*[KMBkmb]?) [Bb]ookmark')
    # Timestamp link that contains /status/ URL
    ts_link_re  = re.compile(
        r'link "([^"]+)" \[ref=(e\d+)\][^\n]*\n\s*- /url: (/(\w+)/status/(\d+))(?![/\d])'
    )

    # Find all article positions
    article_matches = list(article_re.finditer(snap_text))

    for i, am in enumerate(article_matches):
        # Slice of snapshot from this article to the next (or end)
        start = am.start()
        end = article_matches[i + 1].start() if i + 1 < len(article_matches) else len(snap_text)
        block = snap_text[start:end]

        full_text = am.group(1).strip()
        # Skip empty or UI articles
        if len(full_text) < 10:
            continue

        # Find the status URL for permalink + timestamp
        ts_match = ts_link_re.search(block)
        if not ts_match:
            continue
        raw_timestamp = ts_match.group(1).strip()
        permalink = "https://x.com" + ts_match.group(3)
        author_handle = ts_match.group(4)
        tweet_id = ts_match.group(5)

        def parse_num(m):
            if not m:
                return 0
            s = m.group(1).replace(",", "")
            mult = {"k": 1000, "m": 1_000_000, "b": 1_000_000_000}
            if s[-1].lower() in mult:
                return int(float(s[:-1]) * mult[s[-1].lower()])
            try:
                return int(s)
            except ValueError:
                return 0

        tweet = {
            "tweet_id": tweet_id,
            "author_handle": author_handle,
            "raw_timestamp": raw_timestamp,
            "full_text": full_text,
            "replies":   parse_num(replies_re.search(block)),
            "reposts":   parse_num(reposts_re.search(block)),
            "likes":     parse_num(likes_re.search(block)),
            "views":     parse_num(views_re.search(block)),
            "bookmarks": parse_num(bookmarks_re.search(block)),
            "permalink": permalink,
        }
        tweets.append(tweet)

    return tweets


def is_old_timestamp(raw_ts):
    """Return True if this timestamp is clearly older than yesterday."""
    raw_ts = raw_ts.lower().strip()
    # "2d", "3d", "4d" etc — more than 1 day old
    m = re.match(r'^(\d+)d$', raw_ts)
    if m and int(m.group(1)) >= 2:
        return True
    # Explicit old dates like "May 8", "Apr 30", "Jan 5"
    months = ["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"]
    for mon in months:
        if mon in raw_ts:
            # Has a month name — it's an old enough post that Twitter shows date not hours
            return True
    return False


def main():
    print(f"Capture starting. Target date: {DATE_STR}", flush=True)
    setup_browser()

    # Take initial snapshot and click Following
    snap = snapshot()
    click_following_tab(snap)
    snap = snapshot()

    tweets_by_id = {}
    scroll_passes = 0
    consecutive_old = 0
    errors = []

    for i in range(80):  # max 80 scrolls (~10 min at 2.5s each)
        snap = snapshot()
        new_tweets = parse_tweets(snap)
        added = 0
        all_old = True

        for t in new_tweets:
            if t["tweet_id"] not in tweets_by_id:
                tweets_by_id[t["tweet_id"]] = t
                added += 1
            if not is_old_timestamp(t["raw_timestamp"]):
                all_old = False

        scroll_passes += 1
        print(f"Scroll {i+1}: {len(new_tweets)} seen, {added} new, total={len(tweets_by_id)}", flush=True)

        if all_old and i >= 9:  # at least 10 scrolls before stopping
            consecutive_old += 1
            if consecutive_old >= 3:
                print("3 consecutive all-old snapshots — stopping.", flush=True)
                break
        else:
            consecutive_old = 0

        press_pagedown()
        wait_ms(2500)

    all_tweets = list(tweets_by_id.values())
    print(f"\nTotal tweets collected: {len(all_tweets)}", flush=True)

    # Save output
    with open(OUT_JSON, "w") as f:
        json.dump(all_tweets, f, indent=2)

    meta = {
        "target_date": DATE_STR,
        "timezone": "America/Los_Angeles",
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "tweets_found": len(all_tweets),
        "scroll_passes": scroll_passes,
        "notes": [],
        "errors": errors,
    }
    with open(OUT_META, "w") as f:
        json.dump(meta, f, indent=2)

    print(f"Saved to {OUT_JSON}", flush=True)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Eurostar Snap Ticket Monitor
Watches all slots across multiple dates and alerts when any ticket becomes available.
"""

import urllib.request
import json
import re
import time
import subprocess
import sys
import os
from datetime import datetime

# ── Configuration ─────────────────────────────────────────────────────────────
WATCH_DATES = ["2026-04-09", "2026-04-10", "2026-04-11", "2026-04-12"]
ORIGIN = "8727100"       # Paris Gare du Nord
DESTINATION = "7015400"  # London St Pancras
CHECK_INTERVAL_SECONDS = 120
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")
# ──────────────────────────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}


def build_url(date: str) -> str:
    return (
        f"https://snap.eurostar.com/fr-fr/search"
        f"?adult=1&origin={ORIGIN}&destination={DESTINATION}&outbound={date}"
    )


def fetch_availability(url: str):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=20) as resp:
            html = resp.read().decode("utf-8")
    except Exception as e:
        print(f"  [!] Network error: {e}")
        return None

    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        html, re.DOTALL,
    )
    if not match:
        print("  [!] Could not find __NEXT_DATA__ in page")
        return None

    try:
        data = json.loads(match.group(1))
        return data["props"]["pageProps"]
    except (json.JSONDecodeError, KeyError) as e:
        print(f"  [!] JSON parse error: {e}")
        return None


def get_available_slots(props: dict) -> list:
    available = []
    for slot in props.get("outboundTimeSlots") or []:
        fare = slot.get("fare")
        if not fare:
            continue
        window = slot.get("departureWindow", {})
        earliest = window.get("earliest", "")
        dep_time = earliest.split(" ")[-1] if " " in earliest else earliest
        available.append({
            "time": dep_time,
            "seats": fare.get("seats", "?"),
            "price": fare.get("prices", {}).get("displayPrice", "?"),
        })
    return available


def send_slack(title: str, message: str, url: str) -> None:
    if not SLACK_WEBHOOK_URL:
        return
    payload = json.dumps({
        "text": f"*{title}*\n{message}\n<{url}|Book now>",
    }).encode("utf-8")
    try:
        req = urllib.request.Request(
            SLACK_WEBHOOK_URL, data=payload,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"  [!] Slack notification failed: {e}")


def notify(title: str, message: str, url: str) -> None:
    # macOS notification
    script = f'display notification "{message}" with title "{title}" sound name "Glass"'
    subprocess.run(["osascript", "-e", script], check=False)
    # Slack
    send_slack(title, message, url)
    # Open browser
    subprocess.run(["open", url], check=False)


def log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def check_all_dates():
    """Check all watch dates. Returns list of (date, slots) where slots is non-empty."""
    found = []
    for date in WATCH_DATES:
        url = build_url(date)
        props = fetch_availability(url)
        if props is None:
            log(f"  [!] Failed to fetch {date}")
            continue
        slots = get_available_slots(props)
        if slots:
            summary = ", ".join(f"{s['time']} €{s['price']} ({s['seats']} seats)" for s in slots)
            log(f"✅  {date}: {summary}")
            found.append((date, slots, url))
        else:
            log(f"❌  {date}: sold out")
    return found


def run_monitor(interval: int) -> None:
    log(f"Monitoring April 9–12 Paris → London")
    log(f"Checking every {interval}s — Ctrl+C to stop\n")

    # Track which (date, time) combos we've already alerted on
    alerted = set()

    while True:
        found = check_all_dates()
        for date, slots, url in found:
            for slot in slots:
                key = (date, slot["time"])
                if key not in alerted:
                    notify(
                        title="🚂 Eurostar Snap — BUY NOW",
                        message=f"{date} Paris→London: {slot['time']} €{slot['price']} ({slot['seats']} seats)",
                        url=url,
                    )
                    alerted.add(key)
        print(flush=True)
        time.sleep(interval)


def main() -> None:
    # GitHub Actions / CI: single check, send Slack if anything found
    if "--check-once" in sys.argv:
        found = check_all_dates()
        if found:
            for date, slots, url in found:
                msg = ", ".join(f"{s['time']} €{s['price']} ({s['seats']} seats)" for s in slots)
                send_slack("🚂 Eurostar Snap — BUY NOW", f"{date} Paris→London: {msg}", url)
        sys.exit(0)

    try:
        run_monitor(CHECK_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()

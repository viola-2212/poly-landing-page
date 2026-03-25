#!/usr/bin/env python3
"""
Eurostar Snap Ticket Monitor
Watches all slots on a given date and alerts when any ticket becomes available.
"""

import urllib.request
import json
import re
import time
import subprocess
import sys
import argparse
from datetime import datetime

# ── Configuration ─────────────────────────────────────────────────────────────
DEFAULT_DATE = "2026-04-12"
DEFAULT_ORIGIN = "8727100"       # Paris Gare du Nord
DEFAULT_DESTINATION = "7015400"  # London St Pancras
CHECK_INTERVAL_SECONDS = 120     # how often to poll (2 minutes)
# ──────────────────────────────────────────────────────────────────────────────

import os
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")

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


def build_url(date: str, origin: str, destination: str) -> str:
    return (
        f"https://snap.eurostar.com/fr-fr/search"
        f"?adult=1&origin={origin}&destination={destination}&outbound={date}"
    )


def fetch_availability(url: str):
    """Fetch the page and return pageProps dict, or None on failure."""
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=20) as resp:
            html = resp.read().decode("utf-8")
    except Exception as e:
        print(f"  [!] Network error: {e}")
        return None

    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        html,
        re.DOTALL,
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
    """Return list of available slots: [{time, seats, price, booking_url}]"""
    available = []
    slots = props.get("outboundTimeSlots") or []
    for slot in slots:
        fare = slot.get("fare")
        if not fare:
            continue
        window = slot.get("departureWindow", {})
        earliest = window.get("earliest", "")
        # Extract time portion "HH:MM" from "YYYY-MM-DD HH:MM"
        dep_time = earliest.split(" ")[-1] if " " in earliest else earliest
        seats = fare.get("seats", "?")
        price = fare.get("prices", {}).get("displayPrice", "?")
        available.append({
            "time": dep_time,
            "seats": seats,
            "price": price,
            "window": f"{earliest} → {window.get('latest', '')}",
        })
    return available


def notify(title: str, message: str, url: str) -> None:
    """Send a macOS notification, a Slack message, and open the booking URL."""
    # macOS notification
    script = (
        f'display notification "{message}" '
        f'with title "{title}" '
        f'sound name "Glass"'
    )
    subprocess.run(["osascript", "-e", script], check=False)

    # Slack message
    payload = json.dumps({
        "text": f"*{title}*\n{message}\n<{url}|Book now>",
    }).encode("utf-8")
    try:
        req = urllib.request.Request(
            SLACK_WEBHOOK_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"  [!] Slack notification failed: {e}")

    # Open browser
    subprocess.run(["open", url], check=False)


def log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def run_monitor(url: str, date: str, interval: int, once: bool) -> None:
    log(f"Monitoring April 12 tickets: Paris → London")
    log(f"URL: {url}")
    log(f"Checking every {interval}s — Ctrl+C to stop\n")

    last_available_times = set()

    while True:
        props = fetch_availability(url)
        if props is None:
            log("Failed to fetch — will retry")
            time.sleep(interval)
            continue

        available = get_available_slots(props)

        if available:
            summary = ", ".join(
                f"{s['time']} (€{s['price']}, {s['seats']} seats)" for s in available
            )
            log(f"✅  AVAILABLE: {summary}")

            # Only notify when new slots appear
            new_times = {s["time"] for s in available}
            newly_available = new_times - last_available_times
            if newly_available:
                msg = " | ".join(
                    f"{s['time']} €{s['price']} ({s['seats']} seats)"
                    for s in available
                    if s["time"] in newly_available
                )
                notify(
                    title="🚂 Eurostar Snap — BUY NOW",
                    message=f"April 12 Paris→London: {msg}",
                    url=url,
                )

            last_available_times = new_times

            if once:
                log("--once flag set, exiting.")
                break
        else:
            log(f"❌  All slots sold out for {date}")
            last_available_times = set()

        time.sleep(interval)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Monitor Eurostar Snap ticket availability for April 12."
    )
    parser.add_argument(
        "--date", default=DEFAULT_DATE,
        help="Travel date YYYY-MM-DD (default: %(default)s)",
    )
    parser.add_argument(
        "--interval", type=int, default=CHECK_INTERVAL_SECONDS,
        help="Seconds between checks (default: %(default)s)",
    )
    parser.add_argument(
        "--once", action="store_true",
        help="Exit after the first available ticket is detected",
    )
    parser.add_argument(
        "--check-once", action="store_true",
        help="Single check and exit (for testing)",
    )
    args = parser.parse_args()

    url = build_url(args.date, DEFAULT_ORIGIN, DEFAULT_DESTINATION)

    if args.check_once:
        props = fetch_availability(url)
        if not props:
            print("Failed to fetch page.")
            sys.exit(1)
        available = get_available_slots(props)
        if available:
            for s in available:
                print(f"✅  {s['time']}  |  {s['seats']} seats  |  €{s['price']}")
            msg = " | ".join(
                f"{s['time']} €{s['price']} ({s['seats']} seats)" for s in available
            )
            notify(
                title="🚂 Eurostar Snap — BUY NOW",
                message=f"April 12 Paris→London: {msg}",
                url=url,
            )
        else:
            print(f"❌  All slots sold out for {args.date}")
        sys.exit(0)

    try:
        run_monitor(url, args.date, args.interval, args.once)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()

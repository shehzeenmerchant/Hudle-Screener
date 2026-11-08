#!/usr/bin/env python3
"""
🎾 Hudle Mumbai Padel Slot Sniper & Drop Alert Monitor

Monitors Mumbai Padel courts in real-time, detecting cancellations and newly opened
prime slots (e.g., 7:00 PM – 10:00 PM), and dispatches instant Telegram alerts.
"""

import argparse
import json
import os
import ssl
import sys
import time
import urllib.request
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from hudle_client import HudleClient
from search import format_time_12hr, normalize_zone, parse_date, parse_time_window, time_to_minutes
from sync_catalog import load_cached_catalog, sync_mumbai_padel_catalog

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")
CTX = ssl.create_default_context()

def load_config() -> Dict[str, str]:
    cfg = {
        "telegram_bot_token": os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        "telegram_chat_id": os.environ.get("TELEGRAM_CHAT_ID", ""),
        "hudle_auth_token": os.environ.get("HUDLE_AUTH_TOKEN", "")
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                file_cfg = json.load(f)
                for k, v in file_cfg.items():
                    if v and not cfg.get(k):
                        cfg[k] = v
        except Exception:
            pass
    return cfg

def send_telegram_alert(
    bot_token: str,
    chat_id: str,
    slot: Dict[str, Any],
    date_str: str
) -> bool:
    """Send high-priority drop notification with direct booking link."""
    if not bot_token or not chat_id:
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    t_start = format_time_12hr(slot["start_time"])
    t_end = format_time_12hr(slot["end_time"])
    v_name = slot["venue_name"]
    c_name = slot["court_name"]
    price = int(slot["price"])
    booking_url = slot["share_url"]

    # Human-readable date format e.g. Mon, Nov 9
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        friendly_date = dt.strftime("%A, %b %d")
    except Exception:
        friendly_date = date_str

    text = (
        f"🚨 <b>PRIME PADEL SLOT DROPPED!</b>\n\n"
        f"🏟 <b>Venue:</b> {v_name}\n"
        f"🎾 <b>Court:</b> {c_name}\n"
        f"📅 <b>Date:</b> {friendly_date}\n"
        f"⏰ <b>Time:</b> {t_start} – {t_end}\n"
        f"💰 <b>Price:</b> ₹{price}\n\n"
        f"⚡ <i>Slot was just cancelled or opened up. Tap below to reserve instantly!</i>"
    )

    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
        "reply_markup": {
            "inline_keyboard": [
                [{"text": f"⚡ Book Now ({t_start})", "url": booking_url}]
            ]
        }
    }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, context=CTX, timeout=10) as r:
            res = json.loads(r.read().decode("utf-8"))
            return res.get("ok", False)
    except Exception as e:
        print(f"⚠️ Failed to send Telegram alert: {e}")
        return False

class SlotSniper:
    def __init__(
        self,
        date_str: str,
        time_window: str = "19:00-22:00",
        zone: Optional[str] = None,
        venue_query: Optional[str] = None,
        max_price: Optional[float] = None,
        min_duration_minutes: int = 60,
        poll_interval: int = 60,
        telegram_token: Optional[str] = None,
        telegram_chat_id: Optional[str] = None,
        alert_existing: bool = False,
        auto_book: bool = False,
        auth_token: Optional[str] = None
    ):
        self.date_str = date_str
        self.time_window = time_window
        self.zone = normalize_zone(zone)
        self.venue_query = venue_query.strip().lower() if venue_query else None
        self.max_price = max_price
        self.min_duration = min_duration_minutes
        self.interval = max(15, poll_interval)
        self.telegram_token = telegram_token
        self.telegram_chat_id = telegram_chat_id
        self.alert_existing = alert_existing
        self.auto_book = auto_book
        self.auth_token = auth_token

        self.client = HudleClient(delay_between_requests=0.15, auth_token=auth_token)
        self.start_min, self.end_min = parse_time_window(time_window)

        # Load filtered catalog
        raw_catalog = load_cached_catalog() or sync_mumbai_padel_catalog(client=self.client)
        self.catalog = self._filter_catalog(raw_catalog)
        self.known_available_slots: Set[str] = set()
        self.round_num = 0

    def _filter_catalog(self, catalog: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        filtered = catalog
        if self.zone:
            filtered = [v for v in filtered if v.get("zone") == self.zone]
        if self.venue_query:
            filtered = [
                v for v in filtered
                if self.venue_query in v.get("name", "").lower()
                or self.venue_query in v.get("address", "").lower()
                or self.venue_query in v.get("slug", "").lower()
            ]
        return filtered

    def _slot_key(self, slot: Dict[str, Any]) -> str:
        return f"{slot['venue_id']}_{slot['court_uuid']}_{slot['start_time']}"

    def scan_once(self) -> List[Dict[str, Any]]:
        """Scans all courts in target venues once and returns matching open slots."""
        available = []
        for v in self.catalog:
            venue_id = v["venue_id"]
            venue_name = v["name"]
            share_url = v.get("share_url") or f"https://hudle.in/venues/{v.get('slug')}"

            for court in v.get("courts", []):
                court_uuid = court["facility_uuid"]
                court_name = court["name"]

                try:
                    slots = self.client.get_slots(venue_id, court_uuid, self.date_str)
                except Exception:
                    continue

                for s in slots:
                    if not (s.get("is_available") and not s.get("is_booked")):
                        continue

                    s_min = time_to_minutes(s["start_time"])
                    if not (self.start_min <= s_min < self.end_min):
                        continue

                    price = float(s.get("price", 0))
                    if self.max_price is not None and price > self.max_price:
                        continue

                    slot_duration = time_to_minutes(s["end_time"]) - s_min
                    # If min_duration is 60 and slot is 30, we'll keep it for consecutive pairing check
                    available.append({
                        "venue_name": venue_name,
                        "venue_id": venue_id,
                        "court_name": court_name,
                        "court_uuid": court_uuid,
                        "facility_id": court.get("facility_id"),
                        "activity_id": v.get("activity_id"),
                        "start_time": s["start_time"],
                        "end_time": s["end_time"],
                        "duration": slot_duration,
                        "price": price,
                        "slot_id": s["id"],
                        "share_url": share_url
                    })

        # Filter duration if requested
        if self.min_duration > 30:
            final_slots = []
            for s in available:
                if s["duration"] >= self.min_duration:
                    final_slots.append(s)
                else:
                    # Check if consecutive slot exists on same court
                    next_s_min = time_to_minutes(s["end_time"])
                    has_consecutive = any(
                        other["court_uuid"] == s["court_uuid"] and
                        time_to_minutes(other["start_time"]) == next_s_min
                        for other in available
                    )
                    if has_consecutive:
                        final_slots.append(s)
            return final_slots

        return available

    def trigger_drop_alert(self, slot: Dict[str, Any]):
        """Dispatches terminal bell + Telegram notification for newly dropped slot."""
        t_start = format_time_12hr(slot["start_time"])
        t_end = format_time_12hr(slot["end_time"])
        ts = datetime.now().strftime("%H:%M:%S")

        print(f"\a\n" + "═" * 75)
        print(f"🚨 [{ts}] DROP ALERT / CANCELLATION DETECTED!")
        print(f"🏟  Venue: {slot['venue_name']}")
        print(f"🎾  Court: {slot['court_name']}")
        print(f"⏰  Time:  {t_start} – {t_end} ({self.date_str})")
        print(f"💰  Price: ₹{int(slot['price'])}")
        print(f"🔗  Book:  {slot['share_url']}")
        print("═" * 75 + "\n")

        # Telegram dispatch
        if self.telegram_token and self.telegram_chat_id:
            sent = send_telegram_alert(self.telegram_token, self.telegram_chat_id, slot, self.date_str)
            if sent:
                print(f"📲 Telegram alert sent to chat {self.telegram_chat_id}!")

        # Auto-booking trigger if configured
        if self.auto_book and self.auth_token:
            print("⚡ Attempting automatic reservation...")
            try:
                # Booking payload structure
                payload = {
                    "slots": [slot["slot_id"]],
                    "activity_id": slot["activity_id"]
                }
                res = self.client.create_booking(slot["venue_id"], slot["facility_id"], payload)
                print(f"🎉 Booking Response: {res}")
            except Exception as e:
                print(f"⚠️ Auto-booking failed: {e}")

    def run(self):
        total_courts = sum(len(v.get("courts", [])) for v in self.catalog)
        zone_label = self.zone.replace("_", " ").title() if self.zone else "All Mumbai"
        print(f"🎾 Hudle Mumbai Padel Sniper Started")
        print(f"📍 Region: {zone_label} | Filter: {self.venue_query or 'None'}")
        print(f"📅 Target Date: {self.date_str} | Time: {self.time_window}")
        print(f"🔎 Tracking {len(self.catalog)} venues ({total_courts} courts) every {self.interval}s")
        if self.telegram_chat_id:
            print(f"📲 Telegram Alerts Enabled for Chat ID: {self.telegram_chat_id}")
        else:
            print("ℹ️ Telegram Chat ID not set. Alerts will appear in terminal only.")
        print("-" * 75)

        try:
            while True:
                self.round_num += 1
                now_str = datetime.now().strftime("%H:%M:%S")
                print(f"[{now_str}] Round #{self.round_num}: Scanning courts...", end="", flush=True)

                t0 = time.perf_counter()
                current_slots = self.scan_once()
                duration = time.perf_counter() - t0
                current_keys = {self._slot_key(s) for s in current_slots}

                if self.round_num == 1:
                    print(f" Done ({duration:.1f}s). {len(current_slots)} slot(s) currently open.")
                    if self.alert_existing:
                        for s in current_slots:
                            self.trigger_drop_alert(s)
                    self.known_available_slots = current_keys
                else:
                    new_drops = [s for s in current_slots if self._slot_key(s) not in self.known_available_slots]
                    if new_drops:
                        print(f" Done ({duration:.1f}s). 🚨 {len(new_drops)} NEW DROP(S) DETECTED!")
                        for s in new_drops:
                            self.trigger_drop_alert(s)
                    else:
                        print(f" Done ({duration:.1f}s). No new drops ({len(current_slots)} open).")

                    # Update known set
                    self.known_available_slots = current_keys

                time.sleep(self.interval)

        except KeyboardInterrupt:
            print("\n🛑 Sniper stopped by user. Happy playing!")

def main():
    parser = argparse.ArgumentParser(
        description="🎾 Hudle Mumbai Padel Court Sniper & Cancellation Alert Monitor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  # Monitor South Mumbai prime slots (7 PM - 10 PM) tomorrow:
  python sniper.py --zone south --date tomorrow --time 19:00-22:00

  # Monitor Bandra & Khar courts tonight:
  python sniper.py --venue bandra --date today --time 19:00-23:00 --interval 45

  # Monitor and send Telegram alerts:
  python sniper.py --zone south --chat-id 123456789 --interval 60
"""
    )
    parser.add_argument("--date", "-d", default="tomorrow", help="Date: 'today', 'tomorrow', or 'YYYY-MM-DD' (default: tomorrow)")
    parser.add_argument("--time", "-t", default="19:00-22:00", help="Time window, e.g. '19:00-22:00' (default: 19:00-22:00)")
    parser.add_argument("--zone", "-z", choices=["south", "west", "east"], default=None, help="Filter by zone: 'south', 'west', or 'east'")
    parser.add_argument("--venue", "-v", default=None, help="Filter by venue name or area keyword (e.g. 'bandra', 'mazgaon')")
    parser.add_argument("--max-price", "-p", type=float, default=None, help="Max slot price in ₹")
    parser.add_argument("--interval", "-i", type=int, default=60, help="Polling interval in seconds (default: 60)")
    parser.add_argument("--chat-id", "-c", default=None, help="Telegram Chat ID to receive instant alerts")
    parser.add_argument("--alert-existing", action="store_true", help="Also send alerts for slots already available on first scan")
    parser.add_argument("--once", action="store_true", help="Run a single check and exit (useful for cron jobs)")
    parser.add_argument("--auto-book", action="store_true", help="Attempt automatic slot reservation when a drop occurs")

    args = parser.parse_args()
    cfg = load_config()

    try:
        target_date = parse_date(args.date)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    bot_token = cfg.get("telegram_bot_token")
    chat_id = args.chat_id or cfg.get("telegram_chat_id")
    auth_token = cfg.get("hudle_auth_token")

    sniper = SlotSniper(
        date_str=target_date,
        time_window=args.time,
        zone=args.zone,
        venue_query=args.venue,
        max_price=args.max_price,
        poll_interval=args.interval,
        telegram_token=bot_token,
        telegram_chat_id=chat_id,
        alert_existing=args.alert_existing,
        auto_book=args.auto_book,
        auth_token=auth_token
    )

    if args.once:
        slots = sniper.scan_once()
        print(f"Single scan complete for {target_date} ({args.time}): {len(slots)} matching slots open.")
        for s in slots:
            t_s = format_time_12hr(s["start_time"])
            t_e = format_time_12hr(s["end_time"])
            print(f"  • {t_s} - {t_e} | ₹{int(s['price'])} | {s['venue_name']} ({s['court_name']})")
    else:
        sniper.run()

if __name__ == "__main__":
    main()

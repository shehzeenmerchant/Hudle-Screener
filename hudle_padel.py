#!/usr/bin/env python3
import argparse
import getpass
import json
import os
import sys
from datetime import datetime

from search import parse_date, search_slots, display_slots_table, normalize_zone
from sync_catalog import sync_mumbai_padel_catalog, load_cached_catalog
from hudle_client import HudleClient

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")

def load_local_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_local_config(cfg: dict):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)
    os.chmod(CONFIG_FILE, 0o600)

def is_phase2_enabled() -> bool:
    cfg = load_local_config()
    return os.environ.get("ENABLE_PHASE2", "").lower() in ("1", "true") or bool(cfg.get("enable_phase2_sniper", False))

def is_phase3_enabled() -> bool:
    cfg = load_local_config()
    return os.environ.get("ENABLE_PHASE3", "").lower() in ("1", "true") or bool(cfg.get("enable_phase3_autobook", False))

def main():
    parser = argparse.ArgumentParser(
        description="🎾 Hudle Mumbai Padel Slot Finder & Booking Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  # Search all slots for tomorrow between 7 PM and 10 PM
  python hudle_padel.py search --date tomorrow --time 19:00-22:00

  # Search only in Bandra or Khar with max price Rs 1500
  python hudle_padel.py search --date today --time 18:00-21:00 --venue bandra --max-price 1500

  # List all cached Mumbai Padel venues and courts
  python hudle_padel.py venues

  # Refresh the venue catalog
  python hudle_padel.py sync
"""
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Command: search
    search_p = subparsers.add_parser("search", help="Search available padel slots")
    search_p.add_argument("--date", "-d", default="tomorrow", help="Date: 'today', 'tomorrow', or 'YYYY-MM-DD' (default: tomorrow)")
    search_p.add_argument("--time", "-t", default=None, help="Time window or preset: 'morning', 'evening', 'night', 'all', or '19:00-22:00'")
    search_p.add_argument("--zone", "-z", choices=["south", "west", "east"], default=None, help="Filter by zone: 'south' (SoBo), 'west' (Western Suburbs), 'east' (Eastern Suburbs)")
    search_p.add_argument("--venue", "-v", default=None, help="Filter by venue name or area (e.g. 'bandra', 'khar', 'worli')")
    search_p.add_argument("--max-price", "-p", type=float, default=None, help="Maximum price per slot in ₹")
    search_p.add_argument("--json", action="store_true", help="Output results in JSON format")

    # Command: sniper (Phase 2 feature flag)
    sniper_p = subparsers.add_parser("sniper", help="[Phase 2 Feature] Run background monitor for cancellations & newly dropped slots")
    sniper_p.add_argument("--enable", action="store_true", help="Explicitly activate Phase 2 feature")
    sniper_p.add_argument("--date", "-d", default="tomorrow", help="Date: 'today', 'tomorrow', or 'YYYY-MM-DD' (default: tomorrow)")
    sniper_p.add_argument("--time", "-t", default="19:00-22:00", help="Time window, e.g. '19:00-22:00' (default: 19:00-22:00)")
    sniper_p.add_argument("--zone", "-z", choices=["south", "west", "east"], default=None, help="Filter by zone: 'south', 'west', or 'east'")
    sniper_p.add_argument("--venue", "-v", default=None, help="Filter by venue name or area keyword")
    sniper_p.add_argument("--max-price", "-p", type=float, default=None, help="Maximum price in ₹")
    sniper_p.add_argument("--interval", "-i", type=int, default=60, help="Polling interval in seconds (default: 60)")
    sniper_p.add_argument("--chat-id", "-c", default=None, help="Telegram Chat ID for alerts")
    sniper_p.add_argument("--alert-existing", action="store_true", help="Alert on current slots as well")
    sniper_p.add_argument("--once", action="store_true", help="Run a single scan and exit")
    sniper_p.add_argument("--auto-book", action="store_true", help="Attempt auto-booking when slot drops")

    # Command: venues
    venues_p = subparsers.add_parser("venues", help="List all cached Mumbai Padel venues")
    venues_p.add_argument("--zone", "-z", choices=["south", "west", "east"], default=None, help="Filter by zone: 'south', 'west', or 'east'")
    venues_p.add_argument("--query", "-q", default=None, help="Search query for venue name or address")

    # Command: sync
    sync_p = subparsers.add_parser("sync", help="Refresh/update the local venue catalog from Hudle")

    # Command: login (Phase 3 feature flag)
    login_p = subparsers.add_parser("login", help="[Phase 3 Feature] Log into Hudle to save your auth token for bookings")
    login_p.add_argument("--enable", action="store_true", help="Explicitly activate Phase 3 feature")

    args = parser.parse_args()

    if not args.command or args.command == "search":
        date_input = getattr(args, "date", "tomorrow") or "tomorrow"
        try:
            target_date = parse_date(date_input)
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)

        time_window = getattr(args, "time", None)
        venue_filter = getattr(args, "venue", None)
        zone_filter = getattr(args, "zone", None)
        max_price = getattr(args, "max_price", None)
        as_json = getattr(args, "json", False)

        slots = search_slots(
            date_str=target_date,
            time_window=time_window,
            venue_filter=venue_filter,
            zone_filter=zone_filter,
            max_price=max_price
        )

        if as_json:
            print(json.dumps(slots, indent=2))
        else:
            display_slots_table(slots, target_date)

    elif args.command == "sniper":
        if not (getattr(args, "enable", False) or is_phase2_enabled()):
            print("⚠️  Phase 2 (Drop Alert / Court Sniper) is currently disabled.")
            print("To activate in the future, pass '--enable' or set ENABLE_PHASE2=true in your environment/config.json.")
            sys.exit(0)

        from sniper import SlotSniper, load_config
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
            print(f"Scan complete for {target_date} ({args.time}): {len(slots)} matching slots open.")
            from search import format_time_12hr
            for s in slots:
                t_s = format_time_12hr(s["start_time"])
                t_e = format_time_12hr(s["end_time"])
                print(f"  • {t_s} - {t_e} | ₹{int(s['price'])} | {s['venue_name']} ({s['court_name']})")
        else:
            sniper.run()

    elif args.command == "venues":
        catalog = load_cached_catalog()
        if not catalog:
            print("No cached venues found. Run 'python hudle_padel.py sync' first.")
            return

        if getattr(args, "zone", None):
            norm_z = normalize_zone(args.zone)
            catalog = [v for v in catalog if v.get("zone") == norm_z]

        if args.query:
            q = args.query.lower()
            catalog = [v for v in catalog if q in v.get("name", "").lower() or q in v.get("address", "").lower()]

        zone_title = f" [{args.zone.upper()}]" if getattr(args, "zone", None) else ""
        print(f"\n🎾 Mumbai Padel Venues{zone_title} ({len(catalog)} venues total):\n")
        print(f"{'Venue Name':<42} | {'Courts':<8} | {'Zone':<16} | {'Address / Area'}")
        print("-" * 95)
        for v in catalog:
            courts_count = len(v.get("courts", []))
            addr = v.get("address") or "Mumbai"
            z_label = v.get("zone_label") or v.get("zone", "Mumbai")
            print(f"{v['name'][:40]:<42} | {courts_count:<8} | {z_label[:14]:<16} | {addr[:25]}")
        print("-" * 95)

    elif args.command == "sync":
        sync_mumbai_padel_catalog()

    elif args.command == "login":
        if not (getattr(args, "enable", False) or is_phase3_enabled()):
            print("⚠️  Phase 3 (Account Login & Auto-Booking) is currently disabled.")
            print("To activate in the future, pass '--enable' or set ENABLE_PHASE3=true in your environment/config.json.")
            sys.exit(0)

        print("🔐 Hudle Authentication Login")
        email = input("Hudle Registered Email: ").strip()
        password = getpass.getpass("Hudle Password: ").strip()

        client = HudleClient()
        try:
            res = client.login(email, password)
            token = res.get("token") or res.get("data", {}).get("token")
            if token:
                cfg = load_local_config()
                cfg["hudle_auth_token"] = token
                save_local_config(cfg)
                user_name = res.get("data", {}).get("name") or email
                print(f"✅ Success! Logged in as {user_name}.")
                print(f"🔑 Auth token saved securely to config.json.")
            else:
                msg = res.get("message") or res.get("errors") or "Authentication failed"
                print(f"❌ Login failed: {msg}")
        except Exception as e:
            print(f"❌ Login error: {e}")

if __name__ == "__main__":
    main()

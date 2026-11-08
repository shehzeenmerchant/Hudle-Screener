#!/usr/bin/env python3
import argparse
import json
import sys
from datetime import datetime

from search import parse_date, search_slots, display_slots_table
from sync_catalog import sync_mumbai_padel_catalog, load_cached_catalog

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
    search_p.add_argument("--time", "-t", default=None, help="Time window, e.g. '19:00-22:00' or '18-21' (default: all day)")
    search_p.add_argument("--zone", "-z", choices=["south", "west", "east"], default=None, help="Filter by zone: 'south' (SoBo), 'west' (Western Suburbs), 'east' (Eastern Suburbs)")
    search_p.add_argument("--venue", "-v", default=None, help="Filter by venue name or area (e.g. 'bandra', 'khar', 'worli')")
    search_p.add_argument("--max-price", "-p", type=float, default=None, help="Maximum price per slot in ₹")
    search_p.add_argument("--json", action="store_true", help="Output results in JSON format")

    # Command: venues
    venues_p = subparsers.add_parser("venues", help="List all cached Mumbai Padel venues")
    venues_p.add_argument("--zone", "-z", choices=["south", "west", "east"], default=None, help="Filter by zone: 'south', 'west', or 'east'")
    venues_p.add_argument("--query", "-q", default=None, help="Search query for venue name or address")

    # Command: sync
    sync_p = subparsers.add_parser("sync", help="Refresh/update the local venue catalog from Hudle")

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

    elif args.command == "venues":
        catalog = load_cached_catalog()
        if not catalog:
            print("No cached venues found. Run 'python hudle_padel.py sync' first.")
            return

        from search import normalize_zone
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

if __name__ == "__main__":
    main()

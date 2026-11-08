from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from hudle_client import HudleClient
from sync_catalog import load_cached_catalog, sync_mumbai_padel_catalog

def parse_date(date_input: str) -> str:
    date_str = date_input.strip().lower()
    today = datetime.now()
    if date_str in ("today", "t"):
        return today.strftime("%Y-%m-%d")
    elif date_str in ("tomorrow", "tom", "tmrw"):
        return (today + timedelta(days=1)).strftime("%Y-%m-%d")
    elif date_str.isdigit() and len(date_str) in (1, 2):
        # E.g. "+1", "+2"
        days = int(date_str)
        return (today + timedelta(days=days)).strftime("%Y-%m-%d")
    else:
        try:
            parsed = datetime.strptime(date_str, "%Y-%m-%d")
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            raise ValueError(f"Invalid date format '{date_input}'. Use 'today', 'tomorrow', or 'YYYY-MM-DD'.")

def parse_time_window(time_str: Optional[str]):
    """Parses '19:00-22:00', '18-21', or presets ('all', 'morning', 'evening', 'night') into (start_minutes, end_minutes)."""
    if not time_str:
        return 0, 24 * 60

    t_clean = time_str.strip().lower()
    if t_clean in ("all", "any", "day", "all-day", "allday", "*"):
        return 0, 24 * 60
    elif t_clean in ("morning", "am"):
        return 6 * 60, 12 * 60       # 06:00 - 12:00
    elif t_clean in ("afternoon", "noon", "pm"):
        return 12 * 60, 17 * 60      # 12:00 - 17:00
    elif t_clean in ("evening", "prime"):
        return 18 * 60, 22 * 60      # 18:00 - 22:00
    elif t_clean in ("night", "late"):
        return 21 * 60, 24 * 60      # 21:00 - 24:00

    parts = time_str.split("-")
    if len(parts) != 2:
        raise ValueError("Time range must be formatted as 'HH:MM-HH:MM' (e.g. '19:00-22:00' or '18-21') or preset ('all', 'morning', 'evening', 'night')")

    def to_minutes(t_part: str) -> int:
        t_part = t_part.strip()
        if ":" in t_part:
            h, m = t_part.split(":")
            return int(h) * 60 + int(m)
        else:
            return int(t_part) * 60

    return to_minutes(parts[0]), to_minutes(parts[1])

def time_to_minutes(time_str: str) -> int:
    """Converts 'YYYY-MM-DD HH:MM:SS' or 'HH:MM:SS' to minutes of day."""
    if " " in time_str:
        time_str = time_str.split(" ")[1]
    h, m, *_ = time_str.split(":")
    return int(h) * 60 + int(m)

def normalize_zone(zone_input: Optional[str]) -> Optional[str]:
    if not zone_input:
        return None
    z = zone_input.strip().lower()
    if z in ("south", "sobo", "south_mumbai", "south-mumbai", "s"):
        return "south_mumbai"
    elif z in ("west", "western", "western_suburbs", "western-suburbs", "w"):
        return "western_suburbs"
    elif z in ("east", "eastern", "eastern_suburbs", "eastern-suburbs", "e", "central"):
        return "eastern_suburbs"
    return z

SHARED_CLIENT = HudleClient()

def search_slots(
    date_str: str,
    time_window: Optional[str] = None,
    venue_filter: Optional[str] = None,
    zone_filter: Optional[str] = None,
    max_price: Optional[float] = None,
    client: Optional[HudleClient] = None
) -> List[Dict[str, Any]]:
    if client is None:
        client = SHARED_CLIENT

    catalog = load_cached_catalog()
    if not catalog:
        print("ℹ️ Venue catalog not found. Automatically running first-time sync...")
        catalog = sync_mumbai_padel_catalog(client=client)

    # Filter by Zone if specified
    norm_zone = normalize_zone(zone_filter)
    if norm_zone:
        catalog = [v for v in catalog if v.get("zone") == norm_zone]

    # Filter venues if venue_filter specified
    if venue_filter:
        query = venue_filter.strip().lower()
        catalog = [
            v for v in catalog
            if query in v.get("name", "").lower()
            or query in v.get("address", "").lower()
            or query in v.get("slug", "").lower()
        ]

    start_min, end_min = parse_time_window(time_window)
    matched_slots = []

    total_courts = sum(len(v.get("courts", [])) for v in catalog)
    print(f"🔎 Scanning slots across {len(catalog)} venues ({total_courts} courts) for {date_str}...")

    for v in catalog:
        # Skip members-only clubs on general searches to keep queries fast and actionable
        if "members only" in v.get("name", "").lower() and not venue_filter:
            continue

        venue_id = v["venue_id"]
        venue_name = v["name"]
        share_url = v.get("share_url") or f"https://hudle.in/venues/{v.get('slug')}"

        for court in v.get("courts", []):
            court_name = court["name"]
            c_low = court_name.lower()
            # Skip equipment rentals (racquets, balls, machines)
            if any(k in c_low for k in ["racquet", "ball", "paddle", "machine"]):
                continue

            court_uuid = court["facility_uuid"]

            try:
                slots = client.get_slots(venue_id, court_uuid, date_str)
            except Exception as e:
                continue

            for s in slots:
                if not (s.get("is_available") and not s.get("is_booked")):
                    continue

                slot_start_min = time_to_minutes(s["start_time"])
                if not (start_min <= slot_start_min < end_min):
                    continue

                price = float(s.get("price", 0))
                if max_price is not None and price > max_price:
                    continue

                matched_slots.append({
                    "venue_name": venue_name,
                    "venue_id": venue_id,
                    "court_name": court_name,
                    "court_uuid": court_uuid,
                    "facility_id": court.get("facility_id"),
                    "activity_id": v.get("activity_id"),
                    "start_time": s["start_time"],
                    "end_time": s["end_time"],
                    "price": price,
                    "slot_id": s["id"],
                    "share_url": share_url
                })

    return matched_slots

def format_time_12hr(dt_str: str) -> str:
    """Formats '2026-11-09 19:30:00' to '07:30 PM'"""
    try:
        t = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        return t.strftime("%I:%M %p")
    except Exception:
        return dt_str

def display_slots_table(slots: List[Dict[str, Any]], date_str: str):
    if not slots:
        print(f"\n❌ No available slots found matching your criteria for {date_str}.")
        return

    # Sort slots chronologically, then by price
    slots.sort(key=lambda s: (s["start_time"], s["price"]))

    print(f"\n🎾 Found {len(slots)} Available Slot(s) for {date_str}:\n")

    # Table headers
    col_time = 20
    col_venue = 35
    col_court = 16
    col_price = 10
    col_link = 40

    header = f"{'Time Slot':<{col_time}} | {'Venue':<{col_venue}} | {'Court':<{col_court}} | {'Price':<{col_price}} | {'Booking URL'}"
    print(header)
    print("-" * len(header))

    for s in slots:
        time_disp = f"{format_time_12hr(s['start_time'])} - {format_time_12hr(s['end_time'])}"
        v_name = s['venue_name'][:col_venue - 2]
        c_name = s['court_name'][:col_court - 2]
        price_disp = f"₹{int(s['price'])}"
        url = s['share_url']

        print(f"{time_disp:<{col_time}} | {v_name:<{col_venue}} | {c_name:<{col_court}} | {price_disp:<{col_price}} | {url}")

    print("-" * len(header))

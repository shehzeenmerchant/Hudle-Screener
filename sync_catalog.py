import json
import os
import sys
from hudle_client import HudleClient

from classify_zones import classify_venue

CACHE_FILE = os.path.join(os.path.dirname(__file__), "venues_cache.json")

def sync_mumbai_padel_catalog(client: HudleClient = None, verbose: bool = True) -> list:
    if client is None:
        client = HudleClient(delay_between_requests=0.4)

    if verbose:
        print("🔍 Scanning Hudle for Mumbai Padel venues (City ID: 2, Sport ID: 44)...")
    
    venues_list = client.get_venues(city_id=2, sport_id=44, per_page=50)
    if verbose:
        print(f"Found {len(venues_list)} venues. Fetching court details for each...")

    catalog = []

    for idx, v in enumerate(venues_list, 1):
        v_id = v.get("id")
        v_name = v.get("name")
        if verbose:
            print(f"  [{idx}/{len(venues_list)}] Fetching: {v_name}...")

        try:
            vd = client.get_venue_details(v_id)
        except Exception as e:
            if verbose:
                print(f"    ⚠️ Failed to fetch details for {v_name}: {e}")
            continue

        # Look for padel activities and courts
        activities = vd.get("activities", [])
        padel_courts = []
        padel_activity_id = None
        padel_activity_name = "Padel"

        for act in activities:
            if "padel" in act.get("name", "").lower():
                padel_activity_id = act.get("id")
                padel_activity_name = act.get("name")
                for f in act.get("facilities", []):
                    padel_courts.append({
                        "facility_uuid": f.get("id"),
                        "facility_id": f.get("facility_id"),
                        "name": f.get("name"),
                        "slot_length": f.get("slot_length", 30),
                        "price_onwards": f.get("price_onwards") or f.get("price")
                    })

        # Fallback to sports if no activities
        if not padel_courts:
            for s in vd.get("sports", []):
                if "padel" in s.get("name", "").lower():
                    for f in s.get("facilities", []):
                        padel_courts.append({
                            "facility_uuid": f.get("id"),
                            "facility_id": f.get("facility_id"),
                            "name": f.get("name"),
                            "slot_length": f.get("slot_length", 30),
                            "price_onwards": f.get("price_onwards") or f.get("price")
                        })

        if padel_courts:
            v_dict = {
                "venue_id": v_id,
                "name": v_name,
                "slug": vd.get("slug") or v.get("slug"),
                "share_url": vd.get("share_url") or vd.get("web_url"),
                "address": vd.get("short_address") or vd.get("address"),
                "rating": vd.get("rating"),
                "activity_id": padel_activity_id,
                "activity_name": padel_activity_name,
                "courts": padel_courts
            }
            zone_key, zone_label = classify_venue(v_dict)
            v_dict["zone"] = zone_key
            v_dict["zone_label"] = zone_label
            catalog.append(v_dict)
            if verbose:
                print(f"    ✅ Added {len(padel_courts)} padel court(s)")
        else:
            if verbose:
                print(f"    ℹ️ No active padel courts listed")

    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)

    if verbose:
        print(f"\n🎉 Successfully cached {len(catalog)} venues with padel courts to '{CACHE_FILE}'.")
    return catalog

def load_cached_catalog() -> list:
    possible_paths = [
        CACHE_FILE,
        os.path.join(os.getcwd(), "venues_cache.json"),
        os.path.join(os.path.dirname(__file__), "..", "venues_cache.json"),
        "/var/task/venues_cache.json"
    ]
    for p in possible_paths:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
    return []

if __name__ == "__main__":
    sync_mumbai_padel_catalog()

import json
import os
import re
from typing import Any, Dict, Tuple

SOBO_KEYWORDS = [
    'colaba', 'churchgate', 'marine lines', 'fort', 'nariman point',
    'malabar hill', 'breach candy', 'cumballa', 'tardeo', 'mahalaxmi', 'mahalakshmi',
    'worli', 'lower parel', 'parel', 'byculla', 'ranibaug', 'mazgaon', 'sewri', 'reay road',
    'dadar', 'mahim', 'prabhadevi', 'willingdon', 'haji ali'
]

EASTERN_KEYWORDS = [
    'vikhroli', 'bhandup', 'mulund', 'ghatkopar', 'powai', 'marol', 'chembur', 'kurla',
    'kanjurmarg', 'saki vihar', 'saki naka', 'pant nagar'
]

WESTERN_KEYWORDS = [
    'bandra', 'khar', 'santacruz', 'juhu', 'vile parle', 'andheri', 'lokhandwala',
    'oshiwara', 'goregaon', 'jogeshwari', 'kandivali', 'malad', 'borivali', 'dahisar',
    'versova', 'four bungalows', 'veera desai'
]

def classify_venue(v: Dict[str, Any]) -> Tuple[str, str]:
    """Classifies a venue into South Mumbai, Eastern Suburbs, or Western Suburbs based on keywords."""
    text = f"{v.get('name', '')} {v.get('address', '')} {v.get('slug', '')}".lower()

    # Check SoBo first
    for kw in SOBO_KEYWORDS:
        if re.search(r'\b' + re.escape(kw) + r'\b', text):
            return "south_mumbai", "South Mumbai"

    # Check Eastern
    for kw in EASTERN_KEYWORDS:
        if re.search(r'\b' + re.escape(kw) + r'\b', text):
            return "eastern_suburbs", "Eastern Suburbs & Central"

    # Check Western
    for kw in WESTERN_KEYWORDS:
        if re.search(r'\b' + re.escape(kw) + r'\b', text):
            return "western_suburbs", "Western Suburbs"

    # Default fallback
    return "western_suburbs", "Western Suburbs"

if __name__ == "__main__":
    cache_path = os.path.join(os.path.dirname(__file__), "venues_cache.json")
    if not os.path.exists(cache_path):
        print(f"File {cache_path} not found.")
        exit(1)

    with open(cache_path, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    counts = {"south_mumbai": 0, "western_suburbs": 0, "eastern_suburbs": 0}

    for v in catalog:
        zone_key, zone_label = classify_venue(v)
        v["zone"] = zone_key
        v["zone_label"] = zone_label
        counts[zone_key] += 1

    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)

    print("Classification Complete:")
    print(f"  • South Mumbai: {counts['south_mumbai']} venues")
    print(f"  • Western Suburbs: {counts['western_suburbs']} venues")
    print(f"  • Eastern Suburbs: {counts['eastern_suburbs']} venues")
    print(f"  Total: {len(catalog)} venues")

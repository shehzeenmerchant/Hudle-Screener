# 🎾 Hudle Mumbai Padel Slot Finder & Booking Tool

A fast, lightweight CLI and automation toolkit to discover, monitor, and query real-time Padel court availability across Mumbai on [Hudle.in](https://hudle.in/venue-search?venueName=&cityId=2&preferred_sports=44).

---

## ⚡ Features (Phase 1)
- **Local Catalog Cache (`venues_cache.json`):** Pre-maps all 49+ Mumbai Padel venues and their individual court UUIDs to eliminate redundant API calls and prevent rate limiting.
- **Smart Querying:** Search available slots by date (`today`, `tomorrow`, or `YYYY-MM-DD`), time window (`19:00-22:00`), area/venue filter (`bandra`, `worli`, `andheri`, `khar`, etc.), and max price.
- **Direct Booking URLs:** Generates one-click direct web links to reserve courts on Hudle.
- **JSON Output:** Pipe live availability directly into bots, notifications (Telegram/WhatsApp), or scripts.

---

## 🚀 Quick Start

## 🤖 Telegram Bot

A complete, zero-dependency Telegram Bot is included in `telegram_bot.py`.

### Setup in 60 Seconds:
1. Open Telegram and search for **[@BotFather](https://t.me/BotFather)**.
2. Send `/newbot`, name your bot (e.g., `MumbaiPadelBot`), and copy the HTTP API Token.
3. Paste the token into `config.json` or export it:
   ```bash
   export TELEGRAM_BOT_TOKEN="your_token_here"
   ```
4. Start the bot:
   ```bash
   python telegram_bot.py
   ```

### Bot Commands:
- `/start` or `/help` — Welcome menu with quick tap buttons.
- `/sobo` — Search South Mumbai prime slots tomorrow (7–10 PM).
- `/west` — Search Western Suburbs prime slots tomorrow (7–10 PM).
- `/east` — Search Eastern Suburbs prime slots tomorrow (7–10 PM).
- `/slots [zone/venue] [date] [time]` — Custom search (e.g. `/slots bandra today 20:00-22:00`).
- `/venues [south/west/east]` — Browse venues with direct links.

---

### 1. List Mumbai Padel Venues (By Zone or Query)
```bash
# List all 49 venues
python hudle_padel.py venues

# Filter by Zone: 'south', 'west', or 'east'
python hudle_padel.py venues --zone south
python hudle_padel.py venues --zone west
python hudle_padel.py venues --zone east

# Search by keyword
python hudle_padel.py venues --query bandra
```

### 2. Fast Zone-Filtered Slot Search
Searching by zone is significantly faster because it only checks venues in that region:
```bash
# Search South Mumbai prime slots tomorrow evening
python hudle_padel.py search --zone south --date tomorrow --time 19:00-22:00

# Search Western Suburbs slots tonight
python hudle_padel.py search --zone west --date today --time 20:00-23:00

# Search Eastern Suburbs slots
python hudle_padel.py search --zone east --date tomorrow --time 18:00-21:00
```

Search tonight's slots with a price cap:
```bash
python hudle_padel.py search --date today --time 18:00-23:00 --max-price 1500
```

Search by exact date:
```bash
python hudle_padel.py search --date 2026-11-10 --time 20:00-22:00 --venue khar
```

Output as JSON (useful for integrations):
```bash
python hudle_padel.py search --date tomorrow --time 19:00-21:00 --venue andheri --json
```

### 3. Refresh Venue Catalog
If new venues open up in Mumbai, sync the cache:
```bash
python hudle_padel.py sync
```

---

## 📁 Project Structure
- `hudle_client.py`: Core API client with automatic retry, backoff, and header injection.
- `sync_catalog.py`: Maps all venues, courts, facilities, and activity IDs into `venues_cache.json`.
- `search.py`: Query engine for slot filtering and ASCII table rendering.
- `hudle_padel.py`: Command-line interface.
- `venues_cache.json`: Cached Mumbai padel venue catalog.

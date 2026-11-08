# 🎾 Hudle Mumbai Padel Slot Finder, Sniper & Booking Tool

A fast, lightweight CLI and automation toolkit to discover, monitor, and query real-time Padel court availability across Mumbai on [Hudle.in](https://hudle.in/venue-search?venueName=&cityId=2&preferred_sports=44).

---

## ⚡ Features

### Phase 1: Slot Search & Discovery
- **Local Catalog Cache (`venues_cache.json`):** Pre-maps all 49+ Mumbai Padel venues (~106 courts) with individual court UUIDs to eliminate redundant API calls and prevent rate limiting.
- **Smart Querying:** Search available slots by date (`today`, `tomorrow`, or `YYYY-MM-DD`), time window (`19:00-22:00`), area/venue filter (`bandra`, `worli`, `andheri`, `khar`, etc.), and max price.
- **Direct Booking URLs:** Generates one-click direct web links to reserve courts on Hudle.
- **JSON Output:** Pipe live availability directly into bots, notifications (Telegram/WhatsApp), or scripts.

### Phase 2: Drop Alert & Cancellation Sniper
- **Real-Time Court Sniper (`sniper.py`):** Background monitor that continuously checks prime slots (e.g., 7:00 PM – 10:00 PM).
- **Instant Telegram Drop Alerts:** Sends immediate notifications with inline booking buttons as soon as someone cancels a prime court slot.
- **Smart Consecutive Pairing:** Automatically detects and pairs consecutive 30-minute slots into full 1-hour sessions.
- **Rate-Limit Resilient:** Safely polls targeted zones or venues within Hudle's 60 req/min sliding window.

### Phase 3: Account Authentication & Auto-Booking Groundwork
- **CLI Login (`hudle_padel.py login`):** Authenticate with your Hudle account to obtain a session JWT token.
- **Booking API Integration:** Direct programmatic court reservations via `HudleClient.create_booking()`.

---

## 🚀 Quick Start

### 1. Installation
Clone the repository and install requirements (standard library only; zero external dependencies required):
```bash
git clone https://github.com/shehzeenmerchant/Hudle-Screener.git
cd Hudle-Screener
```

### 2. Configuration (Optional for Telegram Alerts)
Copy the example configuration:
```bash
cp config.example.json config.json
```
Edit `config.json` or export environment variables:
```json
{
  "telegram_bot_token": "YOUR_BOT_TOKEN_FROM_BOTFATHER",
  "telegram_chat_id": "YOUR_CHAT_ID",
  "hudle_auth_token": ""
}
```

---

## 🤖 Telegram Bot Setup & Deployment

A complete, zero-dependency Telegram Bot is included in `telegram_bot.py`.

### Option A: Run Bot Locally
1. Open Telegram and search for **[@BotFather](https://t.me/BotFather)**.
2. Send `/newbot`, name your bot (e.g., `MumbaiPadelBot`), and copy the HTTP API Token.
3. Export the token or add it to `config.json`:
   ```bash
   export TELEGRAM_BOT_TOKEN="your_token_here"
   ```
4. Start the bot:
   ```bash
   python telegram_bot.py
   ```

### Option B: Deploy to Vercel (Serverless Webhook)
1. Push your repository to GitHub (already configured on `main`).
2. Go to [Vercel](https://vercel.com) and click **"Add New Project"** -> Import `Hudle-Screener`.
3. In Project Settings -> **Environment Variables**, add:
   - `TELEGRAM_BOT_TOKEN`: `<your_bot_token>`
4. Deploy. Once deployed, copy your deployment URL (e.g. `https://hudle-screener.vercel.app`).
5. Register the Telegram webhook by opening this URL in your browser:
   ```
   https://api.telegram.org/bot<YOUR_TOKEN>/setWebhook?url=https://<YOUR_VERCEL_DOMAIN>/api/webhook
   ```
6. You will receive `{"ok":true,"result":true,"description":"Webhook was set"}`. Your bot is now running serverless 24/7!

### Bot Commands:
- `/start` or `/help` — Welcome menu with quick tap buttons.
- `/sobo` — Search South Mumbai prime slots tomorrow (7–10 PM).
- `/west` — Search Western Suburbs prime slots tomorrow (7–10 PM).
- `/east` — Search Eastern Suburbs prime slots tomorrow (7–10 PM).
- `/slots [zone/venue] [date] [time]` — Custom search (e.g. `/slots bandra today 20:00-22:00`).
- `/sniper` — Get your Chat ID and instructions to start instant drop alerts.
- `/venues [south/west/east]` — Browse venues with direct links.

---

## 🎯 Court Sniper & Drop Alerts (Phase 2)

Never miss a prime evening slot when another player cancels!

```bash
# Monitor South Mumbai prime slots (7 PM - 10 PM) tomorrow with Telegram alerts:
python sniper.py --zone south --date tomorrow --time 19:00-22:00 --chat-id YOUR_CHAT_ID

# Monitor Bandra / Khar courts tonight:
python sniper.py --venue bandra --date today --time 19:00-23:00 --interval 45

# Or use via main CLI:
python hudle_padel.py sniper --zone south --date tomorrow --time 19:00-22:00
```

When a court is cancelled or becomes available, you'll immediately hear a terminal sound bell and receive a Telegram alert with a 1-tap booking button!

---

## 🔍 CLI Usage & Examples

### 1. Search Open Slots
```bash
# Search South Mumbai prime slots tomorrow evening
python hudle_padel.py search --zone south --date tomorrow --time 19:00-22:00

# Search Western Suburbs slots tonight
python hudle_padel.py search --zone west --date today --time 20:00-23:00

# Search Bandra venues with a price cap
python hudle_padel.py search --venue bandra --date tomorrow --time 18:00-22:00 --max-price 2000

# Output results as JSON (ideal for piping into scripts)
python hudle_padel.py search --venue worli --date tomorrow --time 19:00-22:00 --json
```

### 2. Browse Venues by Geographic Zone
```bash
# List all 49 Mumbai venues
python hudle_padel.py venues

# List by Zone
python hudle_padel.py venues --zone south
python hudle_padel.py venues --zone west
python hudle_padel.py venues --zone east

# Search venue by name
python hudle_padel.py venues --query "padel 360"
```

### 3. Log In to Hudle Account (Phase 3)
```bash
python hudle_padel.py login
```
Securely saves your session JWT token into `config.json` for automated bookings.

### 4. Sync Venue Catalog
If new padel clubs open up across Mumbai, update the local cache:
```bash
python hudle_padel.py sync
```

---

## 🗺️ Mumbai Geographic Zones

To prevent triggering Hudle's 60 req/min rate limit during city-wide searches, the 49 venues are organized into 3 zones:

1. **South Mumbai (`--zone south` / `/sobo`):** 19 venues (Worli, Lower Parel, Byculla, Mazgaon, Dadar, Marine Lines, Colaba, Malabar Hill).
2. **Western Suburbs (`--zone west` / `/west`):** 23 venues (Bandra, Khar, Juhu, Vile Parle, Andheri, Lokhandwala, Goregaon, Kandivali).
3. **Eastern Suburbs & Central (`--zone east` / `/east`):** 7 venues (Powai, Ghatkopar, Vikhroli, Bhandup, Mulund).

---

## 📁 Repository Structure
```
├── hudle_client.py     # Resilient API client with rate limit retry & auth
├── search.py           # Slot search query engine and table renderer
├── sniper.py           # Drop Alert & Cancellation Sniper monitor
├── hudle_padel.py      # Unified CLI tool (search, sniper, venues, sync, login)
├── telegram_bot.py     # Zero-dependency interactive Telegram Bot
├── sync_catalog.py     # Venue & court catalog builder
├── venues_cache.json   # 49 Mumbai padel venues & 106 courts mapped
├── api/
│   └── webhook.py      # Serverless Telegram webhook handler for Vercel
├── vercel.json         # Vercel serverless deployment routing
└── config.example.json # Configuration template
```

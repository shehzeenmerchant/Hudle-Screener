import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from hudle_client import HudleClient
from search import format_time_12hr, normalize_zone, parse_date, parse_time_window, search_slots
from sync_catalog import load_cached_catalog

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")
CTX = ssl.create_default_context()

def load_config() -> Dict[str, str]:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"telegram_bot_token": os.environ.get("TELEGRAM_BOT_TOKEN", "")}

def save_config(cfg: Dict[str, str]):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

class TelegramBot:
    def __init__(self, token: str):
        self.token = token.strip()
        self.api_url = f"https://api.telegram.org/bot{self.token}"
        self.last_update_id = 0
        self.client = HudleClient(delay_between_requests=0.15)

    def _api_call(self, method: str, data: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        url = f"{self.api_url}/{method}"
        req_data = None
        headers = {"Content-Type": "application/json"}
        if data:
            req_data = json.dumps(data).encode("utf-8")

        try:
            req = urllib.request.Request(url, data=req_data, headers=headers)
            with urllib.request.urlopen(req, context=CTX, timeout=35) as r:
                res = json.loads(r.read().decode("utf-8"))
                if res.get("ok"):
                    return res.get("result")
                print(f"Telegram API Error: {res}")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="ignore") if hasattr(e, "read") else ""
            print(f"Telegram HTTP {e.code}: {body}")
        except Exception as e:
            print(f"Telegram Call Error: {e}")
        return None

    def send_message(self, chat_id: int, text: str, reply_markup: Optional[Dict[str, Any]] = None, parse_mode: str = "HTML"):
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        return self._api_call("sendMessage", payload)

    def set_commands(self):
        commands = [
            {"command": "sobo", "description": "South Mumbai prime slots tomorrow (7-10 PM)"},
            {"command": "west", "description": "Western Suburbs prime slots tomorrow (7-10 PM)"},
            {"command": "east", "description": "Eastern Suburbs prime slots tomorrow (7-10 PM)"},
            {"command": "slots", "description": "Search slots: /slots [zone/venue] [date] [time]"},
            {"command": "sniper", "description": "Setup drop & cancellation alerts for your chat"},
            {"command": "venues", "description": "List venues: /venues [south/west/east]"},
            {"command": "help", "description": "Show usage instructions"}
        ]
        self._api_call("setMyCommands", {"commands": commands})

    def handle_start(self, chat_id: int, user_first_name: str):
        text = (
            f"👋 <b>Hey {user_first_name}! Welcome to Mumbai Padel Finder.</b>\n\n"
            "I scan all 49+ Mumbai Padel courts across <b>South Mumbai, Western Suburbs & Eastern Suburbs</b> in real time on Hudle.\n\n"
            "⚡ <b>Quick Shortcuts:</b>\n"
            "• /sobo — South Mumbai slots tomorrow (7-10 PM)\n"
            "• /west — Western Suburbs slots tomorrow (7-10 PM)\n"
            "• /east — Eastern Suburbs slots tomorrow (7-10 PM)\n\n"
            "🔍 <b>Custom Search:</b>\n"
            "<code>/slots [zone/venue] [date] [time]</code>\n"
            "<i>Examples:</i>\n"
            "• <code>/slots south tomorrow 19:00-22:00</code>\n"
            "• <code>/slots bandra today 20:00-22:00</code>\n"
            "• <code>/slots mazgaon tomorrow</code>\n\n"
            "Tap a quick button below to start:"
        )
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "🎾 South Mumbai (Tomorrow 7-10 PM)", "callback_data": "search:south:tomorrow:19:00-22:00"},
                ],
                [
                    {"text": "🎾 Western Suburbs (Tomorrow 7-10 PM)", "callback_data": "search:west:tomorrow:19:00-22:00"},
                ],
                [
                    {"text": "🎾 Eastern Suburbs (Tomorrow 7-10 PM)", "callback_data": "search:east:tomorrow:19:00-22:00"},
                ],
                [
                    {"text": "📍 View All Venues", "callback_data": "venues:all"}
                ]
            ]
        }
        self.send_message(chat_id, text, reply_markup=keyboard)

    def handle_sniper_info(self, chat_id: int):
        text = (
            "🎯 <b>Court Drop Alert & Sniper</b>\n\n"
            f"Your Telegram Chat ID: <code>{chat_id}</code>\n\n"
            "To receive instant Telegram alerts whenever prime slots (7–10 PM) open up on cancellations, run on your computer or VPS:\n\n"
            f"<code>python sniper.py --zone south --chat-id {chat_id}</code>\n\n"
            "<i>Or monitor specific suburbs:</i>\n"
            f"• Bandra: <code>python sniper.py --venue bandra --chat-id {chat_id}</code>\n"
            f"• Worli/Lower Parel: <code>python sniper.py --venue worli --chat-id {chat_id}</code>\n"
        )
        self.send_message(chat_id, text)

    def handle_venues(self, chat_id: int, zone_arg: Optional[str] = None):
        catalog = load_cached_catalog()
        norm_z = normalize_zone(zone_arg) if zone_arg else None
        if norm_z:
            catalog = [v for v in catalog if v.get("zone") == norm_z]

        zone_title = f" ({norm_z.replace('_', ' ').title()})" if norm_z else ""
        msg = f"🎾 <b>Mumbai Padel Venues{zone_title} ({len(catalog)} venues):</b>\n\n"

        for idx, v in enumerate(catalog[:15], 1):
            courts_count = len(v.get("courts", []))
            addr = v.get("address") or "Mumbai"
            url = v.get("share_url") or "https://hudle.in"
            msg += f"<b>{idx}. <a href='{url}'>{v['name']}</a></b> ({courts_count} courts)\n📍 <i>{addr[:50]}</i>\n\n"

        if len(catalog) > 15:
            msg += f"<i>...and {len(catalog) - 15} more venues. Use /venues [south/west/east] to filter.</i>"

        self.send_message(chat_id, msg)

    def execute_search(self, chat_id: int, zone_filter: Optional[str] = None, venue_filter: Optional[str] = None, date_input: str = "tomorrow", time_window: str = "19:00-22:00"):
        try:
            target_date = parse_date(date_input)
        except Exception:
            target_date = parse_date("tomorrow")

        area_label = zone_filter or venue_filter or "Mumbai"
        self.send_message(chat_id, f"🔎 <i>Scanning courts in <b>{area_label.title()}</b> for {target_date} ({time_window})...</i>")

        try:
            slots = search_slots(
                date_str=target_date,
                time_window=time_window,
                venue_filter=venue_filter,
                zone_filter=zone_filter,
                client=self.client
            )
        except Exception as e:
            self.send_message(chat_id, f"⚠️ Error querying slots: {e}")
            return

        if not slots:
            self.send_message(
                chat_id,
                f"❌ <b>No available slots found</b> matching your criteria in <b>{area_label.title()}</b> for {target_date} ({time_window})."
            )
            return

        # Sort slots chronologically
        slots.sort(key=lambda s: (s["start_time"], s["price"]))

        msg = f"🎾 <b>Found {len(slots)} Open Slot(s) for {target_date}:</b>\n\n"
        buttons = []

        for s in slots[:10]:
            t_start = format_time_12hr(s["start_time"])
            t_end = format_time_12hr(s["end_time"])
            v_name = s["venue_name"]
            c_name = s["court_name"]
            price = int(s["price"])
            url = s["share_url"]

            msg += f"• <b>{t_start} – {t_end}</b> | <b>₹{price}</b>\n  🏟 <b>{v_name}</b> ({c_name})\n\n"
            buttons.append([{"text": f"Book {v_name[:20]} ({t_start})", "url": url}])

        if len(slots) > 10:
            msg += f"<i>...showing top 10 of {len(slots)} slots.</i>"

        reply_markup = {"inline_keyboard": buttons} if buttons else None
        self.send_message(chat_id, msg, reply_markup=reply_markup)

    def process_message(self, message: Dict[str, Any]):
        chat_id = message.get("chat", {}).get("id")
        text = message.get("text", "").strip()
        first_name = message.get("from", {}).get("first_name", "Player")

        if not text or not chat_id:
            return

        # Commands
        if text.startswith("/start") or text.startswith("/help"):
            self.handle_start(chat_id, first_name)
        elif text.startswith("/sobo"):
            self.execute_search(chat_id, zone_filter="south", date_input="tomorrow", time_window="19:00-22:00")
        elif text.startswith("/west"):
            self.execute_search(chat_id, zone_filter="west", date_input="tomorrow", time_window="19:00-22:00")
        elif text.startswith("/east"):
            self.execute_search(chat_id, zone_filter="east", date_input="tomorrow", time_window="19:00-22:00")
        elif text.startswith("/sniper") or text.startswith("/id") or text.startswith("/alert"):
            self.handle_sniper_info(chat_id)
        elif text.startswith("/venues"):
            parts = text.split()
            zone = parts[1] if len(parts) > 1 else None
            self.handle_venues(chat_id, zone)
        elif text.startswith("/slots"):
            parts = text.split()
            # Usage: /slots [zone/venue] [date] [time]
            zone_or_venue = parts[1] if len(parts) > 1 else "south"
            date_arg = parts[2] if len(parts) > 2 else "tomorrow"
            time_arg = parts[3] if len(parts) > 3 else "19:00-22:00"

            norm_zone = normalize_zone(zone_or_venue)
            if norm_zone:
                self.execute_search(chat_id, zone_filter=norm_zone, date_input=date_arg, time_window=time_arg)
            else:
                self.execute_search(chat_id, venue_filter=zone_or_venue, date_input=date_arg, time_window=time_arg)
        else:
            # Fallback simple search: if user types "bandra" or "mazgaon"
            low = text.lower()
            if any(k in low for k in ["south", "sobo", "west", "east"]):
                norm_zone = normalize_zone(low)
                self.execute_search(chat_id, zone_filter=norm_zone, date_input="tomorrow", time_window="19:00-22:00")
            else:
                self.execute_search(chat_id, venue_filter=text, date_input="tomorrow", time_window="19:00-22:00")

    def process_callback_query(self, cb: Dict[str, Any]):
        cb_id = cb.get("id")
        data = cb.get("data", "")
        message = cb.get("message", {})
        chat_id = message.get("chat", {}).get("id")

        # Acknowledge callback query
        self._api_call("answerCallbackQuery", {"callback_query_id": cb_id})

        if not chat_id:
            return

        if data.startswith("search:"):
            # Format: search:zone:date:time
            _, zone, date_str, time_str = data.split(":")
            self.execute_search(chat_id, zone_filter=zone, date_input=date_str, time_window=time_str)
        elif data.startswith("venues:"):
            _, zone = data.split(":")
            self.handle_venues(chat_id, None if zone == "all" else zone)

    def run(self):
        print("🤖 Setting Telegram Bot commands...")
        self.set_commands()
        print("🚀 Telegram Bot is running! Waiting for messages...")

        while True:
            try:
                updates = self._api_call("getUpdates", {
                    "offset": self.last_update_id + 1,
                    "timeout": 20
                })
                if updates:
                    for u in updates:
                        self.last_update_id = u["update_id"]
                        if "message" in u:
                            self.process_message(u["message"])
                        elif "callback_query" in u:
                            self.process_callback_query(u["callback_query"])
            except Exception as e:
                print(f"Polling error: {e}")
                time.sleep(2)

def main():
    cfg = load_config()
    token = cfg.get("telegram_bot_token")

    if not token or token == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        print("=" * 60)
        print("⚙️ TELEGRAM BOT SETUP")
        print("=" * 60)
        print("To run the bot, you need a free Bot Token from Telegram.")
        print("\nHow to get it in 30 seconds:")
        print("1. Open Telegram and search for '@BotFather'")
        print("2. Send '/newbot' and follow prompts to name your bot")
        print("3. Copy the API Token (e.g. 123456789:ABCdefGHI...)")
        print("=" * 60)
        
        entered_token = input("\nEnter your Telegram Bot Token: ").strip()
        if not entered_token:
            print("No token provided. Exiting.")
            sys.exit(1)
        cfg["telegram_bot_token"] = entered_token
        save_config(cfg)
        token = entered_token

    bot = TelegramBot(token)
    bot.run()

if __name__ == "__main__":
    main()

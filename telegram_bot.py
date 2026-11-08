import html
import json
import ssl
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

import config
from hudle_client import HudleClient
from search import format_time_12hr, normalize_zone, parse_date, search_slots
from sync_catalog import load_cached_catalog

CTX = ssl.create_default_context()

class TelegramBot:
    def __init__(self, token: str):
        self.token = token.strip()
        self.api_url = f"https://api.telegram.org/bot{self.token}"
        self.last_update_id = 0
        self.client = HudleClient(delay_between_requests=0.03)

    def _api_call(self, method: str, data: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        url = f"{self.api_url}/{method}"
        req_data = None
        headers = {"Content-Type": "application/json"}
        if data:
            req_data = json.dumps(data).encode("utf-8")

        try:
            req = urllib.request.Request(url, data=req_data, headers=headers)
            with urllib.request.urlopen(req, context=CTX, timeout=30) as r:
                res = json.loads(r.read().decode("utf-8"))
                if res.get("ok"):
                    return res.get("result")
                print(f"Telegram API Error: {res}", file=sys.stderr)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="ignore") if hasattr(e, "read") else ""
            print(f"Telegram HTTP {e.code}: {body}", file=sys.stderr)
        except Exception as e:
            print(f"Telegram Call Error: {e}", file=sys.stderr)
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
            {"command": "slots", "description": "Search slots: /slots [suburb/venue] [date] [time]"},
            {"command": "venues", "description": "List venues: /venues [south/west/east]"},
            {"command": "help", "description": "Show usage instructions"}
        ]
        if config.is_phase2_enabled():
            commands.insert(4, {"command": "sniper", "description": "Setup drop & cancellation alerts for your chat"})
        self._api_call("setMyCommands", {"commands": commands})

    def handle_start(self, chat_id: int, user_first_name: str):
        safe_name = html.escape(user_first_name)
        text = (
            f"👋 <b>Hey {safe_name}! Welcome to Mumbai Padel Finder.</b>\n\n"
            "I scan Mumbai Padel courts across <b>South Mumbai, Western Suburbs & Eastern Suburbs</b> in real time on Hudle.\n\n"
            "⚡ <b>Instant Hotspot Shortcuts (Tomorrow 7–10 PM):</b>\n"
            "• Tap below for fast instant results:\n\n"
            "🔍 <b>Custom Suburb / Venue Search:</b>\n"
            "<code>/slots [venue/suburb] [date] [time]</code>\n"
            "<i>Examples:</i>\n"
            "• <code>/slots mazgaon tomorrow</code>\n"
            "• <code>/slots worli tomorrow 19:00-22:00</code>\n"
            "• <code>/slots bandra today 20:00-22:00</code>\n"
            "• <code>/sobo</code> or <code>/west</code>"
        )
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "🎾 Mazgaon (Tomorrow 7-10 PM)", "callback_data": "search:venue:mazgaon:tomorrow:19:00-22:00"},
                    {"text": "🎾 Worli (Tomorrow 7-10 PM)", "callback_data": "search:venue:worli:tomorrow:19:00-22:00"},
                ],
                [
                    {"text": "🎾 Bandra (Tomorrow 7-10 PM)", "callback_data": "search:venue:bandra:tomorrow:19:00-22:00"},
                    {"text": "🎾 Ranibaug (Tomorrow 7-10 PM)", "callback_data": "search:venue:ranibaug:tomorrow:19:00-22:00"},
                ],
                [
                    {"text": "🎾 South Mumbai (Top Courts)", "callback_data": "search:zone:south:tomorrow:19:00-22:00"},
                    {"text": "🎾 Western Suburbs (Top Courts)", "callback_data": "search:zone:west:tomorrow:19:00-22:00"},
                ],
                [
                    {"text": "📍 View All 49 Venues", "callback_data": "venues:all"}
                ]
            ]
        }
        self.send_message(chat_id, text, reply_markup=keyboard)

    def handle_sniper_info(self, chat_id: int):
        if not config.is_phase2_enabled():
            self.send_message(
                chat_id,
                "ℹ️ <b>Phase 2 (Court Sniper & Drop Alerts)</b> is currently disabled.\n\n"
                "This feature can be activated by setting <code>ENABLE_PHASE2=true</code> in your environment or configuration."
            )
            return

        text = (
            "🎯 <b>Court Drop Alert & Sniper</b>\n\n"
            f"Your Telegram Chat ID: <code>{chat_id}</code>\n\n"
            "To receive instant Telegram alerts whenever prime slots (7–10 PM) open up on cancellations, run on your computer or VPS:\n\n"
            f"<code>python sniper.py --enable --zone south --chat-id {chat_id}</code>\n\n"
            "<i>Or monitor specific suburbs:</i>\n"
            f"• Bandra: <code>python sniper.py --enable --venue bandra --chat-id {chat_id}</code>\n"
            f"• Worli/Lower Parel: <code>python sniper.py --enable --venue worli --chat-id {chat_id}</code>\n"
        )
        self.send_message(chat_id, text)

    def handle_venues(self, chat_id: int, zone_arg: Optional[str] = None):
        catalog = load_cached_catalog()
        norm_z = normalize_zone(zone_arg) if zone_arg else None
        if norm_z:
            catalog = [v for v in catalog if v.get("zone") == norm_z]

        zone_title = f" ({html.escape(norm_z.replace('_', ' ').title())})" if norm_z else ""
        msg = f"🎾 <b>Mumbai Padel Venues{zone_title} ({len(catalog)} venues):</b>\n\n"

        for idx, v in enumerate(catalog[:15], 1):
            courts_count = len(v.get("courts", []))
            addr = v.get("address") or "Mumbai"
            url = v.get("share_url") or "https://hudle.in"
            safe_name = html.escape(v.get("name", "Unknown Venue"))
            safe_addr = html.escape(addr[:50])
            msg += f"<b>{idx}. <a href='{url}'>{safe_name}</a></b> ({courts_count} courts)\n📍 <i>{safe_addr}</i>\n\n"

        if len(catalog) > 15:
            msg += f"<i>...and {len(catalog) - 15} more venues. Use /venues [south/west/east] to filter.</i>"

        self.send_message(chat_id, msg)

    def execute_search(
        self,
        chat_id: int,
        zone_filter: Optional[str] = None,
        venue_filter: Optional[str] = None,
        date_input: str = "tomorrow",
        time_window: str = "19:00-22:00"
    ):
        try:
            target_date = parse_date(date_input)
        except Exception:
            target_date = parse_date("tomorrow")

        area_label = venue_filter or zone_filter or "Mumbai"
        safe_area = html.escape(area_label.title())
        safe_time = html.escape(time_window)

        # Notify user that search is commencing
        self.send_message(chat_id, f"🔎 <i>Scanning courts in <b>{safe_area}</b> for {target_date} ({safe_time})...</i>")

        # Cap max_venues for broad zone scans to keep serverless execution under 2.5s
        max_v = 2 if (zone_filter and not venue_filter) else None

        try:
            slots = search_slots(
                date_str=target_date,
                time_window=time_window,
                venue_filter=venue_filter,
                zone_filter=zone_filter,
                max_venues=max_v,
                client=self.client
            )
        except Exception as e:
            self.send_message(chat_id, f"⚠️ Error querying slots: {html.escape(str(e))}")
            return

        if not slots:
            self.send_message(
                chat_id,
                f"❌ <b>No available slots found</b> matching your criteria in <b>{safe_area}</b> for {target_date} ({safe_time}).\n\n"
                "💡 <i>Tip: Try another time or specific suburb e.g. <code>/slots mazgaon tomorrow</code></i>"
            )
            return

        # Sort slots chronologically
        slots.sort(key=lambda s: (s["start_time"], s["price"]))

        msg = f"🎾 <b>Found {len(slots)} Open Slot(s) for {target_date}:</b>\n\n"
        buttons = []

        for s in slots[:8]:
            t_start = format_time_12hr(s["start_time"])
            t_end = format_time_12hr(s["end_time"])
            v_name = s["venue_name"]
            c_name = s["court_name"]
            price = int(s["price"])
            url = s["share_url"]

            safe_v = html.escape(v_name)
            safe_c = html.escape(c_name)

            msg += f"• <b>{t_start} – {t_end}</b> | <b>₹{price}</b>\n  🏟 <b>{safe_v}</b> ({safe_c})\n\n"
            buttons.append([{"text": f"Book {v_name[:20]} ({t_start})", "url": url}])

        if len(slots) > 8:
            msg += f"<i>...showing top 8 of {len(slots)} slots.</i>"

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
            zone_or_venue = parts[1] if len(parts) > 1 else "mazgaon"
            date_arg = parts[2] if len(parts) > 2 else "tomorrow"
            time_arg = parts[3] if len(parts) > 3 else "19:00-22:00"

            norm_zone = normalize_zone(zone_or_venue)
            if norm_zone:
                self.execute_search(chat_id, zone_filter=norm_zone, date_input=date_arg, time_window=time_arg)
            else:
                self.execute_search(chat_id, venue_filter=zone_or_venue, date_input=date_arg, time_window=time_arg)
        else:
            # Fallback simple search: if user types "bandra", "mazgaon", "sobo"
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

        # Acknowledge callback query to stop Telegram loading spinner
        self._api_call("answerCallbackQuery", {"callback_query_id": cb_id})

        if not chat_id:
            return

        if data.startswith("search:"):
            # Format: search:type:filter:date:time
            parts = data.split(":")
            if len(parts) == 5:
                _, mode, filter_val, date_str, time_str = parts
                if mode == "venue":
                    self.execute_search(chat_id, venue_filter=filter_val, date_input=date_str, time_window=time_str)
                else:
                    self.execute_search(chat_id, zone_filter=filter_val, date_input=date_str, time_window=time_str)
            elif len(parts) == 4:
                _, zone, date_str, time_str = parts
                self.execute_search(chat_id, zone_filter=zone, date_input=date_str, time_window=time_str)
        elif data.startswith("venues:"):
            parts = data.split(":")
            zone = parts[1] if len(parts) > 1 else "all"
            self.handle_venues(chat_id, None if zone == "all" else zone)

    def run(self):
        print("🤖 Setting Telegram Bot commands...")
        self.set_commands()
        print("🚀 Telegram Bot is running via Long Polling! Waiting for messages...")

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
                print(f"Polling error: {e}", file=sys.stderr)
                time.sleep(2)

def main():
    token = config.get_bot_token()

    if not token:
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
        config.save_config({"telegram_bot_token": entered_token})
        token = entered_token

    bot = TelegramBot(token)
    bot.run()

if __name__ == "__main__":
    main()

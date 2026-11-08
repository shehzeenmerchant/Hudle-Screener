import json
import os
import sys
from http.server import BaseHTTPRequestHandler

# Add root directory to sys.path so it can import hudle_client, search, etc.
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
for d in [current_dir, parent_dir, "/var/task", os.getcwd()]:
    if d not in sys.path:
        sys.path.insert(0, d)

DEFAULT_BOT_TOKEN = "8626370353:AAE5AlaX2d_tqjCqpcVFWkf6yGhKj6lLcek"

try:
    from telegram_bot import TelegramBot, load_config
    IMPORT_ERROR = None
except Exception as e:
    IMPORT_ERROR = str(e)

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        if IMPORT_ERROR:
            self.wfile.write(f"Mumbai Padel Bot (Import Warning: {IMPORT_ERROR})".encode("utf-8"))
        else:
            self.wfile.write(b"Mumbai Padel Telegram Bot is running!")

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else b""
        
        cfg = load_config() if not IMPORT_ERROR else {}
        token = os.environ.get("TELEGRAM_BOT_TOKEN") or cfg.get("telegram_bot_token") or DEFAULT_BOT_TOKEN
        
        if not token:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b"TELEGRAM_BOT_TOKEN environment variable not set")
            return

        try:
            if IMPORT_ERROR:
                raise RuntimeError(f"Dependencies failed to load: {IMPORT_ERROR}")

            update = json.loads(post_data.decode("utf-8"))
            bot = TelegramBot(token)

            if "message" in update:
                bot.process_message(update["message"])
            elif "callback_query" in update:
                bot.process_callback_query(update["callback_query"])

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode("utf-8"))
        except Exception as e:
            print(f"Webhook error: {e}")
            self.send_response(200) # Always return 200 to Telegram so it doesn't repeatedly retry
            self.end_headers()
            self.wfile.write(b"OK")

import json
import os
import sys
from http.server import BaseHTTPRequestHandler

# Add root directory to sys.path so it can import hudle_client, search, etc.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram_bot import TelegramBot, load_config

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Mumbai Padel Telegram Bot is running!")

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length)
        
        cfg = load_config()
        token = os.environ.get("TELEGRAM_BOT_TOKEN") or cfg.get("telegram_bot_token")
        
        if not token:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b"TELEGRAM_BOT_TOKEN environment variable not set")
            return

        try:
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

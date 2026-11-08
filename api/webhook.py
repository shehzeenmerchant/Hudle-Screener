import json
import os
import sys
from http.server import BaseHTTPRequestHandler

# Add root directory to sys.path so serverless handlers can import modules
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
for d in [current_dir, parent_dir, "/var/task", os.getcwd()]:
    if d not in sys.path:
        sys.path.insert(0, d)

try:
    import config
    from telegram_bot import TelegramBot
    IMPORT_ERROR = None
except Exception as e:
    IMPORT_ERROR = str(e)

# In-memory deduplication set to prevent Telegram from looping retries
PROCESSED_UPDATES = set()

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        if IMPORT_ERROR:
            self.wfile.write(f"Mumbai Padel Bot (Import Warning: {IMPORT_ERROR})".encode("utf-8"))
        else:
            self.wfile.write(b"Mumbai Padel Telegram Bot webhook is active and healthy.")

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else b""

        token = config.get_bot_token() if not IMPORT_ERROR else None

        if not token:
            print("Warning: TELEGRAM_BOT_TOKEN is not set in environment or config.json", file=sys.stderr)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"error","message":"TELEGRAM_BOT_TOKEN not configured"}')
            return

        try:
            if not IMPORT_ERROR and post_data:
                update = json.loads(post_data.decode("utf-8"))
                update_id = update.get("update_id")

                # De-duplicate: if Telegram retries the same update, acknowledge and drop it immediately
                if update_id and update_id in PROCESSED_UPDATES:
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"status":"already_processed"}')
                    return

                if update_id:
                    PROCESSED_UPDATES.add(update_id)
                    if len(PROCESSED_UPDATES) > 1000:
                        PROCESSED_UPDATES.clear()

                bot = TelegramBot(token)

                if "message" in update:
                    bot.process_message(update["message"])
                elif "callback_query" in update:
                    bot.process_callback_query(update["callback_query"])
        except Exception as e:
            print(f"Webhook processing error: {e}", file=sys.stderr)

        # Always respond HTTP 200 OK so Telegram registers delivery
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status":"ok"}')

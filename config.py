import json
import os
import sys
from typing import Any, Dict, Optional

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

def _read_raw_file_config() -> Dict[str, Any]:
    """Reads raw configuration from config.json if it exists."""
    possible_paths = [
        CONFIG_FILE,
        os.path.join(os.getcwd(), "config.json"),
        "/var/task/config.json"
    ]
    for path in possible_paths:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
    return {}

def load_config() -> Dict[str, Any]:
    """
    Loads unified configuration with environment variable precedence:
    Environment variables override config.json values.
    """
    file_cfg = _read_raw_file_config()

    cfg: Dict[str, Any] = {
        "telegram_bot_token": os.environ.get("TELEGRAM_BOT_TOKEN") or file_cfg.get("telegram_bot_token", ""),
        "telegram_chat_id": os.environ.get("TELEGRAM_CHAT_ID") or file_cfg.get("telegram_chat_id", ""),
        "hudle_auth_token": os.environ.get("HUDLE_AUTH_TOKEN") or file_cfg.get("hudle_auth_token", ""),
        "enable_phase2_sniper": _str_to_bool(os.environ.get("ENABLE_PHASE2")) if "ENABLE_PHASE2" in os.environ else bool(file_cfg.get("enable_phase2_sniper", False)),
        "enable_phase3_autobook": _str_to_bool(os.environ.get("ENABLE_PHASE3")) if "ENABLE_PHASE3" in os.environ else bool(file_cfg.get("enable_phase3_autobook", False)),
    }
    return cfg

def save_config(updates: Dict[str, Any]) -> bool:
    """
    Saves or updates configuration in config.json with secure 0o600 permissions.
    Returns True on success, False if filesystem is read-only.
    """
    current = _read_raw_file_config()
    current.update(updates)

    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(current, f, indent=2)
        try:
            os.chmod(CONFIG_FILE, 0o600)
        except OSError:
            pass
        return True
    except OSError as e:
        # Graceful handling for read-only filesystems (e.g., serverless Lambda/Vercel)
        print(f"Warning: Could not save configuration to disk: {e}", file=sys.stderr)
        return False

def _str_to_bool(val: Optional[str]) -> bool:
    if not val:
        return False
    return val.strip().lower() in ("1", "true", "yes", "on")

def get_bot_token() -> Optional[str]:
    cfg = load_config()
    token = cfg.get("telegram_bot_token", "").strip()
    return token if token and token != "YOUR_TELEGRAM_BOT_TOKEN_HERE" else None

def get_chat_id() -> Optional[str]:
    cfg = load_config()
    chat_id = str(cfg.get("telegram_chat_id", "")).strip()
    return chat_id if chat_id and chat_id != "YOUR_CHAT_ID_FOR_ALERTS_HERE" else None

def get_auth_token() -> Optional[str]:
    cfg = load_config()
    token = cfg.get("hudle_auth_token", "").strip()
    return token if token and token != "OPTIONAL_JWT_TOKEN_FOR_AUTO_BOOKING" else None

def is_phase2_enabled() -> bool:
    cfg = load_config()
    return bool(cfg.get("enable_phase2_sniper", False))

def is_phase3_enabled() -> bool:
    cfg = load_config()
    return bool(cfg.get("enable_phase3_autobook", False))

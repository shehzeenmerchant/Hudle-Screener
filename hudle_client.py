import json
import ssl
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

BASE_URL = "https://api.hudle.in/api/v1"
HEADERS = {
    "Api-Secret": "hudle-api1798@prod",
    "x-device-source": "3",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
CTX = ssl.create_default_context()

class HudleClient:
    def __init__(self, delay_between_requests: float = 0.3, auth_token: Optional[str] = None):
        self.delay = delay_between_requests
        self.auth_token = auth_token

    def set_auth_token(self, token: str):
        self.auth_token = token.strip() if token else None

    def _request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        method: str = "GET",
        payload: Optional[Dict[str, Any]] = None,
        max_retries: int = 5
    ) -> Dict[str, Any]:
        url = f"{BASE_URL}/{endpoint.lstrip('/')}"
        if params:
            query = "&".join(f"{k}={v}" for k, v in params.items())
            url = f"{url}?{query}" if "?" not in url else f"{url}&{query}"

        headers = dict(HEADERS)
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        data_bytes = None
        if payload is not None:
            data_bytes = json.dumps(payload).encode("utf-8")

        for attempt in range(max_retries):
            try:
                time.sleep(self.delay)
                req = urllib.request.Request(url, data=data_bytes, headers=headers, method=method)
                with urllib.request.urlopen(req, context=CTX, timeout=15) as r:
                    return json.loads(r.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    retry_after = e.headers.get("Retry-After")
                    wait_time = int(retry_after) if retry_after and retry_after.isdigit() else max(5, (attempt + 1) * 8)
                    print(f"⚠️  Rate limited (429). Waiting {wait_time}s before retry (attempt {attempt + 1}/{max_retries})...")
                    time.sleep(wait_time)
                else:
                    body = e.read().decode("utf-8", errors="ignore") if hasattr(e, "read") else ""
                    # Don't spam stack traces for expected validation/auth errors
                    if e.code not in (400, 401, 422):
                        print(f"HTTP {e.code} for {url}: {body[:200]}")
                    try:
                        err_json = json.loads(body)
                        return err_json
                    except Exception:
                        raise
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                time.sleep(2)
        raise RuntimeError(f"Max retries exceeded for {url}")

    def get_venues(self, city_id: int = 2, sport_id: int = 44, per_page: int = 50) -> List[Dict[str, Any]]:
        """Fetch all venues for a city and sport (City 2 = Mumbai, Sport 44 = Padel)."""
        data = self._request("venue-search", {"cityId": city_id, "preferred_sports": sport_id, "page": 1, "per_page": per_page})
        return data.get("data", [])

    def get_venue_details(self, venue_id: str) -> Dict[str, Any]:
        """Fetch complete venue details including activities and court facilities."""
        data = self._request(f"venues/{venue_id}", {"includes": "facilities,activities,activities.facilities"})
        return data.get("data", {})

    def get_slots(self, venue_id: str, facility_uuid: str, date_str: str) -> List[Dict[str, Any]]:
        """Fetch slots for a specific venue, court, and date (YYYY-MM-DD)."""
        endpoint = f"web/venues/{venue_id}/facilities/{facility_uuid}/slots"
        params = {"start_date": date_str, "end_date": date_str, "grid": 1}
        data = self._request(endpoint, params)
        slot_data = data.get("data", {}).get("slot_data", [])
        if slot_data:
            return slot_data[0].get("slots", [])
        return []

    def login(self, email: str, password: str) -> Dict[str, Any]:
        """Authenticate user and retrieve JWT token."""
        res = self._request("login", method="POST", payload={"email": email, "password": password})
        if res.get("token"):
            self.set_auth_token(res["token"])
        elif res.get("data", {}).get("token"):
            self.set_auth_token(res["data"]["token"])
        return res

    def create_booking(self, venue_id: str, facility_id: int, booking_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Reserve a court slot via Hudle booking endpoint."""
        if not self.auth_token:
            raise ValueError("Authentication token required for booking. Set auth_token first.")
        endpoint = f"venues/{venue_id}/facilities/{facility_id}/bookings/new"
        return self._request(endpoint, method="POST", payload=booking_payload)

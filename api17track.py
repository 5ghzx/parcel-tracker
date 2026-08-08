"""Thin client for the 17TRACK Tracking API (https://api.17track.net).

This is what commercial aggregator apps (17TRACK, Parcel, etc.) are built
on top of: one API that auto-detects the carrier from the tracking number
and normalizes ~3000 carriers' tracking events into one schema.

Free tier: 100 tracking numbers/month for testing. Get a key at
https://features.17track.net/en/api (Settings -> Security -> Access Key).
The app stores the key locally only (storage.settings table) - never
bundled, never sent anywhere but 17TRACK's API.
"""
import requests
import storage

BASE = "https://api.17track.net/track/v2.4"


class NoApiKey(Exception):
    pass


def _headers():
    token = storage.get_setting("track17_api_key")
    if not token:
        raise NoApiKey("No 17TRACK API key set. Add one in Settings.")
    return {"17token": token, "Content-Type": "application/json"}


def register(number, carrier=None):
    """Tell 17TRACK to start tracking this number. Carrier is optional -
    omit it and 17TRACK auto-detects from the number format."""
    payload = [{"number": number}]
    if carrier:
        payload[0]["carrier"] = int(carrier)
    resp = requests.post(f"{BASE}/register", headers=_headers(), json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()


def get_track_info(numbers):
    """numbers: list of tracking number strings. Returns raw 17TRACK JSON."""
    payload = [{"number": n} for n in numbers]
    resp = requests.post(f"{BASE}/gettrackinfo", headers=_headers(), json=payload, timeout=20)
    resp.raise_for_status()
    return resp.json()


def parse_events(track_info_response, number):
    """Pull out (status, status_time, events[]) for one tracking number
    from a gettrackinfo response. Each event: time_iso, location_text,
    status_text."""
    accepted = track_info_response.get("data", {}).get("accepted", [])
    for item in accepted:
        if item.get("number") != number:
            continue
        track = item.get("track", {})
        latest = track.get("latest_status", {}) or {}
        status = latest.get("status", "Unknown")
        carrier_name = (track.get("carrier_info") or {}).get("name", "")

        events = []
        for e in track.get("z1", []) or track.get("providers", [{}])[0].get("events", []):
            events.append(
                {
                    "time_iso": e.get("time_iso") or e.get("a") or "",
                    "location_text": e.get("location") or e.get("c") or "",
                    "status_text": e.get("description") or e.get("z") or "",
                    "lat": None,
                    "lon": None,
                }
            )
        status_time = events[-1]["time_iso"] if events else ""
        return status, status_time, carrier_name, events
    return "Not found", "", "", []


# --- Carrier auto-detect fallback (used for display before an API key is
# entered, and to pre-fill the carrier field for register()) ---
_PATTERNS = [
    (r"^1Z[0-9A-Z]{16}$", "UPS"),
    (r"^\d{12}$|^\d{15}$|^\d{20}$", "FedEx"),
    (r"^(94|93|92|95)\d{20}$|^\d{20}$", "USPS"),
    (r"^[A-Z]{2}\d{9}[A-Z]{2}$", "USPS/Intl"),
    (r"^\d{10}$", "DHL"),
    (r"^TBA\d{12}$", "Amazon Logistics"),
]


def guess_carrier_name(number):
    import re

    number = number.strip().upper()
    for pattern, name in _PATTERNS:
        if re.match(pattern, number):
            return name
    return "Unknown (auto-detect on registration)"

"""Geocode carrier event location strings ('MEMPHIS, TN, US' etc.) into
lat/lon using OpenStreetMap's Nominatim, so we can plot a route even when
the carrier doesn't give us coordinates directly (most don't).

Nominatim usage policy: max 1 request/sec, custom User-Agent, cache results.
https://operations.osmfoundation.org/policies/nominatim/
"""
import time
import requests
import storage

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "ParcelsApp/1.0 (personal package tracker, no ads, self-hosted)"

_last_request_time = 0.0


def _throttle():
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < 1.05:
        time.sleep(1.05 - elapsed)
    _last_request_time = time.time()


def geocode(location_text):
    """Return (lat, lon) or None. Cached locally so repeat lookups are free
    and we stay well under Nominatim's rate limit."""
    if not location_text or not location_text.strip():
        return None

    query = location_text.strip()
    cached = storage.geocache_get(query)
    if cached is not None:
        return cached

    _throttle()
    try:
        resp = requests.get(
            NOMINATIM_URL,
            params={"q": query, "format": "json", "limit": 1},
            headers={"User-Agent": USER_AGENT},
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json()
    except Exception:
        return None

    if not results:
        return None

    lat = float(results[0]["lat"])
    lon = float(results[0]["lon"])
    storage.geocache_set(query, lat, lon)
    return (lat, lon)

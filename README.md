# Parcels

Free, no-ads, multi-carrier package tracker. Kivy/Python.

- **Tracking data**: 17TRACK API — same approach the 17TRACK/Parcel apps use:
  one API auto-detects the carrier from the tracking number and normalizes
  ~3000 carriers into one event schema. Free tier = 100 tracked
  numbers/month. Get a key: https://features.17track.net/en/api
  (Settings → Security → Access Key), paste it into the app's Settings screen.
  Stored locally only (sqlite), never bundled into the app.
- **Map**: OpenStreetMap tiles, via `kivy_garden.mapview`. Carriers almost
  never give lat/lon — they give text like "MEMPHIS, TN, US" — so each
  event location is geocoded through OSM's Nominatim (rate-limited to
  1 req/sec per Nominatim's usage policy, and cached locally so you never
  re-geocode the same city twice) and plotted as pins/route.
- **Notifications**: local only (`plyer`), fired when a tracked parcel's
  status changes. No Firebase, no push server, no analytics SDK.
- **No ads, no accounts.**

## Known limitation: background notifications

Status checks run every 30 min while the app is open (foreground or
backgrounded but not killed). A true always-on background service (survives
Doze/app-kill) needs an Android foreground service + WorkManager wired
through python-for-android, which isn't included in this pass — flag if you
want that added next.

## Build the APK

Requires: Linux/WSL/macOS, internet access to `dl.google.com` and
`archive.apache.org` (this is what my sandbox couldn't reach), ~10GB disk,
Java 17.

```bash
pip install --break-system-packages buildozer cython
sudo apt install -y openjdk-17-jdk-headless   # if not already installed
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
cd parcels_app
buildozer android debug
```

First run downloads the Android SDK/NDK (~1-2GB) and takes 15-30 min.
Output: `bin/parcels-1.0-arm64-v8a-debug.apk`. Install with:

```bash
adb install bin/parcels-1.0-arm64-v8a-debug.apk
```

or just copy the APK to your phone and tap it (allow "install unknown apps"
for whichever app you use to open it).

## Run on desktop Linux first (fast sanity check, no build needed)

```bash
pip install --break-system-packages kivy kivy_garden.mapview requests plyer
python3 main.py
```

## Files

- `main.py` — UI, screens, refresh/notify orchestration
- `api17track.py` — 17TRACK API client + carrier auto-detect regexes
- `geocode.py` — OSM Nominatim geocoding with cache
- `storage.py` — sqlite (parcels, events, geocode cache, settings)
- `notify.py` — local notification wrapper
- `buildozer.spec` — Android build config (permissions: INTERNET,
  POST_NOTIFICATIONS, VIBRATE only — no location, no contacts, nothing else)

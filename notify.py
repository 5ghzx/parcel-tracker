"""Local notifications only - no Firebase, no push server, nothing phones
home except the 17TRACK API call itself and OSM's Nominatim."""
try:
    from plyer import notification as _plyer_notify
except Exception:
    _plyer_notify = None


def notify(title, message):
    if _plyer_notify is None:
        print(f"[notify] {title}: {message}")
        return
    try:
        _plyer_notify.notify(title=title, message=message, app_name="Parcels", timeout=10)
    except Exception as exc:
        print(f"[notify] failed: {exc}")

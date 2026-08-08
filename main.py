"""Parcels - free, no-ads, multi-carrier package tracker.

Tracking data: 17TRACK API (auto-detects carrier from tracking number,
same approach the 17TRACK/Parcel apps use).
Map: OpenStreetMap tiles via kivy_garden.mapview. Carriers rarely give
lat/lon directly, so each event's location text (e.g. "MEMPHIS, TN, US")
is geocoded through OSM's Nominatim and cached locally.
Notifications: local only (plyer), fired when a tracked parcel's status
changes while the app is running.
"""
import threading
from datetime import datetime

from kivy.app import App
from kivy.clock import Clock
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.popup import Popup
from kivy.metrics import dp

import storage
import api17track
import geocode
import notify

try:
    from kivy_garden.mapview import MapView, MapMarker, MapSource
    HAVE_MAP = True
except Exception:
    HAVE_MAP = False

REFRESH_INTERVAL_SEC = 30 * 60  # 30 min while app is open/foregrounded


def _row(height=48):
    return BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(height), spacing=dp(8))


class ParcelListScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        root = BoxLayout(orientation="vertical")

        header = _row(56)
        header.add_widget(Label(text="Parcels", font_size="22sp", bold=True))
        refresh_btn = Button(text="Refresh", size_hint_x=None, width=dp(90))
        refresh_btn.bind(on_release=lambda *_: self.refresh_all())
        settings_btn = Button(text="⚙", size_hint_x=None, width=dp(50))
        settings_btn.bind(on_release=lambda *_: setattr(self.manager, "current", "settings"))
        header.add_widget(refresh_btn)
        header.add_widget(settings_btn)
        root.add_widget(header)

        self.list_box = GridLayout(cols=1, size_hint_y=None, spacing=dp(6), padding=dp(6))
        self.list_box.bind(minimum_height=self.list_box.setter("height"))
        scroll = ScrollView()
        scroll.add_widget(self.list_box)
        root.add_widget(scroll)

        add_btn = Button(text="+ Add parcel", size_hint_y=None, height=dp(56))
        add_btn.bind(on_release=lambda *_: setattr(self.manager, "current", "add"))
        root.add_widget(add_btn)

        self.add_widget(root)

    def on_pre_enter(self):
        self.reload_list()

    def reload_list(self):
        self.list_box.clear_widgets()
        parcels = storage.list_parcels()
        if not parcels:
            self.list_box.add_widget(Label(text="No parcels yet. Tap + Add parcel.", size_hint_y=None, height=dp(40)))
            return
        for p in parcels:
            row = _row(64)
            title = p["label"] or p["number"]
            sub = f'{p["carrier_name"] or "?"} · {p["last_status"] or "not checked yet"}'
            lbl = Label(text=f"[b]{title}[/b]\n{sub}", markup=True, halign="left", valign="middle")
            lbl.bind(size=lbl.setter("text_size"))
            open_btn = Button(text="Open", size_hint_x=None, width=dp(70))
            open_btn.bind(on_release=lambda _, n=p["number"]: self.open_detail(n))
            del_btn = Button(text="✕", size_hint_x=None, width=dp(40))
            del_btn.bind(on_release=lambda _, n=p["number"]: self.delete_parcel(n))
            row.add_widget(lbl)
            row.add_widget(open_btn)
            row.add_widget(del_btn)
            self.list_box.add_widget(row)

    def open_detail(self, number):
        self.manager.get_screen("detail").load(number)
        self.manager.current = "detail"

    def delete_parcel(self, number):
        storage.remove_parcel(number)
        self.reload_list()

    def refresh_all(self):
        threading.Thread(target=self._refresh_worker, daemon=True).start()

    def _refresh_worker(self):
        parcels = storage.list_parcels()
        if not parcels:
            return
        numbers = [p["number"] for p in parcels]
        try:
            resp = api17track.get_track_info(numbers)
        except api17track.NoApiKey:
            Clock.schedule_once(lambda *_: notify.notify("Parcels", "Add a 17TRACK API key in Settings to refresh."))
            return
        except Exception as exc:
            Clock.schedule_once(lambda *_: notify.notify("Parcels", f"Refresh failed: {exc}"))
            return

        for p in parcels:
            number = p["number"]
            status, status_time, carrier_name, events = api17track.parse_events(resp, number)
            old_status = p["last_status"]
            storage.update_parcel_status(number, carrier_name, status, status_time)
            storage.replace_events(number, events)
            if old_status and old_status != status:
                label = p["label"] or number
                Clock.schedule_once(
                    lambda *_, l=label, s=status: notify.notify("Parcel update", f"{l}: {s}")
                )
        Clock.schedule_once(lambda *_: self.reload_list())


class AddParcelScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(10))
        root.add_widget(Label(text="Add parcel", font_size="20sp", size_hint_y=None, height=dp(40)))

        self.number_input = TextInput(hint_text="Tracking number", multiline=False, size_hint_y=None, height=dp(48))
        self.label_input = TextInput(hint_text="Label (optional, e.g. 'New shoes')", multiline=False, size_hint_y=None, height=dp(48))
        root.add_widget(self.number_input)
        root.add_widget(self.label_input)

        self.status_lbl = Label(text="", size_hint_y=None, height=dp(30))
        root.add_widget(self.status_lbl)

        btn_row = _row(56)
        save_btn = Button(text="Add & Track")
        save_btn.bind(on_release=lambda *_: self.save())
        cancel_btn = Button(text="Cancel")
        cancel_btn.bind(on_release=lambda *_: setattr(self.manager, "current", "list"))
        btn_row.add_widget(cancel_btn)
        btn_row.add_widget(save_btn)
        root.add_widget(btn_row)

        root.add_widget(BoxLayout())  # spacer
        self.add_widget(root)

    def on_pre_enter(self):
        self.number_input.text = ""
        self.label_input.text = ""
        self.status_lbl.text = ""

    def save(self):
        number = self.number_input.text.strip()
        label = self.label_input.text.strip()
        if not number:
            self.status_lbl.text = "Enter a tracking number."
            return
        guessed = api17track.guess_carrier_name(number)
        storage.add_parcel(number, carrier=None, label=label)
        storage.update_parcel_status(number, guessed, "Registering…", "")
        self.status_lbl.text = "Registering with tracking service…"
        threading.Thread(target=self._register_worker, args=(number,), daemon=True).start()

    def _register_worker(self, number):
        try:
            api17track.register(number)
            msg = "Added. Pull refresh on the list to fetch status."
        except api17track.NoApiKey:
            msg = "Added locally. Add a 17TRACK API key in Settings to fetch live status."
        except Exception as exc:
            msg = f"Added locally (registration failed: {exc})"
        Clock.schedule_once(lambda *_: self._done(msg))

    def _done(self, msg):
        self.status_lbl.text = msg
        Clock.schedule_once(lambda *_: setattr(self.manager, "current", "list"), 1.2)


class DetailScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.number = None
        self.root_box = BoxLayout(orientation="vertical")
        self.add_widget(self.root_box)

    def load(self, number):
        self.number = number
        self.root_box.clear_widgets()

        header = _row(56)
        back_btn = Button(text="< Back", size_hint_x=None, width=dp(80))
        back_btn.bind(on_release=lambda *_: setattr(self.manager, "current", "list"))
        header.add_widget(back_btn)
        header.add_widget(Label(text=number))
        self.root_box.add_widget(header)

        events = storage.get_events(number)

        if HAVE_MAP:
            self.map_view = MapView(zoom=3, lat=20, lon=0, size_hint_y=0.45)
            self.map_view.map_source = MapSource(url="https://tile.openstreetmap.org/{z}/{x}/{y}.png")
            self.root_box.add_widget(self.map_view)
            threading.Thread(target=self._plot_events, args=(events,), daemon=True).start()
        else:
            self.root_box.add_widget(Label(text="(map widget unavailable)", size_hint_y=None, height=dp(30)))

        timeline = GridLayout(cols=1, size_hint_y=None, spacing=dp(4), padding=dp(8))
        timeline.bind(minimum_height=timeline.setter("height"))
        if not events:
            timeline.add_widget(Label(text="No tracking events yet.", size_hint_y=None, height=dp(30)))
        for e in reversed(events):
            text = f'[b]{e["time_iso"]}[/b]  {e["status_text"]}\n{e["location_text"]}'
            lbl = Label(text=text, markup=True, size_hint_y=None, height=dp(52), halign="left", valign="middle")
            lbl.bind(size=lbl.setter("text_size"))
            timeline.add_widget(lbl)
        scroll = ScrollView()
        scroll.add_widget(timeline)
        self.root_box.add_widget(scroll)

    def _plot_events(self, events):
        """Geocode each event location (OSM Nominatim, cached) and drop
        pins on the map - this is the 'build our own map from transit
        locations' path for carriers that don't give coordinates."""
        points = []
        for e in events:
            loc = e["location_text"]
            if not loc:
                continue
            coords = geocode.geocode(loc)
            if coords:
                points.append(coords)
        if not points:
            return

        def apply(*_):
            for lat, lon in points:
                self.map_view.add_marker(MapMarker(lat=lat, lon=lon))
            last_lat, last_lon = points[-1]
            self.map_view.center_on(last_lat, last_lon)
            self.map_view.zoom = 5

        Clock.schedule_once(apply)


class SettingsScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(10))
        root.add_widget(Label(text="Settings", font_size="20sp", size_hint_y=None, height=dp(40)))

        root.add_widget(Label(
            text="17TRACK API key (free, 100 lookups/mo):\nfeatures.17track.net/en/api",
            size_hint_y=None, height=dp(50)
        ))
        self.key_input = TextInput(multiline=False, password=True, size_hint_y=None, height=dp(48))
        root.add_widget(self.key_input)

        save_btn = Button(text="Save", size_hint_y=None, height=dp(48))
        save_btn.bind(on_release=lambda *_: self.save())
        root.add_widget(save_btn)

        back_btn = Button(text="< Back", size_hint_y=None, height=dp(48))
        back_btn.bind(on_release=lambda *_: setattr(self.manager, "current", "list"))
        root.add_widget(back_btn)

        root.add_widget(Label(text="No ads. No accounts. No analytics.\nData stays on this device except calls to\n17TRACK (tracking) and OpenStreetMap (map tiles/geocoding).", size_hint_y=None, height=dp(70)))
        root.add_widget(BoxLayout())
        self.add_widget(root)

    def on_pre_enter(self):
        self.key_input.text = storage.get_setting("track17_api_key", "") or ""

    def save(self):
        storage.set_setting("track17_api_key", self.key_input.text.strip())
        setattr(self.manager, "current", "list")


class ParcelsApp(App):
    def build(self):
        storage.init_db()
        sm = ScreenManager()
        sm.add_widget(ParcelListScreen(name="list"))
        sm.add_widget(AddParcelScreen(name="add"))
        sm.add_widget(DetailScreen(name="detail"))
        sm.add_widget(SettingsScreen(name="settings"))
        Clock.schedule_interval(lambda *_: sm.get_screen("list").refresh_all(), REFRESH_INTERVAL_SEC)
        return sm


if __name__ == "__main__":
    ParcelsApp().run()

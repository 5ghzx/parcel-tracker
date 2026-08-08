[app]
title = Parcels
package.name = parcels
package.domain = org.bigyahu
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 1.0
requirements = python3,kivy==2.3.0,kivy_garden.mapview,requests,plyer,certifi
orientation = portrait
fullscreen = 0

android.permissions = INTERNET,POST_NOTIFICATIONS,VIBRATE
android.api = 34
android.minapi = 24
android.ndk = 25b
android.accept_sdk_license = True
android.archs = arm64-v8a

[buildozer]
log_level = 2
warn_on_root = 1

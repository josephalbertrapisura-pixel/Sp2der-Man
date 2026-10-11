[app]
title = Web Runner
package.name = webrunner
package.domain = org.example
source.dir = .
source.include_exts = py,png,jpg,json,ttf,wav,ogg
version = 0.1
requirements = python3,kivy==2.3.0
orientation = landscape
fullscreen = 1
android.permissions =
android.api = 33
android.minapi = 21
android.archs = arm64-v8a
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1

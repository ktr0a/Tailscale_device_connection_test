[app]
title = Tailnet Chat Node
package.name = tailnetchatnode
package.domain = dev.tailnet
source.dir = .
source.include_exts = py,html,css,js,png,json
version = 0.1.0
icon.filename = %(source.dir)s/icon.png
orientation = portrait
fullscreen = 0

# python3 is the p4a CPython recipe; remaining are pure-Python packages
# pinned to the pydantic-v1/fastapi-0.99 stack (no Rust, builds on ARM)
requirements = python3,fastapi==0.99.1,pydantic==1.10.13,starlette==0.27.0,uvicorn==0.23.2,httpx==0.25.2,httpcore==1.0.2,h11==0.14.0,anyio==3.7.1,sniffio==1.3.0,idna==3.6,certifi,typing_extensions,click,exceptiongroup

android.permissions = INTERNET,ACCESS_NETWORK_STATE
android.api = 34
android.minapi = 24
android.archs = arm64-v8a,armeabi-v7a
# Automatically accept SDK license agreements in non-interactive CI environments.
android.accept_sdk_license = True
# Skip auto-update so buildozer uses the pre-seeded build-tools 34.0.0 rather
# than upgrading to the newest available version (e.g. 37.0.0) which has known
# aidl compatibility issues with buildozer 1.5.0.
android.skip_update = True
p4a.bootstrap = webview
p4a.port = 8000

[buildozer]
log_level = 2
warn_on_root = 0

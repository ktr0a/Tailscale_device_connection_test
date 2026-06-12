[app]
title = Tailnet Chat Node
package.name = tailnetchatnode
package.domain = dev.tailnet
source.dir = .
source.include_exts = py,html,css,js,png,json
source.exclude_dirs = p4a-recipes,bin,data-android
version = 0.1.0
icon.filename = %(source.dir)s/icon.png
orientation = portrait
fullscreen = 0

# python3 is the p4a CPython recipe; remaining are pure-Python packages.
#
# Pydantic v2 / Python 3.14 stack (round-6 fix)
# ---------------------------------------------
# p4a master bundles CPython 3.14.2. pydantic 1.x is fundamentally
# incompatible with Python 3.14 (it introspects removed typing internals,
# crashing at import time inside fastapi/openapi/models.py with:
#   pydantic.errors.ConfigError: unable to infer type for attribute "name")
# p4a master now ships a pydantic-core recipe (RustCompiledComponentsRecipe,
# v2.41.4), so pydantic v2 IS buildable on ARM. We therefore move the entire
# Android stack to pydantic v2 + modern fastapi.
#
# pydantic==2.12.3 is the newest pydantic whose requires_dist pins
# pydantic-core==2.41.4 exactly, matching the p4a recipe version.
# (2.12.4+ require pydantic-core==2.41.5 which has no p4a recipe yet.)
# pydantic-core is listed WITHOUT a version pin so the p4a recipe's
# pre-built 2.41.4 is used; the recipe folder name is "pydantic-core"
# (hyphen) and p4a's get_recipe() normalises by lowercase only.
#
# annotated-types and typing-inspection are pydantic v2 transitive deps
# (pure Python); annotated-doc is a new fastapi>=0.130 transitive dep
# (pure Python, no sub-deps). p4a does not resolve transitives itself,
# so all must be listed explicitly.
#
# Round-5 httpx set unchanged: httpx 0.28.1, httpcore 1.0.9, h11 0.16.0,
# anyio 4.13.0, sniffio 1.3.1, idna 3.18 (fixes Python 3.14 AttributeError
# in httpcore and h11 version constraint from httpcore 1.0.9).
# exceptiongroup dropped: anyio 4.x only requires it on Python<3.11; safe
# to omit for the 3.14 device target.
requirements = python3,fastapi==0.136.3,pydantic==2.12.3,pydantic-core,starlette==1.3.1,uvicorn==0.23.2,httpx==0.28.1,httpcore==1.0.9,h11==0.16.0,anyio==4.13.0,sniffio==1.3.1,idna==3.18,certifi,typing_extensions,click,annotated-types==0.7.0,typing-inspection==0.4.2,annotated-doc==0.0.4

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
p4a.local_recipes = ./p4a-recipes

[buildozer]
log_level = 2
warn_on_root = 0

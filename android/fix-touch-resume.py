#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SURFACE = ROOT / "android/app/src/main/java/org/libsdl/app/SDLSurface.java"

text = SURFACE.read_text()

old = '''    public void handleResume() {
        setFocusable(true);
        setFocusableInTouchMode(true);
        requestFocus();
        setOnKeyListener(this);
        setOnTouchListener(this);
        enableSensor(Sensor.TYPE_ACCELEROMETER, true);
    }
'''

new = '''    public void handleResume() {
        setFocusable(true);
        setFocusableInTouchMode(true);
        requestFocus();
        setOnKeyListener(this);
        // Perfect Dark installs its own surface touch router in MainActivity.
        // Do not restore SDLSurface as the touch listener on resume: doing so
        // bypasses TouchControls/MenuTouchOverlay and makes every finger go
        // through SDL's stock touch path until the app is restarted.
        enableSensor(Sensor.TYPE_ACCELEROMETER, true);
    }
'''

count = text.count(old)
if count != 1:
    raise SystemExit(f"touch resume fix: expected one SDLSurface.handleResume block, found {count}")

SURFACE.write_text(text.replace(old, new, 1))
print("touch resume fix: preserved Perfect Dark surface touch listener across Android resume")

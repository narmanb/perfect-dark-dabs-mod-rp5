#!/usr/bin/env python3
from pathlib import Path


def replace_once(path: str, old: str, new: str, label: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match in {path}, found {count}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"patched {label}: {path}")


# This runs immediately after fix-right-stick-aiming.py. Keep the first script
# focused on the structural overhaul, then tune the user-facing range here.

replace_once(
    "port/src/input.c",
    '''\t// Acceleration is now genuinely time based. Holding a substantial turn for
\t// a short period gradually adds up to 35% extra stick magnitude; quick aim
\t// corrections are untouched. This avoids duplicating the response curve.
''',
    '''\t// Acceleration is genuinely time based. The upper half of the slider is
\t// deliberately obvious for testing: a sustained partial turn can ramp to as
\t// much as double its initial magnitude, while quick centre corrections remain
\t// effectively unaccelerated.
''',
    "acceleration description",
)

replace_once(
    "port/src/input.c",
    '''\tif (acceleration > 0.f) {
\t\tif (magnitude > 0.55f) {
\t\t\trstickAccelHold[cidx] += dt;
\t\t} else if (magnitude < 0.35f) {
\t\t\trstickAccelHold[cidx] = 0.f;
\t\t} else {
\t\t\trstickAccelHold[cidx] -= dt * 2.f;
\t\t\tif (rstickAccelHold[cidx] < 0.f) rstickAccelHold[cidx] = 0.f;
\t\t}

\t\tconst f32 ramp = inputClampUnit((rstickAccelHold[cidx] - 0.12f) / 0.45f);
\t\tconst f32 boost = 1.f + acceleration * 0.35f * ramp;
''',
    '''\tif (acceleration > 0.f) {
\t\tif (magnitude > 0.35f) {
\t\t\trstickAccelHold[cidx] += dt;
\t\t} else if (magnitude < 0.20f) {
\t\t\trstickAccelHold[cidx] = 0.f;
\t\t} else {
\t\t\trstickAccelHold[cidx] -= dt * 3.f;
\t\t\tif (rstickAccelHold[cidx] < 0.f) rstickAccelHold[cidx] = 0.f;
\t\t}

\t\tconst f32 ramp = inputClampUnit((rstickAccelHold[cidx] - 0.05f) / 0.25f);
\t\tconst f32 boost = 1.f + acceleration * 1.00f * ramp;
''',
    "stronger earlier acceleration",
)

replace_once(
    "port/src/input.c",
    '''\tif (smoothing > 0.f) {
\t\t// Treat the setting as retained input per 60 Hz frame, then convert it
\t\t// using real elapsed time. The feel therefore stays stable at different
\t\t// frame rates instead of becoming more sluggish at higher FPS.
\t\tconst f32 retain = powf(smoothing, dt * 60.f);
''',
    '''\tif (smoothing > 0.f) {
\t\t// Map the user slider onto a much wider useful filtering range. The old
\t\t// 75% maximum retained only 75% of the previous sample per 60 Hz frame
\t\t// (roughly a four-frame filter), which was barely perceptible on RP5.
\t\t// 100% now retains 94% per 60 Hz frame (roughly sixteen frames), making
\t\t// the top end intentionally heavy while low values remain practical.
\t\tconst f32 effectiveSmoothing = 1.f - powf(0.06f, smoothing);
\t\tconst f32 retain = powf(effectiveSmoothing, dt * 60.f);
''',
    "stronger smoothing curve",
)

replace_once(
    "port/src/input.c",
    '''\tpadsCfg[cidx].rstickSmoothing = value < 0.f ? 0.f : (value > 0.75f ? 0.75f : value);
''',
    '''\tpadsCfg[cidx].rstickSmoothing = value < 0.f ? 0.f : (value > 1.f ? 1.f : value);
''',
    "smoothing setter range",
)

replace_once(
    "port/src/input.c",
    '''configRegisterFloat(strFmt("%s.RStickSmoothing", secname), &padsCfg[c].rstickSmoothing, 0.f, 0.75f);''',
    '''configRegisterFloat(strFmt("%s.RStickSmoothing", secname), &padsCfg[c].rstickSmoothing, 0.f, 1.f);''',
    "smoothing config range",
)

replace_once(
    "port/src/optionsmenu.c",
    '''\t\t(uintptr_t)"RStick Smoothing", 75, menuhandlerRightStickSmoothing,''',
    '''\t\t(uintptr_t)"RStick Smoothing", 100, menuhandlerRightStickSmoothing,''',
    "smoothing menu range",
)

print("right-stick acceleration/smoothing retune applied")

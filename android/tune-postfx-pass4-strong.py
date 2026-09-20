#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GFX = ROOT / "port/fast3d/gfx_opengl.cpp"
text = GFX.read_text()


def replace_once(old, new, label):
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"postfx pass4 strong: expected one {label}, found {count}")
    text = text.replace(old, new, 1)
    print(f"postfx pass4 strong: {label}")


def replace_exact_count(old, new, expected, label):
    global text
    count = text.count(old)
    if count != expected:
        raise SystemExit(f"postfx pass4 strong: expected {expected} {label}, found {count}")
    text = text.replace(old, new)
    print(f"postfx pass4 strong: {label} ({count} replacements)")


# Run 62's multi-pass path was still too conservative on the RP5. Make edge
# detection much more sensitive, especially in Ultra, while continuing to gate
# the blend to detected edges rather than blurring the whole frame.
replace_once(
    "0.014 : 0.020",
    "0.0045 : 0.012",
    "multi-pass edge threshold",
)
replace_once(
    "local * 0.18",
    "local * 0.08",
    "multi-pass adaptive threshold",
)
# This ramp appears twice in the generated post-FX source after the earlier
# passes are applied. Both copies belong to AA edge detection, so tune both.
replace_exact_count(
    "adapt * 3.2",
    "adapt * 1.8",
    2,
    "multi-pass edge ramp",
)
replace_once(
    "max(edgeX, edgeY) < 0.02",
    "max(edgeX, edgeY) < 0.004",
    "multi-pass edge gate",
)

# Search much farther along lines. Ultra should be unmistakably stronger than
# Multi, not just a tiny numerical step.
replace_once(
    "uQuality >= 4 ? 12 : 7",
    "uQuality >= 4 ? 16 : 10",
    "SMAA search length",
)
replace_once(
    "for (int i = 1; i <= 12; i++)",
    "for (int i = 1; i <= 16; i++)",
    "SMAA maximum search loop",
)

# Raise the minimum directional weights and stop dividing the accumulated edge
# evidence down so aggressively.
replace_once(
    "float wx = e.r * clamp(0.34 + runX / (float(steps) * 1.30), 0.0, 1.0);",
    "float wx = e.r * clamp((uQuality >= 4 ? 0.54 : 0.46) + runX / (float(steps) * (uQuality >= 4 ? 0.82 : 0.96)), 0.0, 1.0);",
    "horizontal blend weight",
)
replace_once(
    "float wy = e.g * clamp(0.34 + runY / (float(steps) * 1.30), 0.0, 1.0);",
    "float wy = e.g * clamp((uQuality >= 4 ? 0.54 : 0.46) + runY / (float(steps) * (uQuality >= 4 ? 0.82 : 0.96)), 0.0, 1.0);",
    "vertical blend weight",
)
replace_once(
    ") * 0.20, 0.0, 1.0);",
    ") * 0.32, 0.0, 1.0);",
    "Ultra diagonal weight",
)

# Keep the neighborhood resolve selective. The previous aggressive Ultra patch
# averaged pixels two texels away and could replace an entire edge pixel, which
# softened detail instead of resolving staircase coverage.
replace_once(
    "if (edge < 0.01) { oCol = vec4(c, 1.0); return; }",
    "if (edge < 0.006) { oCol = vec4(c, 1.0); return; }",
    "final blend gate",
)
replace_once(
    "clamp(w.b * 0.40, 0.0, 0.40)",
    "clamp(w.b * 0.52, 0.0, 0.46)",
    "Ultra diagonal resolve",
)
replace_once(
    "float strength = (uQuality >= 4 ? 0.92 : 0.78);",
    "float strength = (uQuality >= 4 ? 0.88 : 0.76);",
    "multi-pass resolve strength",
)
replace_once(
    "(uQuality >= 4 ? 0.94 : 0.84)",
    "(uQuality >= 4 ? 0.82 : 0.72)",
    "multi-pass resolve cap",
)

# Multi/Ultra are already resolved before the grade shader. Keep their quality
# value visible to that shader: resolveScene() only handles modes 1/2, so modes
# 3/4 do not run AA twice, while the post-sharpen AA restore branch remains on.
replace_once(
    "final_aa_mode = 0;",
    "final_aa_mode = quality;",
    "preserve multi-pass AA through sharpen restore",
)

# If the three-pass path cannot initialize on a particular GLES driver, Ultra
# falls back to SMAA Lite. Strengthen that fallback too so selecting Ultra never
# silently becomes another nearly invisible result.
replace_once(
    "if (edge < 0.010) return c;",
    "if (edge < 0.004) return c;",
    "SMAA Lite fallback gate",
)
replace_once(
    "smoothstep(0.010, 0.120, edge)",
    "smoothstep(0.004, 0.060, edge)",
    "SMAA Lite fallback weight",
)
replace_once(
    "(c * 0.15 + along * 0.85)",
    "(c * 0.03 + along * 0.97)",
    "SMAA Lite fallback blend",
)

GFX.write_text(text)
print("postfx pass4 strong: aggressive RP5 AA tuning applied")

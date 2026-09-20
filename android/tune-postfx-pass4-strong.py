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
replace_once(
    "adapt * 3.2",
    "adapt * 1.8",
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
    "uQuality >= 4 ? 20 : 10",
    "SMAA search length",
)
replace_once(
    "for (int i = 1; i <= 12; i++)",
    "for (int i = 1; i <= 20; i++)",
    "SMAA maximum search loop",
)

# Raise the minimum directional weights and stop dividing the accumulated edge
# evidence down so aggressively.
replace_once(
    "float wx = e.r * clamp(0.34 + runX / (float(steps) * 1.30), 0.0, 1.0);",
    "float wx = e.r * clamp((uQuality >= 4 ? 0.72 : 0.52) + runX / (float(steps) * (uQuality >= 4 ? 0.68 : 0.92)), 0.0, 1.0);",
    "horizontal blend weight",
)
replace_once(
    "float wy = e.g * clamp(0.34 + runY / (float(steps) * 1.30), 0.0, 1.0);",
    "float wy = e.g * clamp((uQuality >= 4 ? 0.72 : 0.52) + runY / (float(steps) * (uQuality >= 4 ? 0.68 : 0.92)), 0.0, 1.0);",
    "vertical blend weight",
)
replace_once(
    ") * 0.20, 0.0, 1.0);",
    ") * 0.48, 0.0, 1.0);",
    "Ultra diagonal weight",
)

# The old final resolve rarely reached a strong enough blend to be visible at
# native RP5 resolution. Ultra now fully resolves strong edges and samples a
# two-pixel neighborhood as well, which attacks wider stair steps and shimmer.
replace_once(
    "if (edge < 0.01) { oCol = vec4(c, 1.0); return; }",
    "if (edge < 0.002) { oCol = vec4(c, 1.0); return; }",
    "final blend gate",
)
replace_once(
    "vec3 target = (((l + r) * 0.5) * w.r + ((t + b) * 0.5) * w.g) / sum;",
    "vec3 target = (((l + r) * 0.5) * w.r + ((t + b) * 0.5) * w.g) / sum;\n"
    "    if (uQuality >= 4) {\n"
    "        vec3 l2 = texture(uTex, vUV - vec2(uTexel.x * 2.0, 0.0)).rgb;\n"
    "        vec3 r2 = texture(uTex, vUV + vec2(uTexel.x * 2.0, 0.0)).rgb;\n"
    "        vec3 t2 = texture(uTex, vUV - vec2(0.0, uTexel.y * 2.0)).rgb;\n"
    "        vec3 b2 = texture(uTex, vUV + vec2(0.0, uTexel.y * 2.0)).rgb;\n"
    "        vec3 wide = (((l2 + r2) * 0.5) * w.r + ((t2 + b2) * 0.5) * w.g) / sum;\n"
    "        target = mix(target, wide, 0.42);\n"
    "    }",
    "Ultra two-pixel neighborhood",
)
replace_once(
    "clamp(w.b * 0.40, 0.0, 0.40)",
    "clamp(w.b * 0.75, 0.0, 0.70)",
    "Ultra diagonal resolve",
)
replace_once(
    "float strength = (uQuality >= 4 ? 0.92 : 0.78);",
    "float strength = (uQuality >= 4 ? 1.35 : 1.02);",
    "multi-pass resolve strength",
)
replace_once(
    "(uQuality >= 4 ? 0.94 : 0.84)",
    "(uQuality >= 4 ? 1.00 : 0.94)",
    "multi-pass resolve cap",
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

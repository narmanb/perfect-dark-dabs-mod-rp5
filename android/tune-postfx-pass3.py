#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GFX = ROOT / "port/fast3d/gfx_opengl.cpp"
text = GFX.read_text()


def replace_once(old, new, label):
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"postfx pass3 tuning: expected one {label}, found {count}")
    text = text.replace(old, new, 1)
    print(f"postfx pass3 tuning: {label}")


# Lens distortion worked on RP5, but the user found the whole curve slightly
# too restrained. Raise all three levels by roughly one third while retaining
# clearly separated Light/Medium/Strong steps.
replace_once(
    "0.025 : (uLensDistort == 2 ? 0.060 : 0.120)",
    "0.035 : (uLensDistort == 2 ? 0.085 : 0.160)",
    "stronger lens distortion curve",
)

# The first AA pass was technically active but too subtle to identify on the
# RP5 screen. Make FXAA react to substantially lower-contrast edges and allow a
# wider directional search. Then add a modest cross-neighbour blend only on
# detected edges so the difference is visible without turning the whole frame
# into a blur.
replace_once(
    "lumaMax - lumaMin < 0.035",
    "lumaMax - lumaMin < 0.012",
    "FXAA edge threshold",
)
replace_once(
    "vec2(-8.0), vec2(8.0)",
    "vec2(-12.0), vec2(12.0)",
    "FXAA search span",
)
replace_once(
    '    "    return (lumaB < lumaMin || lumaB > lumaMax) ? rgbA : rgbB;\\n" \\\n',
    '    "    vec3 aa = (lumaB < lumaMin || lumaB > lumaMax) ? rgbA : rgbB;\\n" \\\n'
    '    "    vec3 cross = 0.25 * (sceneSample(uv + vec2( uTexel.x, 0.0)) + sceneSample(uv + vec2(-uTexel.x, 0.0)) + sceneSample(uv + vec2(0.0,  uTexel.y)) + sceneSample(uv + vec2(0.0, -uTexel.y)));\\n" \\\n'
    '    "    float edgeAmt = smoothstep(0.012, 0.160, lumaMax - lumaMin);\\n" \\\n'
    '    "    return mix(aa, cross, edgeAmt * 0.28);\\n" \\\n',
    "stronger FXAA edge blend",
)

# SMAA Lite is intentionally a one-pass approximation, but its initial edge
# gate and blend weights were much too conservative. Broaden edge detection and
# make the morphological blend decisive enough to be obvious in motion and in
# still screenshots.
replace_once(
    "if (edge < 0.030) return c;",
    "if (edge < 0.010) return c;",
    "SMAA Lite edge threshold",
)
replace_once(
    "smoothstep(0.030, 0.180, edge) * 0.72",
    "smoothstep(0.010, 0.120, edge)",
    "SMAA Lite edge weight",
)
replace_once(
    "(c * 0.45 + along * 0.55)",
    "(c * 0.15 + along * 0.85)",
    "SMAA Lite blend ratio",
)

# Post AA currently resolves before the sharpening stage, so aggressive
# sharpening can re-emphasise the exact edges AA just softened. Re-apply a
# controlled amount of the AA-resolved centre after sharpening. This preserves
# the user's sharpen setting while making Post AA remain visible when both are
# enabled.
marker = '    "    if (uBloom > 0 || uLensDirt > 0 || uLightStreaks > 0) {\\n" \\\n'
insert = (
    '    "    if (uPostAA > 0 && uSharpen > 0) {\\n" \\\n'
    '    "        vec3 aaRestore = resolveScene(vUV);\\n" \\\n'
    '    "        float aaRestoreStrength = (uPostAA == 1 ? 0.68 : 0.82);\\n" \\\n'
    '    "        c = mix(c, aaRestore, aaRestoreStrength);\\n" \\\n'
    '    "    }\\n" \\\n'
    + marker
)
replace_once(marker, insert, "restore AA after sharpen")

GFX.write_text(text)
print("postfx pass3 tuning: complete")

#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "port/fast3d/gfx_opengl.cpp"
text = PATH.read_text()


def replace_once(old, new, label):
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"postfx tuning: expected one {label}, found {count}")
    text = text.replace(old, new, 1)


# A one-pixel-radius sharpen is technically working at 1080p but can be almost
# impossible to see at normal handheld viewing distance. Give Medium/Strong a
# broader sampling radius and a real unsharp-mask gain. Adaptive mode still
# limits halos, but Strong deliberately has enough headroom to be unmistakable.
replace_once(
    '        float amount = (uSharpen == 1 ? 0.10 : (uSharpen == 2 ? 0.20 : 0.32));\\n" \\\n'
    '    "        if (uSharpenMode != 0) {\\n" \\\n'
    '    "            float edge = max(max(length(c - n), length(c - s)), max(length(c - e), length(c - w)));\\n" \\\n'
    '    "            amount *= mix(0.45, 1.0, clamp(edge * 2.5, 0.0, 1.0));\\n" \\\n'
    '    "        }\\n" \\\n'
    '    "        vec3 sh = c + (c * 4.0 - n - s - e - w) * amount;\\n" \\\n'
    '    "        if (uSharpenMode != 0) {\\n" \\\n'
    '    "            vec3 lo = min(c, min(min(n, s), min(e, w)));\\n" \\\n'
    '    "            vec3 hi = max(c, max(max(n, s), max(e, w)));\\n" \\\n'
    '    "            sh = clamp(sh, lo, hi);\\n" \\\n'
    '    "        }\\n" \\\n',
    '        float radius = (uSharpen == 1 ? 1.0 : (uSharpen == 2 ? 1.6 : 2.4));\\n" \\\n'
    '    "        vec2 px = uTexel * radius;\\n" \\\n'
    '    "        n = texture(uTex, vUV + vec2(0.0, -px.y)).rgb;\\n" \\\n'
    '    "        s = texture(uTex, vUV + vec2(0.0,  px.y)).rgb;\\n" \\\n'
    '    "        e = texture(uTex, vUV + vec2( px.x, 0.0)).rgb;\\n" \\\n'
    '    "        w = texture(uTex, vUV + vec2(-px.x, 0.0)).rgb;\\n" \\\n'
    '    "        float amount = (uSharpen == 1 ? 0.45 : (uSharpen == 2 ? 0.95 : 1.65));\\n" \\\n'
    '    "        vec3 blur4 = (n + s + e + w) * 0.25;\\n" \\\n'
    '    "        vec3 detail = c - blur4;\\n" \\\n'
    '    "        if (uSharpenMode != 0) {\\n" \\\n'
    '    "            float edge = max(max(length(c - n), length(c - s)), max(length(c - e), length(c - w)));\\n" \\\n'
    '    "            amount *= mix(0.80, 1.0, clamp(edge * 2.0, 0.0, 1.0));\\n" \\\n'
    '    "        }\\n" \\\n'
    '    "        vec3 sh = c + detail * amount;\\n" \\\n'
    '    "        if (uSharpenMode != 0) {\\n" \\\n'
    '    "            vec3 lo = min(c, min(min(n, s), min(e, w)));\\n" \\\n'
    '    "            vec3 hi = max(c, max(max(n, s), max(e, w)));\\n" \\\n'
    '    "            vec3 range = max(hi - lo, vec3(1.0 / 255.0));\\n" \\\n'
    '    "            float allowance = (uSharpen == 1 ? 0.22 : (uSharpen == 2 ? 0.48 : 0.85));\\n" \\\n'
    '    "            sh = clamp(sh, lo - range * allowance, hi + range * allowance);\\n" \\\n'
    '    "        }\\n" \\\n',
    "adaptive sharpen body",
)

# Grain that changes every 60 Hz frame can perceptually average into almost
# nothing on a small 1080p LCD. Use a slower-changing seed and slightly larger
# grain cells, with a Strong level that is intentionally obvious. This keeps
# Light usable while making the control easy to verify on-device.
replace_once(
    '    "    float noise = hash12(gl_FragCoord.xy + vec2(float(uFrame) * 0.7549, float(uFrame) * 0.5693)) - 0.5;\\n" \\\n',
    '    "    float grainCell = (uGrain == 3 ? 1.75 : (uGrain == 2 ? 1.35 : 1.0));\\n" \\\n'
    '    "    float grainFrame = floor(float(uFrame) / 3.0);\\n" \\\n'
    '    "    vec2 grainCoord = floor(gl_FragCoord.xy / grainCell);\\n" \\\n'
    '    "    float noise = hash12(grainCoord + vec2(grainFrame * 0.7549, grainFrame * 0.5693)) - 0.5;\\n" \\\n',
    "film grain noise seed",
)

replace_once(
    '        float gs = (uGrain == 1 ? 0.012 : (uGrain == 2 ? 0.024 : 0.040));\\n" \\\n',
    '        float gs = (uGrain == 1 ? 0.035 : (uGrain == 2 ? 0.090 : 0.180));\\n" \\\n',
    "film grain strength",
)

PATH.write_text(text)
print("postfx tuning: broader sharpen and slower, stronger film grain applied")

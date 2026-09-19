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


# Run 48 proved the controls are wired, but the original sharpen was far too
# conservative for a 1080p handheld. In adaptive mode it clamped the sharpened
# pixel strictly to the min/max of the centre and four neighbours. Pixels that
# were already a local min/max therefore could not sharpen at all, which is most
# of the visible high-contrast detail. Use an unsharp-mask detail term and a
# small adaptive overshoot allowance instead. Strong is intentionally obvious;
# Light remains restrained.
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
    '        float amount = (uSharpen == 1 ? 0.40 : (uSharpen == 2 ? 0.80 : 1.20));\\n" \\\n'
    '    "        vec3 blur4 = (n + s + e + w) * 0.25;\\n" \\\n'
    '    "        vec3 detail = c - blur4;\\n" \\\n'
    '    "        if (uSharpenMode != 0) {\\n" \\\n'
    '    "            float edge = max(max(length(c - n), length(c - s)), max(length(c - e), length(c - w)));\\n" \\\n'
    '    "            amount *= mix(0.75, 1.0, clamp(edge * 3.0, 0.0, 1.0));\\n" \\\n'
    '    "        }\\n" \\\n'
    '    "        vec3 sh = c + detail * amount;\\n" \\\n'
    '    "        if (uSharpenMode != 0) {\\n" \\\n'
    '    "            vec3 lo = min(c, min(min(n, s), min(e, w)));\\n" \\\n'
    '    "            vec3 hi = max(c, max(max(n, s), max(e, w)));\\n" \\\n'
    '    "            vec3 range = max(hi - lo, vec3(1.0 / 255.0));\\n" \\\n'
    '    "            sh = clamp(sh, lo - range * 0.30, hi + range * 0.30);\\n" \\\n'
    '    "        }\\n" \\\n',
    "adaptive sharpen body",
)

# The first grain curve topped out at +/-2% before luminance weighting, which
# is easy to lose on the RP5 panel and in screenshots. Keep Light subtle but
# make Medium and Strong unmistakably visible so the control has useful range.
replace_once(
    '        float gs = (uGrain == 1 ? 0.012 : (uGrain == 2 ? 0.024 : 0.040));\\n" \\\n',
    '        float gs = (uGrain == 1 ? 0.025 : (uGrain == 2 ? 0.055 : 0.095));\\n" \\\n',
    "film grain strength",
)

PATH.write_text(text)
print("postfx tuning: sharpen and film grain retuned")

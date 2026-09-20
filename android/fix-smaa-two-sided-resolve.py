#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GFX = ROOT / "port/fast3d/gfx_opengl.cpp"
OPTIONS = ROOT / "port/src/optionsmenu.c"

text = GFX.read_text()

old = r'''vec4 smaaNeighborhoodLinearLight(vec2 texcoord, vec4 unusedOffset) {
    // OpenGL/WebGL SMAA channel gather. The weight texture is directional:
    // current R/B plus G from +Y and A from +X identify the four candidates.
    vec4 a;
    a.xz = texture(uBlendTex, texcoord).xz;
    a.y = texture(uBlendTex, texcoord + vec2(0.0, uSmaaMetrics.y)).g;
    a.w = texture(uBlendTex, texcoord + vec2(uSmaaMetrics.x, 0.0)).a;

    if (dot(a, vec4(1.0)) < 1e-5) {
        return textureLod(uColorTex, texcoord, 0.0);
    }

    // Established OpenGL SMAA neighborhood mapping: choose the strongest line
    // crossing this pixel, then blend toward exactly that neighbouring texel.
    vec2 direction;
    direction.x = a.w > a.z ? a.w : -a.z;
    direction.y = a.y > a.x ? -a.y : a.x;
    if (abs(direction.x) > abs(direction.y)) {
        direction.y = 0.0;
    } else {
        direction.x = 0.0;
    }

    float amount = max(abs(direction.x), abs(direction.y));
    vec4 c0 = smaaSampleColorLinear(texcoord);
    vec4 c1 = smaaSampleColorLinear(texcoord + sign(direction) * uSmaaMetrics.xy);
    vec3 linear = mix(c0.rgb, c1.rgb, amount);
    float alpha = mix(c0.a, c1.a, amount);
    return vec4(smaaLinearToSrgb(linear), alpha);
}
'''

new = r'''vec4 smaaNeighborhoodLinearLight(vec2 texcoord, vec4 unusedOffset) {
    // OpenGL-oriented gather for the four directional weights produced by the
    // reference SMAA second pass. Keep the GL Y convention established by the
    // orientation patch, but resolve them with the modern upstream algorithm:
    // select the strongest axis, retain BOTH opposing weights, normalize the
    // pair, and sample at the fractional offsets encoded by those weights.
    vec4 a;
    a.xz = texture(uBlendTex, texcoord).xz;
    a.y = texture(uBlendTex, texcoord + vec2(0.0, uSmaaMetrics.y)).g;
    a.w = texture(uBlendTex, texcoord + vec2(uSmaaMetrics.x, 0.0)).a;

    if (dot(a, vec4(1.0)) < 1e-5) {
        return textureLod(uColorTex, texcoord, 0.0);
    }

    // With the OpenGL gather above:
    //   horizontal pair = +X (a.w), -X (a.z)
    //   vertical pair   = -Y (a.y), +Y (a.x)
    bool horizontal = max(a.w, a.z) > max(a.y, a.x);
    vec2 weights = horizontal ? vec2(a.w, a.z) : vec2(a.y, a.x);
    float weightSum = weights.x + weights.y;
    if (weightSum < 1e-5) {
        return textureLod(uColorTex, texcoord, 0.0);
    }
    weights /= weightSum;

    vec2 uv0;
    vec2 uv1;
    if (horizontal) {
        uv0 = texcoord + vec2(a.w * uSmaaMetrics.x, 0.0);
        uv1 = texcoord - vec2(a.z * uSmaaMetrics.x, 0.0);
    } else {
        uv0 = texcoord - vec2(0.0, a.y * uSmaaMetrics.y);
        uv1 = texcoord + vec2(0.0, a.x * uSmaaMetrics.y);
    }

    vec4 c0 = smaaSampleColorLinear(uv0);
    vec4 c1 = smaaSampleColorLinear(uv1);
    vec3 linear = weights.x * c0.rgb + weights.y * c1.rgb;
    float alpha = weights.x * c0.a + weights.y * c1.a;
    return vec4(smaaLinearToSrgb(linear), alpha);
}
'''

count = text.count(old)
if count != 1:
    raise SystemExit(f"two-sided SMAA resolve: expected one old neighborhood implementation, found {count}")

GFX.write_text(text.replace(old, new, 1))
print("two-sided SMAA resolve: restored normalized two-neighbor reference resolve with OpenGL directional mapping")

# Finalize the user-facing AA menu without renumbering any stored config value:
#   0 Off, 1 FXAA, 2 SMAA Lite, 3 SMAA High, 4 SMAA (upstream Ultra preset).
# Keep the diagnostic shader/readback machinery compiled for CI and future
# troubleshooting, but remove all diagnostic/boost controls from the normal
# Post FX menu so the production UI contains only real AA modes.
options = OPTIONS.read_text()

old_opts = 'static const char *opts[] = { "Off", "FXAA", "SMAA Lite", "SMAA Multi", "SMAA Ultra" };'
new_opts = 'static const char *opts[] = { "Off", "FXAA", "SMAA Lite", "SMAA High", "SMAA" };'
count = options.count(old_opts)
if count != 1:
    raise SystemExit(f"SMAA cleanup: expected one AA option list, found {count}")
options = options.replace(old_opts, new_opts, 1)

handler_start = options.find("static s32 smaaParseStatus(")
handler_end = options.find("static MenuItemHandlerResult menuhandlerPostFxAA", handler_start)
if handler_start < 0 or handler_end < 0:
    raise SystemExit("SMAA cleanup: generated diagnostic handler block not found")
options = options[:handler_start] + options[handler_end:]

old_rows = (
    '\t{ MENUITEMTYPE_DROPDOWN, 0, MENUITEMFLAG_LITERAL_TEXT, (uintptr_t)"SMAA View", 0, menuhandlerSmaaView },\n'
    '\t// Focusable on purpose: these rows scroll completely into view.\n'
    '\t{ MENUITEMTYPE_DROPDOWN, 0, MENUITEMFLAG_LITERAL_TEXT, (uintptr_t)"SMAA Stats", 0, menuhandlerSmaaStatus },\n'
    '\t{ MENUITEMTYPE_DROPDOWN, 0, MENUITEMFLAG_LITERAL_TEXT, (uintptr_t)"SMAA Detail", 0, menuhandlerSmaaDetail },\n'
)
count = options.count(old_rows)
if count != 1:
    raise SystemExit(f"SMAA cleanup: expected one diagnostic menu row block, found {count}")
options = options.replace(old_rows, "", 1)

OPTIONS.write_text(options)
print("SMAA cleanup: renamed High/current SMAA modes and removed diagnostic/boost rows from Post FX")

#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GFX = ROOT / "port/fast3d/gfx_opengl.cpp"
OPTIONS = ROOT / "port/src/optionsmenu.c"
API = ROOT / "port/fast3d/gfx_api.h"

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
text = text.replace(old, new, 1)

# Mode 3 is standard SMAA using the upstream Ultra preset. Mode 4 is our
# stronger SMAA High preset. It stays within the reference implementation's
# documented/custom tuning range: the demo exposes up to 112 H/V search steps
# and 20 diagonal search steps.
old_preset = r'''static std::string gfx_opengl_smaa_fragment_source(bool ultra, int pass) {
    std::string src = gl_es ? "#version 300 es\nprecision highp float;\n" : "#version 130\n";
    src += "#define SMAA_GLSL_3\n";
    src += "#define SMAA_INCLUDE_VS 0\n";
    src += "#define SMAA_INCLUDE_PS 1\n";
    src += ultra ? "#define SMAA_PRESET_ULTRA\n" : "#define SMAA_PRESET_HIGH\n";
    src += "#define SMAA_RT_METRICS uSmaaMetrics\n";
'''
new_preset = r'''static std::string gfx_opengl_smaa_fragment_source(bool high, int pass) {
    std::string src = gl_es ? "#version 300 es\nprecision highp float;\n" : "#version 130\n";
    src += "#define SMAA_GLSL_3\n";
    src += "#define SMAA_INCLUDE_VS 0\n";
    src += "#define SMAA_INCLUDE_PS 1\n";
    if (high) {
        src += "#define SMAA_THRESHOLD 0.025\n";
        src += "#define SMAA_MAX_SEARCH_STEPS 64\n";
        src += "#define SMAA_MAX_SEARCH_STEPS_DIAG 20\n";
        src += "#define SMAA_CORNER_ROUNDING 25\n";
    } else {
        src += "#define SMAA_PRESET_ULTRA\n";
    }
    src += "#define SMAA_RT_METRICS uSmaaMetrics\n";
'''
count = text.count(old_preset)
if count != 1:
    raise SystemExit(f"SMAA High: expected one reference preset selector, found {count}")
text = text.replace(old_preset, new_preset, 1)

old_link = '''static GLuint gfx_opengl_smaa_link(bool ultra, int pass, const char *label) {
    std::string fs = gfx_opengl_smaa_fragment_source(ultra, pass);
'''
new_link = '''static GLuint gfx_opengl_smaa_link(bool high, int pass, const char *label) {
    std::string fs = gfx_opengl_smaa_fragment_source(high, pass);
'''
count = text.count(old_link)
if count != 1:
    raise SystemExit(f"SMAA High: expected one link helper, found {count}")
text = text.replace(old_link, new_link, 1)

old_init = '''    for (int q = 0; q < 2; q++) {
        const bool ultra = q == 1;
        smaa_edge_prog[q] = gfx_opengl_smaa_link(ultra, 0, ultra ? "SMAA Ultra edge" : "SMAA High edge");
        smaa_weight_prog[q] = gfx_opengl_smaa_link(ultra, 1, ultra ? "SMAA Ultra weights" : "SMAA High weights");
        smaa_neighborhood_prog[q] = gfx_opengl_smaa_link(ultra, 2, ultra ? "SMAA Ultra neighborhood" : "SMAA High neighborhood");
        smaa_ready[q] = smaa_edge_prog[q] && smaa_weight_prog[q] && smaa_neighborhood_prog[q];
        if (!smaa_ready[q]) {
            sysLogPrintf(LOG_WARNING, "GL: %s reference SMAA unavailable; SMAA Lite fallback will be used", ultra ? "Ultra" : "High");
        }
    }
'''
new_init = '''    for (int q = 0; q < 2; q++) {
        const bool high = q == 1;
        smaa_edge_prog[q] = gfx_opengl_smaa_link(high, 0, high ? "SMAA High edge" : "SMAA edge");
        smaa_weight_prog[q] = gfx_opengl_smaa_link(high, 1, high ? "SMAA High weights" : "SMAA weights");
        smaa_neighborhood_prog[q] = gfx_opengl_smaa_link(high, 2, high ? "SMAA High neighborhood" : "SMAA neighborhood");
        smaa_ready[q] = smaa_edge_prog[q] && smaa_weight_prog[q] && smaa_neighborhood_prog[q];
        if (!smaa_ready[q]) {
            sysLogPrintf(LOG_WARNING, "GL: %s unavailable; SMAA Lite fallback will be used", high ? "SMAA High" : "SMAA");
        }
    }
'''
count = text.count(old_init)
if count != 1:
    raise SystemExit(f"SMAA High: expected one reference initialization loop, found {count}")
text = text.replace(old_init, new_init, 1)

old_ready_comment = "static bool smaa_ready[2]; // 0 = High/Multi, 1 = Ultra"
new_ready_comment = "static bool smaa_ready[2]; // 0 = SMAA (upstream Ultra), 1 = SMAA High (custom above-Ultra)"
count = text.count(old_ready_comment)
if count != 1:
    raise SystemExit(f"SMAA High: expected one ready-slot comment, found {count}")
text = text.replace(old_ready_comment, new_ready_comment, 1)

GFX.write_text(text)
print("two-sided SMAA resolve: restored normalized two-neighbor reference resolve with OpenGL directional mapping")
print("SMAA High: mode 3 = upstream Ultra; mode 4 = threshold .025, search 64, diagonal 20, corner 25")

# Finalize the user-facing AA menu without changing the 0..4 config range:
#   0 Off, 1 FXAA, 2 SMAA Lite, 3 SMAA (upstream Ultra),
#   4 SMAA High (custom above-Ultra preset).
# Keep diagnostic shader/readback machinery compiled for CI/future debugging,
# but remove the diagnostic/boost controls from the normal Post FX menu.
options = OPTIONS.read_text()

old_opts = 'static const char *opts[] = { "Off", "FXAA", "SMAA Lite", "SMAA Multi", "SMAA Ultra" };'
new_opts = 'static const char *opts[] = { "Off", "FXAA", "SMAA Lite", "SMAA", "SMAA High" };'
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

api = API.read_text()
old_api = "extern int gfx_post_aa;            // 0 off, 1 FXAA, 2 SMAA Lite, 3 SMAA Multi (High), 4 SMAA Ultra"
new_api = "extern int gfx_post_aa;            // 0 off, 1 FXAA, 2 SMAA Lite, 3 SMAA (Ultra), 4 SMAA High (custom)"
count = api.count(old_api)
if count != 1:
    raise SystemExit(f"SMAA cleanup: expected one generated API mode comment, found {count}")
API.write_text(api.replace(old_api, new_api, 1))

print("SMAA cleanup: final Post AA menu is Off / FXAA / SMAA Lite / SMAA / SMAA High")

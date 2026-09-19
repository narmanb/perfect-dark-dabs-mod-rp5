#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GFX_PATH = ROOT / "port/fast3d/gfx_opengl.cpp"
text = GFX_PATH.read_text()


def replace_once(old, new, label):
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"postfx tuning: expected one {label}, found {count}")
    text = text.replace(old, new, 1)


def replace_file_once(relpath, old, new, label):
    p = ROOT / relpath
    src = p.read_text()
    count = src.count(old)
    if count != 1:
        raise SystemExit(f"postfx tuning: expected one {label} in {relpath}, found {count}")
    p.write_text(src.replace(old, new, 1))
    print(f"postfx tuning: patched {relpath}: {label}")


# Run 51 established that the old Strong sharpen is only barely visible at
# normal RP5 viewing distance. Treat that old Strong as the new Light baseline,
# then scale radius/gain aggressively enough that Medium and Strong are visibly
# different without needing screenshot zoom. Adaptive still reins in the worst
# halos, while Basic is intentionally unrestricted.
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
    '        float radius = (uSharpen == 1 ? 2.4 : (uSharpen == 2 ? 3.3 : 4.4));\\n" \\\n'
    '    "        vec2 px = uTexel * radius;\\n" \\\n'
    '    "        n = texture(uTex, vUV + vec2(0.0, -px.y)).rgb;\\n" \\\n'
    '    "        s = texture(uTex, vUV + vec2(0.0,  px.y)).rgb;\\n" \\\n'
    '    "        e = texture(uTex, vUV + vec2( px.x, 0.0)).rgb;\\n" \\\n'
    '    "        w = texture(uTex, vUV + vec2(-px.x, 0.0)).rgb;\\n" \\\n'
    '    "        float amount = (uSharpen == 1 ? 1.65 : (uSharpen == 2 ? 3.00 : 4.60));\\n" \\\n'
    '    "        vec3 blur4 = (n + s + e + w) * 0.25;\\n" \\\n'
    '    "        vec3 detail = c - blur4;\\n" \\\n'
    '    "        if (uSharpenMode != 0) {\\n" \\\n'
    '    "            float edge = max(max(length(c - n), length(c - s)), max(length(c - e), length(c - w)));\\n" \\\n'
    '    "            amount *= mix(0.88, 1.0, clamp(edge * 1.8, 0.0, 1.0));\\n" \\\n'
    '    "        }\\n" \\\n'
    '    "        vec3 sh = c + detail * amount;\\n" \\\n'
    '    "        if (uSharpenMode != 0) {\\n" \\\n'
    '    "            vec3 lo = min(c, min(min(n, s), min(e, w)));\\n" \\\n'
    '    "            vec3 hi = max(c, max(max(n, s), max(e, w)));\\n" \\\n'
    '    "            vec3 range = max(hi - lo, vec3(1.0 / 255.0));\\n" \\\n'
    '    "            float allowance = (uSharpen == 1 ? 0.85 : (uSharpen == 2 ? 1.45 : 2.30));\\n" \\\n'
    '    "            sh = clamp(sh, lo - range * allowance, hi + range * allowance);\\n" \\\n'
    '    "        }\\n" \\\n',
    "adaptive sharpen body",
)

# Shift the Run 51 grain curve upward exactly as requested: old Medium becomes
# new Light, old Strong becomes new Medium, and Strong gets a clearly heavier
# grain level. The coarser cell size also makes it survive a small 1080p panel.
replace_once(
    '    "    float noise = hash12(gl_FragCoord.xy + vec2(float(uFrame) * 0.7549, float(uFrame) * 0.5693)) - 0.5;\\n" \\\n',
    '    "    float grainCell = (uGrain == 3 ? 2.25 : (uGrain == 2 ? 1.75 : (uGrain == 1 ? 1.35 : 1.0)));\\n" \\\n'
    '    "    float grainFrame = floor(float(uFrame) / 3.0);\\n" \\\n'
    '    "    vec2 grainCoord = floor(gl_FragCoord.xy / grainCell);\\n" \\\n'
    '    "    float noise = hash12(grainCoord + vec2(grainFrame * 0.7549, grainFrame * 0.5693)) - 0.5;\\n" \\\n',
    "film grain noise seed",
)

replace_once(
    '        float gs = (uGrain == 1 ? 0.012 : (uGrain == 2 ? 0.024 : 0.040));\\n" \\\n',
    '        float gs = (uGrain == 1 ? 0.090 : (uGrain == 2 ? 0.180 : 0.320));\\n" \\\n',
    "film grain strength",
)

# ---- Phase 2: bloom family -------------------------------------------------
# These effects stay in the already-proven final GLES pass. Bloom uses a
# bright-pass neighbourhood, lens dirt is only revealed by that bright-pass,
# and light streaks sample bright pixels horizontally. Uniform branches keep
# the extra texture reads dormant when the controls are Off.
replace_file_once(
    "port/fast3d/gfx_api.h",
    "extern int gfx_post_dither;        // 0-3\n",
    "extern int gfx_post_dither;        // 0-3\n"
    "extern int gfx_post_bloom;         // 0-3: off/light/medium/strong\n"
    "extern int gfx_post_bloom_threshold; // 0-3: low/medium/high/very high\n"
    "extern int gfx_post_bloom_radius;  // 0-3: tight/medium/wide/very wide\n"
    "extern int gfx_post_lens_dirt;     // 0-3\n"
    "extern int gfx_post_light_streaks; // 0-3\n",
    "phase2 gfx api globals",
)

replace_file_once(
    "port/fast3d/gfx_pc.cpp",
    "int gfx_post_dither = 0;\n",
    "int gfx_post_dither = 0;\n"
    "int gfx_post_bloom = 0;\n"
    "int gfx_post_bloom_threshold = 1;\n"
    "int gfx_post_bloom_radius = 1;\n"
    "int gfx_post_lens_dirt = 0;\n"
    "int gfx_post_light_streaks = 0;\n",
    "phase2 gfx globals",
)

replace_once(
    "static GLint grade_loc_tonemap, grade_loc_posterize, grade_loc_dither;\n",
    "static GLint grade_loc_tonemap, grade_loc_posterize, grade_loc_dither;\n"
    "static GLint grade_loc_bloom, grade_loc_bloom_threshold, grade_loc_bloom_radius;\n"
    "static GLint grade_loc_lens_dirt, grade_loc_light_streaks;\n",
    "phase2 uniform declarations",
)

replace_once(
    '    "uniform int uDither;\\n" \\\n',
    '    "uniform int uDither;\\n" \\\n'
    '    "uniform int uBloom;\\n" \\\n'
    '    "uniform int uBloomThreshold;\\n" \\\n'
    '    "uniform int uBloomRadius;\\n" \\\n'
    '    "uniform int uLensDirt;\\n" \\\n'
    '    "uniform int uLightStreaks;\\n" \\\n',
    "phase2 shader uniforms",
)

replace_once(
    '    "    return fract((p3.x + p3.y) * p3.z);\\n" \\\n'
    '    "}\\n" \\\n',
    '    "    return fract((p3.x + p3.y) * p3.z);\\n" \\\n'
    '    "}\\n" \\\n'
    '    "vec3 bloomExtract(vec3 x, float threshold) {\\n" \\\n'
    '    "    float peak = max(x.r, max(x.g, x.b));\\n" \\\n'
    '    "    float gate = smoothstep(threshold, min(threshold + 0.24, 1.0), peak);\\n" \\\n'
    '    "    return x * gate;\\n" \\\n'
    '    "}\\n" \\\n',
    "bloom extract helper",
)

replace_once(
    '    "    c = max(c - uBlack, 0.0) / (1.0 - uBlack);\\n" \\\n',
    '    "    if (uBloom > 0 || uLensDirt > 0 || uLightStreaks > 0) {\\n" \\\n'
    '    "        float threshold = (uBloomThreshold == 0 ? 0.52 : (uBloomThreshold == 1 ? 0.66 : (uBloomThreshold == 2 ? 0.78 : 0.88)));\\n" \\\n'
    '    "        float radius = (uBloomRadius == 0 ? 2.0 : (uBloomRadius == 1 ? 4.0 : (uBloomRadius == 2 ? 7.0 : 11.0)));\\n" \\\n'
    '    "        vec2 bp = uTexel * radius;\\n" \\\n'
    '    "        vec3 bloom = bloomExtract(texture(uTex, vUV).rgb, threshold) * 0.18;\\n" \\\n'
    '    "        bloom += bloomExtract(texture(uTex, vUV + vec2( bp.x, 0.0)).rgb, threshold) * 0.12;\\n" \\\n'
    '    "        bloom += bloomExtract(texture(uTex, vUV + vec2(-bp.x, 0.0)).rgb, threshold) * 0.12;\\n" \\\n'
    '    "        bloom += bloomExtract(texture(uTex, vUV + vec2(0.0,  bp.y)).rgb, threshold) * 0.12;\\n" \\\n'
    '    "        bloom += bloomExtract(texture(uTex, vUV + vec2(0.0, -bp.y)).rgb, threshold) * 0.12;\\n" \\\n'
    '    "        bloom += bloomExtract(texture(uTex, vUV + vec2( bp.x,  bp.y)).rgb, threshold) * 0.085;\\n" \\\n'
    '    "        bloom += bloomExtract(texture(uTex, vUV + vec2(-bp.x,  bp.y)).rgb, threshold) * 0.085;\\n" \\\n'
    '    "        bloom += bloomExtract(texture(uTex, vUV + vec2( bp.x, -bp.y)).rgb, threshold) * 0.085;\\n" \\\n'
    '    "        bloom += bloomExtract(texture(uTex, vUV + vec2(-bp.x, -bp.y)).rgb, threshold) * 0.085;\\n" \\\n'
    '    "        float bloomStrength = (uBloom == 1 ? 0.32 : (uBloom == 2 ? 0.62 : (uBloom == 3 ? 1.00 : 0.0)));\\n" \\\n'
    '    "        c += bloom * bloomStrength;\\n" \\\n'
    '    "        if (uLensDirt > 0) {\\n" \\\n'
    '    "            vec2 duv = vUV - vec2(0.5);\\n" \\\n'
    '    "            float rings = 0.5 + 0.5 * sin(length(duv * vec2(1.12, 0.92)) * 47.0 + sin(duv.x * 31.0) * 1.7);\\n" \\\n'
    '    "            float smudge = 0.5 + 0.25 * sin(vUV.x * 19.0 + vUV.y * 13.0) + 0.25 * sin(vUV.x * 7.0 - vUV.y * 23.0);\\n" \\\n'
    '    "            float dirt = clamp(rings * 0.45 + smudge * 0.55, 0.0, 1.0);\\n" \\\n'
    '    "            dirt = smoothstep(0.38, 0.82, dirt);\\n" \\\n'
    '    "            float dirtStrength = (uLensDirt == 1 ? 0.12 : (uLensDirt == 2 ? 0.25 : 0.42));\\n" \\\n'
    '    "            c += bloom * dirt * dirtStrength;\\n" \\\n'
    '    "        }\\n" \\\n'
    '    "        if (uLightStreaks > 0) {\\n" \\\n'
    '    "            vec3 streak = vec3(0.0);\\n" \\\n'
    '    "            streak += bloomExtract(texture(uTex, vUV + vec2(bp.x * 2.5, 0.0)).rgb, threshold) * 0.22;\\n" \\\n'
    '    "            streak += bloomExtract(texture(uTex, vUV - vec2(bp.x * 2.5, 0.0)).rgb, threshold) * 0.22;\\n" \\\n'
    '    "            streak += bloomExtract(texture(uTex, vUV + vec2(bp.x * 5.0, 0.0)).rgb, threshold) * 0.14;\\n" \\\n'
    '    "            streak += bloomExtract(texture(uTex, vUV - vec2(bp.x * 5.0, 0.0)).rgb, threshold) * 0.14;\\n" \\\n'
    '    "            streak += bloomExtract(texture(uTex, vUV + vec2(bp.x * 8.0, 0.0)).rgb, threshold) * 0.08;\\n" \\\n'
    '    "            streak += bloomExtract(texture(uTex, vUV - vec2(bp.x * 8.0, 0.0)).rgb, threshold) * 0.08;\\n" \\\n'
    '    "            float streakStrength = (uLightStreaks == 1 ? 0.10 : (uLightStreaks == 2 ? 0.22 : 0.38));\\n" \\\n'
    '    "            c += streak * streakStrength;\\n" \\\n'
    '    "        }\\n" \\\n'
    '    "    }\\n" \\\n'
    '    "    c = max(c - uBlack, 0.0) / (1.0 - uBlack);\\n" \\\n',
    "bloom family shader body",
)

replace_once(
    '    grade_loc_dither = glGetUniformLocation(grade_prog, "uDither");\n',
    '    grade_loc_dither = glGetUniformLocation(grade_prog, "uDither");\n'
    '    grade_loc_bloom = glGetUniformLocation(grade_prog, "uBloom");\n'
    '    grade_loc_bloom_threshold = glGetUniformLocation(grade_prog, "uBloomThreshold");\n'
    '    grade_loc_bloom_radius = glGetUniformLocation(grade_prog, "uBloomRadius");\n'
    '    grade_loc_lens_dirt = glGetUniformLocation(grade_prog, "uLensDirt");\n'
    '    grade_loc_light_streaks = glGetUniformLocation(grade_prog, "uLightStreaks");\n',
    "phase2 uniform lookup",
)

replace_once(
    '        gfx_post_tonemap == 0 && gfx_post_posterize == 0 && gfx_post_dither == 0) {\n',
    '        gfx_post_tonemap == 0 && gfx_post_posterize == 0 && gfx_post_dither == 0 &&\n'
    '        gfx_post_bloom == 0 && gfx_post_lens_dirt == 0 && gfx_post_light_streaks == 0) {\n',
    "phase2 neutral early-out",
)

replace_once(
    '        glUniform1i(grade_loc_dither, gfx_post_dither);\n'
    '        glDrawArrays(GL_TRIANGLES, 0, 3);\n',
    '        glUniform1i(grade_loc_dither, gfx_post_dither);\n'
    '        glUniform1i(grade_loc_bloom, gfx_post_bloom);\n'
    '        glUniform1i(grade_loc_bloom_threshold, gfx_post_bloom_threshold);\n'
    '        glUniform1i(grade_loc_bloom_radius, gfx_post_bloom_radius);\n'
    '        glUniform1i(grade_loc_lens_dirt, gfx_post_lens_dirt);\n'
    '        glUniform1i(grade_loc_light_streaks, gfx_post_light_streaks);\n'
    '        glDrawArrays(GL_TRIANGLES, 0, 3);\n',
    "phase2 uniform upload",
)

GFX_PATH.write_text(text)
print("postfx tuning: sharpen/grain retuned and bloom-family shader added")

# Menu/config plumbing for the phase-2 controls.
replace_file_once(
    "port/src/optionsmenu.c",
    "static s32 g_PostFxDither = 0;\n",
    "static s32 g_PostFxDither = 0;\n"
    "static s32 g_PostFxBloom = 0;\n"
    "static s32 g_PostFxBloomThreshold = 1;\n"
    "static s32 g_PostFxBloomRadius = 1;\n"
    "static s32 g_PostFxLensDirt = 0;\n"
    "static s32 g_PostFxLightStreaks = 0;\n",
    "phase2 menu state",
)

replace_file_once(
    "port/src/optionsmenu.c",
    "\tgfx_post_dither = g_PostFxDither;\n",
    "\tgfx_post_dither = g_PostFxDither;\n"
    "\tgfx_post_bloom = g_PostFxBloom;\n"
    "\tgfx_post_bloom_threshold = g_PostFxBloomThreshold;\n"
    "\tgfx_post_bloom_radius = g_PostFxBloomRadius;\n"
    "\tgfx_post_lens_dirt = g_PostFxLensDirt;\n"
    "\tgfx_post_light_streaks = g_PostFxLightStreaks;\n",
    "phase2 postFxApply",
)

replace_file_once(
    "port/src/optionsmenu.c",
    '\tconfigRegisterInt("Video.PostFxDither", &g_PostFxDither, 0, 3);\n',
    '\tconfigRegisterInt("Video.PostFxDither", &g_PostFxDither, 0, 3);\n'
    '\tconfigRegisterInt("Video.PostFxBloom", &g_PostFxBloom, 0, 3);\n'
    '\tconfigRegisterInt("Video.PostFxBloomThreshold", &g_PostFxBloomThreshold, 0, 3);\n'
    '\tconfigRegisterInt("Video.PostFxBloomRadius", &g_PostFxBloomRadius, 0, 3);\n'
    '\tconfigRegisterInt("Video.PostFxLensDirt", &g_PostFxLensDirt, 0, 3);\n'
    '\tconfigRegisterInt("Video.PostFxLightStreaks", &g_PostFxLightStreaks, 0, 3);\n',
    "phase2 config",
)

handlers = r'''static MenuItemHandlerResult menuhandlerPostFxBloomThreshold(s32 operation, struct menuitem *item, union handlerdata *data)
{
	static const char *opts[] = { "Low", "Medium", "High", "Very High" };
	switch (operation) {
	case MENUOP_GETOPTIONCOUNT: data->dropdown.value = ARRAYCOUNT(opts); break;
	case MENUOP_GETOPTIONTEXT: return (intptr_t)opts[data->dropdown.value];
	case MENUOP_SET: g_PostFxBloomThreshold = data->dropdown.value; postFxApply(); break;
	case MENUOP_GETSELECTEDINDEX: data->dropdown.value = g_PostFxBloomThreshold; break;
	}
	return 0;
}

static MenuItemHandlerResult menuhandlerPostFxBloomRadius(s32 operation, struct menuitem *item, union handlerdata *data)
{
	static const char *opts[] = { "Tight", "Medium", "Wide", "Very Wide" };
	switch (operation) {
	case MENUOP_GETOPTIONCOUNT: data->dropdown.value = ARRAYCOUNT(opts); break;
	case MENUOP_GETOPTIONTEXT: return (intptr_t)opts[data->dropdown.value];
	case MENUOP_SET: g_PostFxBloomRadius = data->dropdown.value; postFxApply(); break;
	case MENUOP_GETSELECTEDINDEX: data->dropdown.value = g_PostFxBloomRadius; break;
	}
	return 0;
}

'''
replace_file_once(
    "port/src/optionsmenu.c",
    "#define POSTFX_LEVEL_ITEM(label, var) \\\n",
    handlers + "#define POSTFX_LEVEL_ITEM(label, var) \\\n",
    "phase2 dropdown handlers",
)

replace_file_once(
    "port/src/optionsmenu.c",
    '\tPOSTFX_LEVEL_ITEM("Dithering", g_PostFxDither),\n'
    '\t{ MENUITEMTYPE_SEPARATOR, 0, 0, 0, 0, NULL },\n',
    '\tPOSTFX_LEVEL_ITEM("Dithering", g_PostFxDither),\n'
    '\t{ MENUITEMTYPE_SEPARATOR, 0, 0, 0, 0, NULL },\n'
    '\tPOSTFX_LEVEL_ITEM("Bloom", g_PostFxBloom),\n'
    '\t{ MENUITEMTYPE_DROPDOWN, 0, MENUITEMFLAG_LITERAL_TEXT, (uintptr_t)"Bloom Threshold", 0, menuhandlerPostFxBloomThreshold },\n'
    '\t{ MENUITEMTYPE_DROPDOWN, 0, MENUITEMFLAG_LITERAL_TEXT, (uintptr_t)"Bloom Radius", 0, menuhandlerPostFxBloomRadius },\n'
    '\tPOSTFX_LEVEL_ITEM("Lens Dirt", g_PostFxLensDirt),\n'
    '\tPOSTFX_LEVEL_ITEM("Light Streaks", g_PostFxLightStreaks),\n'
    '\t{ MENUITEMTYPE_SEPARATOR, 0, 0, 0, 0, NULL },\n',
    "phase2 menu items",
)

print("postfx tuning: phase2 menu/config plumbing added")

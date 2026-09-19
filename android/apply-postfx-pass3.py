#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GFX = ROOT / "port/fast3d/gfx_opengl.cpp"


def replace_file_once(relpath, old, new, label):
    p = ROOT / relpath
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"postfx pass3: expected one {label} in {relpath}, found {count}")
    p.write_text(text.replace(old, new, 1))
    print(f"postfx pass3: patched {relpath}: {label}")


text = GFX.read_text()


def replace_once(old, new, label):
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"postfx pass3: expected one {label}, found {count}")
    text = text.replace(old, new, 1)


# Renderer/config globals.
replace_file_once(
    "port/fast3d/gfx_api.h",
    "extern int gfx_post_light_streaks; // 0-3\n",
    "extern int gfx_post_light_streaks; // 0-3\n"
    "extern int gfx_post_chromatic;     // 0-3: off/light/medium/strong\n"
    "extern int gfx_post_lens_distort;  // 0-3: off/light/medium/strong\n"
    "extern int gfx_post_aa;            // 0 off, 1 FXAA, 2 SMAA Lite\n",
    "pass3 gfx api globals",
)

replace_file_once(
    "port/fast3d/gfx_pc.cpp",
    "int gfx_post_light_streaks = 0;\n",
    "int gfx_post_light_streaks = 0;\n"
    "int gfx_post_chromatic = 0;\n"
    "int gfx_post_lens_distort = 0;\n"
    "int gfx_post_aa = 0;\n",
    "pass3 gfx globals",
)

replace_once(
    "static GLint grade_loc_lens_dirt, grade_loc_light_streaks;\n",
    "static GLint grade_loc_lens_dirt, grade_loc_light_streaks;\n"
    "static GLint grade_loc_chromatic, grade_loc_lens_distort, grade_loc_aa;\n",
    "pass3 uniform declarations",
)

replace_once(
    '    "uniform int uLightStreaks;\\n" \\\n'
    '    "in vec2 vUV;\\n" \\\n',
    '    "uniform int uLightStreaks;\\n" \\\n'
    '    "uniform int uChromatic;\\n" \\\n'
    '    "uniform int uLensDistort;\\n" \\\n'
    '    "uniform int uPostAA;\\n" \\\n'
    '    "in vec2 vUV;\\n" \\\n',
    "pass3 shader uniforms",
)

# Add source-sampling helpers. Lens distortion and chromatic aberration are
# applied at sample time so bloom/sharpen/source AA all see the same warped
# scene. FXAA is a conventional luminance-direction resolve. "SMAA Lite" is a
# single-pass directional morphological edge blend; it intentionally avoids the
# search/area lookup textures and extra framebuffer passes of full SMAA 1x.
helpers = r'''    "float sceneLuma(vec3 x) {\n" \
    "    return dot(x, vec3(0.299, 0.587, 0.114));\n" \
    "}\n" \
    "vec2 lensWarp(vec2 uv) {\n" \
    "    if (uLensDistort <= 0) return uv;\n" \
    "    vec2 p = uv - vec2(0.5);\n" \
    "    float r2 = dot(p, p);\n" \
    "    float k = (uLensDistort == 1 ? 0.025 : (uLensDistort == 2 ? 0.060 : 0.120));\n" \
    "    p *= 1.0 - k * r2 * 2.0;\n" \
    "    return clamp(vec2(0.5) + p, vec2(0.001), vec2(0.999));\n" \
    "}\n" \
    "vec3 sceneSample(vec2 uv) {\n" \
    "    uv = lensWarp(uv);\n" \
    "    vec3 base = texture(uTex, uv).rgb;\n" \
    "    if (uChromatic <= 0) return base;\n" \
    "    vec2 d = uv - vec2(0.5);\n" \
    "    float pixels = (uChromatic == 1 ? 4.0 : (uChromatic == 2 ? 9.0 : 18.0));\n" \
    "    vec2 off = d * pixels * uTexel;\n" \
    "    vec2 ur = clamp(uv + off, vec2(0.001), vec2(0.999));\n" \
    "    vec2 ub = clamp(uv - off, vec2(0.001), vec2(0.999));\n" \
    "    base.r = texture(uTex, ur).r;\n" \
    "    base.b = texture(uTex, ub).b;\n" \
    "    return base;\n" \
    "}\n" \
    "vec3 fxaaResolve(vec2 uv) {\n" \
    "    vec3 rgbM = sceneSample(uv);\n" \
    "    float lumaM = sceneLuma(rgbM);\n" \
    "    float lumaNW = sceneLuma(sceneSample(uv + vec2(-uTexel.x, -uTexel.y)));\n" \
    "    float lumaNE = sceneLuma(sceneSample(uv + vec2( uTexel.x, -uTexel.y)));\n" \
    "    float lumaSW = sceneLuma(sceneSample(uv + vec2(-uTexel.x,  uTexel.y)));\n" \
    "    float lumaSE = sceneLuma(sceneSample(uv + vec2( uTexel.x,  uTexel.y)));\n" \
    "    float lumaMin = min(lumaM, min(min(lumaNW, lumaNE), min(lumaSW, lumaSE)));\n" \
    "    float lumaMax = max(lumaM, max(max(lumaNW, lumaNE), max(lumaSW, lumaSE)));\n" \
    "    if (lumaMax - lumaMin < 0.035) return rgbM;\n" \
    "    vec2 dir;\n" \
    "    dir.x = -((lumaNW + lumaNE) - (lumaSW + lumaSE));\n" \
    "    dir.y =  ((lumaNW + lumaSW) - (lumaNE + lumaSE));\n" \
    "    float dirReduce = max((lumaNW + lumaNE + lumaSW + lumaSE) * 0.03125, 0.0078125);\n" \
    "    float rcpDirMin = 1.0 / (min(abs(dir.x), abs(dir.y)) + dirReduce);\n" \
    "    dir = clamp(dir * rcpDirMin, vec2(-8.0), vec2(8.0)) * uTexel;\n" \
    "    vec3 rgbA = 0.5 * (sceneSample(uv + dir * (1.0 / 3.0 - 0.5)) +\n" \
    "                       sceneSample(uv + dir * (2.0 / 3.0 - 0.5)));\n" \
    "    vec3 rgbB = rgbA * 0.5 + 0.25 * (sceneSample(uv + dir * -0.5) + sceneSample(uv + dir * 0.5));\n" \
    "    float lumaB = sceneLuma(rgbB);\n" \
    "    return (lumaB < lumaMin || lumaB > lumaMax) ? rgbA : rgbB;\n" \
    "}\n" \
    "vec3 smaaLiteResolve(vec2 uv) {\n" \
    "    vec3 c = sceneSample(uv);\n" \
    "    vec3 n = sceneSample(uv + vec2(0.0, -uTexel.y));\n" \
    "    vec3 s = sceneSample(uv + vec2(0.0,  uTexel.y));\n" \
    "    vec3 e = sceneSample(uv + vec2( uTexel.x, 0.0));\n" \
    "    vec3 w = sceneSample(uv + vec2(-uTexel.x, 0.0));\n" \
    "    float lc = sceneLuma(c);\n" \
    "    float edgeH = max(abs(lc - sceneLuma(n)), abs(lc - sceneLuma(s)));\n" \
    "    float edgeV = max(abs(lc - sceneLuma(e)), abs(lc - sceneLuma(w)));\n" \
    "    float edge = max(edgeH, edgeV);\n" \
    "    if (edge < 0.030) return c;\n" \
    "    vec3 along = edgeH > edgeV ? (e + w) * 0.5 : (n + s) * 0.5;\n" \
    "    float weight = smoothstep(0.030, 0.180, edge) * 0.72;\n" \
    "    return mix(c, (c * 0.45 + along * 0.55), weight);\n" \
    "}\n" \
    "vec3 resolveScene(vec2 uv) {\n" \
    "    if (uPostAA == 1) return fxaaResolve(uv);\n" \
    "    if (uPostAA == 2) return smaaLiteResolve(uv);\n" \
    "    return sceneSample(uv);\n" \
    "}\n" \
'''

replace_once(
    '    "vec3 gradePreset(vec3 c, int mode) {\\n" \\\n',
    helpers + '    "vec3 gradePreset(vec3 c, int mode) {\\n" \\\n',
    "pass3 sampling helpers",
)

# Route all existing scene texture reads through lens/chromatic sampling. Then
# let the main colour path choose the requested post-AA resolve.
count = text.count("texture(uTex, vUV")
if count < 1:
    raise SystemExit("postfx pass3: expected scene texture reads")
text = text.replace("texture(uTex, vUV", "sceneSample(vUV")
replace_once(
    '    "    vec3 c = sceneSample(vUV).rgb;\\n" \\\n',
    '    "    vec3 c = resolveScene(vUV);\\n" \\\n',
    "pass3 main AA resolve",
)

replace_once(
    '    grade_loc_light_streaks = glGetUniformLocation(grade_prog, "uLightStreaks");\n',
    '    grade_loc_light_streaks = glGetUniformLocation(grade_prog, "uLightStreaks");\n'
    '    grade_loc_chromatic = glGetUniformLocation(grade_prog, "uChromatic");\n'
    '    grade_loc_lens_distort = glGetUniformLocation(grade_prog, "uLensDistort");\n'
    '    grade_loc_aa = glGetUniformLocation(grade_prog, "uPostAA");\n',
    "pass3 uniform lookup",
)

replace_once(
    '        gfx_post_bloom == 0 && gfx_post_lens_dirt == 0 && gfx_post_light_streaks == 0) {\n',
    '        gfx_post_bloom == 0 && gfx_post_lens_dirt == 0 && gfx_post_light_streaks == 0 &&\n'
    '        gfx_post_chromatic == 0 && gfx_post_lens_distort == 0 && gfx_post_aa == 0) {\n',
    "pass3 neutral early-out",
)

replace_once(
    '        glUniform1i(grade_loc_light_streaks, gfx_post_light_streaks);\n'
    '        glDrawArrays(GL_TRIANGLES, 0, 3);\n',
    '        glUniform1i(grade_loc_light_streaks, gfx_post_light_streaks);\n'
    '        glUniform1i(grade_loc_chromatic, gfx_post_chromatic);\n'
    '        glUniform1i(grade_loc_lens_distort, gfx_post_lens_distort);\n'
    '        glUniform1i(grade_loc_aa, gfx_post_aa);\n'
    '        glDrawArrays(GL_TRIANGLES, 0, 3);\n',
    "pass3 uniform upload",
)

GFX.write_text(text)
print(f"postfx pass3: routed {count} scene texture reads and added aberration/distortion/AA")

# Menu/config plumbing.
replace_file_once(
    "port/src/optionsmenu.c",
    "static s32 g_PostFxLightStreaks = 0;\n",
    "static s32 g_PostFxLightStreaks = 0;\n"
    "static s32 g_PostFxChromatic = 0;\n"
    "static s32 g_PostFxLensDistort = 0;\n"
    "static s32 g_PostFxAA = 0;\n",
    "pass3 menu state",
)

replace_file_once(
    "port/src/optionsmenu.c",
    "\tgfx_post_light_streaks = g_PostFxLightStreaks;\n",
    "\tgfx_post_light_streaks = g_PostFxLightStreaks;\n"
    "\tgfx_post_chromatic = g_PostFxChromatic;\n"
    "\tgfx_post_lens_distort = g_PostFxLensDistort;\n"
    "\tgfx_post_aa = g_PostFxAA;\n",
    "pass3 postFxApply",
)

replace_file_once(
    "port/src/optionsmenu.c",
    '\tconfigRegisterInt("Video.PostFxLightStreaks", &g_PostFxLightStreaks, 0, 3);\n',
    '\tconfigRegisterInt("Video.PostFxLightStreaks", &g_PostFxLightStreaks, 0, 3);\n'
    '\tconfigRegisterInt("Video.PostFxChromatic", &g_PostFxChromatic, 0, 3);\n'
    '\tconfigRegisterInt("Video.PostFxLensDistort", &g_PostFxLensDistort, 0, 3);\n'
    '\tconfigRegisterInt("Video.PostFxAA", &g_PostFxAA, 0, 2);\n',
    "pass3 config",
)

aa_handler = r'''static MenuItemHandlerResult menuhandlerPostFxAA(s32 operation, struct menuitem *item, union handlerdata *data)
{
	static const char *opts[] = { "Off", "FXAA", "SMAA Lite" };
	switch (operation) {
	case MENUOP_GETOPTIONCOUNT: data->dropdown.value = ARRAYCOUNT(opts); break;
	case MENUOP_GETOPTIONTEXT: return (intptr_t)opts[data->dropdown.value];
	case MENUOP_SET: g_PostFxAA = data->dropdown.value; postFxApply(); break;
	case MENUOP_GETSELECTEDINDEX: data->dropdown.value = g_PostFxAA; break;
	}
	return 0;
}

'''

replace_file_once(
    "port/src/optionsmenu.c",
    "#define POSTFX_LEVEL_ITEM(label, var) \\\n",
    aa_handler + "#define POSTFX_LEVEL_ITEM(label, var) \\\n",
    "pass3 AA handler",
)

replace_file_once(
    "port/src/optionsmenu.c",
    '\tPOSTFX_LEVEL_ITEM("Light Streaks", g_PostFxLightStreaks),\n'
    '\t{ MENUITEMTYPE_SEPARATOR, 0, 0, 0, 0, NULL },\n',
    '\tPOSTFX_LEVEL_ITEM("Light Streaks", g_PostFxLightStreaks),\n'
    '\t{ MENUITEMTYPE_SEPARATOR, 0, 0, 0, 0, NULL },\n'
    '\tPOSTFX_LEVEL_ITEM("Chromatic Aberration", g_PostFxChromatic),\n'
    '\tPOSTFX_LEVEL_ITEM("Lens Distortion", g_PostFxLensDistort),\n'
    '\t{ MENUITEMTYPE_DROPDOWN, 0, MENUITEMFLAG_LITERAL_TEXT, (uintptr_t)"Post AA", 0, menuhandlerPostFxAA },\n'
    '\t{ MENUITEMTYPE_SEPARATOR, 0, 0, 0, 0, NULL },\n',
    "pass3 menu items",
)

print("postfx pass3: menu/config plumbing added")

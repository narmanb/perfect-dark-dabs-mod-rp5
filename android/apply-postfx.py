#!/usr/bin/env python3
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def patch(path, fn):
    p = ROOT / path
    old = p.read_text()
    new = fn(old)
    if new == old:
        raise SystemExit(f"postfx patch made no changes to {path}")
    p.write_text(new)
    print(f"postfx: patched {path}")


def replace_once(text, old, new, label):
    if text.count(old) != 1:
        raise SystemExit(f"postfx: expected one {label}, found {text.count(old)}")
    return text.replace(old, new, 1)


def patch_gfx_api(text):
    old = '''extern float gfx_color_saturation;\nextern float gfx_color_contrast;\nextern float gfx_color_black_level;\n'''
    new = old + '''\n// Optional finished-frame post effects. Zero is neutral/off unless noted.\n// All are deliberately backend-neutral settings; the OpenGL/GLES backend\n// consumes them in the same final pass as Vivid Colours and Black Level.\nextern int gfx_post_sharpen;       // 0-3: off/light/medium/strong\nextern int gfx_post_sharpen_mode;  // 0 basic, 1 adaptive\nextern int gfx_post_vignette;      // 0-3\nextern int gfx_post_grain;         // 0-3\nextern int gfx_post_grade;         // 0 neutral, 1 cinematic, 2 cool, 3 warm, 4 night, 5 mono, 6 sepia\nextern int gfx_post_exposure;      // -2..2\nextern int gfx_post_gamma;         // -2..2\nextern int gfx_post_vibrance;      // 0-3\nextern int gfx_post_temperature;   // -2..2\nextern int gfx_post_tint;          // -2..2\nextern int gfx_post_whitepoint;    // -2..2\nextern int gfx_post_tonemap;       // 0 off, 1 Reinhard, 2 filmic\nextern int gfx_post_posterize;     // 0 off, 1 16 levels, 2 8, 3 4\nextern int gfx_post_dither;        // 0-3\n'''
    return replace_once(text, old, new, 'gfx_api colour globals')


def patch_gfx_pc(text):
    old = '''float gfx_color_saturation = 1.0f;\nfloat gfx_color_contrast = 1.0f;\nfloat gfx_color_black_level = 0.0f;\n'''
    new = old + '''int gfx_post_sharpen = 0;\nint gfx_post_sharpen_mode = 1;\nint gfx_post_vignette = 0;\nint gfx_post_grain = 0;\nint gfx_post_grade = 0;\nint gfx_post_exposure = 0;\nint gfx_post_gamma = 0;\nint gfx_post_vibrance = 0;\nint gfx_post_temperature = 0;\nint gfx_post_tint = 0;\nint gfx_post_whitepoint = 0;\nint gfx_post_tonemap = 0;\nint gfx_post_posterize = 0;\nint gfx_post_dither = 0;\n'''
    return replace_once(text, old, new, 'gfx_pc colour globals')


def patch_gfx_opengl(text):
    text = replace_once(
        text,
        'static GLint grade_loc_saturation, grade_loc_contrast, grade_loc_black;\n',
        '''static GLint grade_loc_saturation, grade_loc_contrast, grade_loc_black;\nstatic GLint grade_loc_texel, grade_loc_frame;\nstatic GLint grade_loc_sharpen, grade_loc_sharpen_mode, grade_loc_vignette, grade_loc_grain;\nstatic GLint grade_loc_grade, grade_loc_exposure, grade_loc_gamma, grade_loc_vibrance;\nstatic GLint grade_loc_temperature, grade_loc_tint, grade_loc_whitepoint;\nstatic GLint grade_loc_tonemap, grade_loc_posterize, grade_loc_dither;\n''',
        'grade uniform declarations')

    start = text.find('static const char *grade_fs_desktop =')
    end = text.find('static GLuint gfx_opengl_grade_compile', start)
    if start < 0 or end < 0:
        raise SystemExit('postfx: grade shader block not found')

    shader = r'''#define GRADE_FS_BODY \
    "uniform sampler2D uTex;\n" \
    "uniform vec2 uTexel;\n" \
    "uniform int uFrame;\n" \
    "uniform float uSaturation;\n" \
    "uniform float uContrast;\n" \
    "uniform float uBlack;\n" \
    "uniform int uSharpen;\n" \
    "uniform int uSharpenMode;\n" \
    "uniform int uVignette;\n" \
    "uniform int uGrain;\n" \
    "uniform int uGrade;\n" \
    "uniform int uExposure;\n" \
    "uniform int uGamma;\n" \
    "uniform int uVibrance;\n" \
    "uniform int uTemperature;\n" \
    "uniform int uTint;\n" \
    "uniform int uWhitePoint;\n" \
    "uniform int uToneMap;\n" \
    "uniform int uPosterize;\n" \
    "uniform int uDither;\n" \
    "in vec2 vUV;\n" \
    "out vec4 oCol;\n" \
    "float hash12(vec2 p) {\n" \
    "    vec3 p3 = fract(vec3(p.xyx) * 0.1031);\n" \
    "    p3 += dot(p3, p3.yzx + 33.33);\n" \
    "    return fract((p3.x + p3.y) * p3.z);\n" \
    "}\n" \
    "vec3 gradePreset(vec3 c, int mode) {\n" \
    "    float l = dot(c, vec3(0.2126, 0.7152, 0.0722));\n" \
    "    if (mode == 1) {\n" \
    "        vec3 shadows = vec3(-0.020, 0.012, 0.025) * (1.0 - l);\n" \
    "        vec3 highs = vec3(0.030, 0.012, -0.010) * l;\n" \
    "        c = c + shadows + highs;\n" \
    "    } else if (mode == 2) {\n" \
    "        c *= vec3(0.96, 1.00, 1.06);\n" \
    "    } else if (mode == 3) {\n" \
    "        c *= vec3(1.06, 1.01, 0.95);\n" \
    "    } else if (mode == 4) {\n" \
    "        c = mix(vec3(l), c, 0.55) * vec3(0.78, 1.10, 0.84);\n" \
    "    } else if (mode == 5) {\n" \
    "        c = vec3(l);\n" \
    "    } else if (mode == 6) {\n" \
    "        c = vec3(dot(c, vec3(0.393, 0.769, 0.189)),\n" \
    "                 dot(c, vec3(0.349, 0.686, 0.168)),\n" \
    "                 dot(c, vec3(0.272, 0.534, 0.131)));\n" \
    "    }\n" \
    "    return c;\n" \
    "}\n" \
    "void main() {\n" \
    "    vec3 c = texture(uTex, vUV).rgb;\n" \
    "    if (uSharpen > 0) {\n" \
    "        vec3 n = texture(uTex, vUV + vec2(0.0, -uTexel.y)).rgb;\n" \
    "        vec3 s = texture(uTex, vUV + vec2(0.0,  uTexel.y)).rgb;\n" \
    "        vec3 e = texture(uTex, vUV + vec2( uTexel.x, 0.0)).rgb;\n" \
    "        vec3 w = texture(uTex, vUV + vec2(-uTexel.x, 0.0)).rgb;\n" \
    "        float amount = (uSharpen == 1 ? 0.10 : (uSharpen == 2 ? 0.20 : 0.32));\n" \
    "        if (uSharpenMode != 0) {\n" \
    "            float edge = max(max(length(c - n), length(c - s)), max(length(c - e), length(c - w)));\n" \
    "            amount *= mix(0.45, 1.0, clamp(edge * 2.5, 0.0, 1.0));\n" \
    "        }\n" \
    "        vec3 sh = c + (c * 4.0 - n - s - e - w) * amount;\n" \
    "        if (uSharpenMode != 0) {\n" \
    "            vec3 lo = min(c, min(min(n, s), min(e, w)));\n" \
    "            vec3 hi = max(c, max(max(n, s), max(e, w)));\n" \
    "            sh = clamp(sh, lo, hi);\n" \
    "        }\n" \
    "        c = sh;\n" \
    "    }\n" \
    "    c = max(c - uBlack, 0.0) / (1.0 - uBlack);\n" \
    "    c *= exp2(float(uExposure) * 0.5);\n" \
    "    float temp = float(uTemperature) * 0.022;\n" \
    "    c += vec3(temp, temp * 0.15, -temp);\n" \
    "    float tint = float(uTint) * 0.016;\n" \
    "    c += vec3(tint, -tint * 0.65, tint);\n" \
    "    c = gradePreset(c, uGrade);\n" \
    "    float l = dot(c, vec3(0.2126, 0.7152, 0.0722));\n" \
    "    float mx = max(c.r, max(c.g, c.b));\n" \
    "    float mn = min(c.r, min(c.g, c.b));\n" \
    "    float sat = clamp(mx - mn, 0.0, 1.0);\n" \
    "    float vib = float(uVibrance) * 0.14 * (1.0 - sat);\n" \
    "    c = mix(vec3(l), c, 1.0 + vib);\n" \
    "    l = dot(c, vec3(0.2126, 0.7152, 0.0722));\n" \
    "    c = mix(vec3(l), c, uSaturation);\n" \
    "    c = (c - 0.5) * uContrast + 0.5;\n" \
    "    if (uToneMap == 1) {\n" \
    "        c = (2.0 * c) / (1.0 + max(c, vec3(0.0)));\n" \
    "    } else if (uToneMap == 2) {\n" \
    "        c = (c * (2.51 * c + 0.03)) / (c * (2.43 * c + 0.59) + 0.14);\n" \
    "    }\n" \
    "    float gamma = 1.0 + float(uGamma) * 0.10;\n" \
    "    c = pow(max(c, vec3(0.0)), vec3(1.0 / max(gamma, 0.25)));\n" \
    "    c *= 1.0 + float(uWhitePoint) * 0.045;\n" \
    "    float noise = hash12(gl_FragCoord.xy + vec2(float(uFrame) * 0.7549, float(uFrame) * 0.5693)) - 0.5;\n" \
    "    if (uDither > 0) c += noise * (float(uDither) / 255.0);\n" \
    "    if (uPosterize > 0) {\n" \
    "        float levels = (uPosterize == 1 ? 16.0 : (uPosterize == 2 ? 8.0 : 4.0));\n" \
    "        c = floor(clamp(c, 0.0, 1.0) * (levels - 1.0) + 0.5) / (levels - 1.0);\n" \
    "    }\n" \
    "    if (uGrain > 0) {\n" \
    "        float gs = (uGrain == 1 ? 0.012 : (uGrain == 2 ? 0.024 : 0.040));\n" \
    "        float lum = dot(clamp(c, 0.0, 1.0), vec3(0.2126, 0.7152, 0.0722));\n" \
    "        c += noise * gs * (0.55 + 0.45 * (1.0 - lum));\n" \
    "    }\n" \
    "    if (uVignette > 0) {\n" \
    "        vec2 q = vUV - vec2(0.5);\n" \
    "        float d = dot(q, q) * 2.0;\n" \
    "        float vs = (uVignette == 1 ? 0.12 : (uVignette == 2 ? 0.22 : 0.34));\n" \
    "        c *= 1.0 - smoothstep(0.18, 0.72, d) * vs;\n" \
    "    }\n" \
    "    oCol = vec4(clamp(c, 0.0, 1.0), 1.0);\n" \
    "}\n"

static const char *grade_fs_desktop =
    "#version 130\n"
    GRADE_FS_BODY;

'''
    # Preserve the existing ES vertex shader between fragment declarations by
    # replacing only the two fragment programs and leaving vertex programs alone.
    # The old block contains grade_fs_desktop, grade_vs_es and grade_fs_es, so
    # re-create grade_vs_es here as well.
    shader += r'''/* Android uses an OpenGL ES 3.x context. */
static const char *grade_vs_es =
    "#version 300 es\n"
    "precision highp float;\n"
    "out vec2 vUV;\n"
    "void main() {\n"
    "    vec2 p = vec2(float((gl_VertexID << 1) & 2), float(gl_VertexID & 2));\n"
    "    vUV = p;\n"
    "    gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);\n"
    "}\n";

static const char *grade_fs_es =
    "#version 300 es\n"
    "precision highp float;\n"
    GRADE_FS_BODY;

#undef GRADE_FS_BODY

'''
    text = text[:start] + shader + text[end:]

    old = '''    grade_loc_saturation = glGetUniformLocation(grade_prog, "uSaturation");\n    grade_loc_contrast = glGetUniformLocation(grade_prog, "uContrast");\n    grade_loc_black = glGetUniformLocation(grade_prog, "uBlack");\n'''
    new = old + '''    grade_loc_texel = glGetUniformLocation(grade_prog, "uTexel");\n    grade_loc_frame = glGetUniformLocation(grade_prog, "uFrame");\n    grade_loc_sharpen = glGetUniformLocation(grade_prog, "uSharpen");\n    grade_loc_sharpen_mode = glGetUniformLocation(grade_prog, "uSharpenMode");\n    grade_loc_vignette = glGetUniformLocation(grade_prog, "uVignette");\n    grade_loc_grain = glGetUniformLocation(grade_prog, "uGrain");\n    grade_loc_grade = glGetUniformLocation(grade_prog, "uGrade");\n    grade_loc_exposure = glGetUniformLocation(grade_prog, "uExposure");\n    grade_loc_gamma = glGetUniformLocation(grade_prog, "uGamma");\n    grade_loc_vibrance = glGetUniformLocation(grade_prog, "uVibrance");\n    grade_loc_temperature = glGetUniformLocation(grade_prog, "uTemperature");\n    grade_loc_tint = glGetUniformLocation(grade_prog, "uTint");\n    grade_loc_whitepoint = glGetUniformLocation(grade_prog, "uWhitePoint");\n    grade_loc_tonemap = glGetUniformLocation(grade_prog, "uToneMap");\n    grade_loc_posterize = glGetUniformLocation(grade_prog, "uPosterize");\n    grade_loc_dither = glGetUniformLocation(grade_prog, "uDither");\n'''
    text = replace_once(text, old, new, 'grade uniform lookup')

    old = '''    if (gfx_color_saturation == 1.0f && gfx_color_contrast == 1.0f && gfx_color_black_level == 0.0f) {\n        return;\n    }\n'''
    new = '''    if (gfx_color_saturation == 1.0f && gfx_color_contrast == 1.0f && gfx_color_black_level == 0.0f &&\n        gfx_post_sharpen == 0 && gfx_post_vignette == 0 && gfx_post_grain == 0 && gfx_post_grade == 0 &&\n        gfx_post_exposure == 0 && gfx_post_gamma == 0 && gfx_post_vibrance == 0 &&\n        gfx_post_temperature == 0 && gfx_post_tint == 0 && gfx_post_whitepoint == 0 &&\n        gfx_post_tonemap == 0 && gfx_post_posterize == 0 && gfx_post_dither == 0) {\n        return;\n    }\n'''
    text = replace_once(text, old, new, 'grade neutral early-out')

    old = '''        glUniform1f(grade_loc_saturation, gfx_color_saturation);\n        glUniform1f(grade_loc_contrast, gfx_color_contrast);\n        glUniform1f(grade_loc_black, gfx_color_black_level);\n        glDrawArrays(GL_TRIANGLES, 0, 3);\n'''
    new = '''        glUniform1f(grade_loc_saturation, gfx_color_saturation);\n        glUniform1f(grade_loc_contrast, gfx_color_contrast);\n        glUniform1f(grade_loc_black, gfx_color_black_level);\n        glUniform2f(grade_loc_texel, 1.0f / (float)width, 1.0f / (float)height);\n        glUniform1i(grade_loc_frame, (GLint)frame_count);\n        glUniform1i(grade_loc_sharpen, gfx_post_sharpen);\n        glUniform1i(grade_loc_sharpen_mode, gfx_post_sharpen_mode);\n        glUniform1i(grade_loc_vignette, gfx_post_vignette);\n        glUniform1i(grade_loc_grain, gfx_post_grain);\n        glUniform1i(grade_loc_grade, gfx_post_grade);\n        glUniform1i(grade_loc_exposure, gfx_post_exposure);\n        glUniform1i(grade_loc_gamma, gfx_post_gamma);\n        glUniform1i(grade_loc_vibrance, gfx_post_vibrance);\n        glUniform1i(grade_loc_temperature, gfx_post_temperature);\n        glUniform1i(grade_loc_tint, gfx_post_tint);\n        glUniform1i(grade_loc_whitepoint, gfx_post_whitepoint);\n        glUniform1i(grade_loc_tonemap, gfx_post_tonemap);\n        glUniform1i(grade_loc_posterize, gfx_post_posterize);\n        glUniform1i(grade_loc_dither, gfx_post_dither);\n        glDrawArrays(GL_TRIANGLES, 0, 3);\n'''
    text = replace_once(text, old, new, 'grade uniform upload')
    return text


def patch_options(text):
    text = replace_once(text, '#include "video.h"\n', '#include "video.h"\n#include "../fast3d/gfx_api.h"\n', 'options gfx include')

    marker = 'struct menuitem g_ExtendedDabsModDisplayMenuItems[] = {\n'
    if text.count(marker) != 1:
        raise SystemExit('postfx: display menu marker missing')

    block = r'''/* Android/PC finished-frame post effects. These are separate from the
 * texture/model pack systems: they operate on the completed frame and therefore
 * combine with N64, XBLA and community assets. Values are kept as small integer
 * menu choices in pd.ini and translated to renderer-neutral signed controls. */
static s32 g_PostFxSharpen = 0;
static s32 g_PostFxSharpenMode = 1;
static s32 g_PostFxVignette = 0;
static s32 g_PostFxGrain = 0;
static s32 g_PostFxGrade = 0;
static s32 g_PostFxExposure = 2;
static s32 g_PostFxGamma = 2;
static s32 g_PostFxVibrance = 0;
static s32 g_PostFxTemperature = 2;
static s32 g_PostFxTint = 2;
static s32 g_PostFxWhitePoint = 2;
static s32 g_PostFxToneMap = 0;
static s32 g_PostFxPosterize = 0;
static s32 g_PostFxDither = 0;

static void postFxApply(void)
{
	gfx_post_sharpen = g_PostFxSharpen;
	gfx_post_sharpen_mode = g_PostFxSharpenMode;
	gfx_post_vignette = g_PostFxVignette;
	gfx_post_grain = g_PostFxGrain;
	gfx_post_grade = g_PostFxGrade;
	gfx_post_exposure = g_PostFxExposure - 2;
	gfx_post_gamma = g_PostFxGamma - 2;
	gfx_post_vibrance = g_PostFxVibrance;
	gfx_post_temperature = g_PostFxTemperature - 2;
	gfx_post_tint = g_PostFxTint - 2;
	gfx_post_whitepoint = g_PostFxWhitePoint - 2;
	gfx_post_tonemap = g_PostFxToneMap;
	gfx_post_posterize = g_PostFxPosterize;
	gfx_post_dither = g_PostFxDither;
}

PD_CONSTRUCTOR static void postFxConfigInit(void)
{
	configRegisterInt("Video.PostFxSharpen", &g_PostFxSharpen, 0, 3);
	configRegisterInt("Video.PostFxSharpenMode", &g_PostFxSharpenMode, 0, 1);
	configRegisterInt("Video.PostFxVignette", &g_PostFxVignette, 0, 3);
	configRegisterInt("Video.PostFxGrain", &g_PostFxGrain, 0, 3);
	configRegisterInt("Video.PostFxGrade", &g_PostFxGrade, 0, 6);
	configRegisterInt("Video.PostFxExposure", &g_PostFxExposure, 0, 4);
	configRegisterInt("Video.PostFxGamma", &g_PostFxGamma, 0, 4);
	configRegisterInt("Video.PostFxVibrance", &g_PostFxVibrance, 0, 3);
	configRegisterInt("Video.PostFxTemperature", &g_PostFxTemperature, 0, 4);
	configRegisterInt("Video.PostFxTint", &g_PostFxTint, 0, 4);
	configRegisterInt("Video.PostFxWhitePoint", &g_PostFxWhitePoint, 0, 4);
	configRegisterInt("Video.PostFxToneMap", &g_PostFxToneMap, 0, 2);
	configRegisterInt("Video.PostFxPosterize", &g_PostFxPosterize, 0, 3);
	configRegisterInt("Video.PostFxDither", &g_PostFxDither, 0, 3);
}

static MenuItemHandlerResult menuhandlerPostFxLevel(s32 operation, struct menuitem *item, union handlerdata *data)
{
	static const char *opts[] = { "Off", "Light", "Medium", "Strong" };
	s32 *value = (s32 *)item->param2;

	switch (operation) {
	case MENUOP_GETOPTIONCOUNT: data->dropdown.value = ARRAYCOUNT(opts); break;
	case MENUOP_GETOPTIONTEXT: return (intptr_t)opts[data->dropdown.value];
	case MENUOP_SET: *value = data->dropdown.value; postFxApply(); break;
	case MENUOP_GETSELECTEDINDEX: data->dropdown.value = *value; break;
	}
	return 0;
}

static MenuItemHandlerResult menuhandlerPostFxCentred(s32 operation, struct menuitem *item, union handlerdata *data)
{
	static const char *opts[] = { "Very Low", "Low", "Neutral", "High", "Very High" };
	s32 *value = (s32 *)item->param2;

	switch (operation) {
	case MENUOP_GETOPTIONCOUNT: data->dropdown.value = ARRAYCOUNT(opts); break;
	case MENUOP_GETOPTIONTEXT: return (intptr_t)opts[data->dropdown.value];
	case MENUOP_SET: *value = data->dropdown.value; postFxApply(); break;
	case MENUOP_GETSELECTEDINDEX: data->dropdown.value = *value; break;
	}
	return 0;
}

static MenuItemHandlerResult menuhandlerPostFxSharpenMode(s32 operation, struct menuitem *item, union handlerdata *data)
{
	static const char *opts[] = { "Basic", "Adaptive" };
	switch (operation) {
	case MENUOP_GETOPTIONCOUNT: data->dropdown.value = ARRAYCOUNT(opts); break;
	case MENUOP_GETOPTIONTEXT: return (intptr_t)opts[data->dropdown.value];
	case MENUOP_SET: g_PostFxSharpenMode = data->dropdown.value; postFxApply(); break;
	case MENUOP_GETSELECTEDINDEX: data->dropdown.value = g_PostFxSharpenMode; break;
	}
	return 0;
}

static MenuItemHandlerResult menuhandlerPostFxGrade(s32 operation, struct menuitem *item, union handlerdata *data)
{
	static const char *opts[] = { "Neutral", "Cinematic", "Cool", "Warm", "Night", "Monochrome", "Sepia" };
	switch (operation) {
	case MENUOP_GETOPTIONCOUNT: data->dropdown.value = ARRAYCOUNT(opts); break;
	case MENUOP_GETOPTIONTEXT: return (intptr_t)opts[data->dropdown.value];
	case MENUOP_SET: g_PostFxGrade = data->dropdown.value; postFxApply(); break;
	case MENUOP_GETSELECTEDINDEX: data->dropdown.value = g_PostFxGrade; break;
	}
	return 0;
}

static MenuItemHandlerResult menuhandlerPostFxToneMap(s32 operation, struct menuitem *item, union handlerdata *data)
{
	static const char *opts[] = { "Off", "Reinhard", "Filmic" };
	switch (operation) {
	case MENUOP_GETOPTIONCOUNT: data->dropdown.value = ARRAYCOUNT(opts); break;
	case MENUOP_GETOPTIONTEXT: return (intptr_t)opts[data->dropdown.value];
	case MENUOP_SET: g_PostFxToneMap = data->dropdown.value; postFxApply(); break;
	case MENUOP_GETSELECTEDINDEX: data->dropdown.value = g_PostFxToneMap; break;
	}
	return 0;
}

static MenuItemHandlerResult menuhandlerPostFxPosterize(s32 operation, struct menuitem *item, union handlerdata *data)
{
	static const char *opts[] = { "Off", "16 Levels", "8 Levels", "4 Levels" };
	switch (operation) {
	case MENUOP_GETOPTIONCOUNT: data->dropdown.value = ARRAYCOUNT(opts); break;
	case MENUOP_GETOPTIONTEXT: return (intptr_t)opts[data->dropdown.value];
	case MENUOP_SET: g_PostFxPosterize = data->dropdown.value; postFxApply(); break;
	case MENUOP_GETSELECTEDINDEX: data->dropdown.value = g_PostFxPosterize; break;
	}
	return 0;
}

#define POSTFX_LEVEL_ITEM(label, var) \
	{ MENUITEMTYPE_DROPDOWN, 0, MENUITEMFLAG_LITERAL_TEXT, (uintptr_t)(label), (uintptr_t)&(var), menuhandlerPostFxLevel }
#define POSTFX_CENTRED_ITEM(label, var) \
	{ MENUITEMTYPE_DROPDOWN, 0, MENUITEMFLAG_LITERAL_TEXT, (uintptr_t)(label), (uintptr_t)&(var), menuhandlerPostFxCentred }

struct menuitem g_ExtendedDabsModPostFxMenuItems[] = {
	POSTFX_LEVEL_ITEM("Sharpen", g_PostFxSharpen),
	{ MENUITEMTYPE_DROPDOWN, 0, MENUITEMFLAG_LITERAL_TEXT, (uintptr_t)"Sharpen Method", 0, menuhandlerPostFxSharpenMode },
	POSTFX_LEVEL_ITEM("Vignette", g_PostFxVignette),
	POSTFX_LEVEL_ITEM("Film Grain", g_PostFxGrain),
	{ MENUITEMTYPE_DROPDOWN, 0, MENUITEMFLAG_LITERAL_TEXT, (uintptr_t)"Colour Grade", 0, menuhandlerPostFxGrade },
	POSTFX_CENTRED_ITEM("Exposure", g_PostFxExposure),
	POSTFX_CENTRED_ITEM("Gamma", g_PostFxGamma),
	POSTFX_LEVEL_ITEM("Vibrance", g_PostFxVibrance),
	POSTFX_CENTRED_ITEM("Temperature", g_PostFxTemperature),
	POSTFX_CENTRED_ITEM("Tint", g_PostFxTint),
	POSTFX_CENTRED_ITEM("White Point", g_PostFxWhitePoint),
	{ MENUITEMTYPE_DROPDOWN, 0, MENUITEMFLAG_LITERAL_TEXT, (uintptr_t)"Tone Mapping", 0, menuhandlerPostFxToneMap },
	{ MENUITEMTYPE_DROPDOWN, 0, MENUITEMFLAG_LITERAL_TEXT, (uintptr_t)"Posterize", 0, menuhandlerPostFxPosterize },
	POSTFX_LEVEL_ITEM("Dithering", g_PostFxDither),
	{ MENUITEMTYPE_SEPARATOR, 0, 0, 0, 0, NULL },
	{ MENUITEMTYPE_SELECTABLE, 0, MENUITEMFLAG_SELECTABLE_CLOSESDIALOG, L_OPTIONS_213, 0, NULL },
	{ MENUITEMTYPE_END },
};

#undef POSTFX_LEVEL_ITEM
#undef POSTFX_CENTRED_ITEM

'''
    text = text.replace(marker, block + marker, 1)

    old_chain = '''struct menudialogdef g_ExtendedDabsModDisplayMenuDialog = {\n\tMENUDIALOGTYPE_DEFAULT,\n\t(uintptr_t)"Mods: Display",\n\tg_ExtendedDabsModDisplayMenuItems,\n\tNULL,\n\tMENUDIALOGFLAG_LITERAL_TEXT,\n\t&g_ExtendedDabsModMissionMenuDialog,\n};\n'''
    new_chain = '''struct menudialogdef g_ExtendedDabsModPostFxMenuDialog = {\n\tMENUDIALOGTYPE_DEFAULT,\n\t(uintptr_t)"Mods: Post FX",\n\tg_ExtendedDabsModPostFxMenuItems,\n\tNULL,\n\tMENUDIALOGFLAG_LITERAL_TEXT,\n\t&g_ExtendedDabsModMissionMenuDialog,\n};\n\nstruct menudialogdef g_ExtendedDabsModDisplayMenuDialog = {\n\tMENUDIALOGTYPE_DEFAULT,\n\t(uintptr_t)"Mods: Display",\n\tg_ExtendedDabsModDisplayMenuItems,\n\tNULL,\n\tMENUDIALOGFLAG_LITERAL_TEXT,\n\t&g_ExtendedDabsModPostFxMenuDialog,\n};\n'''
    text = replace_once(text, old_chain, new_chain, 'Dabs display dialog chain')

    text = replace_once(text, 'void optionsMenuInit()\n{\n\tupdateMaxAnisotropyLevel();\n}\n',
                        'void optionsMenuInit()\n{\n\tupdateMaxAnisotropyLevel();\n\tpostFxApply();\n}\n',
                        'optionsMenuInit')
    return text


patch('port/fast3d/gfx_api.h', patch_gfx_api)
patch('port/fast3d/gfx_pc.cpp', patch_gfx_pc)
patch('port/fast3d/gfx_opengl.cpp', patch_gfx_opengl)
patch('port/src/optionsmenu.c', patch_options)
print('postfx: all patches applied')

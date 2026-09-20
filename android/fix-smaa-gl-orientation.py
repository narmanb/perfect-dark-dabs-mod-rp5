#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GFX = ROOT / "port/fast3d/gfx_opengl.cpp"
TEST = ROOT / "android/tests/verify-smaa.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"SMAA GL orientation: expected one {label}, found {count}")
    return text.replace(old, new, 1)


text = GFX.read_text()

# The official SMAA source is authored around the Direct3D/top-left texture
# convention. Merely defining SMAA_GLSL_3 changes syntax/sampling intrinsics; it
# does not change the vertical direction assumed by the edge/weight searches.
# Mature OpenGL/WebGL ports flip these Y directions. Do the transformation on
# the pinned upstream shader text at runtime, with exact-one guards so an
# upstream/source change fails loudly instead of silently producing bad AA.
helper = r'''static bool gfx_opengl_smaa_gl_replace(std::string &src, const char *from, const char *to, const char *label) {
    const std::string needle(from);
    const size_t pos = src.find(needle);
    if (pos == std::string::npos || src.find(needle, pos + needle.size()) != std::string::npos) {
        sysLogPrintf(LOG_WARNING, "GL: SMAA OpenGL orientation patch failed at %s", label);
        return false;
    }
    src.replace(pos, needle.size(), to);
    return true;
}

static bool gfx_opengl_smaa_apply_gl_orientation(std::string &src) {
    bool ok = true;

    // Edge detection: top is +Y in OpenGL texture coordinates.
    ok &= gfx_opengl_smaa_gl_replace(src,
        "float4(-1.0, 0.0, 0.0, -1.0)",
        "float4(-1.0, 0.0, 0.0,  1.0)", "edge top offset");
    ok &= gfx_opengl_smaa_gl_replace(src,
        "float4( 1.0, 0.0, 0.0,  1.0)",
        "float4( 1.0, 0.0, 0.0, -1.0)", "edge bottom offset");
    ok &= gfx_opengl_smaa_gl_replace(src,
        "float4(-2.0, 0.0, 0.0, -2.0)",
        "float4(-2.0, 0.0, 0.0,  2.0)", "edge top-top offset");

    // Pseudo-gather offsets used by the weight pass. X is unchanged; Y is
    // mirrored. Unlike the old WebGL for-loop ports, current SMAA bounds its
    // searches with offset[2], so mirror those vertical end points as well.
    ok &= gfx_opengl_smaa_gl_replace(src,
        "float4(-0.25, -0.125,  1.25, -0.125)",
        "float4(-0.25,  0.125,  1.25,  0.125)", "weight horizontal crossing offset");
    ok &= gfx_opengl_smaa_gl_replace(src,
        "float4(-0.125, -0.25, -0.125,  1.25)",
        "float4(-0.125,  0.25, -0.125, -1.25)", "weight vertical crossing offset");
    ok &= gfx_opengl_smaa_gl_replace(src,
        "float4(-2.0, 2.0, -2.0, 2.0) * float(SMAA_MAX_SEARCH_STEPS)",
        "float4(-2.0, 2.0,  2.0, -2.0) * float(SMAA_MAX_SEARCH_STEPS)", "weight vertical search limits");

    // Current upstream SMAA uses bounded while loops for vertical searches.
    // Mirror both the comparison/movement and the subpixel correction term.
    const char *up_old = R"SMAAFIX(float SMAASearchYUp(SMAATexture2D(edgesTex), SMAATexture2D(searchTex), float2 texcoord, float end) {
    float2 e = float2(1.0, 0.0);
    while (texcoord.y > end && 
           e.r > 0.8281 && // Is there some edge not activated?
           e.g == 0.0) { // Or is there a crossing edge that breaks the line?
        e = SMAASampleLevelZero(edgesTex, texcoord).rg;
        texcoord = mad(-float2(0.0, 2.0), SMAA_RT_METRICS.xy, texcoord);
    }
    float offset = mad(-(255.0 / 127.0), SMAASearchLength(SMAATexturePass2D(searchTex), e.gr, 0.0), 3.25);
    return mad(SMAA_RT_METRICS.y, offset, texcoord.y);
})SMAAFIX";
    const char *up_new = R"SMAAFIX(float SMAASearchYUp(SMAATexture2D(edgesTex), SMAATexture2D(searchTex), float2 texcoord, float end) {
    float2 e = float2(1.0, 0.0);
    while (texcoord.y < end && 
           e.r > 0.8281 && // Is there some edge not activated?
           e.g == 0.0) { // Or is there a crossing edge that breaks the line?
        e = SMAASampleLevelZero(edgesTex, texcoord).rg;
        texcoord = mad(float2(0.0, 2.0), SMAA_RT_METRICS.xy, texcoord);
    }
    float offset = mad(-(255.0 / 127.0), SMAASearchLength(SMAATexturePass2D(searchTex), e.gr, 0.0), 3.25);
    return mad(-SMAA_RT_METRICS.y, offset, texcoord.y);
})SMAAFIX";
    ok &= gfx_opengl_smaa_gl_replace(src, up_old, up_new, "vertical search up");

    const char *down_old = R"SMAAFIX(float SMAASearchYDown(SMAATexture2D(edgesTex), SMAATexture2D(searchTex), float2 texcoord, float end) {
    float2 e = float2(1.0, 0.0);
    while (texcoord.y < end && 
           e.r > 0.8281 && // Is there some edge not activated?
           e.g == 0.0) { // Or is there a crossing edge that breaks the line?
        e = SMAASampleLevelZero(edgesTex, texcoord).rg;
        texcoord = mad(float2(0.0, 2.0), SMAA_RT_METRICS.xy, texcoord);
    }
    float offset = mad(-(255.0 / 127.0), SMAASearchLength(SMAATexturePass2D(searchTex), e.gr, 0.5), 3.25);
    return mad(-SMAA_RT_METRICS.y, offset, texcoord.y);
})SMAAFIX";
    const char *down_new = R"SMAAFIX(float SMAASearchYDown(SMAATexture2D(edgesTex), SMAATexture2D(searchTex), float2 texcoord, float end) {
    float2 e = float2(1.0, 0.0);
    while (texcoord.y > end && 
           e.r > 0.8281 && // Is there some edge not activated?
           e.g == 0.0) { // Or is there a crossing edge that breaks the line?
        e = SMAASampleLevelZero(edgesTex, texcoord).rg;
        texcoord = mad(-float2(0.0, 2.0), SMAA_RT_METRICS.xy, texcoord);
    }
    float offset = mad(-(255.0 / 127.0), SMAASearchLength(SMAATexturePass2D(searchTex), e.gr, 0.5), 3.25);
    return mad(SMAA_RT_METRICS.y, offset, texcoord.y);
})SMAAFIX";
    ok &= gfx_opengl_smaa_gl_replace(src, down_old, down_new, "vertical search down");

    // WebGL/OpenGL ports compensate the crossing-edge fetch by one Y texel.
    ok &= gfx_opengl_smaa_gl_replace(src,
        "        // Fetch the right crossing edges:\n        float e2 = SMAASampleLevelZeroOffset(edgesTex, coords.zy, int2(1, 0)).r;",
        "        // Fetch the right crossing edges (OpenGL Y orientation):\n        coords.y -= SMAA_RT_METRICS.y;\n        float e2 = SMAASampleLevelZeroOffset(edgesTex, coords.zy, int2(1, 0)).r;",
        "horizontal crossing-edge fetch");
    ok &= gfx_opengl_smaa_gl_replace(src,
        "        // Fetch the bottom crossing edges:\n        float e2 = SMAASampleLevelZeroOffset(edgesTex, coords.xz, int2(0, 1)).g;",
        "        // Fetch the bottom crossing edges (OpenGL Y orientation):\n        coords.z -= SMAA_RT_METRICS.y;\n        float e2 = SMAASampleLevelZeroOffset(edgesTex, coords.xz, int2(0, 1)).g;",
        "vertical crossing-edge fetch");

    return ok;
}

'''
anchor = "static std::string gfx_opengl_smaa_fragment_source(bool ultra, int pass) {\n"
text = replace_once(text, anchor, helper + anchor, "SMAA fragment source anchor")
text = replace_once(text,
    "    src += smaa_reference_source;\n\n    if (pass == 0) {\n",
    "    src += smaa_reference_source;\n"
    "    if (!gfx_opengl_smaa_apply_gl_orientation(src)) return std::string();\n\n"
    "    if (pass == 0) {\n",
    "apply GL orientation to pinned SMAA source")

# The reference neighborhood pass gathers channels/neighbours according to the
# D3D coordinate convention. Use the established OpenGL/WebGL channel mapping
# while retaining our exact sRGB-decode -> linear blend -> sRGB-encode path.
old_neighborhood = r'''vec4 smaaNeighborhoodLinearLight(vec2 texcoord, vec4 offset) {
    // This is the upstream SMAANeighborhoodBlendingPS weight/channel mapping.
    vec4 a;
    a.x = texture(uBlendTex, offset.xy).a; // Right
    a.y = texture(uBlendTex, offset.zw).g; // Top
    a.wz = texture(uBlendTex, texcoord).xz; // Bottom / Left

    if (dot(a, vec4(1.0)) < 1e-5) {
        // Preserve untouched pixels bit-for-bit; no transfer round-trip needed.
        return textureLod(uColorTex, texcoord, 0.0);
    }

    bool horizontal = max(a.x, a.z) > max(a.y, a.w);
    vec4 blendingOffset = horizontal ? vec4(a.x, 0.0, a.z, 0.0)
                                     : vec4(0.0, a.y, 0.0, a.w);
    vec2 blendingWeight = horizontal ? a.xz : a.yw;
    blendingWeight /= dot(blendingWeight, vec2(1.0));

    vec4 blendingCoord = blendingOffset * vec4(uSmaaMetrics.xy, -uSmaaMetrics.xy) + texcoord.xyxy;
    vec4 c0 = smaaSampleColorLinear(blendingCoord.xy);
    vec4 c1 = smaaSampleColorLinear(blendingCoord.zw);
    vec3 linear = blendingWeight.x * c0.rgb + blendingWeight.y * c1.rgb;
    float alpha = dot(blendingWeight, vec2(c0.a, c1.a));
    return vec4(smaaLinearToSrgb(linear), alpha);
}
'''
new_neighborhood = r'''vec4 smaaNeighborhoodLinearLight(vec2 texcoord, vec4 unusedOffset) {
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
text = replace_once(text, old_neighborhood, new_neighborhood, "OpenGL neighborhood channel mapping")
GFX.write_text(text)

# Strengthen CI so a future regression cannot pass merely because one diagonal
# orientation happens to improve. Both signs and reciprocal steep/shallow
# slopes must improve independently against the supersampled reference.
test = TEST.read_text()
old_loop = '''for w,h in [(1920,1080),(641,359)]:
    for slope in [1/3,1,3,-1/3]:
        source,ideal=pattern(w,h,slope)
        # Keep both sides of negative/steep diagonals in the target.
        if not np.any(source[:,:,:3]==220) or not np.any(source[:,:,:3]==25):continue
        measure('diagonal and resize',source,ideal,True)
'''
new_loop = '''directional_results={}
for w,h in [(1920,1080),(641,359)]:
    for slope in [1/3,-1/3,3,-3]:
        source,ideal=pattern(w,h,slope)
        # Keep both sides of negative/steep diagonals in the target.
        if not np.any(source[:,:,:3]==220) or not np.any(source[:,:,:3]==25):continue
        before=len(report['cases'])
        measure('diagonal and resize',source,ideal,True)
        item=report['cases'][before]
        directional_results[(w,h,slope)]=(item['aliased_mse'],item['smaa_mse'])
for key,(old_mse,new_mse) in directional_results.items():
    assert new_mse < old_mse, ('directional SMAA regression',key,old_mse,new_mse)
'''
test = replace_once(test, old_loop, new_loop, "directional GLES coverage tests")
old_checks = "    'SMAA after sharpening']\n"
new_checks = "    'SMAA after sharpening','positive/negative and steep/shallow directional coverage']\n"
test = replace_once(test, old_checks, new_checks, "directional check label")
TEST.write_text(test)

print("SMAA OpenGL orientation: corrected edge/weight Y convention, crossing fetches and neighborhood channel mapping")

#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GFX = ROOT / "port/fast3d/gfx_opengl.cpp"
TEST = ROOT / "android/tests/verify-smaa.py"

text = GFX.read_text()
old = r'''in vec2 vUV;
out vec4 oCol;
void main() {
    vec4 offset;
    SMAANeighborhoodBlendingVS(vUV, offset);
    vec4 resolved = SMAANeighborhoodBlendingPS(vUV, offset, uColorTex, uBlendTex);
    oCol = resolved;
'''
new = r'''in vec2 vUV;
out vec4 oCol;

// Upstream SMAA requires the neighborhood pass's color read and output write
// to use sRGB semantics. Edges, weights and lookup textures stay non-sRGB.
// Android's post-FX source is GL_RGBA8 and the normal window path has no sRGB
// texture view, so emulate an sRGB texture fetch exactly: decode each source
// texel to linear *before* bilinear filtering, blend in linear light, then
// encode the final RGB back to sRGB for the ordinary RGBA8 back buffer.
float smaaSrgbToLinear1(float c) {
    return c <= 0.04045 ? c / 12.92 : pow((c + 0.055) / 1.055, 2.4);
}
float smaaLinearToSrgb1(float c) {
    c = clamp(c, 0.0, 1.0);
    return c <= 0.0031308 ? c * 12.92 : 1.055 * pow(c, 1.0 / 2.4) - 0.055;
}
vec3 smaaSrgbToLinear(vec3 c) {
    return vec3(smaaSrgbToLinear1(c.r), smaaSrgbToLinear1(c.g), smaaSrgbToLinear1(c.b));
}
vec3 smaaLinearToSrgb(vec3 c) {
    return vec3(smaaLinearToSrgb1(c.r), smaaLinearToSrgb1(c.g), smaaLinearToSrgb1(c.b));
}

// Equivalent to a GL_SRGB8_ALPHA8 linear-filtered texture read, while keeping
// the same RGBA8 storage that the luma edge pass must read without sRGB decode.
vec4 smaaSampleColorLinear(vec2 uv) {
    vec2 pixel = uv * uSmaaMetrics.zw - vec2(0.5);
    ivec2 p0 = ivec2(floor(pixel));
    ivec2 p1 = p0 + ivec2(1);
    vec2 f = fract(pixel);
    ivec2 hi = ivec2(uSmaaMetrics.zw) - ivec2(1);
    ivec2 p00 = clamp(p0, ivec2(0), hi);
    ivec2 p11 = clamp(p1, ivec2(0), hi);

    vec4 g00 = texelFetch(uColorTex, ivec2(p00.x, p00.y), 0);
    vec4 g10 = texelFetch(uColorTex, ivec2(p11.x, p00.y), 0);
    vec4 g01 = texelFetch(uColorTex, ivec2(p00.x, p11.y), 0);
    vec4 g11 = texelFetch(uColorTex, ivec2(p11.x, p11.y), 0);
    vec4 l00 = vec4(smaaSrgbToLinear(g00.rgb), g00.a);
    vec4 l10 = vec4(smaaSrgbToLinear(g10.rgb), g10.a);
    vec4 l01 = vec4(smaaSrgbToLinear(g01.rgb), g01.a);
    vec4 l11 = vec4(smaaSrgbToLinear(g11.rgb), g11.a);
    return mix(mix(l00, l10, f.x), mix(l01, l11, f.x), f.y);
}

vec4 smaaNeighborhoodLinearLight(vec2 texcoord, vec4 offset) {
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

void main() {
    vec4 offset;
    SMAANeighborhoodBlendingVS(vUV, offset);
    vec4 resolved = smaaNeighborhoodLinearLight(vUV, offset);
    oCol = resolved;
'''
count = text.count(old)
if count != 1:
    raise SystemExit(f"linear-light SMAA: expected one neighborhood wrapper, found {count}")
GFX.write_text(text.replace(old, new, 1))
print("linear-light SMAA: corrected neighborhood sRGB read/filter/write semantics")

# The production test previously used straight interpolation of 8-bit display
# values as its coverage reference. That rewards gamma-space blending, which is
# exactly the integration fallback we are replacing. Validate against linear
# coverage encoded back to sRGB instead.
test = TEST.read_text()
old_pattern = '''def pattern(w,h,slope):
    y,x=np.mgrid[:h,:w]
    f=y+0.5-slope*(x+0.5)-h*0.35
    # Pixel-center rasterization and an independent 8x8 coverage reference.
    ideal=np.zeros_like(f)
    for sy in (np.arange(8)+0.5)/8-0.5:
        for sx in (np.arange(8)+0.5)/8-0.5:
            ideal+=(f+sy-slope*sx>0)/64
    return rgba(np.where(f>0,220,25)),25+195*ideal
'''
new_pattern = '''def _srgb_to_linear(v):
    v=np.asarray(v,dtype=float)
    return np.where(v<=0.04045,v/12.92,((v+0.055)/1.055)**2.4)

def _linear_to_srgb(v):
    v=np.clip(np.asarray(v,dtype=float),0.0,1.0)
    return np.where(v<=0.0031308,12.92*v,1.055*(v**(1/2.4))-0.055)

def pattern(w,h,slope):
    y,x=np.mgrid[:h,:w]
    f=y+0.5-slope*(x+0.5)-h*0.35
    # Pixel-center rasterization and an independent 8x8 *linear-light* coverage
    # reference. SMAA specifies sRGB reads/writes in the neighborhood pass.
    coverage=np.zeros_like(f)
    for sy in (np.arange(8)+0.5)/8-0.5:
        for sx in (np.arange(8)+0.5)/8-0.5:
            coverage+=(f+sy-slope*sx>0)/64
    lo=_srgb_to_linear(25/255.0)
    hi=_srgb_to_linear(220/255.0)
    ideal=255.0*_linear_to_srgb(lo+(hi-lo)*coverage)
    return rgba(np.where(f>0,220,25)),ideal
'''
count = test.count(old_pattern)
if count != 1:
    raise SystemExit(f"linear-light SMAA: expected one verifier pattern, found {count}")
TEST.write_text(test.replace(old_pattern, new_pattern, 1))
print("linear-light SMAA: verifier now uses an sRGB/linear-light coverage reference")

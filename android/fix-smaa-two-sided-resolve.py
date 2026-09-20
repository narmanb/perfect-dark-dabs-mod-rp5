#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GFX = ROOT / "port/fast3d/gfx_opengl.cpp"

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

#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GFX = ROOT / "port/fast3d/gfx_opengl.cpp"


def replace_file_once(relpath, old, new, label):
    p = ROOT / relpath
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"postfx pass4: expected one {label} in {relpath}, found {count}")
    p.write_text(text.replace(old, new, 1))
    print(f"postfx pass4: patched {relpath}: {label}")


text = GFX.read_text()


def replace_once(old, new, label):
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"postfx pass4: expected one {label}, found {count}")
    text = text.replace(old, new, 1)
    print(f"postfx pass4: {label}")


# Expand the existing Post AA selector. Modes 3 and 4 are real multi-pass
# morphological AA: edge detection -> edge-length/weight pass -> neighborhood
# resolve. Ultra searches farther and adds diagonal/corner coverage.
replace_file_once(
    "port/fast3d/gfx_api.h",
    "extern int gfx_post_aa;            // 0 off, 1 FXAA, 2 SMAA Lite\n",
    "extern int gfx_post_aa;            // 0 off, 1 FXAA, 2 SMAA Lite, 3 SMAA Multi, 4 SMAA Ultra\n",
    "AA mode comment",
)

replace_file_once(
    "port/src/optionsmenu.c",
    'configRegisterInt("Video.PostFxAA", &g_PostFxAA, 0, 2);',
    'configRegisterInt("Video.PostFxAA", &g_PostFxAA, 0, 4);',
    "AA config range",
)
replace_file_once(
    "port/src/optionsmenu.c",
    'static const char *opts[] = { "Off", "FXAA", "SMAA Lite" };',
    'static const char *opts[] = { "Off", "FXAA", "SMAA Lite", "SMAA Multi", "SMAA Ultra" };',
    "AA menu choices",
)

# Extra programs and render targets live beside the existing finished-frame
# grade target, so they are only allocated at the current output resolution.
replace_once(
    "static GLint grade_loc_chromatic, grade_loc_lens_distort, grade_loc_aa;\n",
    "static GLint grade_loc_chromatic, grade_loc_lens_distort, grade_loc_aa;\n"
    "static GLuint smaa_edge_prog, smaa_weight_prog, smaa_blend_prog;\n"
    "static GLuint smaa_tex[3], smaa_fbo[3];\n"
    "static bool smaa_ready;\n",
    "SMAA program declarations",
)

# Three full-screen fragment passes. This deliberately avoids a giant blur:
# only pixels that survive the edge detector receive neighborhood blending.
shader_block = r'''
#define SMAA_EDGE_BODY \
    "uniform sampler2D uTex;\n" \
    "uniform vec2 uTexel;\n" \
    "uniform int uQuality;\n" \
    "in vec2 vUV;\n" \
    "out vec4 oCol;\n" \
    "float aaLuma(vec3 c) { return dot(c, vec3(0.299, 0.587, 0.114)); }\n" \
    "void main() {\n" \
    "    float c = aaLuma(texture(uTex, vUV).rgb);\n" \
    "    float l = aaLuma(texture(uTex, vUV - vec2(uTexel.x, 0.0)).rgb);\n" \
    "    float r = aaLuma(texture(uTex, vUV + vec2(uTexel.x, 0.0)).rgb);\n" \
    "    float t = aaLuma(texture(uTex, vUV - vec2(0.0, uTexel.y)).rgb);\n" \
    "    float b = aaLuma(texture(uTex, vUV + vec2(0.0, uTexel.y)).rgb);\n" \
    "    float dl = abs(c - l), dr = abs(c - r), dt = abs(c - t), db = abs(c - b);\n" \
    "    float ex = max(dl, dr);\n" \
    "    float ey = max(dt, db);\n" \
    "    float local = max(ex, ey);\n" \
    "    float th = (uQuality >= 4 ? 0.014 : 0.020);\n" \
    "    float adapt = max(th, local * 0.18);\n" \
    "    float edgeX = smoothstep(adapt, adapt * 3.2, ex);\n" \
    "    float edgeY = smoothstep(adapt, adapt * 3.2, ey);\n" \
    "    if (max(edgeX, edgeY) < 0.02) { oCol = vec4(0.0, 0.0, 0.0, 1.0); return; }\n" \
    "    oCol = vec4(edgeX, edgeY, 0.0, 1.0);\n" \
    "}\n"

static const char *smaa_edge_fs_desktop =
    "#version 130\n"
    SMAA_EDGE_BODY;
static const char *smaa_edge_fs_es =
    "#version 300 es\n"
    "precision highp float;\n"
    SMAA_EDGE_BODY;
#undef SMAA_EDGE_BODY

#define SMAA_WEIGHT_BODY \
    "uniform sampler2D uEdges;\n" \
    "uniform vec2 uTexel;\n" \
    "uniform int uQuality;\n" \
    "in vec2 vUV;\n" \
    "out vec4 oCol;\n" \
    "void main() {\n" \
    "    vec2 e = texture(uEdges, vUV).rg;\n" \
    "    if (max(e.r, e.g) < 0.01) { oCol = vec4(0.0, 0.0, 0.0, 1.0); return; }\n" \
    "    int steps = (uQuality >= 4 ? 12 : 7);\n" \
    "    float runX = 0.0;\n" \
    "    float runY = 0.0;\n" \
    "    for (int i = 1; i <= 12; i++) {\n" \
    "        if (i <= steps) {\n" \
    "            float fi = float(i);\n" \
    "            float fall = 1.0 - (fi - 1.0) / float(steps);\n" \
    "            runX += (texture(uEdges, vUV + vec2(0.0,  uTexel.y * fi)).r + texture(uEdges, vUV - vec2(0.0,  uTexel.y * fi)).r) * fall;\n" \
    "            runY += (texture(uEdges, vUV + vec2( uTexel.x * fi, 0.0)).g + texture(uEdges, vUV - vec2( uTexel.x * fi, 0.0)).g) * fall;\n" \
    "        }\n" \
    "    }\n" \
    "    float wx = e.r * clamp(0.34 + runX / (float(steps) * 1.30), 0.0, 1.0);\n" \
    "    float wy = e.g * clamp(0.34 + runY / (float(steps) * 1.30), 0.0, 1.0);\n" \
    "    float diag = 0.0;\n" \
    "    if (uQuality >= 4) {\n" \
    "        vec2 d1 = texture(uEdges, vUV + vec2( uTexel.x,  uTexel.y)).rg;\n" \
    "        vec2 d2 = texture(uEdges, vUV + vec2(-uTexel.x,  uTexel.y)).rg;\n" \
    "        vec2 d3 = texture(uEdges, vUV + vec2( uTexel.x, -uTexel.y)).rg;\n" \
    "        vec2 d4 = texture(uEdges, vUV + vec2(-uTexel.x, -uTexel.y)).rg;\n" \
    "        diag = clamp((max(d1.r,d1.g) + max(d2.r,d2.g) + max(d3.r,d3.g) + max(d4.r,d4.g)) * 0.20, 0.0, 1.0);\n" \
    "    }\n" \
    "    oCol = vec4(wx, wy, diag, 1.0);\n" \
    "}\n"

static const char *smaa_weight_fs_desktop =
    "#version 130\n"
    SMAA_WEIGHT_BODY;
static const char *smaa_weight_fs_es =
    "#version 300 es\n"
    "precision highp float;\n"
    SMAA_WEIGHT_BODY;
#undef SMAA_WEIGHT_BODY

#define SMAA_BLEND_BODY \
    "uniform sampler2D uTex;\n" \
    "uniform sampler2D uWeights;\n" \
    "uniform vec2 uTexel;\n" \
    "uniform int uQuality;\n" \
    "in vec2 vUV;\n" \
    "out vec4 oCol;\n" \
    "void main() {\n" \
    "    vec3 c = texture(uTex, vUV).rgb;\n" \
    "    vec3 w = texture(uWeights, vUV).rgb;\n" \
    "    float edge = max(w.r, w.g);\n" \
    "    if (edge < 0.01) { oCol = vec4(c, 1.0); return; }\n" \
    "    vec3 l = texture(uTex, vUV - vec2(uTexel.x, 0.0)).rgb;\n" \
    "    vec3 r = texture(uTex, vUV + vec2(uTexel.x, 0.0)).rgb;\n" \
    "    vec3 t = texture(uTex, vUV - vec2(0.0, uTexel.y)).rgb;\n" \
    "    vec3 b = texture(uTex, vUV + vec2(0.0, uTexel.y)).rgb;\n" \
    "    float sum = max(w.r + w.g, 0.0001);\n" \
    "    vec3 target = (((l + r) * 0.5) * w.r + ((t + b) * 0.5) * w.g) / sum;\n" \
    "    if (uQuality >= 4 && w.b > 0.01) {\n" \
    "        vec3 d = (texture(uTex, vUV + vec2( uTexel.x,  uTexel.y)).rgb + texture(uTex, vUV + vec2(-uTexel.x,  uTexel.y)).rgb + texture(uTex, vUV + vec2( uTexel.x, -uTexel.y)).rgb + texture(uTex, vUV + vec2(-uTexel.x, -uTexel.y)).rgb) * 0.25;\n" \
    "        target = mix(target, d, clamp(w.b * 0.40, 0.0, 0.40));\n" \
    "    }\n" \
    "    float strength = (uQuality >= 4 ? 0.92 : 0.78);\n" \
    "    float amount = clamp(edge * strength, 0.0, (uQuality >= 4 ? 0.94 : 0.84));\n" \
    "    oCol = vec4(mix(c, target, amount), 1.0);\n" \
    "}\n"

static const char *smaa_blend_fs_desktop =
    "#version 130\n"
    SMAA_BLEND_BODY;
static const char *smaa_blend_fs_es =
    "#version 300 es\n"
    "precision highp float;\n"
    SMAA_BLEND_BODY;
#undef SMAA_BLEND_BODY

'''
replace_once(
    "static GLuint gfx_opengl_grade_compile(GLenum type, const char *src) {\n",
    shader_block + "static GLuint gfx_opengl_grade_compile(GLenum type, const char *src) {\n",
    "multi-pass SMAA shaders",
)

# Small linker helper reuses the already-proven full-screen vertex shader.
link_helper = r'''static GLuint gfx_opengl_post_link(const char *vs_src, const char *fs_src, const char *label) {
    GLuint vs = gfx_opengl_grade_compile(GL_VERTEX_SHADER, vs_src);
    GLuint fs = vs ? gfx_opengl_grade_compile(GL_FRAGMENT_SHADER, fs_src) : 0;
    if (!vs || !fs) {
        if (vs) glDeleteShader(vs);
        if (fs) glDeleteShader(fs);
        return 0;
    }
    GLuint prog = glCreateProgram();
    glAttachShader(prog, vs);
    glAttachShader(prog, fs);
    if (!gl_es) glBindFragDataLocation(prog, 0, "oCol");
    glLinkProgram(prog);
    GLint ok = 0;
    glGetProgramiv(prog, GL_LINK_STATUS, &ok);
    glDeleteShader(vs);
    glDeleteShader(fs);
    if (!ok) {
        char log[512] = { 0 };
        glGetProgramInfoLog(prog, sizeof(log) - 1, NULL, log);
        sysLogPrintf(LOG_WARNING, "GL: %s shader would not link: %s", label, log);
        glDeleteProgram(prog);
        return 0;
    }
    return prog;
}

'''
replace_once(
    "static void gfx_opengl_grade_free(void) {\n",
    link_helper + "static void gfx_opengl_grade_free(void) {\n",
    "post-process linker helper",
)

# Free the auxiliary resources with the existing grade resources.
replace_once(
    "    if (grade_tex) { glDeleteTextures(1, &grade_tex); grade_tex = 0; }\n    grade_width = grade_height = 0;\n",
    "    if (grade_tex) { glDeleteTextures(1, &grade_tex); grade_tex = 0; }\n"
    "    if (smaa_edge_prog) { glDeleteProgram(smaa_edge_prog); smaa_edge_prog = 0; }\n"
    "    if (smaa_weight_prog) { glDeleteProgram(smaa_weight_prog); smaa_weight_prog = 0; }\n"
    "    if (smaa_blend_prog) { glDeleteProgram(smaa_blend_prog); smaa_blend_prog = 0; }\n"
    "    glDeleteFramebuffers(3, smaa_fbo);\n"
    "    glDeleteTextures(3, smaa_tex);\n"
    "    for (int i = 0; i < 3; i++) { smaa_fbo[i] = 0; smaa_tex[i] = 0; }\n"
    "    smaa_ready = false;\n"
    "    grade_width = grade_height = 0;\n",
    "free SMAA resources",
)

# Compile all three auxiliary programs. If a driver dislikes them, keep all
# existing Post FX alive and fall back to SMAA Lite instead of breaking output.
replace_once(
    "    grade_loc_aa = glGetUniformLocation(grade_prog, \"uPostAA\");\n",
    "    grade_loc_aa = glGetUniformLocation(grade_prog, \"uPostAA\");\n"
    "\n"
    "    smaa_edge_prog = gfx_opengl_post_link(vs_src, gl_es ? smaa_edge_fs_es : smaa_edge_fs_desktop, \"SMAA edge\");\n"
    "    smaa_weight_prog = gfx_opengl_post_link(vs_src, gl_es ? smaa_weight_fs_es : smaa_weight_fs_desktop, \"SMAA weights\");\n"
    "    smaa_blend_prog = gfx_opengl_post_link(vs_src, gl_es ? smaa_blend_fs_es : smaa_blend_fs_desktop, \"SMAA blend\");\n"
    "    smaa_ready = smaa_edge_prog && smaa_weight_prog && smaa_blend_prog;\n"
    "    if (!smaa_ready) sysLogPrintf(LOG_WARNING, \"GL: multi-pass SMAA unavailable; SMAA Lite fallback will be used\");\n",
    "compile SMAA programs",
)

replace_once(
    "    glGenFramebuffers(1, &grade_fbo);\n\n    return true;\n",
    "    glGenFramebuffers(1, &grade_fbo);\n"
    "    if (smaa_ready) {\n"
    "        glGenTextures(3, smaa_tex);\n"
    "        glGenFramebuffers(3, smaa_fbo);\n"
    "    }\n\n"
    "    return true;\n",
    "create SMAA targets",
)

# Allocate all three intermediate targets whenever the final-frame target size
# changes. Edges/weights use nearest sampling; resolved colour uses linear.
replace_once(
    "    grade_width = complete ? width : 0;\n    grade_height = complete ? height : 0;\n    return complete;\n",
    "    grade_width = complete ? width : 0;\n"
    "    grade_height = complete ? height : 0;\n"
    "\n"
    "    if (complete && smaa_ready) {\n"
    "        bool aa_complete = true;\n"
    "        for (int i = 0; i < 3; i++) {\n"
    "            glBindTexture(GL_TEXTURE_2D, smaa_tex[i]);\n"
    "            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, width, height, 0, GL_RGBA, GL_UNSIGNED_BYTE, NULL);\n"
    "            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, i == 2 ? GL_LINEAR : GL_NEAREST);\n"
    "            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, i == 2 ? GL_LINEAR : GL_NEAREST);\n"
    "            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);\n"
    "            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);\n"
    "            glBindFramebuffer(GL_FRAMEBUFFER, smaa_fbo[i]);\n"
    "            glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, smaa_tex[i], 0);\n"
    "            aa_complete = aa_complete && (glCheckFramebufferStatus(GL_FRAMEBUFFER) == GL_FRAMEBUFFER_COMPLETE);\n"
    "        }\n"
    "        if (!aa_complete) {\n"
    "            sysLogPrintf(LOG_WARNING, \"GL: multi-pass SMAA framebuffer incomplete; SMAA Lite fallback will be used\");\n"
    "            smaa_ready = false;\n"
    "        }\n"
    "    }\n"
    "    return complete;\n",
    "allocate SMAA targets",
)

# The blend pass uses texture unit 1 for its weight map, so preserve it just as
# carefully as the original grade code already preserves texture unit 0.
replace_once(
    "    GLint prev_prog = 0, prev_vao = 0, prev_tex = 0, prev_active = GL_TEXTURE0;\n",
    "    GLint prev_prog = 0, prev_vao = 0, prev_tex = 0, prev_tex1 = 0, prev_active = GL_TEXTURE0;\n",
    "save texture unit 1 declaration",
)
replace_once(
    "    glGetIntegerv(GL_TEXTURE_BINDING_2D, &prev_tex);\n    glGetIntegerv(GL_VIEWPORT, prev_viewport);\n",
    "    glGetIntegerv(GL_TEXTURE_BINDING_2D, &prev_tex);\n"
    "    glActiveTexture(GL_TEXTURE1);\n"
    "    glGetIntegerv(GL_TEXTURE_BINDING_2D, &prev_tex1);\n"
    "    glActiveTexture(GL_TEXTURE0);\n"
    "    glGetIntegerv(GL_VIEWPORT, prev_viewport);\n",
    "save texture unit 1 state",
)

passes = r'''        GLuint final_source = grade_tex;
        int final_aa_mode = gfx_post_aa;
        if (gfx_post_aa >= 3 && smaa_ready) {
            const int quality = gfx_post_aa;
            glDisable(GL_BLEND);
            glDisable(GL_DEPTH_TEST);
            glDisable(GL_CULL_FACE);
            glViewport(0, 0, width, height);
            glBindVertexArray(grade_vao);

            // Pass 1: high-contrast/local-contrast edge detection.
            glBindFramebuffer(GL_FRAMEBUFFER, smaa_fbo[0]);
            glUseProgram(smaa_edge_prog);
            glActiveTexture(GL_TEXTURE0);
            glBindTexture(GL_TEXTURE_2D, grade_tex);
            glUniform1i(glGetUniformLocation(smaa_edge_prog, "uTex"), 0);
            glUniform2f(glGetUniformLocation(smaa_edge_prog, "uTexel"), 1.0f / (float)width, 1.0f / (float)height);
            glUniform1i(glGetUniformLocation(smaa_edge_prog, "uQuality"), quality);
            glDrawArrays(GL_TRIANGLES, 0, 3);

            // Pass 2: search along edges and build directional blend weights.
            glBindFramebuffer(GL_FRAMEBUFFER, smaa_fbo[1]);
            glUseProgram(smaa_weight_prog);
            glBindTexture(GL_TEXTURE_2D, smaa_tex[0]);
            glUniform1i(glGetUniformLocation(smaa_weight_prog, "uEdges"), 0);
            glUniform2f(glGetUniformLocation(smaa_weight_prog, "uTexel"), 1.0f / (float)width, 1.0f / (float)height);
            glUniform1i(glGetUniformLocation(smaa_weight_prog, "uQuality"), quality);
            glDrawArrays(GL_TRIANGLES, 0, 3);

            // Pass 3: neighborhood resolve. Ultra uses a longer edge search and
            // diagonal/corner coverage in addition to the normal directional blend.
            glBindFramebuffer(GL_FRAMEBUFFER, smaa_fbo[2]);
            glUseProgram(smaa_blend_prog);
            glActiveTexture(GL_TEXTURE0);
            glBindTexture(GL_TEXTURE_2D, grade_tex);
            glUniform1i(glGetUniformLocation(smaa_blend_prog, "uTex"), 0);
            glActiveTexture(GL_TEXTURE1);
            glBindTexture(GL_TEXTURE_2D, smaa_tex[1]);
            glUniform1i(glGetUniformLocation(smaa_blend_prog, "uWeights"), 1);
            glUniform2f(glGetUniformLocation(smaa_blend_prog, "uTexel"), 1.0f / (float)width, 1.0f / (float)height);
            glUniform1i(glGetUniformLocation(smaa_blend_prog, "uQuality"), quality);
            glDrawArrays(GL_TRIANGLES, 0, 3);

            final_source = smaa_tex[2];
            // The final grade shader must not run its single-pass AA again.
            final_aa_mode = 0;
        } else if (gfx_post_aa >= 3) {
            final_aa_mode = 2;
        }

'''
replace_once(
    "        // And back over the window, graded\n",
    passes + "        // And back over the window, graded\n",
    "three SMAA passes",
)

replace_once(
    "        glBindTexture(GL_TEXTURE_2D, grade_tex);\n        glUniform1i(glGetUniformLocation(grade_prog, \"uTex\"), 0);\n",
    "        glActiveTexture(GL_TEXTURE0);\n"
    "        glBindTexture(GL_TEXTURE_2D, final_source);\n"
    "        glUniform1i(glGetUniformLocation(grade_prog, \"uTex\"), 0);\n",
    "bind resolved AA source",
)
replace_once(
    "        glUniform1i(grade_loc_aa, gfx_post_aa);\n",
    "        glUniform1i(grade_loc_aa, final_aa_mode);\n",
    "upload final AA mode",
)

replace_once(
    "    glBindTexture(GL_TEXTURE_2D, (GLuint)prev_tex);\n    glActiveTexture((GLenum)prev_active);\n",
    "    glActiveTexture(GL_TEXTURE1);\n"
    "    glBindTexture(GL_TEXTURE_2D, (GLuint)prev_tex1);\n"
    "    glActiveTexture(GL_TEXTURE0);\n"
    "    glBindTexture(GL_TEXTURE_2D, (GLuint)prev_tex);\n"
    "    glActiveTexture((GLenum)prev_active);\n",
    "restore texture unit 1",
)

GFX.write_text(text)
print("postfx pass4: multi-pass SMAA and SMAA Ultra added")

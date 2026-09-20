#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GFX = ROOT / "port/fast3d/gfx_opengl.cpp"
SMAA_DIR = ROOT / "port/fast3d/smaa_ref"

for required in ("AreaTex.h", "SearchTex.h", "SMAASource.h"):
    if not (SMAA_DIR / required).is_file():
        raise SystemExit(f"reference SMAA: missing generated dependency {required}")


def replace_file_once(relpath, old, new, label):
    p = ROOT / relpath
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"reference SMAA: expected one {label} in {relpath}, found {count}")
    p.write_text(text.replace(old, new, 1))
    print(f"reference SMAA: patched {relpath}: {label}")


text = GFX.read_text()


def replace_once(old, new, label):
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"reference SMAA: expected one {label}, found {count}")
    text = text.replace(old, new, 1)
    print(f"reference SMAA: {label}")


def patch_grade_block(old, new, label):
    global text
    start = text.find("static void gfx_opengl_grade_frame(void) {")
    end = text.find("static void gfx_opengl_end_frame(void)", start)
    if start < 0 or end < 0:
        raise SystemExit("reference SMAA: grade frame block not found")
    block = text[start:end]
    count = block.count(old)
    if count != 1:
        raise SystemExit(f"reference SMAA: expected one {label} in grade frame, found {count}")
    block = block.replace(old, new, 1)
    text = text[:start] + block + text[end:]
    print(f"reference SMAA: {label}")


# Menu/config plumbing: modes 3 and 4 are the reference SMAA High/Ultra
# presets. Keep the existing user-facing Multi name for mode 3 so existing
# configs and the current menu vocabulary do not change underneath the user.
replace_file_once(
    "port/fast3d/gfx_api.h",
    "extern int gfx_post_aa;            // 0 off, 1 FXAA, 2 SMAA Lite\n",
    "extern int gfx_post_aa;            // 0 off, 1 FXAA, 2 SMAA Lite, 3 SMAA Multi (High), 4 SMAA Ultra\n",
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

# The official SMAA reference shader and lookup tables are fetched at a pinned
# upstream revision by the Android workflow. SMAASource.h wraps SMAA.hlsl in a
# C++ raw string, while the two texture headers contain the canonical byte data.
replace_once(
    "#include <vector>\n",
    "#include <vector>\n"
    "#include <string>\n\n"
    "#include \"smaa_ref/AreaTex.h\"\n"
    "#include \"smaa_ref/SearchTex.h\"\n"
    "#include \"smaa_ref/SMAASource.h\"\n",
    "reference SMAA includes",
)

replace_once(
    "static GLint grade_loc_chromatic, grade_loc_lens_distort, grade_loc_aa;\n",
    "static GLint grade_loc_chromatic, grade_loc_lens_distort, grade_loc_aa;\n"
    "static GLuint smaa_edge_prog[2], smaa_weight_prog[2], smaa_neighborhood_prog[2];\n"
    "static GLuint smaa_tex[3], smaa_fbo[3]; // post-FX colour, edges, blend weights\n"
    "static GLuint smaa_area_tex, smaa_search_tex;\n"
    "static bool smaa_ready[2]; // 0 = High/Multi, 1 = Ultra\n",
    "SMAA declarations",
)

# Build the fragment shaders directly from the upstream SMAA reference source.
# We deliberately compile High and Ultra independently because the reference
# implementation expresses quality as compile-time presets.
smaa_helpers = r'''static std::string gfx_opengl_smaa_fragment_source(bool ultra, int pass) {
    std::string src = gl_es ? "#version 300 es\nprecision highp float;\n" : "#version 130\n";
    src += "#define SMAA_GLSL_3\n";
    src += "#define SMAA_INCLUDE_VS 0\n";
    src += "#define SMAA_INCLUDE_PS 1\n";
    src += ultra ? "#define SMAA_PRESET_ULTRA\n" : "#define SMAA_PRESET_HIGH\n";
    src += "#define SMAA_RT_METRICS uSmaaMetrics\n";
    src += "uniform vec4 uSmaaMetrics;\n";
    src += smaa_reference_source;

    if (pass == 0) {
        src += R"SMAAGLSL(
uniform sampler2D uColorTex;
in vec2 vUV;
out vec4 oCol;
void main() {
    vec4 offset[3];
    offset[0] = uSmaaMetrics.xyxy * vec4(-1.0, 0.0, 0.0, -1.0) + vUV.xyxy;
    offset[1] = uSmaaMetrics.xyxy * vec4( 1.0, 0.0, 0.0,  1.0) + vUV.xyxy;
    offset[2] = uSmaaMetrics.xyxy * vec4(-2.0, 0.0, 0.0, -2.0) + vUV.xyxy;
    vec2 e = SMAALumaEdgeDetectionPS(vUV, offset, uColorTex);
    oCol = vec4(e, 0.0, 1.0);
}
)SMAAGLSL";
    } else if (pass == 1) {
        src += R"SMAAGLSL(
uniform sampler2D uEdges;
uniform sampler2D uArea;
uniform sampler2D uSearch;
in vec2 vUV;
out vec4 oCol;
void main() {
    vec2 pixcoord = vUV * uSmaaMetrics.zw;
    vec4 offset[3];
    offset[0] = uSmaaMetrics.xyxy * vec4(-0.25, -0.125,  1.25, -0.125) + vUV.xyxy;
    offset[1] = uSmaaMetrics.xyxy * vec4(-0.125, -0.25, -0.125,  1.25) + vUV.xyxy;
    offset[2] = uSmaaMetrics.xxyy * (vec4(-2.0, 2.0, -2.0, 2.0) * float(SMAA_MAX_SEARCH_STEPS))
              + vec4(offset[0].xz, offset[1].yw);
    oCol = SMAABlendingWeightCalculationPS(vUV, pixcoord, offset, uEdges, uArea, uSearch, vec4(0.0));
}
)SMAAGLSL";
    } else {
        src += R"SMAAGLSL(
uniform sampler2D uColorTex;
uniform sampler2D uBlendTex;
in vec2 vUV;
out vec4 oCol;
void main() {
    vec4 offset = uSmaaMetrics.xyxy * vec4(1.0, 0.0, 0.0, 1.0) + vUV.xyxy;
    oCol = SMAANeighborhoodBlendingPS(vUV, offset, uColorTex, uBlendTex);
}
)SMAAGLSL";
    }
    return src;
}

static GLuint gfx_opengl_post_link(const char *vs_src, const char *fs_src, const char *label) {
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
        char log[1024] = { 0 };
        glGetProgramInfoLog(prog, sizeof(log) - 1, NULL, log);
        sysLogPrintf(LOG_WARNING, "GL: %s shader would not link: %s", label, log);
        glDeleteProgram(prog);
        return 0;
    }
    return prog;
}

static GLuint gfx_opengl_smaa_link(bool ultra, int pass, const char *label) {
    std::string fs = gfx_opengl_smaa_fragment_source(ultra, pass);
    const char *vs = gl_es ? grade_vs_es : grade_vs_desktop;
    return gfx_opengl_post_link(vs, fs.c_str(), label);
}

static bool gfx_opengl_smaa_any_ready(void) {
    return smaa_ready[0] || smaa_ready[1];
}

'''
replace_once(
    "static void gfx_opengl_grade_free(void) {\n",
    smaa_helpers + "static void gfx_opengl_grade_free(void) {\n",
    "reference SMAA shader helpers",
)

replace_once(
    "    if (grade_tex) { glDeleteTextures(1, &grade_tex); grade_tex = 0; }\n    grade_width = grade_height = 0;\n",
    "    if (grade_tex) { glDeleteTextures(1, &grade_tex); grade_tex = 0; }\n"
    "    for (int q = 0; q < 2; q++) {\n"
    "        if (smaa_edge_prog[q]) { glDeleteProgram(smaa_edge_prog[q]); smaa_edge_prog[q] = 0; }\n"
    "        if (smaa_weight_prog[q]) { glDeleteProgram(smaa_weight_prog[q]); smaa_weight_prog[q] = 0; }\n"
    "        if (smaa_neighborhood_prog[q]) { glDeleteProgram(smaa_neighborhood_prog[q]); smaa_neighborhood_prog[q] = 0; }\n"
    "        smaa_ready[q] = false;\n"
    "    }\n"
    "    if (smaa_area_tex) { glDeleteTextures(1, &smaa_area_tex); smaa_area_tex = 0; }\n"
    "    if (smaa_search_tex) { glDeleteTextures(1, &smaa_search_tex); smaa_search_tex = 0; }\n"
    "    glDeleteFramebuffers(3, smaa_fbo);\n"
    "    glDeleteTextures(3, smaa_tex);\n"
    "    for (int i = 0; i < 3; i++) { smaa_fbo[i] = 0; smaa_tex[i] = 0; }\n"
    "    grade_width = grade_height = 0;\n",
    "free reference SMAA resources",
)

# Compile High and Ultra and upload the canonical lookup textures. A driver can
# reject one preset without disabling the other. If the selected preset is not
# available, the frame path falls back to the existing SMAA Lite mode.
init_block = r'''    for (int q = 0; q < 2; q++) {
        const bool ultra = q == 1;
        smaa_edge_prog[q] = gfx_opengl_smaa_link(ultra, 0, ultra ? "SMAA Ultra edge" : "SMAA High edge");
        smaa_weight_prog[q] = gfx_opengl_smaa_link(ultra, 1, ultra ? "SMAA Ultra weights" : "SMAA High weights");
        smaa_neighborhood_prog[q] = gfx_opengl_smaa_link(ultra, 2, ultra ? "SMAA Ultra neighborhood" : "SMAA High neighborhood");
        smaa_ready[q] = smaa_edge_prog[q] && smaa_weight_prog[q] && smaa_neighborhood_prog[q];
        if (!smaa_ready[q]) {
            sysLogPrintf(LOG_WARNING, "GL: %s reference SMAA unavailable; SMAA Lite fallback will be used", ultra ? "Ultra" : "High");
        }
    }

    if (gfx_opengl_smaa_any_ready()) {
        GLint prev_unpack = 4;
        glGetIntegerv(GL_UNPACK_ALIGNMENT, &prev_unpack);
        glPixelStorei(GL_UNPACK_ALIGNMENT, 1);

        glGenTextures(1, &smaa_area_tex);
        glBindTexture(GL_TEXTURE_2D, smaa_area_tex);
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RG8, AREATEX_WIDTH, AREATEX_HEIGHT, 0, GL_RG, GL_UNSIGNED_BYTE, areaTexBytes);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);

        glGenTextures(1, &smaa_search_tex);
        glBindTexture(GL_TEXTURE_2D, smaa_search_tex);
        glTexImage2D(GL_TEXTURE_2D, 0, GL_R8, SEARCHTEX_WIDTH, SEARCHTEX_HEIGHT, 0, GL_RED, GL_UNSIGNED_BYTE, searchTexBytes);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);

        glPixelStorei(GL_UNPACK_ALIGNMENT, prev_unpack);
        glGenTextures(3, smaa_tex);
        glGenFramebuffers(3, smaa_fbo);
    }
'''
replace_once(
    "    grade_loc_aa = glGetUniformLocation(grade_prog, \"uPostAA\");\n",
    "    grade_loc_aa = glGetUniformLocation(grade_prog, \"uPostAA\");\n\n" + init_block,
    "initialize reference SMAA",
)

# Allocate post-FX colour, edge and blend-weight targets at output resolution.
replace_once(
    "    grade_width = complete ? width : 0;\n    grade_height = complete ? height : 0;\n    return complete;\n",
    "    grade_width = complete ? width : 0;\n"
    "    grade_height = complete ? height : 0;\n"
    "\n"
    "    if (complete && gfx_opengl_smaa_any_ready()) {\n"
    "        bool aa_complete = true;\n"
    "        for (int i = 0; i < 3; i++) {\n"
    "            glBindTexture(GL_TEXTURE_2D, smaa_tex[i]);\n"
    "            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, width, height, 0, GL_RGBA, GL_UNSIGNED_BYTE, NULL);\n"
    "            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);\n"
    "            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);\n"
    "            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);\n"
    "            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);\n"
    "            glBindFramebuffer(GL_FRAMEBUFFER, smaa_fbo[i]);\n"
    "            glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, smaa_tex[i], 0);\n"
    "            aa_complete = aa_complete && (glCheckFramebufferStatus(GL_FRAMEBUFFER) == GL_FRAMEBUFFER_COMPLETE);\n"
    "        }\n"
    "        if (!aa_complete) {\n"
    "            sysLogPrintf(LOG_WARNING, \"GL: reference SMAA framebuffer incomplete; SMAA Lite fallback will be used\");\n"
    "            smaa_ready[0] = smaa_ready[1] = false;\n"
    "        }\n"
    "    }\n"
    "    return complete;\n",
    "allocate reference SMAA targets",
)

# Preserve all texture units touched by the reference weight/neighborhood
# passes. Do this only inside the grading function so the similar NV12 capture
# state-save code cannot be accidentally patched.
patch_grade_block(
    "    GLint prev_prog = 0, prev_vao = 0, prev_tex = 0, prev_active = GL_TEXTURE0;\n",
    "    GLint prev_prog = 0, prev_vao = 0, prev_tex = 0, prev_tex1 = 0, prev_tex2 = 0, prev_active = GL_TEXTURE0;\n",
    "save SMAA texture declarations",
)
patch_grade_block(
    "    glGetIntegerv(GL_TEXTURE_BINDING_2D, &prev_tex);\n    glGetIntegerv(GL_VIEWPORT, prev_viewport);\n",
    "    glGetIntegerv(GL_TEXTURE_BINDING_2D, &prev_tex);\n"
    "    glActiveTexture(GL_TEXTURE1);\n"
    "    glGetIntegerv(GL_TEXTURE_BINDING_2D, &prev_tex1);\n"
    "    glActiveTexture(GL_TEXTURE2);\n"
    "    glGetIntegerv(GL_TEXTURE_BINDING_2D, &prev_tex2);\n"
    "    glActiveTexture(GL_TEXTURE0);\n"
    "    glGetIntegerv(GL_VIEWPORT, prev_viewport);\n",
    "save SMAA texture units",
)

# Most important structural change: when High/Ultra is selected, the normal
# grading shader first writes the fully post-processed image to smaa_tex[0].
# Only then does SMAA run. This prevents sharpening/chromatic/bloom work from
# recreating jagged edges after anti-aliasing.
patch_grade_block(
    "        // And back over the window, graded\n        glBindFramebuffer(GL_FRAMEBUFFER, 0);\n",
    "        const int smaa_quality = gfx_post_aa == 4 ? 1 : 0;\n"
    "        const bool run_smaa = gfx_post_aa >= 3 && smaa_ready[smaa_quality];\n"
    "\n"
    "        // Apply all colour/post effects first. Reference SMAA is the final image pass.\n"
    "        glBindFramebuffer(GL_FRAMEBUFFER, run_smaa ? smaa_fbo[0] : 0);\n",
    "move reference SMAA after post FX",
)
patch_grade_block(
    "        glUniform1i(grade_loc_aa, gfx_post_aa);\n",
    "        glUniform1i(grade_loc_aa, run_smaa ? 0 : (gfx_post_aa >= 3 ? 2 : gfx_post_aa));\n",
    "disable inline AA before reference SMAA",
)

smaa_passes = r'''        if (run_smaa) {
            const GLuint edge_prog = smaa_edge_prog[smaa_quality];
            const GLuint weight_prog = smaa_weight_prog[smaa_quality];
            const GLuint neighborhood_prog = smaa_neighborhood_prog[smaa_quality];
            const GLfloat clear_zero[4] = { 0.0f, 0.0f, 0.0f, 0.0f };
            const float inv_w = 1.0f / (float)width;
            const float inv_h = 1.0f / (float)height;

            // Pass 1: reference SMAA luma/local-contrast edge detection.
            glBindFramebuffer(GL_FRAMEBUFFER, smaa_fbo[1]);
            glClearBufferfv(GL_COLOR, 0, clear_zero);
            glUseProgram(edge_prog);
            glActiveTexture(GL_TEXTURE0);
            glBindTexture(GL_TEXTURE_2D, smaa_tex[0]);
            glUniform1i(glGetUniformLocation(edge_prog, "uColorTex"), 0);
            glUniform4f(glGetUniformLocation(edge_prog, "uSmaaMetrics"), inv_w, inv_h, (float)width, (float)height);
            glDrawArrays(GL_TRIANGLES, 0, 3);

            // Pass 2: canonical SMAA pattern search + AreaTex/SearchTex lookup.
            glBindFramebuffer(GL_FRAMEBUFFER, smaa_fbo[2]);
            glClearBufferfv(GL_COLOR, 0, clear_zero);
            glUseProgram(weight_prog);
            glActiveTexture(GL_TEXTURE0);
            glBindTexture(GL_TEXTURE_2D, smaa_tex[1]);
            glUniform1i(glGetUniformLocation(weight_prog, "uEdges"), 0);
            glActiveTexture(GL_TEXTURE1);
            glBindTexture(GL_TEXTURE_2D, smaa_area_tex);
            glUniform1i(glGetUniformLocation(weight_prog, "uArea"), 1);
            glActiveTexture(GL_TEXTURE2);
            glBindTexture(GL_TEXTURE_2D, smaa_search_tex);
            glUniform1i(glGetUniformLocation(weight_prog, "uSearch"), 2);
            glUniform4f(glGetUniformLocation(weight_prog, "uSmaaMetrics"), inv_w, inv_h, (float)width, (float)height);
            glDrawArrays(GL_TRIANGLES, 0, 3);

            // Pass 3: neighborhood blend directly to the Android back buffer.
            glBindFramebuffer(GL_FRAMEBUFFER, 0);
            glUseProgram(neighborhood_prog);
            glActiveTexture(GL_TEXTURE0);
            glBindTexture(GL_TEXTURE_2D, smaa_tex[0]);
            glUniform1i(glGetUniformLocation(neighborhood_prog, "uColorTex"), 0);
            glActiveTexture(GL_TEXTURE1);
            glBindTexture(GL_TEXTURE_2D, smaa_tex[2]);
            glUniform1i(glGetUniformLocation(neighborhood_prog, "uBlendTex"), 1);
            glUniform4f(glGetUniformLocation(neighborhood_prog, "uSmaaMetrics"), inv_w, inv_h, (float)width, (float)height);
            glDrawArrays(GL_TRIANGLES, 0, 3);
        }
'''
patch_grade_block(
    "        glDrawArrays(GL_TRIANGLES, 0, 3);\n",
    "        glDrawArrays(GL_TRIANGLES, 0, 3);\n" + smaa_passes,
    "run reference SMAA after grading",
)

patch_grade_block(
    "    glBindTexture(GL_TEXTURE_2D, (GLuint)prev_tex);\n    glActiveTexture((GLenum)prev_active);\n",
    "    glActiveTexture(GL_TEXTURE2);\n"
    "    glBindTexture(GL_TEXTURE_2D, (GLuint)prev_tex2);\n"
    "    glActiveTexture(GL_TEXTURE1);\n"
    "    glBindTexture(GL_TEXTURE_2D, (GLuint)prev_tex1);\n"
    "    glActiveTexture(GL_TEXTURE0);\n"
    "    glBindTexture(GL_TEXTURE_2D, (GLuint)prev_tex);\n"
    "    glActiveTexture((GLenum)prev_active);\n",
    "restore SMAA texture units",
)

GFX.write_text(text)
print("reference SMAA: official High/Ultra pipeline applied after all post FX")

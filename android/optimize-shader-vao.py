#!/usr/bin/env python3
"""Cache normal-renderer vertex layout in per-shader VAOs on Android/GLES.

The regular fast3d renderer used one mutable VAO and rebuilt every enabled
attribute plus every glVertexAttribPointer on each shader switch. Android is
GLES 3 here, so a VAO can hold that immutable layout once when the shader is
created. Shader switches then become glUseProgram + glBindVertexArray + the
uniforms whose values really can change per frame.

Post-FX, colour grading and capture use their own VAOs and restore the previous
VAO before returning, so this pass deliberately does not touch those paths.
"""

from pathlib import Path

RENDERER = Path("port/fast3d/gfx_opengl.cpp")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one anchor, found {count}")
    return text.replace(old, new, 1)


def main() -> None:
    src = RENDERER.read_text(encoding="utf-8")

    old = """struct ShaderProgram {\n    GLuint opengl_program_id;\n    uint8_t num_inputs;\n"""
    new = """struct ShaderProgram {\n    GLuint opengl_program_id;\n#if defined(__ANDROID__)\n    // Attribute enables, formats, strides and VBO associations are immutable\n    // for a generated shader. Store them once instead of rebuilding the one\n    // global VAO on every material/shader transition.\n    GLuint android_vao;\n#endif\n    uint8_t num_inputs;\n"""
    src = replace_once(src, old, new, "Android per-shader VAO field")

    old = """static void gfx_opengl_unload_shader(struct ShaderProgram* old_prg) {\n    if (old_prg != NULL) {\n        for (int i = 0; i < old_prg->num_attribs; i++) {\n            if (old_prg->attrib_locations[i] >= 0) {\n                glDisableVertexAttribArray(old_prg->attrib_locations[i]);\n            }\n        }\n    }\n}\n\nstatic void gfx_opengl_load_shader(struct ShaderProgram* new_prg) {\n    // if (!new_prg) return;\n    glUseProgram(new_prg->opengl_program_id);\n    gfx_opengl_vertex_array_set_attribs(new_prg);\n    gfx_opengl_set_uniforms(new_prg);\n}\n"""
    new = """static void gfx_opengl_unload_shader(struct ShaderProgram* old_prg) {\n#if defined(__ANDROID__)\n    // Each shader owns its attribute layout on Android. There is nothing to\n    // tear down before binding the next VAO.\n    (void)old_prg;\n#else\n    if (old_prg != NULL) {\n        for (int i = 0; i < old_prg->num_attribs; i++) {\n            if (old_prg->attrib_locations[i] >= 0) {\n                glDisableVertexAttribArray(old_prg->attrib_locations[i]);\n            }\n        }\n    }\n#endif\n}\n\nstatic void gfx_opengl_load_shader(struct ShaderProgram* new_prg) {\n    // if (!new_prg) return;\n    glUseProgram(new_prg->opengl_program_id);\n#if defined(__ANDROID__)\n    glBindVertexArray(new_prg->android_vao);\n#else\n    gfx_opengl_vertex_array_set_attribs(new_prg);\n#endif\n    gfx_opengl_set_uniforms(new_prg);\n}\n"""
    src = replace_once(src, old, new, "Android shader-switch VAO binding")

    old = """    prg->num_floats = num_floats;\n    prg->num_attribs = cnt;\n\n    glUseProgram(shader_program);\n"""
    new = """    prg->num_floats = num_floats;\n    prg->num_attribs = cnt;\n\n#if defined(__ANDROID__)\n    // GLES VAOs retain the enabled attributes, each attribute format/stride\n    // and the ARRAY_BUFFER that was bound when glVertexAttribPointer ran.\n    // opengl_vbo is the single streaming vertex buffer used by fast3d.\n    glGenVertexArrays(1, &prg->android_vao);\n    glBindVertexArray(prg->android_vao);\n    glBindBuffer(GL_ARRAY_BUFFER, opengl_vbo);\n    gfx_opengl_vertex_array_set_attribs(prg);\n#endif\n\n    glUseProgram(shader_program);\n"""
    src = replace_once(src, old, new, "Android build shader VAO once")

    old = """static void gfx_opengl_clear_shaders(void) {\n    glUseProgram(0);\n    for (auto& pair : shader_program_pool) {\n        glDeleteProgram(pair.second.opengl_program_id);\n    }\n    shader_program_pool.clear();\n}\n"""
    new = """static void gfx_opengl_clear_shaders(void) {\n    glUseProgram(0);\n    for (auto& pair : shader_program_pool) {\n#if defined(__ANDROID__)\n        if (pair.second.android_vao) {\n            glDeleteVertexArrays(1, &pair.second.android_vao);\n            pair.second.android_vao = 0;\n        }\n#endif\n        glDeleteProgram(pair.second.opengl_program_id);\n    }\n    shader_program_pool.clear();\n#if defined(__ANDROID__)\n    // Leave a valid renderer-owned VAO bound between shader-pool rebuilds.\n    glBindVertexArray(opengl_vao);\n#endif\n}\n"""
    src = replace_once(src, old, new, "Android delete cached shader VAOs")

    RENDERER.write_text(src, encoding="utf-8")

    check = RENDERER.read_text(encoding="utf-8")
    required = {
        "per-shader VAO field": "GLuint android_vao;",
        "VAO switch": "glBindVertexArray(new_prg->android_vao);",
        "VAO creation": "glGenVertexArrays(1, &prg->android_vao);",
        "VAO one-time layout": "gfx_opengl_vertex_array_set_attribs(prg);",
        "VAO deletion": "glDeleteVertexArrays(1, &pair.second.android_vao);",
        "Android unload no-op": "(void)old_prg;",
    }
    for label, needle in required.items():
        if check.count(needle) != 1:
            raise SystemExit(f"Android shader VAO cache: {label} expected once, found {check.count(needle)}")

    # The normal Android load path must no longer rebuild attributes every time.
    load_start = check.index("static void gfx_opengl_load_shader")
    load_end = check.index("static void append_str", load_start)
    load_block = check[load_start:load_end]
    if "gfx_opengl_vertex_array_set_attribs(new_prg);" not in load_block:
        raise SystemExit("Android shader VAO cache: desktop fallback disappeared")
    if "#if defined(__ANDROID__)" not in load_block or "#else" not in load_block:
        raise SystemExit("Android shader VAO cache: load path is not platform guarded")

    print("Applied Android normal-renderer optimization: per-shader VAO attribute-layout caching")


if __name__ == "__main__":
    main()

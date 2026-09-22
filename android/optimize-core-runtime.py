#!/usr/bin/env python3
"""Small, conservative Android runtime optimizations applied after generators.

This pass intentionally stays separate from the Post-FX optimization work so
hardware testing can attribute changes cleanly.
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

    # -----------------------------------------------------------------------
    # Android/EGL buffer swapping already submits pending GLES work. Avoid an
    # extra explicit flush immediately before SDL_GL_SwapWindow().
    # -----------------------------------------------------------------------
    old = """static void gfx_opengl_end_frame(void) {\n    gfx_opengl_grade_frame();\n    glFlush();\n}\n"""
    new = """static void gfx_opengl_end_frame(void) {\n    gfx_opengl_grade_frame();\n#if !defined(__ANDROID__)\n    // SDL_GL_SwapWindow submits pending GLES work on Android, so an explicit\n    // glFlush immediately before the swap is redundant there. Keep the old\n    // behavior on other platforms until they are tested independently.\n    glFlush();\n#endif\n}\n"""
    src = replace_once(src, old, new, "Android glFlush removal")

    # -----------------------------------------------------------------------
    # Cache the two ordinary game texture-unit bindings on Android. The fast3d
    # front end can revisit a cached texture repeatedly; issuing identical
    # glActiveTexture/glBindTexture calls still crosses the GLES driver boundary.
    # Keep the cache deliberately narrow: only the two game texture units are
    # tracked. Generated Post-FX code saves/restores its texture state exactly,
    # while framebuffer resize/allocation paths below invalidate our cache.
    # -----------------------------------------------------------------------
    old = """static bool current_textures_linear_filter[2] = {false, false};\n\nstatic int gl_glsl_version = 130;\n"""
    new = """static bool current_textures_linear_filter[2] = {false, false};\n\n#if defined(__ANDROID__)\nstatic int android_cached_active_texture = -1;\nstatic GLuint android_cached_texture_2d[2] = { ~0u, ~0u };\n\nstatic inline void gfx_opengl_android_invalidate_texture_cache(void) {\n    android_cached_active_texture = -1;\n    android_cached_texture_2d[0] = ~0u;\n    android_cached_texture_2d[1] = ~0u;\n}\n\nstatic inline void gfx_opengl_android_activate_texture(int tile) {\n    if (tile < 0 || tile >= 2) {\n        glActiveTexture(GL_TEXTURE0 + tile);\n        android_cached_active_texture = -1;\n        return;\n    }\n\n    if (android_cached_active_texture != tile) {\n        glActiveTexture(GL_TEXTURE0 + tile);\n        android_cached_active_texture = tile;\n    }\n}\n\nstatic inline void gfx_opengl_android_bind_texture_2d(int tile, GLuint texture_id) {\n    gfx_opengl_android_activate_texture(tile);\n\n    if (tile < 0 || tile >= 2) {\n        glBindTexture(GL_TEXTURE_2D, texture_id);\n        return;\n    }\n\n    if (android_cached_texture_2d[tile] != texture_id) {\n        glBindTexture(GL_TEXTURE_2D, texture_id);\n        android_cached_texture_2d[tile] = texture_id;\n    }\n}\n\nstatic inline void gfx_opengl_android_forget_deleted_texture(GLuint texture_id) {\n    for (int tile = 0; tile < 2; ++tile) {\n        if (android_cached_texture_2d[tile] == texture_id) {\n            android_cached_texture_2d[tile] = ~0u;\n        }\n    }\n}\n#endif\n\nstatic int gl_glsl_version = 130;\n"""
    src = replace_once(src, old, new, "Android GLES texture binding cache state")

    old = """static void gfx_opengl_delete_texture(uint32_t texID) {\n    glDeleteTextures(1, &texID);\n}\n\nstatic void gfx_opengl_select_texture(int tile, GLuint texture_id, bool linear_filter) {\n    glActiveTexture(GL_TEXTURE0 + tile);\n    glBindTexture(GL_TEXTURE_2D, texture_id);\n\n    current_textures_linear_filter[tile] = linear_filter;\n}\n"""
    new = """static void gfx_opengl_delete_texture(uint32_t texID) {\n#if defined(__ANDROID__)\n    // Deleting a bound texture makes GL bind zero. Forget the old numeric id\n    // as well, because glGenTextures may later reuse it.\n    gfx_opengl_android_forget_deleted_texture(texID);\n#endif\n    glDeleteTextures(1, &texID);\n}\n\nstatic void gfx_opengl_select_texture(int tile, GLuint texture_id, bool linear_filter) {\n#if defined(__ANDROID__)\n    gfx_opengl_android_bind_texture_2d(tile, texture_id);\n#else\n    glActiveTexture(GL_TEXTURE0 + tile);\n    glBindTexture(GL_TEXTURE_2D, texture_id);\n#endif\n\n    current_textures_linear_filter[tile] = linear_filter;\n}\n"""
    src = replace_once(src, old, new, "Android cached game texture selection")

    old = """    glActiveTexture(GL_TEXTURE0 + tile);\n    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, min_filter);\n"""
    new = """#if defined(__ANDROID__)\n    gfx_opengl_android_activate_texture(tile);\n#else\n    glActiveTexture(GL_TEXTURE0 + tile);\n#endif\n    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, min_filter);\n"""
    src = replace_once(src, old, new, "Android cached sampler texture unit")

    old = """static int gfx_opengl_create_framebuffer() {\n    size_t i = framebuffers.size();\n"""
    new = """static int gfx_opengl_create_framebuffer() {\n#if defined(__ANDROID__)\n    // This setup code binds scratch textures directly rather than through the\n    // game texture selector, so the tracked binding is no longer authoritative.\n    gfx_opengl_android_invalidate_texture_cache();\n#endif\n    size_t i = framebuffers.size();\n"""
    src = replace_once(src, old, new, "Android texture cache invalidation on framebuffer creation")

    old = """                if (msaa_level <= 1) {\n                    glBindTexture(GL_TEXTURE_2D, fb.clrbuf);\n                    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB8, width, height, 0, GL_RGB, GL_UNSIGNED_BYTE, NULL);\n                    glBindTexture(GL_TEXTURE_2D, 0);\n                    glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, fb.clrbuf, 0);\n                } else {\n"""
    new = """                if (msaa_level <= 1) {\n#if defined(__ANDROID__)\n                    // This resize path binds a framebuffer colour texture\n                    // directly, bypassing the ordinary game texture selector.\n                    gfx_opengl_android_invalidate_texture_cache();\n#endif\n                    glBindTexture(GL_TEXTURE_2D, fb.clrbuf);\n                    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB8, width, height, 0, GL_RGB, GL_UNSIGNED_BYTE, NULL);\n                    glBindTexture(GL_TEXTURE_2D, 0);\n                    glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, fb.clrbuf, 0);\n                } else {\n"""
    src = replace_once(src, old, new, "Android texture cache invalidation on framebuffer texture resize")

    old = """    // glDisable(GL_DEPTH_TEST);\n    glActiveTexture(GL_TEXTURE0 + 0);\n    glBindTexture(GL_TEXTURE_2D, framebuffers[fb_id].clrbuf);\n\n    current_textures_linear_filter[0] = true;\n"""
    new = """    // glDisable(GL_DEPTH_TEST);\n#if defined(__ANDROID__)\n    gfx_opengl_android_bind_texture_2d(0, framebuffers[fb_id].clrbuf);\n#else\n    glActiveTexture(GL_TEXTURE0 + 0);\n    glBindTexture(GL_TEXTURE_2D, framebuffers[fb_id].clrbuf);\n#endif\n\n    current_textures_linear_filter[0] = true;\n"""
    src = replace_once(src, old, new, "Android cached framebuffer texture selection")

    RENDERER.write_text(src, encoding="utf-8")

    check = RENDERER.read_text(encoding="utf-8")
    if "#if !defined(__ANDROID__)\n" not in check:
        raise SystemExit("Android glFlush removal: generated guard missing")
    if check.count("    glFlush();") != 1:
        raise SystemExit("Android glFlush removal: unexpected glFlush count")
    if check.count("gfx_opengl_android_bind_texture_2d") != 3:
        raise SystemExit("Android texture binding cache: expected helper plus two call sites")
    if check.count("gfx_opengl_android_invalidate_texture_cache();") != 2:
        raise SystemExit("Android texture binding cache: expected two framebuffer invalidation sites")
    if check.count("gfx_opengl_android_activate_texture(tile);") != 2:
        raise SystemExit("Android texture binding cache: expected bind helper and sampler activation")

    print("Applied Android core runtime optimizations: redundant glFlush and GLES texture-state caching")


if __name__ == "__main__":
    main()

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

    old = """static void gfx_opengl_end_frame(void) {\n    gfx_opengl_grade_frame();\n    glFlush();\n}\n"""
    new = """static void gfx_opengl_end_frame(void) {\n    gfx_opengl_grade_frame();\n#if !defined(__ANDROID__)\n    // SDL_GL_SwapWindow submits pending GLES work on Android, so an explicit\n    // glFlush immediately before the swap is redundant there. Keep the old\n    // behavior on other platforms until they are tested independently.\n    glFlush();\n#endif\n}\n"""

    src = replace_once(src, old, new, "Android glFlush removal")
    RENDERER.write_text(src, encoding="utf-8")

    check = RENDERER.read_text(encoding="utf-8")
    if "#if !defined(__ANDROID__)\n" not in check:
        raise SystemExit("Android glFlush removal: generated guard missing")
    if check.count("    glFlush();") != 1:
        raise SystemExit("Android glFlush removal: unexpected glFlush count")

    print("Applied Android core runtime optimization: skip redundant per-frame glFlush")


if __name__ == "__main__":
    main()

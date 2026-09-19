#!/usr/bin/env python3
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "port/fast3d/gfx_opengl.cpp"
text = p.read_text()
start = text.find("static void gfx_opengl_nv12_convert(int width, int height) {")
end = text.find("static void gfx_opengl_nv12_readback", start)
if start < 0 or end < 0:
    raise SystemExit("postfx pass4 prep: NV12 convert function not found")
block = text[start:end]

repls = [
    (
        "    GLint prev_prog = 0, prev_vao = 0, prev_tex = 0, prev_active = GL_TEXTURE0;\n",
        "    GLint prev_prog = 0; GLint prev_vao = 0, prev_tex = 0, prev_active = GL_TEXTURE0;\n",
    ),
    (
        "    glGetIntegerv(GL_TEXTURE_BINDING_2D, &prev_tex);\n    glGetIntegerv(GL_VIEWPORT, prev_viewport);\n",
        "    glGetIntegerv(GL_TEXTURE_BINDING_2D, &prev_tex);\n    /* NV12 capture keeps its own texture-state path. */\n    glGetIntegerv(GL_VIEWPORT, prev_viewport);\n",
    ),
    (
        "    glBindTexture(GL_TEXTURE_2D, (GLuint)prev_tex);\n    glActiveTexture((GLenum)prev_active);\n",
        "    glBindTexture(GL_TEXTURE_2D, (GLuint)prev_tex);\n    /* NV12 capture restores only the texture unit it uses. */\n    glActiveTexture((GLenum)prev_active);\n",
    ),
]

for old, new in repls:
    if block.count(old) != 1:
        raise SystemExit(f"postfx pass4 prep: expected one NV12 state pattern, found {block.count(old)}")
    block = block.replace(old, new, 1)

text = text[:start] + block + text[end:]
p.write_text(text)
print("postfx pass4 prep: disambiguated NV12 state-save patterns")

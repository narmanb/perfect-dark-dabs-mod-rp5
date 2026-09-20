#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OPTIONS = ROOT / "port/src/optionsmenu.c"
GFX = ROOT / "port/fast3d/gfx_opengl.cpp"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"SMAA diagnostics fix: expected one {label}, found {count}")
    return text.replace(old, new, 1)


# Keep the detailed runtime status visible, but do not leave a mutable,
# non-focusable label between the last selectable diagnostic and Back.  With
# the status immediately above SMAA View, focus-driven scrolling brings the
# status and selector into view together while the selector/separator/Back
# spacing remains stable.
options = OPTIONS.read_text()
old_rows = (
    '\t{ MENUITEMTYPE_DROPDOWN, 0, MENUITEMFLAG_LITERAL_TEXT, (uintptr_t)"SMAA View", 0, menuhandlerSmaaView },\n'
    '\t{ MENUITEMTYPE_LABEL, 0, MENUITEMFLAG_LITERAL_TEXT, (uintptr_t)gfx_smaa_status, 0, NULL },\n'
)
new_rows = (
    '\t// Keep runtime diagnostics above the focusable selector so menu scrolling cannot\n'
    '\t// strand the mutable label in the bottom separator/Back scissor region.\n'
    '\t{ MENUITEMTYPE_LABEL, 0, MENUITEMFLAG_LITERAL_TEXT, (uintptr_t)gfx_smaa_status, 0, NULL },\n'
    '\t{ MENUITEMTYPE_DROPDOWN, 0, MENUITEMFLAG_LITERAL_TEXT, (uintptr_t)"SMAA View", 0, menuhandlerSmaaView },\n'
)
options = replace_once(options, old_rows, new_rows, "SMAA View/status row pair")

# The original diagnostic selector exposed raw render-target channels directly.
# That is useful to the CI harness but poor on-device diagnostics: RG edges look
# red/green, blend weights look like false colour, and "Resolved" was identical
# to Normal.  Keep the legacy raw modes internally for regression tests and map
# the on-device selector to clean visualization modes instead.
old_handler = '''static MenuItemHandlerResult menuhandlerSmaaView(s32 operation, struct menuitem *item, union handlerdata *data)
{
    static const char *opts[] = { "Normal", "Edges", "Weights", "Resolved", "Difference x8" };
    switch (operation) {
    case MENUOP_GETOPTIONCOUNT: data->dropdown.value = ARRAYCOUNT(opts); break;
    case MENUOP_GETOPTIONTEXT: return (intptr_t)opts[data->dropdown.value];
    case MENUOP_SET: gfx_smaa_debug = data->dropdown.value; break;
    case MENUOP_GETSELECTEDINDEX: data->dropdown.value = gfx_smaa_debug; break;
    }
    return 0;
}
'''
new_handler = '''static MenuItemHandlerResult menuhandlerSmaaView(s32 operation, struct menuitem *item, union handlerdata *data)
{
    static const char *opts[] = { "Normal", "Edges", "Weights", "Source", "Difference x8" };
    static const s32 modes[] = { 0, 5, 6, 7, 8 };
    switch (operation) {
    case MENUOP_GETOPTIONCOUNT:
        data->dropdown.value = ARRAYCOUNT(opts);
        break;
    case MENUOP_GETOPTIONTEXT:
        return (intptr_t)opts[data->dropdown.value];
    case MENUOP_SET:
        if (data->dropdown.value >= 0 && data->dropdown.value < ARRAYCOUNT(modes)) {
            gfx_smaa_debug = modes[data->dropdown.value];
        }
        break;
    case MENUOP_GETSELECTEDINDEX:
        data->dropdown.value = 0;
        for (s32 i = 0; i < ARRAYCOUNT(modes); ++i) {
            if (gfx_smaa_debug == modes[i]) {
                data->dropdown.value = i;
                break;
            }
        }
        break;
    }
    return 0;
}
'''
options = replace_once(options, old_handler, new_handler, "SMAA View handler")
OPTIONS.write_text(options)

# Add clean, human-readable debug views without changing the production SMAA
# path.  Modes 1-4 stay exactly as they were for the GLES regression harness.
# The menu uses modes 5-8:
#   5 edges as grayscale magnitude
#   6 blend weights as grayscale magnitude
#   7 pre-SMAA source image
#   8 resolved-vs-source difference as grayscale magnitude
# Normal remains mode 0 (the actual resolved frame).
gfx = GFX.read_text()
old_debug = '''    if (uDebugView == 1) {
        oCol = vec4(texture(uEdges, vUV).rg, 0.0, 1.0);
    } else if (uDebugView == 2) {
        vec4 w = texture(uBlendTex, vUV);
        oCol = vec4(max(w.r, w.b), max(w.g, w.a), max(w.b, w.a), 1.0);
    } else if (uDebugView == 4) {
        oCol = vec4(abs(resolved.rgb - texture(uColorTex, vUV).rgb) * 8.0, 1.0);
    }
'''
new_debug = '''    if (uDebugView == 1) {
        oCol = vec4(texture(uEdges, vUV).rg, 0.0, 1.0);
    } else if (uDebugView == 2) {
        vec4 w = texture(uBlendTex, vUV);
        oCol = vec4(max(w.r, w.b), max(w.g, w.a), max(w.b, w.a), 1.0);
    } else if (uDebugView == 4) {
        oCol = vec4(abs(resolved.rgb - texture(uColorTex, vUV).rgb) * 8.0, 1.0);
    } else if (uDebugView == 5) {
        vec2 e = texture(uEdges, vUV).rg;
        float m = max(e.r, e.g);
        oCol = vec4(vec3(m), 1.0);
    } else if (uDebugView == 6) {
        vec4 w = texture(uBlendTex, vUV);
        float m = max(max(w.r, w.g), max(w.b, w.a));
        oCol = vec4(vec3(m), 1.0);
    } else if (uDebugView == 7) {
        oCol = texture(uColorTex, vUV);
    } else if (uDebugView == 8) {
        vec3 d = abs(resolved.rgb - texture(uColorTex, vUV).rgb);
        float m = max(max(d.r, d.g), d.b);
        oCol = vec4(vec3(clamp(m * 8.0, 0.0, 1.0)), 1.0);
    }
'''
gfx = replace_once(gfx, old_debug, new_debug, "resolve diagnostic shader block")
GFX.write_text(gfx)

print("SMAA diagnostics: status restored above selector; clean Edges/Weights/Source/Difference views installed")

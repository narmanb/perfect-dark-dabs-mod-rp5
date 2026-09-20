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


# A literal status LABEL is not focusable, so the Perfect Dark menu scroller can
# leave it partly behind the bottom scissor when it sits near Back.  Make the
# status a real one-option dropdown instead.  The cursor can land on it, which
# forces normal row geometry and focus-driven scrolling, while GETOPTIONTEXT
# still returns the live runtime string every time the row is rendered.
options = OPTIONS.read_text()
old_rows = (
    '\t{ MENUITEMTYPE_DROPDOWN, 0, MENUITEMFLAG_LITERAL_TEXT, (uintptr_t)"SMAA View", 0, menuhandlerSmaaView },\n'
    '\t{ MENUITEMTYPE_LABEL, 0, MENUITEMFLAG_LITERAL_TEXT, (uintptr_t)gfx_smaa_status, 0, NULL },\n'
)
new_rows = (
    '\t{ MENUITEMTYPE_DROPDOWN, 0, MENUITEMFLAG_LITERAL_TEXT, (uintptr_t)"SMAA View", 0, menuhandlerSmaaView },\n'
    '\t// Focusable on purpose: selecting this row scrolls the entire diagnostic into view.\n'
    '\t{ MENUITEMTYPE_DROPDOWN, 0, MENUITEMFLAG_LITERAL_TEXT, (uintptr_t)"SMAA Stats", 0, menuhandlerSmaaStatus },\n'
)
options = replace_once(options, old_rows, new_rows, "SMAA View/status row pair")

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
new_handler = '''static MenuItemHandlerResult menuhandlerSmaaStatus(s32 operation, struct menuitem *item, union handlerdata *data)
{
    switch (operation) {
    case MENUOP_GETOPTIONCOUNT:
        data->dropdown.value = 1;
        break;
    case MENUOP_GETOPTIONTEXT:
        return (intptr_t)gfx_smaa_status;
    case MENUOP_GETSELECTEDINDEX:
        data->dropdown.value = 0;
        break;
    case MENUOP_SET:
        // Read-only diagnostic row.  It is a dropdown solely so it is focusable
        // and participates in the menu's scrolling/layout calculations.
        break;
    }
    return 0;
}

static MenuItemHandlerResult menuhandlerSmaaView(s32 operation, struct menuitem *item, union handlerdata *data)
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
options = replace_once(options, old_handler, new_handler, "SMAA handlers")
OPTIONS.write_text(options)

# Add clean, human-readable debug views without changing the production SMAA
# path. Modes 1-4 stay exactly as they were for the GLES regression harness.
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

# Keep every possible value short enough for the menu's right-hand value
# column.  The detailed renderer log still keeps the long-form diagnostic.
gfx = replace_once(gfx, '"Post FX initialization failed (see log)"', '"INIT FAIL (log)"', "compact init failure")
gfx = replace_once(gfx, 'gfx_post_aa >= 3 ? "SMAA starting..." : "SMAA not selected"', 'gfx_post_aa >= 3 ? "Starting..." : "Not active"', "compact selection status")
gfx = replace_once(gfx, '"SMAA failed: %s (Lite fallback)"', '"FAIL:%s -> Lite"', "compact fallback status")
GFX.write_text(gfx)

print("SMAA diagnostics: focusable Stats row installed; clean debug views and compact live status enabled")

#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GFX = ROOT / "port/fast3d/gfx_opengl.cpp"
OPTIONS = ROOT / "port/src/optionsmenu.c"
API = ROOT / "port/fast3d/gfx_api.h"


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"final AA modes: expected one {label}, found {count}")
    return text.replace(old, new, 1)


# At this point the workflow has already applied the proven OpenGL orientation
# and two-sided neighborhood fixes. Preserve those unchanged. Only remap the two
# reference-program slots:
#   q0 / mode 3 = upstream Ultra, shown as "SMAA"
#   q1 / mode 4 = custom above-Ultra preset, shown as "SMAA High"
#
# The upstream demo exposes custom H/V search values up to 112 and diagonal
# search values up to 20. 64/20 therefore stays within the reference shader's
# intended custom tuning range while lowering the luma threshold to 0.025.
gfx = GFX.read_text()

gfx = replace_once(
    gfx,
    '    src += ultra ? "#define SMAA_PRESET_ULTRA\\n" : "#define SMAA_PRESET_HIGH\\n";\n',
    '    if (ultra) {\n'
    '        src += "#define SMAA_THRESHOLD 0.025\\n";\n'
    '        src += "#define SMAA_MAX_SEARCH_STEPS 64\\n";\n'
    '        src += "#define SMAA_MAX_SEARCH_STEPS_DIAG 20\\n";\n'
    '        src += "#define SMAA_CORNER_ROUNDING 25\\n";\n'
    '    } else {\n'
    '        src += "#define SMAA_PRESET_ULTRA\\n";\n'
    '    }\n',
    "reference preset selector",
)

gfx = replace_once(
    gfx,
    'static bool smaa_ready[2]; // 0 = High/Multi, 1 = Ultra\n',
    'static bool smaa_ready[2]; // 0 = SMAA (upstream Ultra), 1 = SMAA High (custom above-Ultra)\n',
    "reference slot comment",
)

gfx = replace_once(
    gfx,
    '''    for (int q = 0; q < 2; q++) {
        const bool ultra = q == 1;
        smaa_edge_prog[q] = gfx_opengl_smaa_link(ultra, 0, ultra ? "SMAA Ultra edge" : "SMAA High edge");
        smaa_weight_prog[q] = gfx_opengl_smaa_link(ultra, 1, ultra ? "SMAA Ultra weights" : "SMAA High weights");
        smaa_neighborhood_prog[q] = gfx_opengl_smaa_link(ultra, 2, ultra ? "SMAA Ultra neighborhood" : "SMAA High neighborhood");
        smaa_ready[q] = smaa_edge_prog[q] && smaa_weight_prog[q] && smaa_neighborhood_prog[q];
        if (!smaa_ready[q]) {
            sysLogPrintf(LOG_WARNING, "GL: %s reference SMAA unavailable; SMAA Lite fallback will be used", ultra ? "Ultra" : "High");
        }
    }
''',
    '''    for (int q = 0; q < 2; q++) {
        const bool high = q == 1;
        smaa_edge_prog[q] = gfx_opengl_smaa_link(high, 0, high ? "SMAA High edge" : "SMAA edge");
        smaa_weight_prog[q] = gfx_opengl_smaa_link(high, 1, high ? "SMAA High weights" : "SMAA weights");
        smaa_neighborhood_prog[q] = gfx_opengl_smaa_link(high, 2, high ? "SMAA High neighborhood" : "SMAA neighborhood");
        smaa_ready[q] = smaa_edge_prog[q] && smaa_weight_prog[q] && smaa_neighborhood_prog[q];
        if (!smaa_ready[q]) {
            sysLogPrintf(LOG_WARNING, "GL: %s unavailable; SMAA Lite fallback will be used", high ? "SMAA High" : "SMAA");
        }
    }
''',
    "reference program initialization",
)

GFX.write_text(gfx)

options = OPTIONS.read_text()
options = replace_once(
    options,
    'static const char *opts[] = { "Off", "FXAA", "SMAA Lite", "SMAA High", "SMAA" };',
    'static const char *opts[] = { "Off", "FXAA", "SMAA Lite", "SMAA", "SMAA High" };',
    "final AA menu order",
)
OPTIONS.write_text(options)

api = API.read_text()
api = replace_once(
    api,
    'extern int gfx_post_aa;            // 0 off, 1 FXAA, 2 SMAA Lite, 3 SMAA Multi (High), 4 SMAA Ultra\n',
    'extern int gfx_post_aa;            // 0 off, 1 FXAA, 2 SMAA Lite, 3 SMAA (Ultra), 4 SMAA High (custom)\n',
    "AA mode API comment",
)
API.write_text(api)

print("final AA modes: Off / FXAA / SMAA Lite / SMAA / SMAA High")
print("final AA modes: SMAA=upstream Ultra; SMAA High=threshold .025 search 64 diag 20 corner 25")

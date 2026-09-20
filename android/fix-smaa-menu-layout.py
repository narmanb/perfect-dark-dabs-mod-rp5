#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OPTIONS = ROOT / "port/src/optionsmenu.c"

text = OPTIONS.read_text()
old = (
    '\t{ MENUITEMTYPE_DROPDOWN, 0, MENUITEMFLAG_LITERAL_TEXT, (uintptr_t)"SMAA View", 0, menuhandlerSmaaView },\n'
    '\t{ MENUITEMTYPE_LABEL, 0, MENUITEMFLAG_LITERAL_TEXT, (uintptr_t)gfx_smaa_status, 0, NULL },\n'
)
new = (
    '\t{ MENUITEMTYPE_DROPDOWN, 0, MENUITEMFLAG_LITERAL_TEXT, (uintptr_t)"SMAA View", 0, menuhandlerSmaaView },\n'
    '\t// gfx_smaa_status changes while this dialog is open. Menu geometry is measured\n'
    '\t// separately from rendering, so keep mutable runtime status in the diagnostic log\n'
    '\t// instead of a non-focusable row that can be clipped at the dialog scissor.\n'
)
count = text.count(old)
if count != 1:
    raise SystemExit(f"SMAA menu layout: expected one runtime status row after SMAA View, found {count}")
OPTIONS.write_text(text.replace(old, new, 1))
print("SMAA menu layout: kept SMAA View; runtime status remains in renderer/log diagnostics")

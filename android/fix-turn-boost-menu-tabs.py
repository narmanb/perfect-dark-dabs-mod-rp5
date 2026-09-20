#!/usr/bin/env python3
from pathlib import Path

p = Path("port/src/optionsmenu.c")
s = p.read_text(encoding="utf-8")
start_marker = "static MenuItemHandlerResult menuhandlerTurnBoost(s32 op"
end_marker = "struct menudialogdef g_ExtendedStickMenuDialog = {"
start = s.find(start_marker)
end = s.find(end_marker, start)
if start < 0 or end < 0:
    raise SystemExit("turn boost generated menu block not found")
block = s[start:end]
count = block.count("\\t")
if count < 10:
    raise SystemExit(f"expected literal tab escapes in generated turn boost menu, found {count}")
block = block.replace("\\t", "\t")
s = s[:start] + block + s[end:]

# The dedicated Turn Boost submenu compiled successfully but does not open on
# the Android runtime from the already-nested Advanced Stick Calibration page.
# Keep the same handlers/settings but place the controls directly on Advanced
# Stick Calibration. This removes the fragile extra dialog push entirely.
old_decl = 'extern struct menudialogdef g_TurnBoostMenuDialog;\n'
new_decl = '''static MenuItemHandlerResult menuhandlerTurnBoost(s32 op, struct menuitem *item, union handlerdata *data);\nstatic MenuItemHandlerResult menuhandlerTurnBoostRamp(s32 op, struct menuitem *item, union handlerdata *data);\nstatic MenuItemHandlerResult menuhandlerTurnBoostThreshold(s32 op, struct menuitem *item, union handlerdata *data);\nstatic MenuItemHandlerResult menuhandlerTurnBoostRelease(s32 op, struct menuitem *item, union handlerdata *data);\nstatic MenuItemHandlerResult menuhandlerTurnBoostAim(s32 op, struct menuitem *item, union handlerdata *data);\n'''
if s.count(old_decl) != 1:
    raise SystemExit(f"turn boost dialog declaration: expected 1 match, found {s.count(old_decl)}")
s = s.replace(old_decl, new_decl, 1)

old_row = '''\t{
\t\tMENUITEMTYPE_SELECTABLE, 0, MENUITEMFLAG_SELECTABLE_OPENSDIALOG | MENUITEMFLAG_LITERAL_TEXT,
\t\t(uintptr_t)"Turn Boost Settings...\\n", 0, (void *)&g_TurnBoostMenuDialog,
\t},
'''
new_rows = '''\t{
\t\tMENUITEMTYPE_SLIDER, 0, MENUITEMFLAG_LITERAL_TEXT | MENUITEMFLAG_SLIDER_WIDE,
\t\t(uintptr_t)"Turn Boost", 100, menuhandlerTurnBoost,
\t},
\t{
\t\tMENUITEMTYPE_SLIDER, 0, MENUITEMFLAG_LITERAL_TEXT | MENUITEMFLAG_SLIDER_WIDE,
\t\t(uintptr_t)"Boost Ramp", 55, menuhandlerTurnBoostRamp,
\t},
\t{
\t\tMENUITEMTYPE_SLIDER, 0, MENUITEMFLAG_LITERAL_TEXT | MENUITEMFLAG_SLIDER_WIDE,
\t\t(uintptr_t)"Boost Threshold", 50, menuhandlerTurnBoostThreshold,
\t},
\t{
\t\tMENUITEMTYPE_SLIDER, 0, MENUITEMFLAG_LITERAL_TEXT | MENUITEMFLAG_SLIDER_WIDE,
\t\t(uintptr_t)"Boost Release", 95, menuhandlerTurnBoostRelease,
\t},
\t{
\t\tMENUITEMTYPE_DROPDOWN, 0, MENUITEMFLAG_LITERAL_TEXT,
\t\t(uintptr_t)"Boost While Aiming", 0, menuhandlerTurnBoostAim,
\t},
'''
if s.count(old_row) != 1:
    raise SystemExit(f"turn boost submenu row: expected 1 match, found {s.count(old_row)}")
s = s.replace(old_row, new_rows, 1)

p.write_text(s, encoding="utf-8")
print(f"fixed {count} literal tab escapes and inlined turn boost controls")

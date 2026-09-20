#!/usr/bin/env python3
from pathlib import Path

p = Path("port/src/optionsmenu.c")
s = p.read_text(encoding="utf-8")

old_decl = 'extern struct menudialogdef g_TurnBoostMenuDialog;\n'
new_decl = '''static MenuItemHandlerResult menuhandlerTurnBoost(s32 op, struct menuitem *item, union handlerdata *data);\nstatic MenuItemHandlerResult menuhandlerTurnBoostRamp(s32 op, struct menuitem *item, union handlerdata *data);\nstatic MenuItemHandlerResult menuhandlerTurnBoostThreshold(s32 op, struct menuitem *item, union handlerdata *data);\nstatic MenuItemHandlerResult menuhandlerTurnBoostRelease(s32 op, struct menuitem *item, union handlerdata *data);\nstatic MenuItemHandlerResult menuhandlerTurnBoostAim(s32 op, struct menuitem *item, union handlerdata *data);\n'''
if s.count(old_decl) != 1:
    raise SystemExit(f"turn boost dialog declaration: expected 1 match, found {s.count(old_decl)}")
s = s.replace(old_decl, new_decl, 1)

old_row = '''\t{\n\t\tMENUITEMTYPE_SELECTABLE, 0, MENUITEMFLAG_SELECTABLE_OPENSDIALOG | MENUITEMFLAG_LITERAL_TEXT,\n\t\t(uintptr_t)"Turn Boost Settings...\\n", 0, (void *)&g_TurnBoostMenuDialog,\n\t},\n'''
new_rows = '''\t{\n\t\tMENUITEMTYPE_SLIDER, 0, MENUITEMFLAG_LITERAL_TEXT | MENUITEMFLAG_SLIDER_WIDE,\n\t\t(uintptr_t)"Turn Boost", 100, menuhandlerTurnBoost,\n\t},\n\t{\n\t\tMENUITEMTYPE_SLIDER, 0, MENUITEMFLAG_LITERAL_TEXT | MENUITEMFLAG_SLIDER_WIDE,\n\t\t(uintptr_t)"Boost Ramp", 55, menuhandlerTurnBoostRamp,\n\t},\n\t{\n\t\tMENUITEMTYPE_SLIDER, 0, MENUITEMFLAG_LITERAL_TEXT | MENUITEMFLAG_SLIDER_WIDE,\n\t\t(uintptr_t)"Boost Threshold", 50, menuhandlerTurnBoostThreshold,\n\t},\n\t{\n\t\tMENUITEMTYPE_SLIDER, 0, MENUITEMFLAG_LITERAL_TEXT | MENUITEMFLAG_SLIDER_WIDE,\n\t\t(uintptr_t)"Boost Release", 95, menuhandlerTurnBoostRelease,\n\t},\n\t{\n\t\tMENUITEMTYPE_DROPDOWN, 0, MENUITEMFLAG_LITERAL_TEXT,\n\t\t(uintptr_t)"Boost While Aiming", 0, menuhandlerTurnBoostAim,\n\t},\n'''
if s.count(old_row) != 1:
    raise SystemExit(f"turn boost submenu row: expected 1 match, found {s.count(old_row)}")
s = s.replace(old_row, new_rows, 1)

p.write_text(s, encoding="utf-8")
print("turn boost controls inlined into Advanced Stick Calibration")

#!/usr/bin/env python3
from pathlib import Path

def rep(path, old, new, label):
    p=Path(path); s=p.read_text(encoding="utf-8")
    if s.count(old)!=1: raise SystemExit(f"{label}: expected 1 match, found {s.count(old)}")
    p.write_text(s.replace(old,new,1),encoding="utf-8"); print("patched",label)

# Persistent controller settings.
rep("port/src/input.c",
'\t.rstickSmoothing = 0.f, \\\n}',
'\t.rstickSmoothing = 0.f, \\\n\t.turnBoost = 0.f, \\\n\t.turnBoostRamp = 1.25f, \\\n\t.turnBoostThreshold = 0.90f, \\\n\t.turnBoostRelease = 0.20f, \\\n\t.turnBoostAimMode = 0, \\\n}',
"default turn boost settings")

rep("port/src/input.c",
'\tf32 rstickSmoothing;\n} padsCfg',
'\tf32 rstickSmoothing;\n\tf32 turnBoost;\n\tf32 turnBoostRamp;\n\tf32 turnBoostThreshold;\n\tf32 turnBoostRelease;\n\ts32 turnBoostAimMode;\n} padsCfg',
"turn boost config fields")

rep("port/src/input.c",
'\t\tconfigRegisterFloat(strFmt("%s.RStickSmoothing", secname), &padsCfg[c].rstickSmoothing, 0.f, 1.f);',
'\t\tconfigRegisterFloat(strFmt("%s.RStickSmoothing", secname), &padsCfg[c].rstickSmoothing, 0.f, 1.f);\n'
'\t\tconfigRegisterFloat(strFmt("%s.TurnBoost", secname), &padsCfg[c].turnBoost, 0.f, 1.f);\n'
'\t\tconfigRegisterFloat(strFmt("%s.TurnBoostRamp", secname), &padsCfg[c].turnBoostRamp, 0.25f, 3.f);\n'
'\t\tconfigRegisterFloat(strFmt("%s.TurnBoostThreshold", secname), &padsCfg[c].turnBoostThreshold, 0.50f, 1.f);\n'
'\t\tconfigRegisterFloat(strFmt("%s.TurnBoostRelease", secname), &padsCfg[c].turnBoostRelease, 0.05f, 1.f);\n'
'\t\tconfigRegisterInt(strFmt("%s.TurnBoostAimMode", secname), &padsCfg[c].turnBoostAimMode, 0, 2);',
"turn boost config registration")

anchor='s32 inputControllerUsesFullRightStickRange(s32 cidx)\n{\n'
idx=Path("port/src/input.c").read_text().find(anchor)
if idx < 0: raise SystemExit("turn boost API anchor missing")
p=Path("port/src/input.c"); s=p.read_text(); api='''f32 inputControllerGetTurnBoost(s32 cidx) { return padsCfg[cidx].turnBoost; }
void inputControllerSetTurnBoost(s32 cidx, f32 v) { padsCfg[cidx].turnBoost = v < 0.f ? 0.f : (v > 1.f ? 1.f : v); }
f32 inputControllerGetTurnBoostRamp(s32 cidx) { return padsCfg[cidx].turnBoostRamp; }
void inputControllerSetTurnBoostRamp(s32 cidx, f32 v) { padsCfg[cidx].turnBoostRamp = v < 0.25f ? 0.25f : (v > 3.f ? 3.f : v); }
f32 inputControllerGetTurnBoostThreshold(s32 cidx) { return padsCfg[cidx].turnBoostThreshold; }
void inputControllerSetTurnBoostThreshold(s32 cidx, f32 v) { padsCfg[cidx].turnBoostThreshold = v < 0.50f ? 0.50f : (v > 1.f ? 1.f : v); }
f32 inputControllerGetTurnBoostRelease(s32 cidx) { return padsCfg[cidx].turnBoostRelease; }
void inputControllerSetTurnBoostRelease(s32 cidx, f32 v) { padsCfg[cidx].turnBoostRelease = v < 0.05f ? 0.05f : (v > 1.f ? 1.f : v); }
s32 inputControllerGetTurnBoostAimMode(s32 cidx) { return padsCfg[cidx].turnBoostAimMode; }
void inputControllerSetTurnBoostAimMode(s32 cidx, s32 v) { padsCfg[cidx].turnBoostAimMode = v < 0 ? 0 : (v > 2 ? 2 : v); }

'''
s=s[:idx]+api+s[idx:]; p.write_text(s)

p=Path("port/include/input.h"); s=p.read_text()
anchor='s32 inputControllerUsesFullRightStickRange(s32 cidx);\n'
if anchor not in s: raise SystemExit("input header generated anchor missing")
decl='''s32 inputControllerUsesFullRightStickRange(s32 cidx);
f32 inputControllerGetTurnBoost(s32 cidx);
void inputControllerSetTurnBoost(s32 cidx, f32 value);
f32 inputControllerGetTurnBoostRamp(s32 cidx);
void inputControllerSetTurnBoostRamp(s32 cidx, f32 value);
f32 inputControllerGetTurnBoostThreshold(s32 cidx);
void inputControllerSetTurnBoostThreshold(s32 cidx, f32 value);
f32 inputControllerGetTurnBoostRelease(s32 cidx);
void inputControllerSetTurnBoostRelease(s32 cidx, f32 value);
s32 inputControllerGetTurnBoostAimMode(s32 cidx);
void inputControllerSetTurnBoostAimMode(s32 cidx, s32 value);
'''
p.write_text(s.replace(anchor,decl,1))

# Advanced menu: one entry opens a dedicated page so the calibration page does not overflow.
p=Path("port/src/optionsmenu.c"); s=p.read_text()
anchor='static MenuItemHandlerResult menuhandlerRightStickSmoothing(s32 operation, struct menuitem *item, union handlerdata *data);\n'
if anchor not in s: raise SystemExit("menu declaration anchor missing")
s=s.replace(anchor,anchor+'extern struct menudialogdef g_TurnBoostMenuDialog;\n',1)
old='''\t{
\t\tMENUITEMTYPE_SLIDER, 0, MENUITEMFLAG_LITERAL_TEXT | MENUITEMFLAG_SLIDER_WIDE,
\t\t(uintptr_t)"RStick Smoothing", 100, menuhandlerRightStickSmoothing,
\t},
\t{
\t\tMENUITEMTYPE_SEPARATOR,
'''
new='''\t{
\t\tMENUITEMTYPE_SLIDER, 0, MENUITEMFLAG_LITERAL_TEXT | MENUITEMFLAG_SLIDER_WIDE,
\t\t(uintptr_t)"RStick Smoothing", 100, menuhandlerRightStickSmoothing,
\t},
\t{
\t\tMENUITEMTYPE_SELECTABLE, 0, MENUITEMFLAG_SELECTABLE_OPENSDIALOG | MENUITEMFLAG_LITERAL_TEXT,
\t\t(uintptr_t)"Turn Boost Settings...\\n", 0, (void *)&g_TurnBoostMenuDialog,
\t},
\t{
\t\tMENUITEMTYPE_SEPARATOR,
'''
if old not in s: raise SystemExit("turn boost menu row anchor missing")
s=s.replace(old,new,1)
anchor='struct menudialogdef g_ExtendedStickMenuDialog = {\n'
if anchor not in s: raise SystemExit("stick dialog anchor missing")
block=r'''static MenuItemHandlerResult menuhandlerTurnBoost(s32 op, struct menuitem *item, union handlerdata *data)
{
\tswitch (op) {
\tcase MENUOP_GETSLIDER: data->slider.value = inputControllerGetTurnBoost(g_ExtMenuPlayer) * 100.f + 0.5f; break;
\tcase MENUOP_SET: inputControllerSetTurnBoost(g_ExtMenuPlayer, (f32)data->slider.value / 100.f); break;
\tcase MENUOP_GETSLIDERLABEL: sprintf(data->slider.label, "%d%%", data->slider.value); break;
\t}
\treturn 0;
}
static MenuItemHandlerResult menuhandlerTurnBoostRamp(s32 op, struct menuitem *item, union handlerdata *data)
{
\tswitch (op) {
\tcase MENUOP_GETSLIDER: data->slider.value = (inputControllerGetTurnBoostRamp(g_ExtMenuPlayer) - 0.25f) * 20.f + 0.5f; break;
\tcase MENUOP_SET: inputControllerSetTurnBoostRamp(g_ExtMenuPlayer, 0.25f + (f32)data->slider.value / 20.f); break;
\tcase MENUOP_GETSLIDERLABEL: sprintf(data->slider.label, "%.2fs", 0.25f + (f32)data->slider.value / 20.f); break;
\t}
\treturn 0;
}
static MenuItemHandlerResult menuhandlerTurnBoostThreshold(s32 op, struct menuitem *item, union handlerdata *data)
{
\tswitch (op) {
\tcase MENUOP_GETSLIDER: data->slider.value = (inputControllerGetTurnBoostThreshold(g_ExtMenuPlayer) - 0.50f) * 100.f + 0.5f; break;
\tcase MENUOP_SET: inputControllerSetTurnBoostThreshold(g_ExtMenuPlayer, 0.50f + (f32)data->slider.value / 100.f); break;
\tcase MENUOP_GETSLIDERLABEL: sprintf(data->slider.label, "%d%%", 50 + data->slider.value); break;
\t}
\treturn 0;
}
static MenuItemHandlerResult menuhandlerTurnBoostRelease(s32 op, struct menuitem *item, union handlerdata *data)
{
\tswitch (op) {
\tcase MENUOP_GETSLIDER: data->slider.value = (inputControllerGetTurnBoostRelease(g_ExtMenuPlayer) - 0.05f) * 100.f + 0.5f; break;
\tcase MENUOP_SET: inputControllerSetTurnBoostRelease(g_ExtMenuPlayer, 0.05f + (f32)data->slider.value / 100.f); break;
\tcase MENUOP_GETSLIDERLABEL: sprintf(data->slider.label, "%.2fs", 0.05f + (f32)data->slider.value / 100.f); break;
\t}
\treturn 0;
}
static MenuItemHandlerResult menuhandlerTurnBoostAim(s32 op, struct menuitem *item, union handlerdata *data)
{
\tstatic const char *opts[] = { "Off", "Reduced (25%)", "Full" };
\tswitch (op) {
\tcase MENUOP_GETOPTIONCOUNT: data->dropdown.value = ARRAYCOUNT(opts); break;
\tcase MENUOP_GETOPTIONTEXT: return (uintptr_t)opts[data->dropdown.value];
\tcase MENUOP_GETSELECTEDINDEX: data->dropdown.value = inputControllerGetTurnBoostAimMode(g_ExtMenuPlayer); break;
\tcase MENUOP_SET: inputControllerSetTurnBoostAimMode(g_ExtMenuPlayer, data->dropdown.value); break;
\t}
\treturn 0;
}

static struct menuitem g_TurnBoostMenuItems[] = {
\t{ MENUITEMTYPE_SLIDER, 0, MENUITEMFLAG_LITERAL_TEXT | MENUITEMFLAG_SLIDER_WIDE, (uintptr_t)"Turn Boost", 100, menuhandlerTurnBoost },
\t{ MENUITEMTYPE_SLIDER, 0, MENUITEMFLAG_LITERAL_TEXT | MENUITEMFLAG_SLIDER_WIDE, (uintptr_t)"Boost Ramp", 55, menuhandlerTurnBoostRamp },
\t{ MENUITEMTYPE_SLIDER, 0, MENUITEMFLAG_LITERAL_TEXT | MENUITEMFLAG_SLIDER_WIDE, (uintptr_t)"Boost Threshold", 50, menuhandlerTurnBoostThreshold },
\t{ MENUITEMTYPE_SLIDER, 0, MENUITEMFLAG_LITERAL_TEXT | MENUITEMFLAG_SLIDER_WIDE, (uintptr_t)"Boost Release", 95, menuhandlerTurnBoostRelease },
\t{ MENUITEMTYPE_DROPDOWN, 0, MENUITEMFLAG_LITERAL_TEXT, (uintptr_t)"Boost While Aiming", 0, menuhandlerTurnBoostAim },
\t{ MENUITEMTYPE_SEPARATOR, 0, 0, 0, 0, NULL },
\t{ MENUITEMTYPE_SELECTABLE, 0, MENUITEMFLAG_SELECTABLE_CLOSESDIALOG, L_OPTIONS_213, 0, NULL },
\t{ MENUITEMTYPE_END },
};

struct menudialogdef g_TurnBoostMenuDialog = {
\tMENUDIALOGTYPE_DEFAULT, (uintptr_t)"Turn Boost Settings", g_TurnBoostMenuItems,
\tNULL, MENUDIALOGFLAG_LITERAL_TEXT, NULL,
};

'''
s=s.replace(anchor,block+anchor,1); p.write_text(s)

# Runtime camera boost. Horizontal only; it raises the sustained maximum turn speed.
p=Path("src/game/bondmove.c"); s=p.read_text()
anchor='\tif (movedata.cannaturalturn) {\n'
if anchor not in s: raise SystemExit("natural turn anchor missing")
state='''#ifndef PLATFORM_N64
\tstatic f32 turnboostlevel[4] = { 0.f, 0.f, 0.f, 0.f };
#endif

'''
s=s.replace(anchor,state+anchor,1)
old='''\t\tif (fVar25 >= 0) {
\t\t\tfVar25 *= fVar25;
\t\t} else {
\t\t\tfVar25 *= -fVar25;
\t\t}

#ifndef PLATFORM_N64
\t\tfVar25 += movedata.freelookdx * mlookscale;
#endif
'''
new='''\t\tif (fVar25 >= 0) {
\t\t\tfVar25 *= fVar25;
\t\t} else {
\t\t\tfVar25 *= -fVar25;
\t\t}

#ifndef PLATFORM_N64
\t\t// Optional horizontal edge-turn boost. It begins only near the outer
\t\t// stick edge, ramps above the ordinary maximum, and releases smoothly.
\t\tif (contpad1 >= 0 && contpad1 < 4 && inputControllerGetTurnBoost(contpad1) > 0.f
\t\t\t\t&& inputControllerGetSticksSwapped(contpad1)) {
\t\t\tconst f32 mag = fabsf((f32)movedata.analogturn) / 127.f;
\t\t\tconst f32 threshold = inputControllerGetTurnBoostThreshold(contpad1);
\t\t\tconst f32 dt = g_Vars.lvupdate60freal / 60.f;
\t\t\tif (mag >= threshold) {
\t\t\t\tturnboostlevel[contpad1] += dt / inputControllerGetTurnBoostRamp(contpad1);
\t\t\t} else {
\t\t\t\tturnboostlevel[contpad1] -= dt / inputControllerGetTurnBoostRelease(contpad1);
\t\t\t}
\t\t\tif (turnboostlevel[contpad1] < 0.f) turnboostlevel[contpad1] = 0.f;
\t\t\tif (turnboostlevel[contpad1] > 1.f) turnboostlevel[contpad1] = 1.f;

\t\t\tf32 aimfactor = 1.f;
\t\t\tif (g_Vars.currentplayer->insightaimmode) {
\t\t\t\tconst s32 aimmode = inputControllerGetTurnBoostAimMode(contpad1);
\t\t\t\taimfactor = aimmode == 0 ? 0.f : (aimmode == 1 ? 0.25f : 1.f);
\t\t\t}
\t\t\t// 100% Turn Boost = up to +50% sustained horizontal turn speed.
\t\t\tfVar25 *= 1.f + inputControllerGetTurnBoost(contpad1) * 0.50f * turnboostlevel[contpad1] * aimfactor;
\t\t} else if (contpad1 >= 0 && contpad1 < 4) {
\t\t\tturnboostlevel[contpad1] = 0.f;
\t\t}
\t\tfVar25 += movedata.freelookdx * mlookscale;
#endif
'''
if old not in s: raise SystemExit("turn boost camera insertion anchor missing")
s=s.replace(old,new,1); p.write_text(s)
print("turn boost controls applied")

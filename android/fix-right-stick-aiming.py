#!/usr/bin/env python3
from pathlib import Path


def replace_once(path: str, old: str, new: str, label: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match in {path}, found {count}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"patched {label}: {path}")


# ---------------------------------------------------------------------------
# Input layer: tune the physical right stick, not whichever logical stick the
# game's 1.2/PC mapping currently calls the right stick.
# ---------------------------------------------------------------------------
replace_once(
    "port/src/input.c",
    '''static inline s32 inputRightStickShape(s32 x, const s32 curve, const f32 outerThreshold)
{
\tconst f32 sign = x < 0 ? -1.f : 1.f;
\tf32 value = fabsf((f32)x / 32767.f);
\tconst f32 threshold = outerThreshold < 0.50f ? 0.50f : (outerThreshold > 1.f ? 1.f : outerThreshold);

\tif (curve == 1) value = value * value;
\telse if (curve == 2) value = value * value * value;

\tvalue /= threshold;
\tif (value > 1.f) value = 1.f;
\treturn (s32)(sign * value * 32767.f);
}

static f32 rstickSmoothed[INPUT_MAX_CONTROLLERS][2];

static inline s32 inputRightStickDynamic(s32 x, s32 cidx, s32 axis, const f32 acceleration, const f32 smoothing)
{
\tf32 value = (f32)x;
\tif (acceleration > 0.f) {
\t\tconst f32 magnitude = fabsf(value) / 32767.f;
\t\tvalue *= 1.f + acceleration * magnitude;
\t\tif (value > 32767.f) value = 32767.f;
\t\telse if (value < -32768.f) value = -32768.f;
\t}
\tif (smoothing > 0.f) {
\t\t// 0 is the exact legacy path. Higher values retain more of the prior
\t\t// sample, trading immediacy for steadier fine aiming.
\t\trstickSmoothed[cidx][axis] += (value - rstickSmoothed[cidx][axis]) * (1.f - smoothing);
\t\tvalue = rstickSmoothed[cidx][axis];
\t} else {
\t\trstickSmoothed[cidx][axis] = value;
\t}
\treturn (s32)value;
}
''',
    '''static inline f32 inputClampUnit(f32 value)
{
\treturn value < 0.f ? 0.f : (value > 1.f ? 1.f : value);
}

static inline s32 inputRightStickShape(s32 x, const s32 curve, const f32 outerThreshold)
{
\t// Preserve the exact old path for Classic. This matters both for regression
\t// testing and for players who want the original Dabs/Perfect Dark feel.
\tif (curve == 0 && outerThreshold >= 0.9999f) {
\t\treturn x;
\t}

\tconst f32 sign = x < 0 ? -1.f : 1.f;
\tconst f32 threshold = outerThreshold < 0.50f ? 0.50f : (outerThreshold > 1.f ? 1.f : outerThreshold);
\tf32 value = inputClampUnit(fabsf((f32)x / 32767.f) / threshold);

\t// Perfect Dark applies its own square curve later when converting analogue
\t// look into camera speed. The old Precision/Fine implementation squared or
\t// cubed here as well, creating effective fourth/sixth-power response curves.
\t// These gentler exponents are designed to work with the game's downstream
\t// curve instead of multiplying it into something excessively steep.
\tif (curve == 1) {
\t\tvalue = powf(value, 0.85f); // Balanced: responsive, still controlled
\t} else if (curve == 2) {
\t\tvalue = value;              // Precision: game supplies the square curve
\t} else if (curve == 3) {
\t\tvalue = powf(value, 1.15f); // Fine: slightly more centre precision
\t}

\treturn (s32)(sign * value * 32767.f);
}

static f32 rstickSmoothed[INPUT_MAX_CONTROLLERS][2];
static f32 rstickAccelHold[INPUT_MAX_CONTROLLERS];
static u64 rstickLastSampleUs[INPUT_MAX_CONTROLLERS];

static inline void inputResetRightStickState(s32 cidx)
{
\tif (cidx < 0 || cidx >= INPUT_MAX_CONTROLLERS) {
\t\treturn;
\t}
\trstickSmoothed[cidx][0] = 0.f;
\trstickSmoothed[cidx][1] = 0.f;
\trstickAccelHold[cidx] = 0.f;
\trstickLastSampleUs[cidx] = 0;
}

static inline void inputRightStickDynamic(s32 *x, s32 *y, s32 cidx, const f32 acceleration, const f32 smoothing)
{
\tconst u64 now = sysGetMicroseconds();
\tf32 dt = 1.f / 60.f;

\tif (rstickLastSampleUs[cidx] && now > rstickLastSampleUs[cidx]) {
\t\tdt = (f32)(now - rstickLastSampleUs[cidx]) / 1000000.f;
\t\tif (dt > 0.10f) dt = 0.10f;
\t}
\trstickLastSampleUs[cidx] = now;

\t// Acceleration is now genuinely time based. Holding a substantial turn for
\t// a short period gradually adds up to 35% extra stick magnitude; quick aim
\t// corrections are untouched. This avoids duplicating the response curve.
\tf32 fx = (f32)*x / 32767.f;
\tf32 fy = (f32)*y / 32767.f;
\tf32 magnitude = sqrtf(fx * fx + fy * fy);

\tif (acceleration > 0.f) {
\t\tif (magnitude > 0.55f) {
\t\t\trstickAccelHold[cidx] += dt;
\t\t} else if (magnitude < 0.35f) {
\t\t\trstickAccelHold[cidx] = 0.f;
\t\t} else {
\t\t\trstickAccelHold[cidx] -= dt * 2.f;
\t\t\tif (rstickAccelHold[cidx] < 0.f) rstickAccelHold[cidx] = 0.f;
\t\t}

\t\tconst f32 ramp = inputClampUnit((rstickAccelHold[cidx] - 0.12f) / 0.45f);
\t\tconst f32 boost = 1.f + acceleration * 0.35f * ramp;
\t\tfx *= boost;
\t\tfy *= boost;

\t\tmagnitude = sqrtf(fx * fx + fy * fy);
\t\tif (magnitude > 1.f) {
\t\t\tfx /= magnitude;
\t\t\tfy /= magnitude;
\t\t}
\t} else {
\t\trstickAccelHold[cidx] = 0.f;
\t}

\tf32 targetX = fx * 32767.f;
\tf32 targetY = fy * 32767.f;

\tif (smoothing > 0.f) {
\t\t// Treat the setting as retained input per 60 Hz frame, then convert it
\t\t// using real elapsed time. The feel therefore stays stable at different
\t\t// frame rates instead of becoming more sluggish at higher FPS.
\t\tconst f32 retain = powf(smoothing, dt * 60.f);
\t\tconst f32 blend = 1.f - retain;
\t\trstickSmoothed[cidx][0] += (targetX - rstickSmoothed[cidx][0]) * blend;
\t\trstickSmoothed[cidx][1] += (targetY - rstickSmoothed[cidx][1]) * blend;
\t\ttargetX = rstickSmoothed[cidx][0];
\t\ttargetY = rstickSmoothed[cidx][1];
\t} else {
\t\trstickSmoothed[cidx][0] = targetX;
\t\trstickSmoothed[cidx][1] = targetY;
\t}

\t*x = (s32)targetX;
\t*y = (s32)targetY;
}
''',
    "right-stick shaping/dynamics",
)

replace_once(
    "port/src/input.c",
    '''\tleftX = inputAxisScale(leftX, cfg->deadzone[cfg->axisMap[0][0]], cfg->sens[cfg->axisMap[0][0]]);
\tleftY = inputAxisScale(leftY, cfg->deadzone[cfg->axisMap[0][1]], cfg->sens[cfg->axisMap[0][1]]);
\trightX = inputAxisScale(rightX, cfg->deadzone[cfg->axisMap[1][0]], cfg->sens[cfg->axisMap[1][0]]);
\trightY = inputAxisScale(rightY, cfg->deadzone[cfg->axisMap[1][1]], cfg->sens[cfg->axisMap[1][1]]);
\trightX = inputRightStickShape(rightX, cfg->rstickCurve, cfg->rstickOuterThreshold);
\trightY = inputRightStickShape(rightY, cfg->rstickCurve, cfg->rstickOuterThreshold);
\trightX = inputRightStickDynamic(rightX, idx, 0, cfg->rstickAcceleration, cfg->rstickSmoothing);
\trightY = inputRightStickDynamic(rightY, idx, 1, cfg->rstickAcceleration, cfg->rstickSmoothing);
''',
    '''\tleftX = inputAxisScale(leftX, cfg->deadzone[cfg->axisMap[0][0]], cfg->sens[cfg->axisMap[0][0]]);
\tleftY = inputAxisScale(leftY, cfg->deadzone[cfg->axisMap[0][1]], cfg->sens[cfg->axisMap[0][1]]);
\trightX = inputAxisScale(rightX, cfg->deadzone[cfg->axisMap[1][0]], cfg->sens[cfg->axisMap[1][0]]);
\trightY = inputAxisScale(rightY, cfg->deadzone[cfg->axisMap[1][1]], cfg->sens[cfg->axisMap[1][1]]);

\t// axisMap swaps the two logical sticks for the default PC/FPS control style.
\t// Find SDL's physical right-stick axes explicitly so these options always
\t// tune the RP5 right stick instead of accidentally tuning the movement stick.
\ts32 *physicalRightX = cfg->axisMap[0][0] == SDL_CONTROLLER_AXIS_RIGHTX ? &leftX : &rightX;
\ts32 *physicalRightY = cfg->axisMap[0][1] == SDL_CONTROLLER_AXIS_RIGHTY ? &leftY : &rightY;
\t*physicalRightX = inputRightStickShape(*physicalRightX, cfg->rstickCurve, cfg->rstickOuterThreshold);
\t*physicalRightY = inputRightStickShape(*physicalRightY, cfg->rstickCurve, cfg->rstickOuterThreshold);
\tinputRightStickDynamic(physicalRightX, physicalRightY, idx, cfg->rstickAcceleration, cfg->rstickSmoothing);
''',
    "physical right-stick routing",
)

replace_once(
    "port/src/input.c",
    '''s32 inputControllerGetRightStickCurve(s32 cidx) { return padsCfg[cidx].rstickCurve; }
void inputControllerSetRightStickCurve(s32 cidx, s32 curve) { padsCfg[cidx].rstickCurve = curve < 0 ? 0 : (curve > 2 ? 2 : curve); }
f32 inputControllerGetRightStickOuterThreshold(s32 cidx) { return padsCfg[cidx].rstickOuterThreshold; }
void inputControllerSetRightStickOuterThreshold(s32 cidx, f32 value) { padsCfg[cidx].rstickOuterThreshold = value < 0.50f ? 0.50f : (value > 1.f ? 1.f : value); }
f32 inputControllerGetRightStickAcceleration(s32 cidx) { return padsCfg[cidx].rstickAcceleration; }
void inputControllerSetRightStickAcceleration(s32 cidx, f32 value) { padsCfg[cidx].rstickAcceleration = value < 0.f ? 0.f : (value > 1.f ? 1.f : value); }
f32 inputControllerGetRightStickSmoothing(s32 cidx) { return padsCfg[cidx].rstickSmoothing; }
void inputControllerSetRightStickSmoothing(s32 cidx, f32 value) { padsCfg[cidx].rstickSmoothing = value < 0.f ? 0.f : (value > 0.75f ? 0.75f : value); }
''',
    '''s32 inputControllerGetRightStickCurve(s32 cidx) { return padsCfg[cidx].rstickCurve; }
void inputControllerSetRightStickCurve(s32 cidx, s32 curve)
{
\tpadsCfg[cidx].rstickCurve = curve < 0 ? 0 : (curve > 3 ? 3 : curve);
\tinputResetRightStickState(cidx);
}
f32 inputControllerGetRightStickOuterThreshold(s32 cidx) { return padsCfg[cidx].rstickOuterThreshold; }
void inputControllerSetRightStickOuterThreshold(s32 cidx, f32 value)
{
\tpadsCfg[cidx].rstickOuterThreshold = value < 0.50f ? 0.50f : (value > 1.f ? 1.f : value);
\tinputResetRightStickState(cidx);
}
f32 inputControllerGetRightStickAcceleration(s32 cidx) { return padsCfg[cidx].rstickAcceleration; }
void inputControllerSetRightStickAcceleration(s32 cidx, f32 value)
{
\tpadsCfg[cidx].rstickAcceleration = value < 0.f ? 0.f : (value > 1.f ? 1.f : value);
\tinputResetRightStickState(cidx);
}
f32 inputControllerGetRightStickSmoothing(s32 cidx) { return padsCfg[cidx].rstickSmoothing; }
void inputControllerSetRightStickSmoothing(s32 cidx, f32 value)
{
\tpadsCfg[cidx].rstickSmoothing = value < 0.f ? 0.f : (value > 0.75f ? 0.75f : value);
\tinputResetRightStickState(cidx);
}

static inline s32 inputRightStickNear(f32 a, f32 b)
{
\treturn fabsf(a - b) < 0.005f;
}

s32 inputControllerGetRightStickPreset(s32 cidx)
{
\tconst struct controllercfg *cfg = &padsCfg[cidx];
\tif (cfg->rstickCurve == 0 && inputRightStickNear(cfg->rstickOuterThreshold, 1.00f)
\t\t\t&& inputRightStickNear(cfg->rstickAcceleration, 0.00f) && inputRightStickNear(cfg->rstickSmoothing, 0.00f)) return 0;
\tif (cfg->rstickCurve == 1 && inputRightStickNear(cfg->rstickOuterThreshold, 0.95f)
\t\t\t&& inputRightStickNear(cfg->rstickAcceleration, 0.20f) && inputRightStickNear(cfg->rstickSmoothing, 0.08f)) return 1;
\tif (cfg->rstickCurve == 2 && inputRightStickNear(cfg->rstickOuterThreshold, 1.00f)
\t\t\t&& inputRightStickNear(cfg->rstickAcceleration, 0.08f) && inputRightStickNear(cfg->rstickSmoothing, 0.18f)) return 2;
\tif (cfg->rstickCurve == 1 && inputRightStickNear(cfg->rstickOuterThreshold, 0.85f)
\t\t\t&& inputRightStickNear(cfg->rstickAcceleration, 0.70f) && inputRightStickNear(cfg->rstickSmoothing, 0.03f)) return 3;
\treturn 4; // Custom
}

void inputControllerSetRightStickPreset(s32 cidx, s32 preset)
{
\tstruct controllercfg *cfg = &padsCfg[cidx];
\tswitch (preset) {
\tcase 0: // Classic: exact pre-tuning behaviour
\t\tcfg->rstickCurve = 0; cfg->rstickOuterThreshold = 1.00f; cfg->rstickAcceleration = 0.00f; cfg->rstickSmoothing = 0.00f; break;
\tcase 1: // Balanced
\t\tcfg->rstickCurve = 1; cfg->rstickOuterThreshold = 0.95f; cfg->rstickAcceleration = 0.20f; cfg->rstickSmoothing = 0.08f; break;
\tcase 2: // Precision
\t\tcfg->rstickCurve = 2; cfg->rstickOuterThreshold = 1.00f; cfg->rstickAcceleration = 0.08f; cfg->rstickSmoothing = 0.18f; break;
\tcase 3: // Fast
\t\tcfg->rstickCurve = 1; cfg->rstickOuterThreshold = 0.85f; cfg->rstickAcceleration = 0.70f; cfg->rstickSmoothing = 0.03f; break;
\tdefault:
\t\treturn; // Custom is descriptive; choosing it does not destroy the current values.
\t}
\tinputResetRightStickState(cidx);
}

s32 inputControllerUsesFullRightStickRange(s32 cidx)
{
\t// Non-classic response modes opt into the corrected PC camera range. The
\t// bond movement code also checks that the physical right stick is actually
\t// mapped to look before using it.
\treturn padsCfg[cidx].rstickCurve != 0;
}
''',
    "right-stick API and presets",
)

replace_once(
    "port/src/input.c",
    'configRegisterInt(strFmt("%s.RStickCurve", secname), &padsCfg[c].rstickCurve, 0, 2);',
    'configRegisterInt(strFmt("%s.RStickCurve", secname), &padsCfg[c].rstickCurve, 0, 3);',
    "right-stick curve config range",
)

replace_once(
    "port/include/input.h",
    '''f32 inputControllerGetRightStickSmoothing(s32 cidx);
void inputControllerSetRightStickSmoothing(s32 cidx, f32 value);
''',
    '''f32 inputControllerGetRightStickSmoothing(s32 cidx);
void inputControllerSetRightStickSmoothing(s32 cidx, f32 value);
s32 inputControllerGetRightStickPreset(s32 cidx);
void inputControllerSetRightStickPreset(s32 cidx, s32 preset);
s32 inputControllerUsesFullRightStickRange(s32 cidx);
''',
    "right-stick header API",
)

# Menu: presets sit above the advanced response controls. Preset state is
# derived from the actual values, so manual edits automatically display Custom.
replace_once(
    "port/src/optionsmenu.c",
    '''static MenuItemHandlerResult menuhandlerStickDeadzone(s32 operation, struct menuitem *item, union handlerdata *data);
static MenuItemHandlerResult menuhandlerRightStickCurve(s32 operation, struct menuitem *item, union handlerdata *data);
''',
    '''static MenuItemHandlerResult menuhandlerStickDeadzone(s32 operation, struct menuitem *item, union handlerdata *data);
static MenuItemHandlerResult menuhandlerRightStickPreset(s32 operation, struct menuitem *item, union handlerdata *data);
static MenuItemHandlerResult menuhandlerRightStickCurve(s32 operation, struct menuitem *item, union handlerdata *data);
''',
    "right-stick preset handler declaration",
)

replace_once(
    "port/src/optionsmenu.c",
    '''\t{
\t\tMENUITEMTYPE_DROPDOWN, 0, MENUITEMFLAG_LITERAL_TEXT,
\t\t(uintptr_t)"RStick Response", 0, menuhandlerRightStickCurve,
\t},
''',
    '''\t{
\t\tMENUITEMTYPE_DROPDOWN, 0, MENUITEMFLAG_LITERAL_TEXT,
\t\t(uintptr_t)"RStick Preset", 0, menuhandlerRightStickPreset,
\t},
\t{
\t\tMENUITEMTYPE_DROPDOWN, 0, MENUITEMFLAG_LITERAL_TEXT,
\t\t(uintptr_t)"RStick Response", 0, menuhandlerRightStickCurve,
\t},
''',
    "right-stick preset menu row",
)

replace_once(
    "port/src/optionsmenu.c",
    '''static MenuItemHandlerResult menuhandlerRightStickCurve(s32 operation, struct menuitem *item, union handlerdata *data)
{
\tstatic const char *opts[] = { "Linear (Classic)", "Precision", "Fine" };
\tswitch (operation) {
\tcase MENUOP_GETOPTIONCOUNT: data->dropdown.value = ARRAYCOUNT(opts); break;
\tcase MENUOP_GETOPTIONTEXT: return (uintptr_t)opts[data->dropdown.value];
\tcase MENUOP_GETSELECTEDINDEX: data->dropdown.value = inputControllerGetRightStickCurve(g_ExtMenuPlayer); break;
\tcase MENUOP_SET: inputControllerSetRightStickCurve(g_ExtMenuPlayer, data->dropdown.value); break;
\t}
\treturn 0;
}
''',
    '''static MenuItemHandlerResult menuhandlerRightStickPreset(s32 operation, struct menuitem *item, union handlerdata *data)
{
\tstatic const char *opts[] = { "Classic", "Balanced", "Precision", "Fast", "Custom" };
\tswitch (operation) {
\tcase MENUOP_GETOPTIONCOUNT: data->dropdown.value = ARRAYCOUNT(opts); break;
\tcase MENUOP_GETOPTIONTEXT: return (uintptr_t)opts[data->dropdown.value];
\tcase MENUOP_GETSELECTEDINDEX: data->dropdown.value = inputControllerGetRightStickPreset(g_ExtMenuPlayer); break;
\tcase MENUOP_SET: inputControllerSetRightStickPreset(g_ExtMenuPlayer, data->dropdown.value); break;
\t}
\treturn 0;
}

static MenuItemHandlerResult menuhandlerRightStickCurve(s32 operation, struct menuitem *item, union handlerdata *data)
{
\tstatic const char *opts[] = { "Classic", "Balanced", "Precision", "Fine" };
\tswitch (operation) {
\tcase MENUOP_GETOPTIONCOUNT: data->dropdown.value = ARRAYCOUNT(opts); break;
\tcase MENUOP_GETOPTIONTEXT: return (uintptr_t)opts[data->dropdown.value];
\tcase MENUOP_GETSELECTEDINDEX: data->dropdown.value = inputControllerGetRightStickCurve(g_ExtMenuPlayer); break;
\tcase MENUOP_SET: inputControllerSetRightStickCurve(g_ExtMenuPlayer, data->dropdown.value); break;
\t}
\treturn 0;
}
''',
    "right-stick preset/response handlers",
)

# Camera range: stock PD reaches maximum natural turn/pitch at stick value 70,
# leaving nearly half of a modern analogue stick unused. Modern response modes
# spread that same maximum camera speed across the full 0..127 stick range.
modern_pitch = '''#ifndef PLATFORM_N64
\t\t\t\tfVar25 = movedata.analogpitch / ((controlmode == CONTROLMODE_PC
\t\t\t\t\t\t&& inputControllerGetSticksSwapped(contpad1)
\t\t\t\t\t\t&& inputControllerUsesFullRightStickRange(contpad1)) ? 127.0f : 70.0f);
#else
\t\t\t\tfVar25 = movedata.analogpitch / 70.0f;
#endif'''
replace_once(
    "src/game/bondmove.c",
    '\t\t\t\tfVar25 = movedata.analogpitch / 70.0f;',
    modern_pitch,
    "full-range PC pitch",
)

modern_turn = '''#ifndef PLATFORM_N64
\t\tfVar25 = movedata.analogturn / ((controlmode == CONTROLMODE_PC
\t\t\t\t&& inputControllerGetSticksSwapped(contpad1)
\t\t\t\t&& inputControllerUsesFullRightStickRange(contpad1)) ? 127.0f : 70.0f);
#else
\t\tfVar25 = movedata.analogturn / 70.0f;
#endif'''
replace_once(
    "src/game/bondmove.c",
    '\t\tfVar25 = movedata.analogturn / 70.0f;',
    modern_turn,
    "full-range PC turn",
)

print("right-stick aiming overhaul applied")

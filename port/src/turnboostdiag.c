// Passive diagnostics: never write controller, movement, or camera state.
#include <stdio.h>
#include <math.h>
#include <string.h>
#include "turnboostdiag.h"
#include "input.h"
#include "system.h"
#include "constants.h"
#include "bss.h"
#include "data.h"
#include "types.h"
#include "game/game_1531a0.h"
#include "lib/vi.h"

s32 g_TurnBoostReadout = 1; // Investigation build: visible on first launch.
static s32 rawStick[INPUT_MAX_CONTROLLERS], shapedStick[INPUT_MAX_CONTROLLERS];
static struct {
    bool armed;
    s32 stage, pad, mode, analog, natural, aiming;
    f32 oldbody, oldcam, level, multiplier, control, speed, amount, mouse;
    f32 seconds, baseSum, bodySum, camSum;
    f32 baseRate, bodyRate, camRate, bodyRatio, camRatio;
    u64 started, lastEnd;
    f32 realRate;
} diag[4];

static f32 angleDelta(f32 delta)
{
    while (delta > 180.f) delta -= 360.f;
    while (delta < -180.f) delta += 360.f;
    return delta;
}

static f32 cameraYaw(void)
{
    // Read the final first-person camera vector, not the intended yaw input.
    return -atan2f(g_Vars.currentplayer->cam_look.x,
            g_Vars.currentplayer->cam_look.z) * (180.f / M_PI);
}

void turnBoostDiagStick(s32 pad, s32 raw, s32 processed)
{
    if (pad >= 0 && pad < INPUT_MAX_CONTROLLERS) {
        rawStick[pad] = raw;
        shapedStick[pad] = processed;
    }
}

void turnBoostDiagBegin(void)
{
    const s32 p = g_Vars.currentplayernum;
    if (p < 0 || p >= 4) return;
    diag[p].armed = false;
    if (!g_TurnBoostReadout || g_Vars.currentplayer->isdead
            || g_Vars.currentplayer->pausemode != PAUSEMODE_UNPAUSED
            || g_Vars.currentplayer->bondmovemode != MOVEMODE_WALK
            || g_Vars.lvupdate60freal <= 0.f) return;
    const u64 now = sysGetMicroseconds();
    if (diag[p].stage != g_Vars.stagenum || !diag[p].lastEnd
            || now - diag[p].lastEnd > 250000) {
        memset(&diag[p], 0, sizeof diag[p]);
        diag[p].stage = g_Vars.stagenum;
        diag[p].started = now;
    }
    diag[p].oldbody = g_Vars.currentplayer->vv_theta;
    diag[p].oldcam = cameraYaw();
    diag[p].armed = true;
}

void turnBoostDiagControl(s32 pad, s32 mode, s32 analog, s32 natural,
        f32 level, f32 multiplier, f32 mouse)
{
    const s32 p = g_Vars.currentplayernum;
    if (p < 0 || p >= 4 || !diag[p].armed) return;
    diag[p].pad = pad;
    diag[p].mode = mode;
    diag[p].analog = analog;
    diag[p].natural = natural;
    diag[p].aiming = g_Vars.currentplayer->insightaimmode;
    diag[p].level = level;
    diag[p].multiplier = multiplier;
    diag[p].control = g_Vars.currentplayer->speedthetacontrol;
    diag[p].speed = g_Vars.currentplayer->speedtheta;
    diag[p].mouse = mouse;
    const f32 max = viGetFovY() / PLAYER_DEFAULT_FOV * (natural ? 1.f : .7f);
    diag[p].amount = max > 0.f ? fabsf(diag[p].control) / max : 0.f;
}

void turnBoostDiagEnd(void)
{
    const s32 p = g_Vars.currentplayernum;
    if (p < 0 || p >= 4 || !diag[p].armed) return;
    diag[p].armed = false;
    const u64 now = sysGetMicroseconds();
    diag[p].lastEnd = now;
    const f32 dt = g_Vars.lvupdate60freal / 60.f;
    const f32 body = angleDelta(g_Vars.currentplayer->vv_theta - diag[p].oldbody);
    const f32 cam = angleDelta(cameraYaw() - diag[p].oldcam);
    // Counterfactual unboosted delta from the same tick and controller value.
    const f32 base = diag[p].control * g_Vars.lvupdate60freal
        * 0.0174505133f * 3.5f * 360.f / M_BADTAU;
    diag[p].seconds += dt;
    diag[p].baseSum += base;
    diag[p].bodySum += body;
    diag[p].camSum += cam;
    if (diag[p].seconds >= .25f) {
        diag[p].baseRate = diag[p].baseSum / diag[p].seconds;
        diag[p].bodyRate = diag[p].bodySum / diag[p].seconds;
        diag[p].camRate = diag[p].camSum / diag[p].seconds;
        diag[p].bodyRatio = fabsf(diag[p].baseSum) > .01f ? diag[p].bodySum / diag[p].baseSum : 0.f;
        diag[p].camRatio = fabsf(diag[p].baseSum) > .01f ? diag[p].camSum / diag[p].baseSum : 0.f;
        diag[p].realRate = now > diag[p].started ? diag[p].camSum * 1000000.f / (now - diag[p].started) : 0.f;
        const s32 pad = diag[p].pad;
        sysLogPrintf(LOG_NOTE, "turnboost p=%d pad=%d mode=%d natural=%d aim=%d raw=%d shaped=%d analog=%d amount=%.3f charge=%.3f mult=%.3f control=%.3f speed=%.3f mouse=%.3f base_dps=%.3f body_dps=%.3f camera_dps=%.3f body_ratio=%.4f camera_ratio=%.4f real_dps=%.3f strength=%.3f ramp=%.2f threshold=%.2f release=%.2f aimmode=%d",
            p, pad, diag[p].mode, diag[p].natural, diag[p].aiming,
            pad >= 0 && pad < INPUT_MAX_CONTROLLERS ? rawStick[pad] : 0,
            pad >= 0 && pad < INPUT_MAX_CONTROLLERS ? shapedStick[pad] : 0,
            diag[p].analog, diag[p].amount, diag[p].level, diag[p].multiplier,
            diag[p].control, diag[p].speed, diag[p].mouse,
            diag[p].baseRate, diag[p].bodyRate, diag[p].camRate,
            diag[p].bodyRatio, diag[p].camRatio, diag[p].realRate,
            pad >= 0 && pad < INPUT_MAX_CONTROLLERS ? inputControllerGetTurnBoost(pad) : 0.f,
            pad >= 0 && pad < INPUT_MAX_CONTROLLERS ? inputControllerGetTurnBoostRamp(pad) : 0.f,
            pad >= 0 && pad < INPUT_MAX_CONTROLLERS ? inputControllerGetTurnBoostThreshold(pad) : 0.f,
            pad >= 0 && pad < INPUT_MAX_CONTROLLERS ? inputControllerGetTurnBoostRelease(pad) : 0.f,
            pad >= 0 && pad < INPUT_MAX_CONTROLLERS ? inputControllerGetTurnBoostAimMode(pad) : 0);
        diag[p].seconds = diag[p].baseSum = diag[p].bodySum = diag[p].camSum = 0.f;
        diag[p].started = now;
    }
}

Gfx *turnBoostDiagRender(Gfx *gdl)
{
    // Single-player hardware investigation. Keep the readout away from menus.
    const s32 p = 0;
    const s32 pad = diag[p].pad;
    if (!g_TurnBoostReadout || !g_Vars.players[0] || !diag[p].lastEnd
            || g_Vars.players[0]->pausemode != PAUSEMODE_UNPAUSED
            || g_Vars.tickmode != TICKMODE_NORMAL
            || !g_FontHandelGothicXs || !g_CharsHandelGothicXs) return gdl;
    char lines[7][64];
    snprintf(lines[0], sizeof lines[0], "Pad %d  mode %d  aim %d", pad + 1, diag[p].mode, diag[p].aiming);
    snprintf(lines[1], sizeof lines[1], "Stick %d  turn %d  gate %.2f",
        pad >= 0 && pad < INPUT_MAX_CONTROLLERS ? rawStick[pad] : 0, diag[p].analog, diag[p].amount);
    snprintf(lines[2], sizeof lines[2], "Charge %.0f%%  boost %.2fx", diag[p].level*100.f, diag[p].multiplier);
    snprintf(lines[3], sizeof lines[3], "Control %.2f  output %.2f", diag[p].control, diag[p].speed);
    snprintf(lines[4], sizeof lines[4], "Deg/s base %.1f  body %.1f", diag[p].baseRate, diag[p].bodyRate);
    snprintf(lines[5], sizeof lines[5], "Camera %.1f  real %.1f", diag[p].camRate, diag[p].realRate);
    snprintf(lines[6], sizeof lines[6], "Ratio body %.2f  camera %.2f", diag[p].bodyRatio, diag[p].camRatio);
    gSPSetExtraGeometryModeEXT(gdl++, g_HudAlignModeL);
    gdl = text0f153628(gdl);
    s32 y = 40;
    for (s32 i = 0; i < 7; i++) {
        s32 x = 24, height, width;
        textMeasure(&height, &width, lines[i], g_CharsHandelGothicXs, g_FontHandelGothicXs, 0);
        if (width + x > viGetWidth() - 12 || y + height > viGetHeight() - 12) continue;
        s32 drawy = y;
        gdl = textRender(gdl, &x, &drawy, lines[i], g_CharsHandelGothicXs,
            g_FontHandelGothicXs, 0xffffffff, 0x000000c0, viGetWidth(), viGetHeight(), 0, 0);
        y += height + 2;
    }
    gdl = text0f153780(gdl);
    gSPClearExtraGeometryModeEXT(gdl++, g_HudAlignModeL);
    return gdl;
}

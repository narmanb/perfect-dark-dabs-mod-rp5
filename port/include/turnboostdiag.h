#ifndef TURNBOOSTDIAG_H
#define TURNBOOSTDIAG_H
#include <ultra64.h>

extern s32 g_TurnBoostReadout;
void turnBoostDiagStick(s32 pad, s32 raw, s32 processed);
void turnBoostDiagBegin(void);
void turnBoostDiagControl(s32 pad, s32 mode, s32 analog, s32 natural,
        f32 level, f32 multiplier, f32 mouse);
void turnBoostDiagEnd(void);
Gfx *turnBoostDiagRender(Gfx *gdl);
#endif

#!/usr/bin/env python3
from pathlib import Path

p = Path("src/game/bondmove.c")
s = p.read_text(encoding="utf-8")

old_decl = '''#ifndef PLATFORM_N64
\t// Sustained outer-edge horizontal turn boost. This runs after both the
\t// natural-turn path and the normal aim-turn path, so CoD Aim Lock and
\t// classic Perfect Dark aiming can both use the same optional boost.
\tif (contpad1 >= 0 && contpad1 < INPUT_MAX_CONTROLLERS
'''
new_decl = '''#ifndef PLATFORM_N64
\tf32 turnboostmult = 1.f;

\t// Sustained outer-edge horizontal turn boost. This runs after both the
\t// natural-turn path and the normal aim-turn path. The ramp is keyed from
\t// the actual controller turn output rather than a logical/raw stick axis,
\t// so stick swaps, response curves and hardware range cannot silently keep
\t// the boost below its threshold.
\tif (contpad1 >= 0 && contpad1 < INPUT_MAX_CONTROLLERS
'''
if s.count(old_decl) != 1:
    raise SystemExit(f"turn boost declaration anchor: expected 1 match, found {s.count(old_decl)}")
s = s.replace(old_decl, new_decl, 1)

old_apply = '''\t\tconst f32 p = turnboostlevel[contpad1];
\t\tconst f32 eased = p * p * (3.f - 2.f * p);
\t\tg_Vars.currentplayer->speedthetacontrol *=
\t\t\t1.f + inputControllerGetTurnBoost(contpad1) * 0.50f * eased * aimfactor;
'''
new_apply = '''\t\tconst f32 p = turnboostlevel[contpad1];
\t\tconst f32 eased = p * p * (3.f - 2.f * p);
\t\tturnboostmult = 1.f + inputControllerGetTurnBoost(contpad1) * 1.00f * eased * aimfactor;
'''
if s.count(old_apply) != 1:
    raise SystemExit(f"turn boost persistent multiplier: expected 1 match, found {s.count(old_apply)}")
s = s.replace(old_apply, new_apply, 1)

old_gate = '''\tif (contpad1 >= 0 && contpad1 < INPUT_MAX_CONTROLLERS
\t\t\t&& controlmode == CONTROLMODE_PC
\t\t\t&& inputControllerGetSticksSwapped(contpad1)
\t\t\t&& inputControllerGetTurnBoost(contpad1) > 0.f) {
\t\tf32 amount = fabsf((f32)movedata.c1stickxraw) / 127.f;
\t\tf32 dt = g_Vars.lvupdate60freal / 60.f;
\t\tf32 aimfactor = 1.f;
'''
new_gate = '''\tif (contpad1 >= 0 && contpad1 < INPUT_MAX_CONTROLLERS
\t\t\t&& inputControllerGetTurnBoost(contpad1) > 0.f) {
\t\tconst f32 turnbase = viGetFovY() / PLAYER_DEFAULT_FOV;
\t\tconst bool controllerturn = movedata.cannaturalturn
\t\t\t? movedata.analogturn != 0
\t\t\t: (movedata.aimturnleftspeed > 0.f || movedata.aimturnrightspeed > 0.f);
\t\tconst f32 normalmax = movedata.cannaturalturn ? turnbase : turnbase * 0.7f;
\t\tf32 amount = controllerturn && normalmax > 0.f
\t\t\t? fabsf(g_Vars.currentplayer->speedthetacontrol) / normalmax
\t\t\t: 0.f;
\t\tf32 dt = g_Vars.lvupdate60freal / 60.f;
\t\tf32 aimfactor = 1.f;
'''
if s.count(old_gate) != 1:
    raise SystemExit(f"turn boost trigger source: expected 1 match, found {s.count(old_gate)}")
s = s.replace(old_gate, new_gate, 1)

old_final = '''#endif

\tg_Vars.currentplayer->speedtheta = g_Vars.currentplayer->speedthetacontrol;'''
new_final = '''\tg_Vars.currentplayer->speedtheta = g_Vars.currentplayer->speedthetacontrol * turnboostmult;
#else
\tg_Vars.currentplayer->speedtheta = g_Vars.currentplayer->speedthetacontrol;
#endif'''
if s.count(old_final) != 1:
    raise SystemExit(f"turn boost final-output anchor: expected 1 match, found {s.count(old_final)}")
s = s.replace(old_final, new_final, 1)

p.write_text(s, encoding="utf-8")
print("turn boost now ramps from actual controller turn output and reaches 2x at 100%")

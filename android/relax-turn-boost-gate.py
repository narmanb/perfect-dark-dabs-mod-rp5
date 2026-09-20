#!/usr/bin/env python3
from pathlib import Path

p = Path("src/game/bondmove.c")
s = p.read_text(encoding="utf-8")

old_gate = '''\tif (contpad1 >= 0 && contpad1 < INPUT_MAX_CONTROLLERS
\t\t\t&& controlmode == CONTROLMODE_PC
\t\t\t&& inputControllerGetSticksSwapped(contpad1)
\t\t\t&& inputControllerGetTurnBoost(contpad1) > 0.f) {'''
new_gate = '''\tif (contpad1 >= 0 && contpad1 < INPUT_MAX_CONTROLLERS
\t\t\t&& inputControllerGetSticksSwapped(contpad1)
\t\t\t&& inputControllerGetTurnBoost(contpad1) > 0.f) {'''
if s.count(old_gate) != 1:
    raise SystemExit(f"turn boost control-mode gate: expected 1 match, found {s.count(old_gate)}")
s = s.replace(old_gate, new_gate, 1)

old_strength = '''\t\t// Smoothstep makes acceleration into and out of the sustained boost less
\t\t// mechanical. 100% Turn Boost tops out at +50% camera turn speed.
\t\tconst f32 p = turnboostlevel[contpad1];
\t\tconst f32 eased = p * p * (3.f - 2.f * p);
\t\tturnboostmult = 1.f + inputControllerGetTurnBoost(contpad1) * 0.50f * eased * aimfactor;'''
new_strength = '''\t\t// Smoothstep makes acceleration into and out of the sustained boost less
\t\t// mechanical. Keep 100% intentionally obvious for calibration: it can
\t\t// double the normal sustained horizontal turn speed. Lower slider values
\t\t// remain proportionally milder for normal play.
\t\tconst f32 p = turnboostlevel[contpad1];
\t\tconst f32 eased = p * p * (3.f - 2.f * p);
\t\tturnboostmult = 1.f + inputControllerGetTurnBoost(contpad1) * 1.00f * eased * aimfactor;'''
if s.count(old_strength) != 1:
    raise SystemExit(f"turn boost strength block: expected 1 match, found {s.count(old_strength)}")
s = s.replace(old_strength, new_strength, 1)

p.write_text(s, encoding="utf-8")
print("turn boost no longer depends on CONTROLMODE_PC; 100% boost now reaches 2x normal speed")

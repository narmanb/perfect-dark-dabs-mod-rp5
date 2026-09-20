#!/usr/bin/env python3
"""Instrument generated Run 129 code without changing movement behavior."""
from pathlib import Path


def replace(path, old, new):
    p = Path(path)
    source = p.read_text()
    assert source.count(old) == 1, (path, old, source.count(old))
    p.write_text(source.replace(old, new, 1))


for path in ['port/src/input.c', 'port/src/optionsmenu.c', 'src/game/bondmove.c', 'src/game/player.c']:
    replace(path, '#include "input.h"', '#include "input.h"\n#include "turnboostdiag.h"')
replace('src/game/lv.c', '#include "video.h"', '#include "video.h"\n#include "turnboostdiag.h"')
replace('port/src/input.c', '\tconfigRegisterInt("Input.MouseEnabled", &mouseEnabled, 0, 1);',
        '\tconfigRegisterInt("Input.TurnBoostReadout", &g_TurnBoostReadout, 0, 1);\n\tconfigRegisterInt("Input.MouseEnabled", &mouseEnabled, 0, 1);')
replace('port/src/input.c', '\tleftX = inputAxisScale(leftX,',
        '\tconst s32 physicalRawX = cfg->axisMap[0][0] == SDL_CONTROLLER_AXIS_RIGHTX ? leftX : rightX;\n\n\tleftX = inputAxisScale(leftX,')
replace('port/src/input.c', '\tinputRightStickDynamic(physicalRightX, physicalRightY, idx, cfg->rstickAcceleration, cfg->rstickSmoothing);',
        '\tinputRightStickDynamic(physicalRightX, physicalRightY, idx, cfg->rstickAcceleration, cfg->rstickSmoothing);\n\tturnBoostDiagStick(idx, physicalRawX, *physicalRightX);')
replace('src/game/bondmove.c', '\tbmoveUpdateSpeedTheta();\n', '''\tbmoveUpdateSpeedTheta();
#ifndef PLATFORM_N64
\tturnBoostDiagControl(contpad1, controlmode, movedata.analogturn, movedata.cannaturalturn,
\t\tcontpad1 >= 0 && contpad1 < INPUT_MAX_CONTROLLERS ? turnboostlevel[contpad1] : 0.f,
\t\tturnboostmult, movedata.freelookdx);
#endif
''')
# These hooks enclose the normal movement tick AND final camera construction.
replace('src/game/player.c', '''\t\tif (g_PlayersWithControl[g_Vars.currentplayernum]) {
\t\t\tbmoveTick(1, 1, arg0, 0);
\t\t} else {
\t\t\tbmoveTick(0, 0, 0, 1);
\t\t}

\t\tplayerUpdateShake();''', '''#ifndef PLATFORM_N64
\t\tturnBoostDiagBegin();
#endif
\t\tif (g_PlayersWithControl[g_Vars.currentplayernum]) {
\t\t\tbmoveTick(1, 1, arg0, 0);
\t\t} else {
\t\t\tbmoveTick(0, 0, 0, 1);
\t\t}

\t\tplayerUpdateShake();''')
anchor = '''\t\tplayer0f0c1840(&spf4, &camup, &camlook,
\t\t\t\t&g_Vars.currentplayer->prop->pos,
\t\t\t\tg_Vars.currentplayer->prop->rooms);'''
replace('src/game/player.c', anchor, anchor + '''
#ifndef PLATFORM_N64
\t\tturnBoostDiagEnd();
#endif''')
replace('src/game/lv.c', '\tif (videoGetDisplayFPS()) {', '\tgdl = turnBoostDiagRender(gdl);\n\n\tif (videoGetDisplayFPS()) {')
anchor = 'static MenuItemHandlerResult menuhandlerTurnBoost(s32 op, struct menuitem *item, union handlerdata *data)\n{'
replace('port/src/optionsmenu.c', anchor, '''static MenuItemHandlerResult menuhandlerTurnBoostReadout(s32 op, struct menuitem *item, union handlerdata *data)
{
\tif (op == MENUOP_GET) return g_TurnBoostReadout;
\tif (op == MENUOP_SET) g_TurnBoostReadout = !!data->checkbox.value;
\treturn 0;
}

''' + anchor)
anchor = 'static MenuItemHandlerResult menuhandlerTurnBoost(s32 op, struct menuitem *item, union handlerdata *data);'
replace('port/src/optionsmenu.c', anchor, anchor + '\nstatic MenuItemHandlerResult menuhandlerTurnBoostReadout(s32 op, struct menuitem *item, union handlerdata *data);')
anchor = '''\t\t(uintptr_t)"Boost While Aiming", 0, menuhandlerTurnBoostAim,
\t},'''
replace('port/src/optionsmenu.c', anchor, anchor + '''
\t{
\t\tMENUITEMTYPE_CHECKBOX, 0, MENUITEMFLAG_LITERAL_TEXT,
\t\t(uintptr_t)"Turn Boost Readout", 0, menuhandlerTurnBoostReadout,
\t},''')
print('turn boost: passive input/player/final-camera readout added; yaw behavior unchanged')

#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match in {path}, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"patched {label}: {path.relative_to(ROOT)}")


# ---------------------------------------------------------------------------
# Existing Display FPS option: the menu/config plumbing was already present,
# and video.c already computes a rolling average, but nothing drew it. Render
# that existing value at the end of Player 1's HUD pass.
# ---------------------------------------------------------------------------
player = ROOT / "src/game/player.c"
replace_once(
    player,
    '''#ifndef PLATFORM_N64
#include "video.h"
#include "input.h"
#include "platform.h"
#endif
''',
    '''#ifndef PLATFORM_N64
#include <stdio.h>
#include "video.h"
#include "input.h"
#include "platform.h"
#endif
#ifdef ANDROID
s32 androidConsumeAutoPauseRequest(void);
#endif
''',
    "FPS/Android QoL declarations",
)

replace_once(
    player,
    '''void playerTick(bool arg0)
{
\tf32 aspectratio;
\tf32 f20;

#ifndef PLATFORM_N64
''',
    '''void playerTick(bool arg0)
{
\tf32 aspectratio;
\tf32 f20;

#ifdef ANDROID
\t// Android's UI thread only records the lifecycle request. Consume it here on
\t// the game thread, then use Perfect Dark's normal pause path so returning
\t// from Home/app-switch leaves the mission in the ordinary pause menu.
\tif (g_Vars.currentplayernum == 0 && androidConsumeAutoPauseRequest()
\t\t\t&& g_Vars.currentplayer->pausemode == PAUSEMODE_UNPAUSED
\t\t\t&& !g_Vars.currentplayer->isdead) {
\t\tif (!g_Vars.mplayerisrunning) {
\t\t\tplayerPause(MENUROOT_MAINMENU);
\t\t} else {
\t\t\tmpPushPauseDialog();
\t\t}
\t}
#endif

#ifndef PLATFORM_N64
''',
    "game-thread Android auto-pause",
)

replace_once(
    player,
    '''\t\tgdl = hudmsgsRender(gdl);
\t\tgdl = playerDrawStoredFade(gdl);
\t}

\treturn gdl;
}

void playerDie(bool force)
''',
    '''\t\tgdl = hudmsgsRender(gdl);
\t\tgdl = playerDrawStoredFade(gdl);
\t}

#ifndef PLATFORM_N64
\t// The Display FPS checkbox and rolling average already existed in the port;
\t// make the option visible in-game instead of merely storing a flag.
\tif (g_Vars.currentplayernum == 0 && videoGetDisplayFPS()
\t\t\t&& g_FontHandelGothicXs && g_CharsHandelGothicXs) {
\t\tchar fpstext[32];
\t\ts32 x = viGetViewLeft() + 6;
\t\ts32 y = viGetViewTop() + 6;
\t\tsnprintf(fpstext, sizeof fpstext, "FPS %.1f", videoGetAverageFPS());
\t\tgdl = text0f153628(gdl);
\t\tgdl = textRender(gdl, &x, &y, fpstext, g_CharsHandelGothicXs,
\t\t\tg_FontHandelGothicXs, 0xffffffff, 0x000000c0,
\t\t\tviGetWidth(), viGetHeight(), 0, 0);
\t\tgdl = text0f153780(gdl);
\t}
#endif

\treturn gdl;
}

void playerDie(bool force)
''',
    "existing Display FPS HUD output",
)


# ---------------------------------------------------------------------------
# Android lifecycle bridge. MainActivity requests a pause only when native
# gameplay is actually active; the game thread above consumes it once.
# ---------------------------------------------------------------------------
androidtouch = ROOT / "port/src/androidtouch.c"
replace_once(
    androidtouch,
    '''extern s32 g_MenuKeyboardPlayer;

/*
 * Tell the Java touch layer when it is safe to replace SDL's normal finger
''',
    '''extern s32 g_MenuKeyboardPlayer;

static volatile s32 g_AndroidAutoPauseRequested = 0;

JNIEXPORT void JNICALL
Java_com_perfectdark_port_MainActivity_nativeRequestAutoPause(JNIEnv *env, jobject thiz)
{
\t(void)env;
\t(void)thiz;
\tg_AndroidAutoPauseRequested = 1;
}

s32 androidConsumeAutoPauseRequest(void)
{
\tif (g_AndroidAutoPauseRequested) {
\t\tg_AndroidAutoPauseRequested = 0;
\t\treturn 1;
\t}

\treturn 0;
}

/*
 * Tell the Java touch layer when it is safe to replace SDL's normal finger
''',
    "Android auto-pause JNI bridge",
)

mainactivity = ROOT / "android/app/src/main/java/com/perfectdark/port/MainActivity.java"
replace_once(
    mainactivity,
    '''    @Override
    protected void onPause() {
        touchUiHandler.removeCallbacks(touchUiPoll);
''',
    '''    @Override
    protected void onPause() {
        // Ask the native game to enter its normal pause menu on the game thread.
        // Do this only during actual mission gameplay: title screens, existing
        // menus and cutscenes are deliberately left alone.
        if (nativeGameplayTouchActive()) {
            nativeRequestAutoPause();
        }

        touchUiHandler.removeCallbacks(touchUiPoll);
''',
    "MainActivity gameplay auto-pause request",
)

replace_once(
    mainactivity,
    '''    public native boolean nativeGameplayTouchActive();
    public native boolean nativeTextInputActive();
''',
    '''    public native boolean nativeGameplayTouchActive();
    public native void nativeRequestAutoPause();
    public native boolean nativeTextInputActive();
''',
    "MainActivity auto-pause native declaration",
)

print("Android QoL applied: existing FPS toggle now renders; gameplay auto-pauses on app focus loss")

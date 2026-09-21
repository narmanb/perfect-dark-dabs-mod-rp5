#!/usr/bin/env python3
from pathlib import Path

opt = Path("port/src/optionsmenu.c").read_text(encoding="utf-8")
android = Path("port/src/androidcontrolsmenu.c").read_text(encoding="utf-8")
move = Path("src/game/bondmove.c").read_text(encoding="utf-8")

required_arrays = [
    "g_ExtendedMouseMenuItems", "g_ExtendedControllerMenuItems",
    "g_ExtendedStickMenuItems", "g_TurnBoostMenuItems",
    "g_ExtendedVideoMenuItems", "g_ExtendedAudioMenuItems",
    "g_ExtendedGameMenuItems", "g_ExtendedGameCrosshairColourMenuItems",
    "g_ExtendedDabsModPlayerMenuItems", "g_ExtendedDabsModCameraMenuItems",
    "g_ExtendedDabsModDisplayMenuItems", "g_ExtendedDabsModMissionMenuItems",
    "g_ExtendedDabsModPostFxMenuItems",
]
for name in required_arrays:
    start = opt.find(f"struct menuitem {name}[] = {{")
    assert start >= 0, name
    end = opt.find("\n};", start)
    assert end >= 0, name
    body = opt[start:end]
    assert "Restore Defaults\\n" in body, f"{name}: reset missing"

assert "Restore All Settings...\\n" in opt
assert "g_RestoreAllSettingsDialog" in opt
assert "menuhandlerRestoreAllConfirm" in opt
assert "L_OPTIONS_385" in opt and "L_OPTIONS_386" in opt
assert 'configResetPrefix("Video.PostFx")' in opt
assert "postFxApply();" in opt
assert "androidControlsRestoreDefaults();" in opt
assert "Restore Defaults\\n" in android
for key in ("TurnBoost", "TurnBoostRamp", "TurnBoostThreshold", "TurnBoostRelease", "TurnBoostAimMode"):
    assert f'"{key}"' in opt
assert "* 3.00f * eased" in move, "4x sustained Turn Boost regression"
assert "Restore Defaults\n" not in opt.replace("Restore Defaults\\n", "")
print("restore defaults: generated menu/reset integration verified")

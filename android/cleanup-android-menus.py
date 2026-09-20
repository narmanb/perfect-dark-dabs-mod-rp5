#!/usr/bin/env python3
"""Android-only menu cleanup.

The desktop fork keeps its recorder/updater source. Android hides video recording,
keeps Screenshot reachable from Mods: Display, and hard-disables the desktop
self-updater so this APK can never follow the desktop release channel.
"""
from pathlib import Path

def replace_once(path, old, new, label):
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"android menu cleanup: expected one {label} in {path}, found {count}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"android menu cleanup: {label}")

# Keep the recording implementation compiled, but make the Recording sibling
# unreachable on Android. This leaves restoring it later trivial.
replace_once(
    "port/src/optionsmenu.c",
    """struct menudialogdef g_ExtendedDabsModMissionMenuDialog = {
	MENUDIALOGTYPE_DEFAULT,
	(uintptr_t)"Mods: Missions",
	g_ExtendedDabsModMissionMenuItems,
	NULL,
	MENUDIALOGFLAG_LITERAL_TEXT,
	&g_ExtendedDabsModRecordingMenuDialog,
};""",
    """struct menudialogdef g_ExtendedDabsModMissionMenuDialog = {
	MENUDIALOGTYPE_DEFAULT,
	(uintptr_t)"Mods: Missions",
	g_ExtendedDabsModMissionMenuItems,
	NULL,
	MENUDIALOGFLAG_LITERAL_TEXT,
	NULL,
};""",
    "hide Mods: Recording page",
)

# The old Recording page also contained Screenshot. Preserve that non-recording
# binding by exposing it on Display beside the texture/XBLA utility bindings.
display_anchor = """	{
		MENUITEMTYPE_DROPDOWN,
		0,
		0,
		(uintptr_t)menutextModKeyBind,
		2,
		menuhandlerModKeyBind,
	},"""
display_with_screenshot = """	{
		MENUITEMTYPE_DROPDOWN,
		0,
		0,
		(uintptr_t)menutextModKeyBind,
		0,
		menuhandlerModKeyBind,
	},
""" + display_anchor
replace_once(
    "port/src/optionsmenu.c",
    display_anchor,
    display_with_screenshot,
    "move Screenshot binding to Mods: Display",
)

# Remove the desktop updater's entry point from the Android Perfect Menu.
update_row = """	{
		MENUITEMTYPE_SELECTABLE,
		0,
		MENUITEMFLAG_SELECTABLE_OPENSDIALOG | MENUITEMFLAG_BIGFONT | MENUITEMFLAG_LITERAL_TEXT,
		(uintptr_t)"Check for Updates",
		0x0000000a,
		(void *)&g_UpdateMenuDialog,
	},
"""
replace_once(
    "src/game/mainmenu.c",
    update_row,
    "",
    "hide Check for Updates",
)

# Defense in depth: even if some dormant code calls updateCheck(), Android
# reports the desktop updater unavailable. No updater source is deleted.
replace_once(
    "port/src/update.c",
    """bool updateIsAvailable(void)
{
#ifdef PD_GHOST_NET
	return true;
#else
	return false;
#endif
}""",
    """bool updateIsAvailable(void)
{
	// Android builds are distributed separately from the desktop fork.
	// Never allow this APK to follow the desktop self-update channel.
	return false;
}""",
    "disable desktop updater on Android",
)

print("android menu cleanup: complete")

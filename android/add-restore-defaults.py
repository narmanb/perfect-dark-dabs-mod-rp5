#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OPTIONS = ROOT / "port/src/optionsmenu.c"
ANDROID = ROOT / "port/src/androidcontrolsmenu.c"


def add_before_back(text: str, array: str, handler: str, label: str = "Restore Defaults\n") -> str:
    marker = f"struct menuitem {array}[] = {{"
    start = text.find(marker)
    if start < 0:
        raise SystemExit(f"restore defaults: menu array not found: {array}")
    end = text.find("\n};", start)
    if end < 0:
        raise SystemExit(f"restore defaults: menu array end not found: {array}")
    body = text[start:end]
    flag = body.rfind("MENUITEMFLAG_SELECTABLE_CLOSESDIALOG")
    if flag < 0:
        raise SystemExit(f"restore defaults: Back row not found: {array}")
    item = body.rfind("\n\t{", 0, flag)
    if item < 0:
        raise SystemExit(f"restore defaults: Back item start not found: {array}")
    pos = start + item
    row = f'''\n\t{{
\t\tMENUITEMTYPE_SELECTABLE,
\t\t0,
\t\tMENUITEMFLAG_LITERAL_TEXT,
\t\t(uintptr_t)"{label}",
\t\t0,
\t\t{handler},
\t}},
\t{{
\t\tMENUITEMTYPE_SEPARATOR,
\t\t0,
\t\t0,
\t\t0,
\t\t0,
\t\tNULL,
\t}},'''
    return text[:pos] + row + text[pos:]


text = OPTIONS.read_text()

if "menuhandlerRestoreMouseDefaults" in text:
    raise SystemExit("restore defaults: options menu already patched")

proto_anchor = "static MenuItemHandlerResult menuhandlerSelectPlayer(s32 operation, struct menuitem *item, union handlerdata *data);\n"
if text.count(proto_anchor) != 1:
    raise SystemExit(f"restore defaults: expected one prototype anchor, found {text.count(proto_anchor)}")

protos = r'''

/* Android/RP5 settings reset layer. The config registry remembers every
 * scalar's compiled default before pd.ini is loaded, so these handlers restore
 * the build's real defaults instead of maintaining a second set of numbers in
 * the menu. Content selections, saves and installed mods are intentionally not
 * part of this system. */
static MenuItemHandlerResult menuhandlerRestoreMouseDefaults(s32 operation, struct menuitem *item, union handlerdata *data);
static MenuItemHandlerResult menuhandlerRestoreControllerDefaults(s32 operation, struct menuitem *item, union handlerdata *data);
static MenuItemHandlerResult menuhandlerRestoreStickDefaults(s32 operation, struct menuitem *item, union handlerdata *data);
static MenuItemHandlerResult menuhandlerRestoreVideoDefaults(s32 operation, struct menuitem *item, union handlerdata *data);
static MenuItemHandlerResult menuhandlerRestoreAudioDefaults(s32 operation, struct menuitem *item, union handlerdata *data);
static MenuItemHandlerResult menuhandlerRestoreGameDefaults(s32 operation, struct menuitem *item, union handlerdata *data);
static MenuItemHandlerResult menuhandlerRestoreModPlayerDefaults(s32 operation, struct menuitem *item, union handlerdata *data);
static MenuItemHandlerResult menuhandlerRestoreModCameraDefaults(s32 operation, struct menuitem *item, union handlerdata *data);
static MenuItemHandlerResult menuhandlerRestoreModDisplayDefaults(s32 operation, struct menuitem *item, union handlerdata *data);
static MenuItemHandlerResult menuhandlerRestoreModMissionDefaults(s32 operation, struct menuitem *item, union handlerdata *data);
static MenuItemHandlerResult menuhandlerRestorePostFxDefaults(s32 operation, struct menuitem *item, union handlerdata *data);
static MenuItemHandlerResult menuhandlerRestoreAllSettings(s32 operation, struct menuitem *item, union handlerdata *data);
static MenuItemHandlerResult menuhandlerRestoreAllConfirm(s32 operation, struct menuitem *item, union handlerdata *data);
static struct menudialogdef g_RestoreAllSettingsDialog;
'''
text = text.replace(proto_anchor, proto_anchor + protos, 1)

menus = [
    ("g_ExtendedMouseMenuItems", "menuhandlerRestoreMouseDefaults"),
    ("g_ExtendedControllerMenuItems", "menuhandlerRestoreControllerDefaults"),
    ("g_ExtendedStickMenuItems", "menuhandlerRestoreStickDefaults"),
    ("g_ExtendedVideoMenuItems", "menuhandlerRestoreVideoDefaults"),
    ("g_ExtendedAudioMenuItems", "menuhandlerRestoreAudioDefaults"),
    ("g_ExtendedGameMenuItems", "menuhandlerRestoreGameDefaults"),
    ("g_ExtendedDabsModPlayerMenuItems", "menuhandlerRestoreModPlayerDefaults"),
    ("g_ExtendedDabsModCameraMenuItems", "menuhandlerRestoreModCameraDefaults"),
    ("g_ExtendedDabsModDisplayMenuItems", "menuhandlerRestoreModDisplayDefaults"),
    ("g_ExtendedDabsModMissionMenuItems", "menuhandlerRestoreModMissionDefaults"),
]

for array, handler in menus:
    text = add_before_back(text, array, handler)

# Post FX is generated earlier in this workflow, so this late patch can treat it
# just like a normal menu even though it is not present in the checked-in file.
text = add_before_back(text, "g_ExtendedDabsModPostFxMenuItems", "menuhandlerRestorePostFxDefaults")
text = add_before_back(text, "g_ExtendedMenuItems", "menuhandlerRestoreAllSettings", "Restore All Settings...\\n")

handlers = r'''

/* ---------------- Restore Defaults ---------------- */

static void restorePlayerConfigPointer(void *ptr)
{
	/* A few old fork options are direct globals and a few are registered config
	 * values. configResetPointer is deliberately harmless for an unregistered
	 * pointer, which lets one reset handler cover both generations of the menu. */
	configResetPointer(ptr);
}

static void restoreInputPlayerKey(s32 player, const char *name)
{
	char key[128];
	snprintf(key, sizeof(key), "Input.Player%d.%s", player + 1, name);
	configResetKey(key);
}

static MenuItemHandlerResult menuhandlerRestoreMouseDefaults(s32 operation, struct menuitem *item, union handlerdata *data)
{
	if (operation != MENUOP_SET) return 0;

	configResetKey("Input.MouseEnabled");
	configResetKey("Input.MouseLockMode");
	configResetKey("Input.MouseSpeedX");
	configResetKey("Input.MouseSpeedY");
	restorePlayerConfigPointer(&g_PlayerExtCfg[g_ExtMenuPlayer].mouseaimmode);
	restorePlayerConfigPointer(&g_PlayerExtCfg[g_ExtMenuPlayer].mouseaimspeedx);
	restorePlayerConfigPointer(&g_PlayerExtCfg[g_ExtMenuPlayer].mouseaimspeedy);
	restorePlayerConfigPointer(&g_PlayerExtCfg[0].radialmenuspeed);
	restorePlayerConfigPointer(&g_MenuMouseControl);

	/* Re-apply the lock policy after the backing values have been restored. */
	inputSetMouseLockMode(inputGetMouseLockMode());
	inputMouseEnable(inputMouseIsEnabled());
	return 0;
}

static MenuItemHandlerResult menuhandlerRestoreControllerDefaults(s32 operation, struct menuitem *item, union handlerdata *data)
{
	if (operation != MENUOP_SET) return 0;

	restoreInputPlayerKey(g_ExtMenuPlayer, "RumbleScale");
	restoreInputPlayerKey(g_ExtMenuPlayer, "StickCButtons");
	restoreInputPlayerKey(g_ExtMenuPlayer, "CancelCButtons");
	restoreInputPlayerKey(g_ExtMenuPlayer, "SwapSticks");

	/* SwapSticks has a derived axis map which is not itself serialized. */
	inputControllerSetSticksSwapped(g_ExtMenuPlayer,
			inputControllerGetSticksSwapped(g_ExtMenuPlayer));
	return 0;
}

static MenuItemHandlerResult menuhandlerRestoreStickDefaults(s32 operation, struct menuitem *item, union handlerdata *data)
{
	static const char *keys[] = {
		"LStickDeadzoneX", "LStickDeadzoneY", "RStickDeadzoneX", "RStickDeadzoneY",
		"LStickScaleX", "LStickScaleY", "RStickScaleX", "RStickScaleY",
		"RStickCurve", "RStickOuterThreshold", "RStickAcceleration", "RStickSmoothing",
		"TurnBoost", "TurnBoostRamp", "TurnBoostThreshold", "TurnBoostRelease", "TurnBoostAimMode",
	};
	if (operation != MENUOP_SET) return 0;

	for (u32 i = 0; i < ARRAYCOUNT(keys); ++i) {
		restoreInputPlayerKey(g_ExtMenuPlayer, keys[i]);
	}
	return 0;
}

static void restoreVideoConfigKeys(void)
{
	static const char *keys[] = {
		"Video.DefaultFullscreen", "Video.DefaultMaximize", "Video.DefaultWidth", "Video.DefaultHeight",
		"Video.ExclusiveFullscreen", "Video.CenterWindow", "Video.AllowHiDpi", "Video.VSync",
		"Video.FramebufferEffects", "Video.FramerateLimit", "Video.DisplayFPS", "Video.DisplayFPSInterval",
		"Video.MSAA", "Video.TextureFilter", "Video.TextureFilter2D", "Video.DetailTextures",
		"Video.MipmapFilter", "Video.AnisotropicFilter", "Video.GlareBrightness", "Video.OverexposureScale",
	};
	for (u32 i = 0; i < ARRAYCOUNT(keys); ++i) configResetKey(keys[i]);
}

static MenuItemHandlerResult menuhandlerRestoreVideoDefaults(s32 operation, struct menuitem *item, union handlerdata *data)
{
	union handlerdata hd = { 0 };
	if (operation != MENUOP_SET) return 0;

	restoreVideoConfigKeys();
	restorePlayerConfigPointer(&g_TickRateDiv);
	restorePlayerConfigPointer(&g_HudCenter);
	restorePlayerConfigPointer(&g_BgunGeMuzzleFlashes);
	restorePlayerConfigPointer(&g_ViShakeIntensityMult);

	/* The renderer has live state as well as backing config values. These are
	 * the Android build defaults from video.c, applied immediately. */
	videoSetFullscreen(0);
	videoSetFullscreenMode(0);
	videoSetCenterWindow(0);
	videoSetMSAA(1);
	videoSetVsync(1);
	videoSetFramerateLimit(0);
	videoSetDisplayFPS(0);
	videoSetTextureFilter(FILTER_LINEAR);
	videoSetTextureFilter2D(1);
	videoSetAnisotropicFilter(4);
	videoSetDetailTextures(0);
	videoSetGlareBrightness(1.f);
	videoSetOverexposureScale(1.f);

	/* HUD centering also owns two derived alignment masks. */
	hd.dropdown.value = g_HudCenter;
	menuhandlerCenterHUD(MENUOP_SET, NULL, &hd);
	return 0;
}

static MenuItemHandlerResult menuhandlerRestoreAudioDefaults(s32 operation, struct menuitem *item, union handlerdata *data)
{
	if (operation == MENUOP_SET) restorePlayerConfigPointer(&g_MusicDisableMpDeath);
	return 0;
}

static MenuItemHandlerResult menuhandlerRestoreGameDefaults(s32 operation, struct menuitem *item, union handlerdata *data)
{
	if (operation != MENUOP_SET) return 0;

	restorePlayerConfigPointer(&g_PlayerExtCfg[g_ExtMenuPlayer].crouchmode);
	restorePlayerConfigPointer(&g_PlayerExtCfg[g_ExtMenuPlayer].fovy);
	restorePlayerConfigPointer(&g_PlayerExtCfg[g_ExtMenuPlayer].crosshairsway);
	restorePlayerConfigPointer(&g_PlayerExtCfg[g_ExtMenuPlayer].crosshairedgeboundary);
	restorePlayerConfigPointer(&g_PlayerExtCfg[g_ExtMenuPlayer].crosshairsize);
	restorePlayerConfigPointer(&g_PlayerExtCfg[g_ExtMenuPlayer].crosshaircolour);
	restorePlayerConfigPointer(&g_PlayerExtCfg[g_ExtMenuPlayer].crosshairhealth);
	restorePlayerConfigPointer(&g_PlayerExtCfg[g_ExtMenuPlayer].usereloads);
	return 0;
}

static MenuItemHandlerResult menuhandlerRestoreModPlayerDefaults(s32 operation, struct menuitem *item, union handlerdata *data)
{
	if (operation != MENUOP_SET) return 0;
	g_ModOptions.jumpheight = 0;
	g_ModOptions.jumpwho = MODWHO_EVERYONE;
	g_ModOptions.roll = MODROLL_OFF;
	g_ModOptions.melee = false;
	g_ModOptions.flinch = false;
	g_ModOptions.explosionshake = false;
	g_ModOptions.tranqeffect = true;
	g_ModOptions.spawnweapon = SPAWNWEAPON_OFF;
	g_ModOptions.spawnweaponwho = MODWHO_EVERYONE;
	g_ModOptions.akimbo = MODAKIMBO_OFF;
	g_ModOptions.akimbotriggers = false;
	return 0;
}

static MenuItemHandlerResult menuhandlerRestoreModCameraDefaults(s32 operation, struct menuitem *item, union handlerdata *data)
{
	if (operation != MENUOP_SET) return 0;
	g_ModOptions.cameratilt = MODTILT_OFF;
	g_ModOptions.tiltinvert = false;
	g_ModOptions.tiltforward = false;
	g_ModOptions.gunsway = true;
	g_ModOptions.codaiming = false;
	g_ModOptions.codaimlock = true;
	g_ModOptions.camdist = THIRDPERSON_CAMDIST;
	g_ModOptions.camclearance = THIRDPERSON_CAMCLEARANCE;
	g_ModOptions.cammindist = THIRDPERSON_CAMMINDIST;
	g_ModOptions.camside = THIRDPERSON_CAMSIDE;
	g_ModOptions.camfwd = THIRDPERSON_CAMFWD;
	g_ModOptions.camheight = THIRDPERSON_CAMHEIGHT;
	g_ModOptions.camtether = MODTETHER_OFF;
	g_ModOptions.camturnspeed = MODTURN_DEFAULT;
	restorePlayerConfigPointer(&g_ModSpectateSpeed);
	return 0;
}

static MenuItemHandlerResult menuhandlerRestoreModDisplayDefaults(s32 operation, struct menuitem *item, union handlerdata *data)
{
	if (operation != MENUOP_SET) return 0;
	g_ModOptions.cleantext = false;
	g_ModOptions.smoothtext = false;
	g_ModOptions.modellod = true;
	g_ModOptions.enhancetextures = MODENHANCE_OFF;
	g_ModOptions.vividcolours = MODVIVID_OFF;
	g_ModOptions.blacklevel = MODBLACK_OFF;
	g_ModOptions.xblareflectcutoff = true;
	configResetKey("Video.StretchedEdges");
	videoSetCleanTextOutlines(0);
	videoSetTextureEnhance(1, 1);
	videoSetVividColours(1.f, 1.f);
	videoSetBlackLevel(0.f);
	videoSetClampedEdgeMode(CLAMPED_EDGE_STRETCH);
	return 0;
}

static MenuItemHandlerResult menuhandlerRestoreModMissionDefaults(s32 operation, struct menuitem *item, union handlerdata *data)
{
	if (operation != MENUOP_SET) return 0;
	g_ModOptions.missionrespawn = false;
	g_ModOptions.missionlives = MODLIVES_UNLIMITED;
	g_ModOptions.guardsalerted = MODALARM_OFF;
	g_ModOptions.alertedguards = MODALARM_GUARDS_DEFAULT;
	g_ModOptions.guardspawnspeed = MODALARM_SPEED_DEFAULT;
	g_ModOptions.guardweapons = MODALARM_WEAPONS_STAGE;
	g_ModOptions.alarmsound = true;
	g_ModOptions.bodies = MODBODIES_OFF;
	g_ModOptions.bodytime = MODBODYTIME_OFF;
	g_ModOptions.bodiesdrawn = 64;
	restorePlayerConfigPointer(&g_ModGhostMode);
	restorePlayerConfigPointer(&g_ModGhostPick);
	restorePlayerConfigPointer(&g_ModGhostAlpha);
	restorePlayerConfigPointer(&g_ModGhostSplits);
	return 0;
}

static MenuItemHandlerResult menuhandlerRestorePostFxDefaults(s32 operation, struct menuitem *item, union handlerdata *data)
{
	if (operation != MENUOP_SET) return 0;
	configResetPrefix("Video.PostFx");
	postFxApply();
	return 0;
}

static MenuItemHandlerResult menuhandlerRestoreAllConfirm(s32 operation, struct menuitem *item, union handlerdata *data)
{
	if (operation != MENUOP_SET) return 0;

	/* Player-independent pages. */
	menuhandlerRestoreVideoDefaults(MENUOP_SET, NULL, NULL);
	menuhandlerRestoreAudioDefaults(MENUOP_SET, NULL, NULL);
	menuhandlerRestoreModPlayerDefaults(MENUOP_SET, NULL, NULL);
	menuhandlerRestoreModCameraDefaults(MENUOP_SET, NULL, NULL);
	menuhandlerRestoreModDisplayDefaults(MENUOP_SET, NULL, NULL);
	menuhandlerRestoreModMissionDefaults(MENUOP_SET, NULL, NULL);
	menuhandlerRestorePostFxDefaults(MENUOP_SET, NULL, NULL);

	/* Per-player control/game settings and binds. Keep ControllerIndex intact so
	 * restoring settings cannot strand the player without an assigned RP5 pad. */
	for (s32 p = 0; p < INPUT_MAX_CONTROLLERS; ++p) {
		g_ExtMenuPlayer = p;
		menuhandlerRestoreControllerDefaults(MENUOP_SET, NULL, NULL);
		menuhandlerRestoreStickDefaults(MENUOP_SET, NULL, NULL);
		menuhandlerRestoreGameDefaults(MENUOP_SET, NULL, NULL);
		inputSetDefaultKeyBinds(p, false);
	}
	g_ExtMenuPlayer = 0;
	menuhandlerRestoreMouseDefaults(MENUOP_SET, NULL, NULL);

#ifdef ANDROID
	androidControlsRestoreDefaults();
#endif

	return 0;
}

static MenuItemHandlerResult menuhandlerRestoreAllSettings(s32 operation, struct menuitem *item, union handlerdata *data)
{
	if (operation == MENUOP_SET) menuPushDialog(&g_RestoreAllSettingsDialog);
	return 0;
}

static struct menuitem g_RestoreAllSettingsItems[] = {
	{
		MENUITEMTYPE_LABEL,
		0,
		MENUITEMFLAG_LITERAL_TEXT | MENUITEMFLAG_LESSLEFTPADDING,
		(uintptr_t)"Restore all settings and control bindings to their defaults?\n",
		0,
		NULL,
	},
	{
		MENUITEMTYPE_LABEL,
		0,
		MENUITEMFLAG_LITERAL_TEXT | MENUITEMFLAG_LESSLEFTPADDING,
		(uintptr_t)"Saves, profiles, ROM data and installed mods will not be removed.\n",
		0,
		NULL,
	},
	{
		MENUITEMTYPE_SEPARATOR,
		0, 0, 0, 0, NULL,
	},
	{
		MENUITEMTYPE_SELECTABLE,
		0,
		MENUITEMFLAG_SELECTABLE_CLOSESDIALOG | MENUITEMFLAG_SELECTABLE_CENTRE,
		L_OPTIONS_385, /* No */
		0,
		NULL,
	},
	{
		MENUITEMTYPE_SELECTABLE,
		0,
		MENUITEMFLAG_SELECTABLE_CLOSESDIALOG | MENUITEMFLAG_SELECTABLE_CENTRE,
		L_OPTIONS_386, /* Yes */
		0,
		menuhandlerRestoreAllConfirm,
	},
	{ MENUITEMTYPE_END },
};

static struct menudialogdef g_RestoreAllSettingsDialog = {
	MENUDIALOGTYPE_DANGER,
	(uintptr_t)"Restore All Settings",
	g_RestoreAllSettingsItems,
	NULL,
	MENUDIALOGFLAG_LITERAL_TEXT,
	NULL,
};
'''

text += handlers
OPTIONS.write_text(text)

# Android's touch page owns settings not visible to optionsmenu.c. Give it its
# own page reset and an exported helper for the global reset.
atext = ANDROID.read_text()
if "androidControlsRestoreDefaults" in atext:
    raise SystemExit("restore defaults: Android controls already patched")

func_anchor = "s32 androidControlsGetGameplayTouchEnabled(void) { return g_AndroidGameplayTouchEnabled; }\n"
if atext.count(func_anchor) != 1:
    raise SystemExit(f"restore defaults: Android helper anchor count {atext.count(func_anchor)}")

android_helpers = r'''
void androidControlsRestoreDefaults(void)
{
	configResetPointer(&g_AndroidGameplayTouchEnabled);
	configResetPointer(&g_AndroidGameplayTouchOpacity);
	configResetPointer(&g_AndroidTouchLookMode);
	configResetPointer(&g_AndroidTouchLookSensitivityX);
	configResetPointer(&g_AndroidTouchLookSensitivityY);
}

static MenuItemHandlerResult menuhandlerAndroidRestoreDefaults(s32 operation, struct menuitem *item, union handlerdata *data)
{
	if (operation == MENUOP_SET) androidControlsRestoreDefaults();
	return 0;
}

'''
atext = atext.replace(func_anchor, android_helpers + func_anchor, 1)
atext = add_before_back(atext, "g_AndroidControllerSettingsMenuItems", "menuhandlerAndroidRestoreDefaults")
ANDROID.write_text(atext)

# optionsmenu.c calls this only in Android builds.
print("restore defaults: added page resets, Android reset, and confirmed global reset")

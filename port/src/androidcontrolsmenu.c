#ifdef ANDROID

#include <stdio.h>
#include <PR/ultratypes.h>

#include "platform.h"
#include "types.h"
#include "input.h"
#include "config.h"

/* These are defined by optionsmenu.c. The selected player's number is already
 * reflected in the mutable dialog title ("Player 1 Controller Options"), so
 * the Android-only submenu can follow the same player without exposing the
 * file's private g_ExtMenuPlayer variable. */
extern struct menuitem g_ExtendedControllerMenuItems[];
extern struct menudialogdef g_ExtendedControllerMenuDialog;
extern struct menudialogdef g_ExtendedStickMenuDialog;

static s32 g_AndroidGameplayTouchEnabled = 1;
static f32 g_AndroidGameplayTouchOpacity = 0.46f;
static s32 g_AndroidTouchLookMode = 0;
static f32 g_AndroidTrackpadSensitivityX = 1.0f;
static f32 g_AndroidTrackpadSensitivityY = 1.0f;

static s32 androidControlsCurrentPlayer(void)
{
	const char *title = (const char *)g_ExtendedControllerMenuDialog.title;

	if (title && title[7] >= '1' && title[7] <= '4') {
		return title[7] - '1';
	}

	return 0;
}

/* In the PC control style the first logical stick is look/aim and the second
 * logical stick is movement. Swap Sticks maps that first logical stick to the
 * physical right stick, which is the default modern-controller layout. */
static s32 androidControlsLookStick(s32 player)
{
	return inputControllerGetSticksSwapped(player) ? 1 : 0;
}

static f32 androidControlsGetPlayerLookScale(s32 player, s32 axis)
{
	return inputControllerGetAxisScale(player, androidControlsLookStick(player), axis);
}

static void androidControlsSetPlayerLookScale(s32 player, s32 axis, f32 value)
{
	inputControllerSetAxisScale(player, androidControlsLookStick(player), axis, value);
}

static MenuItemHandlerResult menuhandlerAndroidGameplayTouchEnabled(s32 operation, struct menuitem *item, union handlerdata *data)
{
	(void)item;
	switch (operation) {
	case MENUOP_CHECKHIDDEN: return androidControlsCurrentPlayer() != 0;
	case MENUOP_GET: return g_AndroidGameplayTouchEnabled;
	case MENUOP_SET: g_AndroidGameplayTouchEnabled = data->checkbox.value ? 1 : 0; break;
	}
	return 0;
}

static MenuItemHandlerResult menuhandlerAndroidGameplayTouchOpacity(s32 operation, struct menuitem *item, union handlerdata *data)
{
	(void)item;
	switch (operation) {
	case MENUOP_CHECKHIDDEN: return androidControlsCurrentPlayer() != 0;
	case MENUOP_GETSLIDER: data->slider.value = (s32)(g_AndroidGameplayTouchOpacity * 100.0f + 0.5f); break;
	case MENUOP_SET: g_AndroidGameplayTouchOpacity = (f32)data->slider.value / 100.0f; break;
	case MENUOP_GETSLIDERLABEL: sprintf(data->slider.label, "%d%%", data->slider.value); break;
	}
	return 0;
}

static MenuItemHandlerResult menuhandlerAndroidTouchLookMode(s32 operation, struct menuitem *item, union handlerdata *data)
{
	static const char *opts[] = {
		"Analog Stick",
		"Trackpad",
	};

	(void)item;

	switch (operation) {
	case MENUOP_CHECKHIDDEN:
		return androidControlsCurrentPlayer() != 0;
	case MENUOP_GETOPTIONCOUNT:
		data->dropdown.value = 2;
		break;
	case MENUOP_GETOPTIONTEXT:
		return (intptr_t)opts[data->dropdown.value ? 1 : 0];
	case MENUOP_SET:
		if (androidControlsCurrentPlayer() == 0) {
			g_AndroidTouchLookMode = data->dropdown.value ? 1 : 0;
		}
		break;
	case MENUOP_GETSELECTEDINDEX:
		data->dropdown.value = g_AndroidTouchLookMode;
		break;
	}

	return 0;
}

static struct menuitem g_AndroidControllerSettingsMenuItems[];

static MenuItemHandlerResult menuhandlerAndroidLookSensitivity(s32 operation, struct menuitem *item, union handlerdata *data)
{
	const s32 player = androidControlsCurrentPlayer();
	const s32 axis = item - (g_AndroidControllerSettingsMenuItems + 3);
	f32 value;

	if (axis < 0 || axis > 1) {
		return 0;
	}

	switch (operation) {
	case MENUOP_GETSLIDER:
		value = androidControlsGetPlayerLookScale(player, axis);
		if (value < 0.0f) value = 0.0f;
		if (value > 4.0f) value = 4.0f;
		data->slider.value = value * 10.0f + 0.5f;
		break;
	case MENUOP_SET:
		androidControlsSetPlayerLookScale(player, axis, (f32)data->slider.value / 10.0f);
		break;
	case MENUOP_GETSLIDERLABEL:
		sprintf(data->slider.label, "%.1fx", (f32)data->slider.value / 10.0f);
		break;
	}

	return 0;
}

static MenuItemHandlerResult menuhandlerAndroidTrackpadSensitivity(s32 operation, struct menuitem *item, union handlerdata *data)
{
	const s32 axis = item - (g_AndroidControllerSettingsMenuItems + 5);
	f32 *value;

	if (axis < 0 || axis > 1) {
		return 0;
	}

	value = axis ? &g_AndroidTrackpadSensitivityY : &g_AndroidTrackpadSensitivityX;

	switch (operation) {
	case MENUOP_CHECKHIDDEN:
		return androidControlsCurrentPlayer() != 0;
	case MENUOP_GETSLIDER:
		data->slider.value = *value * 10.0f + 0.5f;
		break;
	case MENUOP_SET:
		*value = (f32)data->slider.value / 10.0f;
		break;
	case MENUOP_GETSLIDERLABEL:
		sprintf(data->slider.label, "%.1fx", (f32)data->slider.value / 10.0f);
		break;
	}

	return 0;
}

static struct menuitem g_AndroidControllerSettingsMenuItems[] = {
	{ MENUITEMTYPE_CHECKBOX, 0, MENUITEMFLAG_LITERAL_TEXT, (uintptr_t)"Gameplay Touch Controls", 0, menuhandlerAndroidGameplayTouchEnabled },
	{ MENUITEMTYPE_SLIDER, 0, MENUITEMFLAG_LITERAL_TEXT | MENUITEMFLAG_SLIDER_WIDE, (uintptr_t)"Gameplay Touch Opacity", 100, menuhandlerAndroidGameplayTouchOpacity },
	{
		MENUITEMTYPE_DROPDOWN,
		0,
		MENUITEMFLAG_LITERAL_TEXT,
		(uintptr_t)"Touch Look Mode",
		0,
		menuhandlerAndroidTouchLookMode,
	},
	{
		MENUITEMTYPE_SLIDER,
		0,
		MENUITEMFLAG_LITERAL_TEXT | MENUITEMFLAG_SLIDER_WIDE,
		(uintptr_t)"Look Sensitivity X",
		40,
		menuhandlerAndroidLookSensitivity,
	},
	{
		MENUITEMTYPE_SLIDER,
		0,
		MENUITEMFLAG_LITERAL_TEXT | MENUITEMFLAG_SLIDER_WIDE,
		(uintptr_t)"Look Sensitivity Y",
		40,
		menuhandlerAndroidLookSensitivity,
	},
	{
		MENUITEMTYPE_SLIDER,
		0,
		MENUITEMFLAG_LITERAL_TEXT | MENUITEMFLAG_SLIDER_WIDE,
		(uintptr_t)"Trackpad Sensitivity X",
		40,
		menuhandlerAndroidTrackpadSensitivity,
	},
	{
		MENUITEMTYPE_SLIDER,
		0,
		MENUITEMFLAG_LITERAL_TEXT | MENUITEMFLAG_SLIDER_WIDE,
		(uintptr_t)"Trackpad Sensitivity Y",
		40,
		menuhandlerAndroidTrackpadSensitivity,
	},
	{
		MENUITEMTYPE_SEPARATOR,
		0,
		0,
		0,
		0,
		NULL,
	},
	{
		MENUITEMTYPE_SELECTABLE,
		0,
		MENUITEMFLAG_SELECTABLE_OPENSDIALOG | MENUITEMFLAG_LITERAL_TEXT,
		(uintptr_t)"Advanced Stick Calibration...\n",
		0,
		(void *)&g_ExtendedStickMenuDialog,
	},
	{
		MENUITEMTYPE_SEPARATOR,
		0,
		0,
		0,
		0,
		NULL,
	},
	{
		MENUITEMTYPE_SELECTABLE,
		0,
		MENUITEMFLAG_SELECTABLE_CLOSESDIALOG | MENUITEMFLAG_LITERAL_TEXT,
		(uintptr_t)"Back\n",
		0,
		NULL,
	},
	{ MENUITEMTYPE_END },
};

static struct menudialogdef g_AndroidControllerSettingsMenuDialog = {
	MENUDIALOGTYPE_DEFAULT,
	(uintptr_t)"Look & Stick Settings",
	g_AndroidControllerSettingsMenuItems,
	NULL,
	MENUDIALOGFLAG_LITERAL_TEXT,
	NULL,
};

s32 androidControlsGetGameplayTouchEnabled(void) { return g_AndroidGameplayTouchEnabled; }
f32 androidControlsGetGameplayTouchOpacity(void) { return g_AndroidGameplayTouchOpacity; }

s32 androidControlsGetTouchLookMode(void)
{
	return g_AndroidTouchLookMode;
}

f32 androidControlsGetTouchLookSensitivityX(void)
{
	return androidControlsGetPlayerLookScale(0, 0);
}

f32 androidControlsGetTouchLookSensitivityY(void)
{
	return androidControlsGetPlayerLookScale(0, 1);
}

f32 androidControlsGetTrackpadSensitivityX(void)
{
	return g_AndroidTrackpadSensitivityX;
}

f32 androidControlsGetTrackpadSensitivityY(void)
{
	return g_AndroidTrackpadSensitivityY;
}

PD_CONSTRUCTOR static void androidControlsConfigInit(void)
{
	configRegisterInt("Input.AndroidGameplayTouchEnabled", &g_AndroidGameplayTouchEnabled, 0, 1);
	configRegisterFloat("Input.AndroidGameplayTouchOpacity", &g_AndroidGameplayTouchOpacity, 0.0f, 1.0f);
	configRegisterInt("Input.AndroidTouchLookMode", &g_AndroidTouchLookMode, 0, 1);
	configRegisterFloat("Input.AndroidTrackpadSensitivityX", &g_AndroidTrackpadSensitivityX, 0.0f, 4.0f);
	configRegisterFloat("Input.AndroidTrackpadSensitivityY", &g_AndroidTrackpadSensitivityY, 0.0f, 4.0f);

	/* Replace the Android build's existing Stick Settings door with a page that
	 * exposes the useful look controls first, while keeping every original axis
	 * scale/deadzone option one level deeper under Advanced Stick Calibration. */
	g_ExtendedControllerMenuItems[3].param2 = (uintptr_t)"Look & Stick Settings...\n";
	g_ExtendedControllerMenuItems[3].handler =
		(uintptr_t (*)(s32, struct menuitem *, union handlerdata *))&g_AndroidControllerSettingsMenuDialog;
}

#endif

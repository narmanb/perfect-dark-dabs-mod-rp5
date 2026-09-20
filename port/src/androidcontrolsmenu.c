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
static f32 g_AndroidTouchLookSensitivityX = 1.0f;
static f32 g_AndroidTouchLookSensitivityY = 1.0f;

static s32 androidControlsCurrentPlayer(void)
{
	const char *title = (const char *)g_ExtendedControllerMenuDialog.title;

	if (title && title[7] >= '1' && title[7] <= '4') {
		return title[7] - '1';
	}

	return 0;
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

/* One touch-only sensitivity pair drives whichever touchscreen look mode is
 * selected. It deliberately does not touch controller axis scale; the physical
 * RP5 right stick is tuned only in Advanced Stick Calibration. */
static MenuItemHandlerResult menuhandlerAndroidTouchLookSensitivity(s32 operation, struct menuitem *item, union handlerdata *data)
{
	const s32 axis = item - (g_AndroidControllerSettingsMenuItems + 3);
	f32 *value;

	if (axis < 0 || axis > 1) {
		return 0;
	}

	value = axis ? &g_AndroidTouchLookSensitivityY : &g_AndroidTouchLookSensitivityX;

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
		(uintptr_t)"Touch Look Sensitivity X",
		40,
		menuhandlerAndroidTouchLookSensitivity,
	},
	{
		MENUITEMTYPE_SLIDER,
		0,
		MENUITEMFLAG_LITERAL_TEXT | MENUITEMFLAG_SLIDER_WIDE,
		(uintptr_t)"Touch Look Sensitivity Y",
		40,
		menuhandlerAndroidTouchLookSensitivity,
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
	return g_AndroidTouchLookSensitivityX;
}

f32 androidControlsGetTouchLookSensitivityY(void)
{
	return g_AndroidTouchLookSensitivityY;
}

/* Keep the existing JNI names used by TouchControls.java. Both analog-stick
 * and trackpad paths intentionally receive the same touch-only sensitivity. */
f32 androidControlsGetTrackpadSensitivityX(void)
{
	return g_AndroidTouchLookSensitivityX;
}

f32 androidControlsGetTrackpadSensitivityY(void)
{
	return g_AndroidTouchLookSensitivityY;
}

PD_CONSTRUCTOR static void androidControlsConfigInit(void)
{
	configRegisterInt("Input.AndroidGameplayTouchEnabled", &g_AndroidGameplayTouchEnabled, 0, 1);
	configRegisterFloat("Input.AndroidGameplayTouchOpacity", &g_AndroidGameplayTouchOpacity, 0.0f, 1.0f);
	configRegisterInt("Input.AndroidTouchLookMode", &g_AndroidTouchLookMode, 0, 1);

	/* Retain the old Trackpad config keys so an update-in-place preserves the
	 * user's previous touch sensitivity, but the values now apply to both touch
	 * look modes and never to the physical controller. */
	configRegisterFloat("Input.AndroidTrackpadSensitivityX", &g_AndroidTouchLookSensitivityX, 0.0f, 4.0f);
	configRegisterFloat("Input.AndroidTrackpadSensitivityY", &g_AndroidTouchLookSensitivityY, 0.0f, 4.0f);

	/* Replace the Android build's existing Stick Settings door with a page that
	 * exposes touch-only controls first, while keeping physical stick calibration
	 * and right-stick response tuning one level deeper. */
	g_ExtendedControllerMenuItems[3].param2 = (uintptr_t)"Look & Stick Settings...\n";
	g_ExtendedControllerMenuItems[3].handler =
		(uintptr_t (*)(s32, struct menuitem *, union handlerdata *))&g_AndroidControllerSettingsMenuDialog;
}

#endif

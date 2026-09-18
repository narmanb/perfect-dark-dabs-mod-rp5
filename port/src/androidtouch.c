#ifdef ANDROID

#include <jni.h>

/* bss.h includes ultra64 before constants.h. Keep that order: constants.h
 * defines osSyncPrintf away for game code, while ultra64 still declares it. */
#include "bss.h"
#include "input.h"

/* Android-only controller/touch options live in androidcontrolsmenu.c. */
s32 androidControlsGetTouchLookMode(void);
f32 androidControlsGetTouchLookSensitivityX(void);
f32 androidControlsGetTouchLookSensitivityY(void);
f32 androidControlsGetTrackpadSensitivityX(void);
f32 androidControlsGetTrackpadSensitivityY(void);

/* menu.c owns this PC keyboard-mode marker. Android uses the game's own
 * on-screen keyboard, so Java may clear this mode if the system IME is opened. */
extern s32 g_MenuKeyboardPlayer;

/*
 * Tell the Java touch layer when it is safe to replace SDL's normal finger
 * events with virtual gameplay controls. Menus must keep SDL touch input so
 * they remain directly tappable, while missions get the Android overlay.
 */
JNIEXPORT jboolean JNICALL
Java_com_perfectdark_port_MainActivity_nativeGameplayTouchActive(JNIEnv *env, jobject thiz)
{
	(void)env;
	(void)thiz;

	/* The title stage contains the front end, file select and main menus. */
	if (g_Vars.stagenum == STAGE_TITLE) {
		return JNI_FALSE;
	}

	/* Any normal or pause dialog should use the game's existing mouse/touch UI. */
	if (g_MenuData.count > 0) {
		return JNI_FALSE;
	}

	/* Cutscenes should keep ordinary SDL touch/button behaviour as well. */
	if (g_Vars.in_cutscene) {
		return JNI_FALSE;
	}

	/* Avoid enabling the overlay during stage setup before gameplay has ticked. */
	if (g_Vars.lvframenum <= 0) {
		return JNI_FALSE;
	}

	return JNI_TRUE;
}

JNIEXPORT jboolean JNICALL
Java_com_perfectdark_port_MainActivity_nativeTextInputActive(JNIEnv *env, jobject thiz)
{
	(void)env;
	(void)thiz;
	return (inputIsTextInputActive() || g_MenuKeyboardPlayer >= 0) ? JNI_TRUE : JNI_FALSE;
}

JNIEXPORT void JNICALL
Java_com_perfectdark_port_MainActivity_nativeCancelTextInput(JNIEnv *env, jobject thiz)
{
	(void)env;
	(void)thiz;

	if (inputIsTextInputActive()) {
		inputStopTextInput();
	}

	g_MenuKeyboardPlayer = -1;
}

JNIEXPORT jint JNICALL
Java_com_perfectdark_port_TouchControls_nativeTouchLookMode(JNIEnv *env, jclass clazz)
{
	(void)env;
	(void)clazz;
	return (jint)androidControlsGetTouchLookMode();
}

JNIEXPORT jfloat JNICALL
Java_com_perfectdark_port_TouchControls_nativeTouchLookSensitivityX(JNIEnv *env, jclass clazz)
{
	(void)env;
	(void)clazz;
	return (jfloat)androidControlsGetTouchLookSensitivityX();
}

JNIEXPORT jfloat JNICALL
Java_com_perfectdark_port_TouchControls_nativeTouchLookSensitivityY(JNIEnv *env, jclass clazz)
{
	(void)env;
	(void)clazz;
	return (jfloat)androidControlsGetTouchLookSensitivityY();
}

JNIEXPORT jfloat JNICALL
Java_com_perfectdark_port_TouchControls_nativeTrackpadSensitivityX(JNIEnv *env, jclass clazz)
{
	(void)env;
	(void)clazz;
	return (jfloat)androidControlsGetTrackpadSensitivityX();
}

JNIEXPORT jfloat JNICALL
Java_com_perfectdark_port_TouchControls_nativeTrackpadSensitivityY(JNIEnv *env, jclass clazz)
{
	(void)env;
	(void)clazz;
	return (jfloat)androidControlsGetTrackpadSensitivityY();
}

#endif

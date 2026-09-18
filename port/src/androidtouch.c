#ifdef ANDROID

#include <jni.h>

/* bss.h includes ultra64 before constants.h. Keep that order: constants.h
 * defines osSyncPrintf away for game code, while ultra64 still declares it. */
#include "bss.h"

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

#endif

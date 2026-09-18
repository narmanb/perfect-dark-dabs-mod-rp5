package com.perfectdark.port;

import org.libsdl.app.SDLActivity;

import android.content.Context;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.KeyEvent;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.view.inputmethod.InputMethodManager;

import java.io.File;

public class MainActivity extends SDLActivity {
    private TouchControls touchControls;
    private final Handler touchUiHandler = new Handler(Looper.getMainLooper());

    private final Runnable touchUiPoll = new Runnable() {
        @Override
        public void run() {
            refreshTouchMode();
            touchUiHandler.postDelayed(this, 250L);
        }
    };

    static {
        System.loadLibrary("SDL2");
        System.loadLibrary("pd");
    }

    /**
     * Dab's filesystem defaults its base directory to $E/data, where $E is the
     * native executable directory. On Android that resolves through app_process
     * rather than this application's scoped files directory. Pass the exact
     * directory used by LauncherActivity so the native game opens the same ROM
     * that the launcher just copied and verified.
     */
    @Override
    protected String[] getArguments() {
        File dataDir = new File(getExternalFilesDir(null), "data");
        String path = dataDir.getAbsolutePath();
        android.util.Log.i("PerfectDark", "Native basedir/savedir: " + path);
        return new String[] { "--basedir", path, "--savedir", path };
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        android.util.Log.i("PerfectDark", "MainActivity onCreate start");

        super.onCreate(savedInstanceState);
        android.util.Log.i("PerfectDark", "MainActivity super.onCreate complete");

        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);

        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.P) {
            getWindow().getAttributes().layoutInDisplayCutoutMode =
                    WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES;
        }

        hideSystemUI();
        installTouchControls();

        // No external storage permissions needed with SAF + app-scoped storage.
        initializeGame();
        startTouchUiPoll();
        android.util.Log.i("PerfectDark", "MainActivity onCreate complete");
    }

    private void hideSystemUI() {
        View decorView = getWindow().getDecorView();
        int uiOptions = View.SYSTEM_UI_FLAG_FULLSCREEN
                | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                | View.SYSTEM_UI_FLAG_LAYOUT_STABLE;
        decorView.setSystemUiVisibility(uiOptions);
    }

    /**
     * Gameplay gets our Android control layer, while menus keep SDL's original
     * finger events. That preserves direct menu tapping without bringing back
     * the old problem where every gameplay touch also acted as mouse-fire.
     */
    private void installTouchControls() {
        if (touchControls == null) {
            touchControls = new TouchControls(this);
            // The app boots into title/front-end UI, so do not flash gameplay
            // controls before the native game has established its state.
            touchControls.setGameplayActive(false);
        }

        if (mLayout != null && touchControls.getOverlayView().getParent() == null) {
            mLayout.addView(touchControls.getOverlayView(), new ViewGroup.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT,
                    ViewGroup.LayoutParams.MATCH_PARENT));
        }

        if (mSurface != null) {
            mSurface.setOnTouchListener((view, event) -> {
                int width = Math.max(1, view.getWidth());
                int height = Math.max(1, view.getHeight());
                boolean gameplay = nativeGameplayTouchActive();

                touchControls.setGameplayActive(gameplay);

                if (gameplay) {
                    return touchControls.onTouchEvent(event, width, height);
                }

                // Front end, pause dialogs and cutscenes use SDL's normal touch
                // stream so the game's existing mouse-driven menus stay tappable.
                return forwardTouchToSdl(event, width, height);
            });
        }
    }

    /**
     * Equivalent to SDLSurface's stock touchscreen path. We call it explicitly
     * because the surface listener is replaced while the Android gameplay
     * overlay is installed.
     */
    private boolean forwardTouchToSdl(MotionEvent event, int width, int height) {
        int touchDevId = event.getDeviceId();
        if (touchDevId < 0) {
            touchDevId -= 1;
        }

        final int action = event.getActionMasked();
        final int pointerCount = event.getPointerCount();

        switch (action) {
            case MotionEvent.ACTION_MOVE:
                for (int i = 0; i < pointerCount; i++) {
                    sendNativeTouch(event, i, touchDevId, action, width, height);
                }
                break;

            case MotionEvent.ACTION_DOWN:
            case MotionEvent.ACTION_UP:
                sendNativeTouch(event, 0, touchDevId, action, width, height);
                break;

            case MotionEvent.ACTION_POINTER_DOWN:
            case MotionEvent.ACTION_POINTER_UP:
                sendNativeTouch(event, event.getActionIndex(), touchDevId, action, width, height);
                break;

            case MotionEvent.ACTION_CANCEL:
                for (int i = 0; i < pointerCount; i++) {
                    sendNativeTouch(event, i, touchDevId, MotionEvent.ACTION_UP, width, height);
                }
                break;

            default:
                break;
        }

        // A tap can launch/close a menu or start a stage. Refresh soon rather
        // than waiting for the next quarter-second poll.
        touchUiHandler.postDelayed(this::refreshTouchMode, 40L);
        return true;
    }

    private static void sendNativeTouch(MotionEvent event, int index, int touchDevId,
            int action, int width, int height) {
        float x = event.getX(index) / width;
        float y = event.getY(index) / height;
        float pressure = Math.min(1.0f, event.getPressure(index));
        SDLActivity.onNativeTouch(
                touchDevId,
                event.getPointerId(index),
                action,
                x,
                y,
                pressure);
    }

    private void startTouchUiPoll() {
        touchUiHandler.removeCallbacks(touchUiPoll);
        touchUiHandler.post(touchUiPoll);
    }

    private void refreshTouchMode() {
        if (touchControls == null || isFinishing()) {
            return;
        }

        touchControls.setGameplayActive(nativeGameplayTouchActive());
    }

    private void initializeGame() {
        android.util.Log.i("PerfectDark", "initializeGame start");

        File dataDir = new File(getExternalFilesDir(null), "data");
        android.util.Log.i("PerfectDark", "Data dir: " + dataDir.getAbsolutePath());
        if (!dataDir.exists()) {
            dataDir.mkdirs();
        }

        android.util.Log.i("PerfectDark", "Calling nativeInit");
        nativeInit(dataDir.getAbsolutePath());

        android.util.Log.i("PerfectDark", "initializeGame complete");
    }

    /**
     * Android Back should mean Escape inside Perfect Dark rather than exiting
     * the Activity. If SDL text input is active, the first Back only dismisses
     * the Android keyboard; the next Back becomes Escape in the game.
     */
    @Override
    public void onBackPressed() {
        if (SDLActivity.isScreenKeyboardShown()) {
            View focused = getCurrentFocus();
            if (focused != null) {
                InputMethodManager imm = (InputMethodManager) getSystemService(Context.INPUT_METHOD_SERVICE);
                if (imm != null) {
                    imm.hideSoftInputFromWindow(focused.getWindowToken(), 0);
                }
            }
            SDLActivity.onNativeKeyboardFocusLost();
            if (mSurface != null) {
                mSurface.requestFocus();
            }
            return;
        }

        SDLActivity.onNativeKeyDown(KeyEvent.KEYCODE_ESCAPE);
        SDLActivity.onNativeKeyUp(KeyEvent.KEYCODE_ESCAPE);
        touchUiHandler.postDelayed(this::refreshTouchMode, 40L);
    }

    @Override
    protected void onResume() {
        super.onResume();
        hideSystemUI();
        // SDLSurface restores its stock listener when SDL resumes.
        installTouchControls();
        startTouchUiPoll();
    }

    @Override
    protected void onPause() {
        touchUiHandler.removeCallbacks(touchUiPoll);
        if (touchControls != null) {
            touchControls.releaseAll();
        }
        super.onPause();
    }

    @Override
    protected void onDestroy() {
        touchUiHandler.removeCallbacksAndMessages(null);
        if (touchControls != null) {
            touchControls.releaseAll();
        }
        super.onDestroy();
        nativeDestroy();
    }

    public native void nativeInit(String dataPath);
    public native void nativeStartGame();
    public native void nativeDestroy();
    public native boolean nativeGameplayTouchActive();
}

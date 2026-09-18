package com.perfectdark.port;

import org.libsdl.app.SDLActivity;

import android.content.Context;
import android.os.Bundle;
import android.view.KeyEvent;
import android.view.View;
import android.view.WindowManager;
import android.view.inputmethod.InputMethodManager;

import java.io.File;

public class MainActivity extends SDLActivity {
    private TouchControls touchControls;

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
     * SDL normally turns finger input into mouse input. Perfect Dark maps
     * mouse-left to fire, so a finger drag currently shoots as well as looks.
     * Replace the stock SDL touch listener with the phone-control layer.
     */
    private void installTouchControls() {
        if (touchControls == null) {
            touchControls = new TouchControls(this);
        }

        if (mSurface != null) {
            mSurface.setOnTouchListener((view, event) ->
                    touchControls.onTouchEvent(event,
                            Math.max(1, view.getWidth()),
                            Math.max(1, view.getHeight())));
        }
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
    }

    @Override
    protected void onResume() {
        super.onResume();
        hideSystemUI();
        // SDLSurface restores its stock listener when SDL resumes.
        installTouchControls();
    }

    @Override
    protected void onPause() {
        if (touchControls != null) {
            touchControls.releaseAll();
        }
        super.onPause();
    }

    @Override
    protected void onDestroy() {
        if (touchControls != null) {
            touchControls.releaseAll();
        }
        super.onDestroy();
        nativeDestroy();
    }

    public native void nativeInit(String dataPath);
    public native void nativeStartGame();
    public native void nativeDestroy();
}

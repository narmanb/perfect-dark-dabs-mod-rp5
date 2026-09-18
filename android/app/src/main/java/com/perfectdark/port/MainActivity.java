package com.perfectdark.port;

import org.libsdl.app.SDLActivity;

import android.content.Context;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.KeyEvent;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.view.inputmethod.InputMethodManager;
import android.window.OnBackInvokedCallback;
import android.window.OnBackInvokedDispatcher;

import java.io.File;

public class MainActivity extends SDLActivity {
    private TouchControls touchControls;
    private boolean menuTouchActive;
    private OnBackInvokedCallback backInvokedCallback;
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

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            getWindow().getAttributes().layoutInDisplayCutoutMode =
                    WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES;
        }

        hideSystemUI();
        installTouchControls();
        registerModernBackHandler();

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
     * Gameplay gets our Android control layer. Menus are treated as a real
     * absolute mouse instead of relying on SDL's touch-to-mouse emulation. That
     * matters for Perfect Dark because closely stacked rows use the current
     * mouse position and the click in the same game tick; a bare finger tap can
     * otherwise activate the previously highlighted row.
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
                final int action = event.getActionMasked();

                // Keep an entire finger gesture on the path where it began. A
                // menu tap can start a stage on ACTION_DOWN; routing ACTION_UP
                // into gameplay after that would leave the synthetic mouse held.
                if (action == MotionEvent.ACTION_DOWN) {
                    boolean gameplay = nativeGameplayTouchActive();
                    menuTouchActive = !gameplay;
                    touchControls.setGameplayActive(gameplay);
                }

                if (menuTouchActive) {
                    boolean handled = forwardMenuTouchAsMouse(event, width, height);
                    if (action == MotionEvent.ACTION_UP || action == MotionEvent.ACTION_CANCEL) {
                        menuTouchActive = false;
                    }
                    return handled;
                }

                boolean gameplay = nativeGameplayTouchActive();
                touchControls.setGameplayActive(gameplay);

                if (gameplay) {
                    return touchControls.onTouchEvent(event, width, height);
                }

                return forwardMenuTouchAsMouse(event, width, height);
            });
        }
    }

    /**
     * Present a touchscreen finger as an ordinary absolute left mouse button.
     * Moving the mouse to the exact tap coordinate before pressing is much more
     * precise than SDL's synthesized touch mouse for tightly packed menu rows.
     */
    private boolean forwardMenuTouchAsMouse(MotionEvent event, int width, int height) {
        final int action = event.getActionMasked();

        // Menus are single-pointer UI. Ignore extra fingers rather than turning
        // them into additional clicks.
        if (action == MotionEvent.ACTION_POINTER_DOWN || action == MotionEvent.ACTION_POINTER_UP) {
            return true;
        }

        float x = event.getX(0);
        float y = event.getY(0);

        switch (action) {
            case MotionEvent.ACTION_DOWN:
                // First move the cursor, then press. The explicit move fixes the
                // stale-selection problem seen on Cancel/Abort-style dialogs.
                SDLActivity.onNativeMouse(0, MotionEvent.ACTION_MOVE, x, y, false);
                SDLActivity.onNativeMouse(MotionEvent.BUTTON_PRIMARY,
                        MotionEvent.ACTION_DOWN, x, y, false);
                break;

            case MotionEvent.ACTION_MOVE:
                SDLActivity.onNativeMouse(MotionEvent.BUTTON_PRIMARY,
                        MotionEvent.ACTION_MOVE, x, y, false);
                break;

            case MotionEvent.ACTION_UP:
                SDLActivity.onNativeMouse(MotionEvent.BUTTON_PRIMARY,
                        MotionEvent.ACTION_MOVE, x, y, false);
                SDLActivity.onNativeMouse(0, MotionEvent.ACTION_UP, x, y, false);
                break;

            case MotionEvent.ACTION_CANCEL:
                SDLActivity.onNativeMouse(0, MotionEvent.ACTION_UP, x, y, false);
                break;

            default:
                break;
        }

        // A tap can launch/close a menu, start a stage or enable the PC keyboard
        // row. Refresh quickly instead of waiting for the normal poll.
        touchUiHandler.postDelayed(this::refreshTouchMode, 40L);
        return true;
    }

    private void startTouchUiPoll() {
        touchUiHandler.removeCallbacks(touchUiPoll);
        touchUiHandler.post(touchUiPoll);
    }

    private void refreshTouchMode() {
        if (touchControls == null || isFinishing()) {
            return;
        }

        // The extra sixth row on the port's name-entry screen is specifically a
        // PC keyboard-input toggle. Android already has the game's clickable
        // on-screen alphabet, and SDL's IME steals focus when that row is tapped.
        // Cancel that mode immediately so the system keyboard cannot strand the
        // menu with controller/button input suppressed.
        if (nativeTextInputActive()) {
            disableAndroidTextInput();
        }

        touchControls.setGameplayActive(nativeGameplayTouchActive());
    }

    private void disableAndroidTextInput() {
        nativeCancelTextInput();

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
     * Perfect Dark's PC cancel binding is right mouse, not Escape. Android Back
     * therefore sends a synthetic right click. This works in dialogs such as
     * Customize Character where Escape alone is not bound to CK_CANCEL.
     */
    private void sendGameBack() {
        if (nativeTextInputActive() || SDLActivity.isScreenKeyboardShown()) {
            disableAndroidTextInput();
            return;
        }

        SDLActivity.onNativeMouse(MotionEvent.BUTTON_SECONDARY,
                MotionEvent.ACTION_DOWN, 0.0f, 0.0f, true);
        SDLActivity.onNativeMouse(0,
                MotionEvent.ACTION_UP, 0.0f, 0.0f, true);
        touchUiHandler.postDelayed(this::refreshTouchMode, 40L);
    }

    private void registerModernBackHandler() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            backInvokedCallback = this::sendGameBack;
            getOnBackInvokedDispatcher().registerOnBackInvokedCallback(
                    OnBackInvokedDispatcher.PRIORITY_DEFAULT,
                    backInvokedCallback);
        }
    }

    @Override
    public void onBackPressed() {
        sendGameBack();
    }

    @Override
    public boolean dispatchKeyEvent(KeyEvent event) {
        if (event.getKeyCode() == KeyEvent.KEYCODE_BACK) {
            if (event.getAction() == KeyEvent.ACTION_UP) {
                sendGameBack();
            }
            return true;
        }
        return super.dispatchKeyEvent(event);
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
        menuTouchActive = false;
        if (touchControls != null) {
            touchControls.releaseAll();
        }
        super.onPause();
    }

    @Override
    protected void onDestroy() {
        touchUiHandler.removeCallbacksAndMessages(null);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU && backInvokedCallback != null) {
            getOnBackInvokedDispatcher().unregisterOnBackInvokedCallback(backInvokedCallback);
            backInvokedCallback = null;
        }
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
    public native boolean nativeTextInputActive();
    public native void nativeCancelTextInput();
}

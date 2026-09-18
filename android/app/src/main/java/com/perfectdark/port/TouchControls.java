package com.perfectdark.port;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Typeface;
import android.os.Handler;
import android.os.Looper;
import android.util.SparseIntArray;
import android.view.KeyEvent;
import android.view.MotionEvent;
import android.view.View;

import org.libsdl.app.SDLActivity;

/**
 * Android gameplay controls layered over SDL.
 *
 * Menus do not use this class for input; MainActivity routes those touches back
 * through SDL's normal finger path so menu items remain directly tappable.
 *
 * Gameplay layout (first visible/testable pass):
 *  - lower-left fixed stick: movement (WASD)
 *  - lower-right fixed stick: analog-style continuous look or trackpad look
 *  - FIRE: Space / Z trigger
 *  - AIM: Z / R trigger
 *  - ACTION: E / B button
 *  - ALT: R / X button
 *  - L: F / L trigger
 *  - START: Tab
 *
 * The RP5's physical controller continues through SDL's normal controller path.
 */
public class TouchControls {
    public static final int LOOK_MODE_ANALOG = 0;
    public static final int LOOK_MODE_TRACKPAD = 1;

    private static native boolean nativeGameplayTouchEnabled();
    private static native float nativeGameplayTouchOpacity();
    private static native int nativeTouchLookMode();
    private static native float nativeTouchLookSensitivityX();
    private static native float nativeTouchLookSensitivityY();
    private static native float nativeTrackpadSensitivityX();
    private static native float nativeTrackpadSensitivityY();

    private static final float MOVE_X = 0.16f;
    private static final float MOVE_Y = 0.74f;
    private static final float MOVE_RADIUS = 0.135f;

    private static final float LOOK_X = 0.67f;
    private static final float LOOK_Y = 0.75f;
    private static final float LOOK_RADIUS = 0.125f;

    private static final float FIRE_X = 0.91f;
    private static final float FIRE_Y = 0.56f;
    private static final float FIRE_RADIUS = 0.075f;

    private static final float AIM_X = 0.82f;
    private static final float AIM_Y = 0.43f;
    private static final float AIM_RADIUS = 0.060f;

    private static final float ACTION_X = 0.91f;
    private static final float ACTION_Y = 0.78f;
    private static final float ACTION_RADIUS = 0.060f;

    private static final float ALT_X = 0.80f;
    private static final float ALT_Y = 0.87f;
    private static final float ALT_RADIUS = 0.052f;

    private static final float L_X = 0.08f;
    private static final float L_Y = 0.18f;
    private static final float L_RADIUS = 0.050f;

    private static final float START_X = 0.93f;
    private static final float START_Y = 0.14f;
    private static final float START_RADIUS = 0.045f;

    private static final float MOVE_THRESHOLD = 0.22f;
    private static final float LOOK_DEADZONE = 0.12f;
    // Full-stick speed is deliberately much higher than the first pass. The
    // original 8/6.5 deltas felt effectively unusable on a phone-sized stick.
    private static final float LOOK_SPEED_X = 32.0f;
    private static final float LOOK_SPEED_Y = 26.0f;
    private static final float TRACKPAD_GAIN = 1.30f;
    private static final long LOOK_TICK_MS = 16L;

    private final Handler handler = new Handler(Looper.getMainLooper());
    private final SparseIntArray heldButtonKeys = new SparseIntArray();
    private final ControlOverlay overlay;

    private boolean gameplayActive;
    private boolean gameplayTouchEnabled = true;
    private float controlOpacity = 0.46f;
    private int lookMode = LOOK_MODE_ANALOG;
    private float lookSensitivityX = 1.0f;
    private float lookSensitivityY = 1.0f;
    private float trackpadSensitivityX = 1.0f;
    private float trackpadSensitivityY = 1.0f;

    private int movePointerId = -1;
    private int lookPointerId = -1;

    private float moveNormX;
    private float moveNormY;
    private float lookNormX;
    private float lookNormY;
    private float lookLastX;
    private float lookLastY;

    private boolean keyW;
    private boolean keyA;
    private boolean keyS;
    private boolean keyD;
    private boolean lookTickRunning;

    public TouchControls(Context context) {
        overlay = new ControlOverlay(context);
        overlay.setClickable(false);
        overlay.setFocusable(false);
    }

    public View getOverlayView() {
        return overlay;
    }

    public void setGameplayActive(boolean active) {
        if (gameplayActive == active) {
            return;
        }

        gameplayActive = active;

        if (gameplayActive) {
            refreshNativeSettings();
        } else {
            releaseAll();
        }

        overlay.invalidate();
    }

    public boolean isGameplayActive() {
        return gameplayActive;
    }

    /** Ready for the in-game Android options page later. */
    public void setOpacity(float opacity) {
        controlOpacity = clamp(opacity, 0.0f, 1.0f);
        overlay.invalidate();
    }

    /** Direct Java override; entering gameplay re-syncs the native menu value. */
    public void setLookMode(int mode) {
        if (mode != LOOK_MODE_ANALOG && mode != LOOK_MODE_TRACKPAD) {
            return;
        }

        lookMode = mode;
        lookNormX = 0.0f;
        lookNormY = 0.0f;
        overlay.invalidate();
    }

    public void refreshNativeSettings() {
        gameplayTouchEnabled = nativeGameplayTouchEnabled();
        controlOpacity = clamp(nativeGameplayTouchOpacity(), 0.0f, 1.0f);
        int configuredMode = nativeTouchLookMode();
        if (configuredMode == LOOK_MODE_ANALOG || configuredMode == LOOK_MODE_TRACKPAD) {
            lookMode = configuredMode;
        }

        // The analog values are the same physical look-stick scale used by the
        // selected Player 1 controller, so one sensitivity setting changes both
        // the RP5 stick and the touchscreen stick. Negative advanced calibration
        // values remain meaningful as axis inversion.
        lookSensitivityX = clamp(nativeTouchLookSensitivityX(), -4.0f, 4.0f);
        lookSensitivityY = clamp(nativeTouchLookSensitivityY(), -4.0f, 4.0f);
        trackpadSensitivityX = clamp(nativeTrackpadSensitivityX(), 0.0f, 4.0f);
        trackpadSensitivityY = clamp(nativeTrackpadSensitivityY(), 0.0f, 4.0f);

        lookNormX = 0.0f;
        lookNormY = 0.0f;
    }

    public boolean onTouchEvent(MotionEvent event, int viewWidth, int viewHeight) {
        // Re-read the native values at the start of every gameplay gesture. This
        // makes sensitivity changes effective immediately after closing a menu.
        refreshNativeSettings();
        if (!gameplayActive || !gameplayTouchEnabled || viewWidth <= 0 || viewHeight <= 0) {
            return true;
        }

        final int action = event.getActionMasked();
        final int actionIndex = event.getActionIndex();

        switch (action) {
            case MotionEvent.ACTION_DOWN:
            case MotionEvent.ACTION_POINTER_DOWN:
                handleDown(event, actionIndex, viewWidth, viewHeight);
                break;

            case MotionEvent.ACTION_MOVE:
                handleMove(event, viewWidth, viewHeight);
                break;

            case MotionEvent.ACTION_UP:
            case MotionEvent.ACTION_POINTER_UP:
                handleUp(event.getPointerId(actionIndex));
                break;

            case MotionEvent.ACTION_CANCEL:
                releaseAll();
                break;

            default:
                break;
        }

        overlay.invalidate();
        return true;
    }

    private void handleDown(MotionEvent event, int index, int width, int height) {
        final int pointerId = event.getPointerId(index);
        final float x = event.getX(index);
        final float y = event.getY(index);

        // Buttons take priority over stick hit areas where their generous touch
        // circles happen to meet.
        if (hit(x, y, width, height, FIRE_X, FIRE_Y, FIRE_RADIUS, 1.30f)) {
            pressButton(pointerId, KeyEvent.KEYCODE_SPACE);
            return;
        }
        if (hit(x, y, width, height, AIM_X, AIM_Y, AIM_RADIUS, 1.35f)) {
            pressButton(pointerId, KeyEvent.KEYCODE_Z);
            return;
        }
        if (hit(x, y, width, height, ACTION_X, ACTION_Y, ACTION_RADIUS, 1.35f)) {
            pressButton(pointerId, KeyEvent.KEYCODE_E);
            return;
        }
        if (hit(x, y, width, height, ALT_X, ALT_Y, ALT_RADIUS, 1.35f)) {
            pressButton(pointerId, KeyEvent.KEYCODE_R);
            return;
        }
        if (hit(x, y, width, height, L_X, L_Y, L_RADIUS, 1.40f)) {
            pressButton(pointerId, KeyEvent.KEYCODE_F);
            return;
        }
        if (hit(x, y, width, height, START_X, START_Y, START_RADIUS, 1.45f)) {
            pressButton(pointerId, KeyEvent.KEYCODE_TAB);
            return;
        }

        if (movePointerId == -1
                && hit(x, y, width, height, MOVE_X, MOVE_Y, MOVE_RADIUS, 1.45f)) {
            movePointerId = pointerId;
            updateMoveStick(x, y, width, height);
            return;
        }

        if (lookPointerId == -1
                && hit(x, y, width, height, LOOK_X, LOOK_Y, LOOK_RADIUS, 1.50f)) {
            lookPointerId = pointerId;

            if (lookMode == LOOK_MODE_ANALOG) {
                updateLookStick(x, y, width, height);
                startLookTicker();
            } else {
                lookLastX = x;
                lookLastY = y;
            }
        }
    }

    private void handleMove(MotionEvent event, int width, int height) {
        for (int i = 0; i < event.getPointerCount(); i++) {
            final int pointerId = event.getPointerId(i);
            final float x = event.getX(i);
            final float y = event.getY(i);

            if (pointerId == movePointerId) {
                updateMoveStick(x, y, width, height);
            }

            if (pointerId == lookPointerId) {
                if (lookMode == LOOK_MODE_ANALOG) {
                    updateLookStick(x, y, width, height);
                } else {
                    float dx = (x - lookLastX) * TRACKPAD_GAIN * trackpadSensitivityX;
                    float dy = (y - lookLastY) * TRACKPAD_GAIN * trackpadSensitivityY;
                    lookLastX = x;
                    lookLastY = y;

                    if (dx != 0.0f || dy != 0.0f) {
                        SDLActivity.onNativeMouse(0, MotionEvent.ACTION_MOVE, dx, dy, true);
                    }
                }
            }
        }
    }

    private void handleUp(int pointerId) {
        if (pointerId == movePointerId) {
            movePointerId = -1;
            moveNormX = 0.0f;
            moveNormY = 0.0f;
            setMovement(0.0f, 0.0f);
        }

        if (pointerId == lookPointerId) {
            lookPointerId = -1;
            lookNormX = 0.0f;
            lookNormY = 0.0f;
        }

        int key = heldButtonKeys.get(pointerId, -1);
        if (key != -1) {
            heldButtonKeys.delete(pointerId);
            sendKey(key, false);
        }
    }

    private void updateMoveStick(float x, float y, int width, int height) {
        float radius = radiusPixels(width, height, MOVE_RADIUS);
        float dx = (x - MOVE_X * width) / radius;
        float dy = (y - MOVE_Y * height) / radius;
        float[] v = clampStick(dx, dy);
        moveNormX = v[0];
        moveNormY = v[1];
        setMovement(moveNormX, moveNormY);
    }

    private void updateLookStick(float x, float y, int width, int height) {
        float radius = radiusPixels(width, height, LOOK_RADIUS);
        float dx = (x - LOOK_X * width) / radius;
        float dy = (y - LOOK_Y * height) / radius;
        float[] v = clampStick(dx, dy);
        lookNormX = v[0];
        lookNormY = v[1];
    }

    private void startLookTicker() {
        if (lookTickRunning) {
            return;
        }

        lookTickRunning = true;
        handler.post(lookTick);
    }

    private final Runnable lookTick = new Runnable() {
        @Override
        public void run() {
            if (!gameplayActive || lookMode != LOOK_MODE_ANALOG || lookPointerId == -1) {
                lookTickRunning = false;
                return;
            }

            float[] v = applyRadialDeadzone(lookNormX, lookNormY, LOOK_DEADZONE);
            float dx = v[0] * LOOK_SPEED_X * lookSensitivityX;
            float dy = v[1] * LOOK_SPEED_Y * lookSensitivityY;

            if (dx != 0.0f || dy != 0.0f) {
                // Continuous relative motion is what makes this behave like an
                // analog stick: holding the thumb off-centre keeps turning.
                SDLActivity.onNativeMouse(0, MotionEvent.ACTION_MOVE, dx, dy, true);
            }

            handler.postDelayed(this, LOOK_TICK_MS);
        }
    };

    private void pressButton(int pointerId, int keyCode) {
        if (heldButtonKeys.get(pointerId, -1) != -1) {
            return;
        }

        heldButtonKeys.put(pointerId, keyCode);
        sendKey(keyCode, true);
    }

    private void setMovement(float x, float y) {
        setKeyW(y < -MOVE_THRESHOLD);
        setKeyS(y > MOVE_THRESHOLD);
        setKeyA(x < -MOVE_THRESHOLD);
        setKeyD(x > MOVE_THRESHOLD);
    }

    private void setKeyW(boolean down) {
        if (keyW != down) {
            keyW = down;
            sendKey(KeyEvent.KEYCODE_W, down);
        }
    }

    private void setKeyA(boolean down) {
        if (keyA != down) {
            keyA = down;
            sendKey(KeyEvent.KEYCODE_A, down);
        }
    }

    private void setKeyS(boolean down) {
        if (keyS != down) {
            keyS = down;
            sendKey(KeyEvent.KEYCODE_S, down);
        }
    }

    private void setKeyD(boolean down) {
        if (keyD != down) {
            keyD = down;
            sendKey(KeyEvent.KEYCODE_D, down);
        }
    }

    private static void sendKey(int keyCode, boolean down) {
        if (down) {
            SDLActivity.onNativeKeyDown(keyCode);
        } else {
            SDLActivity.onNativeKeyUp(keyCode);
        }
    }

    public void releaseAll() {
        movePointerId = -1;
        lookPointerId = -1;
        moveNormX = 0.0f;
        moveNormY = 0.0f;
        lookNormX = 0.0f;
        lookNormY = 0.0f;

        setMovement(0.0f, 0.0f);

        for (int i = 0; i < heldButtonKeys.size(); i++) {
            sendKey(heldButtonKeys.valueAt(i), false);
        }
        heldButtonKeys.clear();

        overlay.invalidate();
    }

    private static boolean hit(float x, float y, int width, int height,
            float cx, float cy, float radiusNorm, float hitScale) {
        float dx = x - cx * width;
        float dy = y - cy * height;
        float radius = radiusPixels(width, height, radiusNorm) * hitScale;
        return dx * dx + dy * dy <= radius * radius;
    }

    private static float radiusPixels(int width, int height, float radiusNorm) {
        return Math.min(width, height) * radiusNorm;
    }

    private static float[] clampStick(float x, float y) {
        float length = (float)Math.sqrt(x * x + y * y);
        if (length > 1.0f) {
            return new float[] { x / length, y / length };
        }
        return new float[] { x, y };
    }

    private static float[] applyRadialDeadzone(float x, float y, float deadzone) {
        float length = (float)Math.sqrt(x * x + y * y);
        if (length <= deadzone || length == 0.0f) {
            return new float[] { 0.0f, 0.0f };
        }

        float scaledLength = (length - deadzone) / (1.0f - deadzone);
        scaledLength = Math.min(1.0f, scaledLength);
        float scale = scaledLength / length;
        return new float[] { x * scale, y * scale };
    }

    private static float clamp(float value, float min, float max) {
        return Math.max(min, Math.min(max, value));
    }

    private boolean isKeyHeld(int keyCode) {
        return heldButtonKeys.indexOfValue(keyCode) >= 0;
    }

    private class ControlOverlay extends View {
        private final Paint fill = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final Paint outline = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final Paint text = new Paint(Paint.ANTI_ALIAS_FLAG);

        ControlOverlay(Context context) {
            super(context);
            setWillNotDraw(false);
            text.setTypeface(Typeface.DEFAULT_BOLD);
            text.setTextAlign(Paint.Align.CENTER);
        }

        @Override
        protected void onDraw(Canvas canvas) {
            super.onDraw(canvas);

            if (!gameplayActive || !gameplayTouchEnabled || controlOpacity <= 0.0f) {
                return;
            }

            int width = getWidth();
            int height = getHeight();
            if (width <= 0 || height <= 0) {
                return;
            }

            int fillAlpha = (int)(255.0f * controlOpacity * 0.55f);
            int lineAlpha = (int)(255.0f * Math.min(1.0f, controlOpacity + 0.22f));
            int textAlpha = (int)(255.0f * Math.min(1.0f, controlOpacity + 0.35f));

            fill.setStyle(Paint.Style.FILL);
            fill.setColor(Color.argb(fillAlpha, 0, 20, 28));

            outline.setStyle(Paint.Style.STROKE);
            outline.setStrokeWidth(Math.max(2.0f, Math.min(width, height) * 0.004f));
            outline.setColor(Color.argb(lineAlpha, 70, 225, 255));

            text.setColor(Color.argb(textAlpha, 235, 252, 255));

            drawStick(canvas, width, height, MOVE_X, MOVE_Y, MOVE_RADIUS,
                    moveNormX, moveNormY, "MOVE");
            drawStick(canvas, width, height, LOOK_X, LOOK_Y, LOOK_RADIUS,
                    lookMode == LOOK_MODE_ANALOG ? lookNormX : 0.0f,
                    lookMode == LOOK_MODE_ANALOG ? lookNormY : 0.0f,
                    lookMode == LOOK_MODE_ANALOG ? "LOOK" : "PAD");

            drawButton(canvas, width, height, FIRE_X, FIRE_Y, FIRE_RADIUS,
                    "FIRE", isKeyHeld(KeyEvent.KEYCODE_SPACE));
            drawButton(canvas, width, height, AIM_X, AIM_Y, AIM_RADIUS,
                    "AIM", isKeyHeld(KeyEvent.KEYCODE_Z));
            drawButton(canvas, width, height, ACTION_X, ACTION_Y, ACTION_RADIUS,
                    "ACTION", isKeyHeld(KeyEvent.KEYCODE_E));
            drawButton(canvas, width, height, ALT_X, ALT_Y, ALT_RADIUS,
                    "ALT", isKeyHeld(KeyEvent.KEYCODE_R));
            drawButton(canvas, width, height, L_X, L_Y, L_RADIUS,
                    "L", isKeyHeld(KeyEvent.KEYCODE_F));
            drawButton(canvas, width, height, START_X, START_Y, START_RADIUS,
                    "START", isKeyHeld(KeyEvent.KEYCODE_TAB));
        }

        private void drawStick(Canvas canvas, int width, int height,
                float cx, float cy, float radiusNorm,
                float nx, float ny, String label) {
            float x = cx * width;
            float y = cy * height;
            float radius = radiusPixels(width, height, radiusNorm);

            canvas.drawCircle(x, y, radius, fill);
            canvas.drawCircle(x, y, radius, outline);

            float thumbRadius = radius * 0.38f;
            float thumbX = x + nx * radius * 0.62f;
            float thumbY = y + ny * radius * 0.62f;
            canvas.drawCircle(thumbX, thumbY, thumbRadius, fill);
            canvas.drawCircle(thumbX, thumbY, thumbRadius, outline);

            text.setTextSize(radius * 0.25f);
            canvas.drawText(label, x, y + radius + text.getTextSize() * 1.15f, text);
        }

        private void drawButton(Canvas canvas, int width, int height,
                float cx, float cy, float radiusNorm, String label, boolean pressed) {
            float x = cx * width;
            float y = cy * height;
            float radius = radiusPixels(width, height, radiusNorm);

            if (pressed) {
                int pressedAlpha = (int)(255.0f * Math.min(1.0f, controlOpacity + 0.30f));
                fill.setColor(Color.argb(pressedAlpha, 20, 130, 155));
            } else {
                int fillAlpha = (int)(255.0f * controlOpacity * 0.55f);
                fill.setColor(Color.argb(fillAlpha, 0, 20, 28));
            }

            canvas.drawCircle(x, y, radius, fill);
            canvas.drawCircle(x, y, radius, outline);

            text.setTextSize(Math.max(12.0f, radius * (label.length() > 4 ? 0.35f : 0.45f)));
            Paint.FontMetrics fm = text.getFontMetrics();
            float baseline = y - (fm.ascent + fm.descent) * 0.5f;
            canvas.drawText(label, x, baseline, text);
        }
    }
}

package com.perfectdark.port;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Typeface;
import android.view.KeyEvent;
import android.view.MotionEvent;
import android.view.View;

import org.libsdl.app.SDLActivity;

/**
 * Simple Android-only menu navigation overlay.
 *
 * This deliberately uses the PC keyboard/menu bindings rather than creating a
 * virtual game controller. That keeps the RP5's physical SDL controller path
 * completely independent while giving phones large, reliable menu controls.
 */
public final class MenuTouchOverlay extends View {
    public interface BackAction {
        void run();
    }

    private static final int CONTROL_NONE = 0;
    private static final int CONTROL_UP = 1;
    private static final int CONTROL_DOWN = 2;
    private static final int CONTROL_LEFT = 3;
    private static final int CONTROL_RIGHT = 4;
    private static final int CONTROL_OK = 5;
    private static final int CONTROL_BACK = 6;

    private static final float DPAD_X = 0.16f;
    private static final float DPAD_Y = 0.72f;
    private static final float DPAD_STEP = 0.145f;
    private static final float DPAD_RADIUS = 0.067f;

    private static final float OK_X = 0.86f;
    private static final float OK_Y = 0.62f;
    private static final float OK_RADIUS = 0.090f;

    private static final float BACK_X = 0.86f;
    private static final float BACK_Y = 0.82f;
    private static final float BACK_RADIUS = 0.072f;

    private final BackAction backAction;
    private final Paint fill = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint outline = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint text = new Paint(Paint.ANTI_ALIAS_FLAG);

    private boolean menuActive = true;
    private int activePointerId = -1;
    private int activeControl = CONTROL_NONE;
    private int heldKeyCode = -1;

    public MenuTouchOverlay(Context context, BackAction backAction) {
        super(context);
        this.backAction = backAction;
        setWillNotDraw(false);
        // Input is deliberately received by MainActivity's SDL surface listener.
        // Keeping this View non-clickable also preserves direct menu tapping in
        // every area not occupied by one of these controls.
        setClickable(false);
        setFocusable(false);
        text.setTypeface(Typeface.DEFAULT_BOLD);
        text.setTextAlign(Paint.Align.CENTER);
    }

    public void setMenuActive(boolean active) {
        if (menuActive == active) {
            return;
        }

        menuActive = active;
        if (!menuActive) {
            releaseAll();
        }
        invalidate();
    }

    public boolean isMenuActive() {
        return menuActive;
    }

    /**
     * Handle a touch that MainActivity received on the SDL surface.
     * Returns false on ACTION_DOWN when the finger is outside this overlay so
     * MainActivity can keep using direct coordinate-based menu tapping there.
     */
    public boolean handleTouch(MotionEvent event, int width, int height) {
        if (!menuActive || width <= 0 || height <= 0) {
            return false;
        }

        final int action = event.getActionMasked();
        final int actionIndex = event.getActionIndex();

        if (action == MotionEvent.ACTION_DOWN) {
            int control = findControl(event.getX(actionIndex), event.getY(actionIndex), width, height);
            if (control == CONTROL_NONE) {
                return false;
            }

            activePointerId = event.getPointerId(actionIndex);
            activeControl = control;
            pressControl(control);
            invalidate();
            return true;
        }

        if (activeControl == CONTROL_NONE) {
            return false;
        }

        switch (action) {
            case MotionEvent.ACTION_UP:
                if (event.getPointerId(actionIndex) == activePointerId) {
                    releaseControl(true);
                }
                break;

            case MotionEvent.ACTION_CANCEL:
                releaseControl(false);
                break;

            case MotionEvent.ACTION_POINTER_UP:
                if (event.getPointerId(actionIndex) == activePointerId) {
                    releaseControl(true);
                }
                break;

            default:
                // Holding a direction keeps its SDL key down, which gives the
                // game's normal menu repeat behavior without a custom timer.
                break;
        }

        invalidate();
        return true;
    }

    public void releaseAll() {
        releaseControl(false);
        invalidate();
    }

    private void pressControl(int control) {
        int keyCode = keyForControl(control);
        if (keyCode != -1) {
            heldKeyCode = keyCode;
            SDLActivity.onNativeKeyDown(keyCode);
        }
        // Back is fired on release so a touch that gets cancelled cannot
        // accidentally leave a menu.
    }

    private void releaseControl(boolean activateBack) {
        if (heldKeyCode != -1) {
            SDLActivity.onNativeKeyUp(heldKeyCode);
            heldKeyCode = -1;
        }

        boolean runBack = activateBack && activeControl == CONTROL_BACK;
        activePointerId = -1;
        activeControl = CONTROL_NONE;

        if (runBack && backAction != null) {
            backAction.run();
        }
    }

    private static int keyForControl(int control) {
        switch (control) {
            case CONTROL_UP:
                return KeyEvent.KEYCODE_DPAD_UP;
            case CONTROL_DOWN:
                return KeyEvent.KEYCODE_DPAD_DOWN;
            case CONTROL_LEFT:
                return KeyEvent.KEYCODE_DPAD_LEFT;
            case CONTROL_RIGHT:
                return KeyEvent.KEYCODE_DPAD_RIGHT;
            case CONTROL_OK:
                return KeyEvent.KEYCODE_ENTER;
            default:
                return -1;
        }
    }

    private static int findControl(float x, float y, int width, int height) {
        float stepX = DPAD_STEP * Math.min(width, height) / width;
        float stepY = DPAD_STEP * Math.min(width, height) / height;

        if (hit(x, y, width, height, DPAD_X, DPAD_Y - stepY, DPAD_RADIUS, 1.28f)) {
            return CONTROL_UP;
        }
        if (hit(x, y, width, height, DPAD_X, DPAD_Y + stepY, DPAD_RADIUS, 1.28f)) {
            return CONTROL_DOWN;
        }
        if (hit(x, y, width, height, DPAD_X - stepX, DPAD_Y, DPAD_RADIUS, 1.28f)) {
            return CONTROL_LEFT;
        }
        if (hit(x, y, width, height, DPAD_X + stepX, DPAD_Y, DPAD_RADIUS, 1.28f)) {
            return CONTROL_RIGHT;
        }
        if (hit(x, y, width, height, OK_X, OK_Y, OK_RADIUS, 1.20f)) {
            return CONTROL_OK;
        }
        if (hit(x, y, width, height, BACK_X, BACK_Y, BACK_RADIUS, 1.25f)) {
            return CONTROL_BACK;
        }
        return CONTROL_NONE;
    }

    private static boolean hit(float x, float y, int width, int height,
            float cx, float cy, float radiusNorm, float hitScale) {
        float dx = x - cx * width;
        float dy = y - cy * height;
        float radius = Math.min(width, height) * radiusNorm * hitScale;
        return dx * dx + dy * dy <= radius * radius;
    }

    @Override
    protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        if (!menuActive) {
            return;
        }

        int width = getWidth();
        int height = getHeight();
        if (width <= 0 || height <= 0) {
            return;
        }

        float min = Math.min(width, height);
        float stepX = DPAD_STEP * min / width;
        float stepY = DPAD_STEP * min / height;

        fill.setStyle(Paint.Style.FILL);
        fill.setColor(Color.argb(125, 0, 20, 28));

        outline.setStyle(Paint.Style.STROKE);
        outline.setStrokeWidth(Math.max(3.0f, min * 0.005f));
        outline.setColor(Color.argb(225, 70, 225, 255));

        text.setColor(Color.argb(245, 235, 252, 255));

        drawButton(canvas, width, height, DPAD_X, DPAD_Y - stepY, DPAD_RADIUS,
                "UP", activeControl == CONTROL_UP);
        drawButton(canvas, width, height, DPAD_X, DPAD_Y + stepY, DPAD_RADIUS,
                "DN", activeControl == CONTROL_DOWN);
        drawButton(canvas, width, height, DPAD_X - stepX, DPAD_Y, DPAD_RADIUS,
                "LT", activeControl == CONTROL_LEFT);
        drawButton(canvas, width, height, DPAD_X + stepX, DPAD_Y, DPAD_RADIUS,
                "RT", activeControl == CONTROL_RIGHT);
        drawButton(canvas, width, height, OK_X, OK_Y, OK_RADIUS,
                "OK", activeControl == CONTROL_OK);
        drawButton(canvas, width, height, BACK_X, BACK_Y, BACK_RADIUS,
                "BACK", activeControl == CONTROL_BACK);
    }

    private void drawButton(Canvas canvas, int width, int height,
            float cx, float cy, float radiusNorm, String label, boolean pressed) {
        float x = cx * width;
        float y = cy * height;
        float radius = Math.min(width, height) * radiusNorm;

        if (pressed) {
            fill.setColor(Color.argb(205, 20, 130, 155));
        } else {
            fill.setColor(Color.argb(125, 0, 20, 28));
        }

        canvas.drawCircle(x, y, radius, fill);
        canvas.drawCircle(x, y, radius, outline);

        text.setTextSize(Math.max(14.0f, radius * (label.length() > 2 ? 0.42f : 0.52f)));
        Paint.FontMetrics fm = text.getFontMetrics();
        float baseline = y - (fm.ascent + fm.descent) * 0.5f;
        canvas.drawText(label, x, baseline, text);
    }
}

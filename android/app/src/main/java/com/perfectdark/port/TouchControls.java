package com.perfectdark.port;

import android.content.Context;
import android.view.KeyEvent;
import android.view.MotionEvent;

import org.libsdl.app.SDLActivity;

/**
 * Lightweight phone controls layered over SDL.
 *
 * Lower-left: floating movement stick (WASD)
 * Lower-right: floating look area (relative mouse motion)
 * Upper-right: fire (Space / Z trigger)
 * Upper-left: aim (Z / R trigger)
 *
 * The RP5's physical controller still goes through SDL's normal game-controller
 * path; this class only handles touchscreen events.
 */
public class TouchControls {
    private static final float UPPER_ZONE_END = 0.45f;
    private static final float SIDE_BUTTON_EDGE = 0.45f;
    private static final float MOVE_RADIUS_X = 0.12f;
    private static final float MOVE_RADIUS_Y = 0.20f;
    private static final float MOVE_THRESHOLD = 0.22f;
    private static final float LOOK_GAIN = 1.35f;

    private final Context context;

    private int movePointerId = -1;
    private int lookPointerId = -1;
    private int firePointerId = -1;
    private int aimPointerId = -1;

    private float moveCenterX;
    private float moveCenterY;
    private float lookLastX;
    private float lookLastY;

    private boolean keyW;
    private boolean keyA;
    private boolean keyS;
    private boolean keyD;
    private boolean fireDown;
    private boolean aimDown;

    public TouchControls(Context context) {
        this.context = context;
    }

    public boolean onTouchEvent(MotionEvent event, int viewWidth, int viewHeight) {
        final int action = event.getActionMasked();
        final int actionIndex = event.getActionIndex();

        switch (action) {
            case MotionEvent.ACTION_DOWN:
            case MotionEvent.ACTION_POINTER_DOWN: {
                int pointerId = event.getPointerId(actionIndex);
                float x = event.getX(actionIndex) / viewWidth;
                float y = event.getY(actionIndex) / viewHeight;
                handleDown(pointerId, x, y);
                break;
            }

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

        return true;
    }

    private void handleDown(int pointerId, float x, float y) {
        // Dedicated buttons live in the upper corners so looking never fires.
        if (y < UPPER_ZONE_END) {
            if (x > 1.0f - SIDE_BUTTON_EDGE && firePointerId == -1) {
                firePointerId = pointerId;
                setFire(true);
                return;
            }
            if (x < SIDE_BUTTON_EDGE && aimPointerId == -1) {
                aimPointerId = pointerId;
                setAim(true);
                return;
            }
        }

        // Floating sticks begin wherever the thumb lands in the lower half.
        if (x < 0.5f && movePointerId == -1) {
            movePointerId = pointerId;
            moveCenterX = x;
            moveCenterY = y;
            setMovement(0.0f, 0.0f);
            return;
        }

        if (x >= 0.5f && lookPointerId == -1) {
            lookPointerId = pointerId;
            lookLastX = x;
            lookLastY = y;
        }
    }

    private void handleMove(MotionEvent event, int viewWidth, int viewHeight) {
        for (int i = 0; i < event.getPointerCount(); i++) {
            int pointerId = event.getPointerId(i);
            float x = event.getX(i) / viewWidth;
            float y = event.getY(i) / viewHeight;

            if (pointerId == movePointerId) {
                float nx = clamp((x - moveCenterX) / MOVE_RADIUS_X, -1.0f, 1.0f);
                float ny = clamp((y - moveCenterY) / MOVE_RADIUS_Y, -1.0f, 1.0f);
                setMovement(nx, ny);
            }

            if (pointerId == lookPointerId) {
                float dx = (x - lookLastX) * viewWidth * LOOK_GAIN;
                float dy = (y - lookLastY) * viewHeight * LOOK_GAIN;
                lookLastX = x;
                lookLastY = y;

                if (dx != 0.0f || dy != 0.0f) {
                    // Feed relative mouse motion only. No mouse button is pressed,
                    // which prevents the old "drag = shoot" behaviour.
                    SDLActivity.onNativeMouse(0, MotionEvent.ACTION_MOVE, dx, dy, true);
                }
            }
        }
    }

    private void handleUp(int pointerId) {
        if (pointerId == movePointerId) {
            movePointerId = -1;
            setMovement(0.0f, 0.0f);
        }

        if (pointerId == lookPointerId) {
            lookPointerId = -1;
        }

        if (pointerId == firePointerId) {
            firePointerId = -1;
            setFire(false);
        }

        if (pointerId == aimPointerId) {
            aimPointerId = -1;
            setAim(false);
        }
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

    private void setFire(boolean down) {
        if (fireDown != down) {
            fireDown = down;
            // Space is Perfect Dark PC controls' secondary Z-trigger/fire bind.
            sendKey(KeyEvent.KEYCODE_SPACE, down);
        }
    }

    private void setAim(boolean down) {
        if (aimDown != down) {
            aimDown = down;
            // Z is the default keyboard bind for R-trigger/manual aim.
            sendKey(KeyEvent.KEYCODE_Z, down);
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
        firePointerId = -1;
        aimPointerId = -1;

        setMovement(0.0f, 0.0f);
        setFire(false);
        setAim(false);
    }

    private static float clamp(float value, float min, float max) {
        return Math.max(min, Math.min(max, value));
    }
}

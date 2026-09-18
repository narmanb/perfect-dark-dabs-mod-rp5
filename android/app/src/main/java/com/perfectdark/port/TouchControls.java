package com.perfectdark.port;

import android.content.Context;
import android.view.MotionEvent;

public class TouchControls {
    private Context context;
    private boolean leftStickActive = false;
    private boolean rightStickActive = false;
    private float leftStickCenterX, leftStickCenterY;
    private float rightStickCenterX, rightStickCenterY;
    private int leftStickPointerId = -1;
    private int rightStickPointerId = -1;
    
    // Touch zones (normalized coordinates 0-1)
    private static final float LEFT_STICK_X = 0.15f;
    private static final float LEFT_STICK_Y = 0.7f;
    private static final float RIGHT_STICK_X = 0.85f;
    private static final float RIGHT_STICK_Y = 0.7f;
    private static final float STICK_RADIUS = 0.1f;
    
    // Button zones
    private static final float FIRE_BUTTON_X = 0.9f;
    private static final float FIRE_BUTTON_Y = 0.3f;
    private static final float AIM_BUTTON_X = 0.1f;
    private static final float AIM_BUTTON_Y = 0.3f;
    private static final float BUTTON_RADIUS = 0.08f;
    
    public TouchControls(Context context) {
        this.context = context;
    }
    
    public boolean onTouchEvent(MotionEvent event) {
        int action = event.getActionMasked();
        int pointerIndex = event.getActionIndex();
        int pointerId = event.getPointerId(pointerIndex);
        
        float x = event.getX(pointerIndex) / context.getResources().getDisplayMetrics().widthPixels;
        float y = event.getY(pointerIndex) / context.getResources().getDisplayMetrics().heightPixels;
        
        switch (action) {
            case MotionEvent.ACTION_DOWN:
            case MotionEvent.ACTION_POINTER_DOWN:
                handleTouchDown(x, y, pointerId);
                break;
                
            case MotionEvent.ACTION_MOVE:
                handleTouchMove(event);
                break;
                
            case MotionEvent.ACTION_UP:
            case MotionEvent.ACTION_POINTER_UP:
                handleTouchUp(pointerId);
                break;
        }
        
        return true;
    }
    
    private void handleTouchDown(float x, float y, int pointerId) {
        // Check for left stick
        if (isInCircle(x, y, LEFT_STICK_X, LEFT_STICK_Y, STICK_RADIUS) && leftStickPointerId == -1) {
            leftStickActive = true;
            leftStickPointerId = pointerId;
            leftStickCenterX = LEFT_STICK_X;
            leftStickCenterY = LEFT_STICK_Y;
            return;
        }
        
        // Check for right stick
        if (isInCircle(x, y, RIGHT_STICK_X, RIGHT_STICK_Y, STICK_RADIUS) && rightStickPointerId == -1) {
            rightStickActive = true;
            rightStickPointerId = pointerId;
            rightStickCenterX = RIGHT_STICK_X;
            rightStickCenterY = RIGHT_STICK_Y;
            return;
        }
        
        // Check for fire button
        if (isInCircle(x, y, FIRE_BUTTON_X, FIRE_BUTTON_Y, BUTTON_RADIUS)) {
            nativeButtonDown(0); // Fire button
            return;
        }
        
        // Check for aim button
        if (isInCircle(x, y, AIM_BUTTON_X, AIM_BUTTON_Y, BUTTON_RADIUS)) {
            nativeButtonDown(1); // Aim button
            return;
        }
    }
    
    private void handleTouchMove(MotionEvent event) {
        for (int i = 0; i < event.getPointerCount(); i++) {
            int pointerId = event.getPointerId(i);
            float x = event.getX(i) / context.getResources().getDisplayMetrics().widthPixels;
            float y = event.getY(i) / context.getResources().getDisplayMetrics().heightPixels;
            
            if (pointerId == leftStickPointerId && leftStickActive) {
                float deltaX = x - leftStickCenterX;
                float deltaY = y - leftStickCenterY;
                float distance = (float) Math.sqrt(deltaX * deltaX + deltaY * deltaY);
                
                if (distance > STICK_RADIUS) {
                    deltaX = deltaX / distance * STICK_RADIUS;
                    deltaY = deltaY / distance * STICK_RADIUS;
                }
                
                // Normalize to -1 to 1 range
                float normalizedX = deltaX / STICK_RADIUS;
                float normalizedY = deltaY / STICK_RADIUS;
                
                nativeStickInput(0, normalizedX, normalizedY); // Left stick
            }
            
            if (pointerId == rightStickPointerId && rightStickActive) {
                float deltaX = x - rightStickCenterX;
                float deltaY = y - rightStickCenterY;
                float distance = (float) Math.sqrt(deltaX * deltaX + deltaY * deltaY);
                
                if (distance > STICK_RADIUS) {
                    deltaX = deltaX / distance * STICK_RADIUS;
                    deltaY = deltaY / distance * STICK_RADIUS;
                }
                
                float normalizedX = deltaX / STICK_RADIUS;
                float normalizedY = deltaY / STICK_RADIUS;
                
                nativeStickInput(1, normalizedX, normalizedY); // Right stick
            }
        }
    }
    
    private void handleTouchUp(int pointerId) {
        if (pointerId == leftStickPointerId) {
            leftStickActive = false;
            leftStickPointerId = -1;
            nativeStickInput(0, 0, 0);
        }
        
        if (pointerId == rightStickPointerId) {
            rightStickActive = false;
            rightStickPointerId = -1;
            nativeStickInput(1, 0, 0);
        }
        
        // Handle button releases
        nativeButtonUp(0); // Fire button
        nativeButtonUp(1); // Aim button
    }
    
    private boolean isInCircle(float x, float y, float centerX, float centerY, float radius) {
        float dx = x - centerX;
        float dy = y - centerY;
        return (dx * dx + dy * dy) <= (radius * radius);
    }
    
    // Native methods
    public native void nativeStickInput(int stick, float x, float y);
    public native void nativeButtonDown(int button);
    public native void nativeButtonUp(int button);
}
package com.golikehelper;

import android.accessibilityservice.AccessibilityService;
import android.accessibilityservice.GestureDescription;
import android.graphics.Path;
import android.view.accessibility.AccessibilityEvent;

public class AutoClickService extends AccessibilityService {

    public static AutoClickService instance;

    @Override
    public void onServiceConnected() {
        super.onServiceConnected();
        instance = this;
        MainActivity.addLog("Accessibility Service da ket noi.");
    }

    @Override
    public void onAccessibilityEvent(AccessibilityEvent event) {}

    @Override
    public void onInterrupt() {}

    @Override
    public void onDestroy() {
        super.onDestroy();
        instance = null;
    }

    /**
     * Thuc hien click tai toa do (x, y) thong qua Gesture API.
     */
    public boolean performClick(float x, float y) {
        Path clickPath = new Path();
        clickPath.moveTo(x, y);

        GestureDescription.StrokeDescription stroke =
            new GestureDescription.StrokeDescription(clickPath, 0, 100);

        GestureDescription.Builder builder = new GestureDescription.Builder();
        builder.addStroke(stroke);

        boolean dispatched = dispatchGesture(builder.build(), new GestureResultCallback() {
            @Override
            public void onCompleted(GestureDescription gestureDescription) {
                MainActivity.addLog("Click OK: (" + (int)x + "," + (int)y + ")");
            }
            @Override
            public void onCancelled(GestureDescription gestureDescription) {
                MainActivity.addLog("Click bi huy: (" + (int)x + "," + (int)y + ")");
            }
        }, null);

        return dispatched;
    }

    /**
     * Thuc hien swipe tu (x1,y1) toi (x2,y2).
     */
    public boolean performSwipe(float x1, float y1, float x2, float y2, long duration) {
        Path swipePath = new Path();
        swipePath.moveTo(x1, y1);
        swipePath.lineTo(x2, y2);

        GestureDescription.StrokeDescription stroke =
            new GestureDescription.StrokeDescription(swipePath, 0, duration);

        GestureDescription.Builder builder = new GestureDescription.Builder();
        builder.addStroke(stroke);

        return dispatchGesture(builder.build(), null, null);
    }
}

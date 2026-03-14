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
        MainActivity.addLog("Accessibility Service da ngat ket noi.");
    }

    public boolean performClick(float x, float y) {
        Path clickPath = new Path();
        clickPath.moveTo(x, y);
        GestureDescription.StrokeDescription stroke =
            new GestureDescription.StrokeDescription(clickPath, 0, 80);
        GestureDescription.Builder builder = new GestureDescription.Builder();
        builder.addStroke(stroke);
        boolean dispatched = dispatchGesture(builder.build(), new GestureResultCallback() {
            @Override
            public void onCompleted(GestureDescription g) {
                HttpServerService.totalClicks++;
                MainActivity.addLog("Click OK (" + (int)x + "," + (int)y + ")");
            }
            @Override
            public void onCancelled(GestureDescription g) {
                MainActivity.addLog("Click bi huy (" + (int)x + "," + (int)y + ")");
            }
        }, null);
        return dispatched;
    }

    public boolean performLongClick(float x, float y, long durationMs) {
        Path clickPath = new Path();
        clickPath.moveTo(x, y);
        GestureDescription.StrokeDescription stroke =
            new GestureDescription.StrokeDescription(clickPath, 0, durationMs);
        GestureDescription.Builder builder = new GestureDescription.Builder();
        builder.addStroke(stroke);
        return dispatchGesture(builder.build(), new GestureResultCallback() {
            @Override
            public void onCompleted(GestureDescription g) {
                HttpServerService.totalClicks++;
                MainActivity.addLog("LongPress OK (" + (int)x + "," + (int)y + ") " + durationMs + "ms");
            }
            @Override
            public void onCancelled(GestureDescription g) {}
        }, null);
    }

    public boolean performSwipe(float x1, float y1, float x2, float y2, long duration) {
        Path swipePath = new Path();
        swipePath.moveTo(x1, y1);
        swipePath.lineTo(x2, y2);
        GestureDescription.StrokeDescription stroke =
            new GestureDescription.StrokeDescription(swipePath, 0, duration);
        GestureDescription.Builder builder = new GestureDescription.Builder();
        builder.addStroke(stroke);
        return dispatchGesture(builder.build(), new GestureResultCallback() {
            @Override
            public void onCompleted(GestureDescription g) {
                MainActivity.addLog("Swipe OK");
            }
            @Override
            public void onCancelled(GestureDescription g) {}
        }, null);
    }
}

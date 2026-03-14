package com.golike.bot;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.util.Log;

public class BootReceiver extends BroadcastReceiver {

    private static final String TAG = "GLBotBoot";

    @Override
    public void onReceive(Context context, Intent intent) {
        String action = intent.getAction();
        if (Intent.ACTION_BOOT_COMPLETED.equals(action)
                || "android.intent.action.QUICKBOOT_POWERON".equals(action)) {
            Log.d(TAG, "Boot completed → starting BotService");

            Intent svc = new Intent(context, BotService.class);
            svc.putExtra("port", 8080);
            svc.putExtra("boot", true);
            try {
                context.startForegroundService(svc);
            } catch (Exception e) {
                context.startService(svc);
            }
        }
    }
}

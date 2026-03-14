package com.golike.bot;

import android.app.*;
import android.content.*;
import android.os.*;
import android.util.Log;
import androidx.core.app.NotificationCompat;
import java.io.*;

public class BotService extends Service {
    private static final String TAG = "GLBotService";
    private static final String CH  = "glbot_ch";
    private static final int NID    = 1001;
    private Process botProcess;

    @Override
    public void onCreate() {
        super.onCreate();
        NotificationChannel nc = new NotificationChannel(
            CH, "GoLike Bot", NotificationManager.IMPORTANCE_LOW);
        nc.setDescription("Bot chạy ngầm");
        getSystemService(NotificationManager.class).createNotificationChannel(nc);
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        int port = intent != null ? intent.getIntExtra("port", 8080) : 8080;
        startForeground(NID, buildNotif("GoLike Bot đang chạy...", "Đang khởi động..."));
        new Thread(() -> startBot(port)).start();
        return START_STICKY;
    }

    private void startBot(int port) {
        try {
            File f = new File(getFilesDir(), "bot.py");
            if (!f.exists() || f.length() < 1000) {
                try (InputStream is = getAssets().open("bot.py");
                     FileOutputStream fos = new FileOutputStream(f)) {
                    byte[] buf = new byte[8192]; int n;
                    while ((n = is.read(buf)) > 0) fos.write(buf, 0, n);
                }
            }

            String py = findPython();
            if (py == null) {
                notify("Lỗi: Không tìm thấy Python",
                       "Cài Termux + 'pkg install python'");
                return;
            }

            notify("GoLike Bot đang chạy", "Port: " + port);
            ProcessBuilder pb = new ProcessBuilder(
                py, f.getAbsolutePath(), "--headless", "--port", String.valueOf(port));
            pb.directory(getFilesDir());
            pb.redirectErrorStream(true);
            botProcess = pb.start();

            try (BufferedReader br = new BufferedReader(
                    new InputStreamReader(botProcess.getInputStream()))) {
                String line;
                while ((line = br.readLine()) != null) {
                    Log.d(TAG, line);
                    if (line.contains("Server")) notify("GoLike Bot đang chạy", "✓ Server OK: " + port);
                    else if (line.contains("DONE")) notify("GoLike Bot", "✓ " + line.trim());
                }
            }
        } catch (Exception e) {
            Log.e(TAG, "startBot: " + e.getMessage());
            notify("GoLike Bot - Lỗi", e.getMessage());
        }
    }

    private String findPython() {
        for (String p : new String[]{
            "/data/data/com.termux/files/usr/bin/python3",
            "/data/data/com.termux/files/usr/bin/python",
            "/usr/bin/python3", "/usr/local/bin/python3"
        }) { if (new File(p).exists()) return p; }
        return null;
    }

    private Notification buildNotif(String title, String text) {
        return new NotificationCompat.Builder(this, CH)
            .setContentTitle(title).setContentText(text)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setOngoing(true).build();
    }

    private void notify(String title, String text) {
        getSystemService(NotificationManager.class).notify(NID, buildNotif(title, text));
    }

    @Override public IBinder onBind(Intent i) { return null; }

    @Override
    public void onDestroy() {
        if (botProcess != null) botProcess.destroy();
        super.onDestroy();
    }
}

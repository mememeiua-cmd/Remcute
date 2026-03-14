package com.golikehelper;

import android.app.Activity;
import android.content.Intent;
import android.media.projection.MediaProjectionManager;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.widget.Button;
import android.widget.TextView;
import android.widget.Toast;
import androidx.appcompat.app.AppCompatActivity;

public class MainActivity extends AppCompatActivity {

    private static final int REQUEST_MEDIA_PROJECTION = 1001;

    private TextView tvStatus;
    private TextView tvLog;
    private TextView tvAccessStatus;
    private TextView tvOverlayStatus;
    private TextView tvScreenStatus;
    private TextView tvRunBadge;
    private TextView tvRequestCount;
    private TextView tvScreenshotCount;
    private TextView tvClickCount;

    private MediaProjectionManager projectionManager;
    private Handler uiHandler = new Handler(Looper.getMainLooper());
    private Runnable statsUpdater;

    public static MainActivity instance;
    public static StringBuilder logBuilder = new StringBuilder();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        instance = this;
        setContentView(R.layout.activity_main);

        tvStatus         = findViewById(R.id.tvStatus);
        tvLog            = findViewById(R.id.tvLog);
        tvAccessStatus   = findViewById(R.id.tvAccessStatus);
        tvOverlayStatus  = findViewById(R.id.tvOverlayStatus);
        tvScreenStatus   = findViewById(R.id.tvScreenStatus);
        tvRunBadge       = findViewById(R.id.tvRunBadge);
        tvRequestCount   = findViewById(R.id.tvRequestCount);
        tvScreenshotCount = findViewById(R.id.tvScreenshotCount);
        tvClickCount     = findViewById(R.id.tvClickCount);

        projectionManager = (MediaProjectionManager)
            getSystemService(MEDIA_PROJECTION_SERVICE);

        findViewById(R.id.btnStart).setOnClickListener(v -> startHelper());
        findViewById(R.id.btnStop).setOnClickListener(v -> stopHelper());
        findViewById(R.id.btnClearLog).setOnClickListener(v -> {
            logBuilder.setLength(0);
            tvLog.setText("Log đã xóa.\n");
        });
        findViewById(R.id.btnAccessibility).setOnClickListener(v ->
            startActivity(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)));
        findViewById(R.id.btnOverlay).setOnClickListener(v ->
            startActivity(new Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                Uri.parse("package:" + getPackageName()))));
        findViewById(R.id.btnAppInfo).setOnClickListener(v -> {
            Intent i = new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS);
            i.setData(Uri.parse("package:" + getPackageName()));
            startActivity(i);
        });

        addLog("=== GoLike Helper v2.0 ===");
        addLog("Đang chờ lệnh Start...");
        startStatsUpdater();
    }

    @Override
    protected void onResume() {
        super.onResume();
        updatePermissionStatus();
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        if (statsUpdater != null) uiHandler.removeCallbacks(statsUpdater);
        instance = null;
    }

    private void updatePermissionStatus() {
        boolean accessOk  = AutoClickService.instance != null;
        boolean overlayOk = Settings.canDrawOverlays(this);
        boolean screenOk  = HttpServerService.isScreenCaptureReady;

        tvAccessStatus.setText(accessOk  ? "Đã kích hoạt ✓" : "Chưa kích hoạt ✗");
        tvAccessStatus.setTextColor(accessOk  ? 0xFF00E5A0 : 0xFFFF5252);

        tvOverlayStatus.setText(overlayOk ? "Đã cấp quyền ✓" : "Chưa cấp quyền ✗");
        tvOverlayStatus.setTextColor(overlayOk ? 0xFF00E5A0 : 0xFFFF5252);

        tvScreenStatus.setText(screenOk   ? "Đã cấp quyền ✓" : "Chưa cấp quyền (tự cấp khi Start)");
        tvScreenStatus.setTextColor(screenOk  ? 0xFF00E5A0 : 0xFF4A4A6A);
    }

    private void startStatsUpdater() {
        statsUpdater = new Runnable() {
            @Override
            public void run() {
                updatePermissionStatus();
                tvRequestCount.setText(String.valueOf(HttpServerService.totalRequests));
                tvScreenshotCount.setText(String.valueOf(HttpServerService.totalScreenshots));
                tvClickCount.setText(String.valueOf(HttpServerService.totalClicks));
                uiHandler.postDelayed(this, 1500);
            }
        };
        uiHandler.post(statsUpdater);
    }

    private void startHelper() {
        if (!Settings.canDrawOverlays(this)) {
            Toast.makeText(this, "Cần cấp quyền Overlay trước!", Toast.LENGTH_LONG).show();
            startActivity(new Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                Uri.parse("package:" + getPackageName())));
            return;
        }
        if (AutoClickService.instance == null) {
            Toast.makeText(this, "Cần bật Accessibility Service trước!", Toast.LENGTH_LONG).show();
            startActivity(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS));
            return;
        }
        addLog("Đang xin quyền chụp màn hình...");
        startActivityForResult(
            projectionManager.createScreenCaptureIntent(), REQUEST_MEDIA_PROJECTION);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == REQUEST_MEDIA_PROJECTION) {
            if (resultCode == Activity.RESULT_OK && data != null) {
                HttpServerService.projectionResultCode = resultCode;
                HttpServerService.projectionData       = data;
                startForegroundService(new Intent(this, HttpServerService.class));
                setServerRunning(true);
                addLog("✓ HTTP Server đang chạy tại :7788");
                addLog("✓ Python bot có thể kết nối ngay!");
                addLog("✓ Tất cả endpoint sẵn sàng");
            } else {
                addLog("✗ Người dùng từ chối quyền chụp màn hình.");
                Toast.makeText(this, "Cần cấp quyền chụp màn hình để hoạt động!", Toast.LENGTH_LONG).show();
            }
        }
    }

    private void stopHelper() {
        stopService(new Intent(this, HttpServerService.class));
        HttpServerService.isScreenCaptureReady = false;
        setServerRunning(false);
        addLog("■ Server đã dừng.");
    }

    private void setServerRunning(boolean running) {
        if (running) {
            tvStatus.setText("Đang chạy — Port 7788");
            tvStatus.setTextColor(0xFF00E5A0);
            tvRunBadge.setText("● RUN");
            tvRunBadge.setTextColor(0xFF00E5A0);
            tvRunBadge.setBackgroundResource(R.drawable.badge_run);
        } else {
            tvStatus.setText("Đang dừng");
            tvStatus.setTextColor(0xFFFF5252);
            tvRunBadge.setText("● STOP");
            tvRunBadge.setTextColor(0xFFFF5252);
            tvRunBadge.setBackgroundResource(R.drawable.badge_stop);
        }
        updatePermissionStatus();
    }

    public static void addLog(String msg) {
        if (instance == null) return;
        instance.uiHandler.post(() -> {
            String time = new java.text.SimpleDateFormat("HH:mm:ss",
                java.util.Locale.getDefault()).format(new java.util.Date());
            logBuilder.insert(0, "[" + time + "] " + msg + "\n");
            if (logBuilder.length() > 6000) logBuilder.setLength(6000);
            if (instance != null && instance.tvLog != null)
                instance.tvLog.setText(logBuilder.toString());
        });
    }
}

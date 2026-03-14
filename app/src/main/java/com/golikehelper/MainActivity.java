package com.golikehelper;

import android.app.Activity;
import android.content.Intent;
import android.media.projection.MediaProjectionManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.provider.Settings;
import android.widget.Button;
import android.widget.TextView;
import android.widget.Toast;
import androidx.appcompat.app.AppCompatActivity;

public class MainActivity extends AppCompatActivity {

    private static final int REQUEST_MEDIA_PROJECTION = 1001;
    private TextView tvStatus, tvLog, tvAccessStatus;
    private MediaProjectionManager projectionManager;

    public static MainActivity instance;
    public static StringBuilder logBuilder = new StringBuilder();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        instance = this;
        setContentView(R.layout.activity_main);

        tvStatus       = findViewById(R.id.tvStatus);
        tvLog          = findViewById(R.id.tvLog);
        tvAccessStatus = findViewById(R.id.tvAccessStatus);

        projectionManager = (MediaProjectionManager)
            getSystemService(MEDIA_PROJECTION_SERVICE);

        findViewById(R.id.btnStart).setOnClickListener(v -> startHelper());
        findViewById(R.id.btnStop).setOnClickListener(v -> stopHelper());
        findViewById(R.id.btnClearLog).setOnClickListener(v -> {
            logBuilder.setLength(0);
            tvLog.setText("Log da xoa.\n");
        });
        findViewById(R.id.btnAccessibility).setOnClickListener(v ->
            startActivity(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)));
        findViewById(R.id.btnOverlay).setOnClickListener(v ->
            startActivity(new Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                Uri.parse("package:" + getPackageName()))));

        findViewById(R.id.btnAppInfo).setOnClickListener(v -> openAppInfo());

        addLog("=== GoLike Helper khoi dong ===");
        addLog("Dang cho lenh Start...");
    }

    private void openAppInfo() {
        try {
            Intent intent = new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS);
            intent.setData(Uri.parse("package:" + getPackageName()));
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            startActivity(intent);
            addLog("Mo App Info thanh cong.");
            addLog("Nhan menu 3 cham → 'Cho phep cai dat bi han che'");
        } catch (Exception e) {
            Toast.makeText(this, "Khong the mo App Info: " + e.getMessage(), Toast.LENGTH_LONG).show();
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        boolean accessOk = AutoClickService.instance != null;
        tvAccessStatus.setText(accessOk
            ? "Accessibility: Da kich hoat ✓"
            : "Accessibility: Chua kich hoat ✗");
        tvAccessStatus.setTextColor(accessOk ? 0xFF3fb950 : 0xFFf85149);

        TextView tvOverlay = findViewById(R.id.tvOverlayStatus);
        if (tvOverlay != null) {
            boolean overlayOk = Settings.canDrawOverlays(this);
            tvOverlay.setText(overlayOk
                ? "Overlay: Da cap quyen ✓"
                : "Overlay: Chua cap quyen ✗");
            tvOverlay.setTextColor(overlayOk ? 0xFF3fb950 : 0xFFf85149);
        }
    }

    private void startHelper() {
        if (!Settings.canDrawOverlays(this)) {
            Toast.makeText(this, "Cap quyen 'Hien thi tren ung dung khac' truoc!", Toast.LENGTH_LONG).show();
            return;
        }
        if (AutoClickService.instance == null) {
            Toast.makeText(this, "Bat Accessibility Service trong Cai dat truoc!", Toast.LENGTH_LONG).show();
            return;
        }
        addLog("Dang xin quyen chup man hinh...");
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
                tvStatus.setText("Dang chay - Port 7788");
                tvStatus.setTextColor(0xFF3fb950);
                addLog("HTTP Server da bat tai :7788");
                addLog("Python bot co the ket noi ngay bay gio!");
            } else {
                addLog("Nguoi dung tu choi quyen chup man hinh.");
            }
        }
    }

    private void stopHelper() {
        stopService(new Intent(this, HttpServerService.class));
        tvStatus.setText("Dang dung");
        tvStatus.setTextColor(0xFFf85149);
        addLog("Server da dung.");
    }

    public static void addLog(String msg) {
        if (instance == null) return;
        instance.runOnUiThread(() -> {
            String time = java.text.DateFormat.getTimeInstance().format(new java.util.Date());
            logBuilder.insert(0, "[" + time + "] " + msg + "\n");
            if (logBuilder.length() > 4000) logBuilder.setLength(4000);
            if (instance.tvLog != null) instance.tvLog.setText(logBuilder.toString());
        });
    }
}

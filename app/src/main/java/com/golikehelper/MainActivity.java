package com.golikehelper;

import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.media.projection.MediaProjectionManager;
import android.net.Uri;
import android.os.Bundle;
import android.provider.Settings;
import android.widget.Button;
import android.widget.EditText;
import android.widget.TextView;
import android.widget.Toast;
import androidx.appcompat.app.AppCompatActivity;

public class MainActivity extends AppCompatActivity {

    private static final int REQUEST_MEDIA_PROJECTION = 1001;
    private static final String PREFS_NAME = "ShopeeCredentials";

    private TextView tvStatus, tvLog, tvAccessStatus, tvCredStatus;
    private EditText etAuth, etTToken, etShopId;
    private MediaProjectionManager projectionManager;

    public static MainActivity instance;
    public static StringBuilder logBuilder = new StringBuilder();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        instance = this;
        setContentView(R.layout.activity_main);

        tvStatus      = findViewById(R.id.tvStatus);
        tvLog         = findViewById(R.id.tvLog);
        tvAccessStatus = findViewById(R.id.tvAccessStatus);
        tvCredStatus  = findViewById(R.id.tvCredStatus);
        etAuth        = findViewById(R.id.etAuth);
        etTToken      = findViewById(R.id.etTToken);
        etShopId      = findViewById(R.id.etShopId);

        projectionManager = (MediaProjectionManager)
            getSystemService(MEDIA_PROJECTION_SERVICE);

        loadCredentials();

        findViewById(R.id.btnSaveCredentials).setOnClickListener(v -> saveCredentials());
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
        findViewById(R.id.btnAppInfo).setOnClickListener(v -> {
            Intent intent = new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS);
            intent.setData(Uri.parse("package:" + getPackageName()));
            startActivity(intent);
        });

        addLog("=== GoLike Helper khoi dong ===");
        addLog("Dang cho lenh Start...");
    }

    @Override
    protected void onResume() {
        super.onResume();
        boolean accessOk = AutoClickService.instance != null;
        tvAccessStatus.setText(accessOk
            ? "Accessibility: Da kich hoat \u2713"
            : "Accessibility: Chua kich hoat \u2717");
        tvAccessStatus.setTextColor(accessOk ? 0xFF3fb950 : 0xFFf85149);
    }

    private void saveCredentials() {
        String auth   = etAuth.getText().toString().trim();
        String tToken = etTToken.getText().toString().trim();
        String shopId = etShopId.getText().toString().trim();

        if (auth.isEmpty() || tToken.isEmpty() || shopId.isEmpty()) {
            Toast.makeText(this, "Vui long dien day du Auth, T Token va ID Shop!", Toast.LENGTH_SHORT).show();
            return;
        }

        SharedPreferences prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
        prefs.edit()
            .putString("auth", auth)
            .putString("t_token", tToken)
            .putString("shop_id", shopId)
            .apply();

        tvCredStatus.setText("Da luu: Shop ID " + shopId + " \u2713");
        tvCredStatus.setTextColor(0xFF3fb950);
        addLog("Da luu thong tin Shopee: shop_id=" + shopId);
        Toast.makeText(this, "Da luu thong tin thanh cong!", Toast.LENGTH_SHORT).show();
    }

    private void loadCredentials() {
        SharedPreferences prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
        String auth   = prefs.getString("auth", "");
        String tToken = prefs.getString("t_token", "");
        String shopId = prefs.getString("shop_id", "");

        etAuth.setText(auth);
        etTToken.setText(tToken);
        etShopId.setText(shopId);

        if (!shopId.isEmpty()) {
            tvCredStatus.setText("Da luu: Shop ID " + shopId + " \u2713");
            tvCredStatus.setTextColor(0xFF3fb950);
        } else {
            tvCredStatus.setText("Chua luu thong tin");
            tvCredStatus.setTextColor(0xFF8b949e);
        }
    }

    public static String getSavedCredentialsJson() {
        if (instance == null) return "{\"error\":\"app_not_ready\"}";
        SharedPreferences prefs = instance.getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
        String auth   = prefs.getString("auth", "");
        String tToken = prefs.getString("t_token", "");
        String shopId = prefs.getString("shop_id", "");
        return "{\"auth\":\"" + auth + "\",\"t\":\"" + tToken + "\",\"shop_id\":\"" + shopId + "\"}";
    }

    private void startHelper() {
        String shopId = etShopId.getText().toString().trim();
        if (shopId.isEmpty()) {
            Toast.makeText(this, "Vui long nhap va luu thong tin Shopee truoc!", Toast.LENGTH_LONG).show();
            return;
        }
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

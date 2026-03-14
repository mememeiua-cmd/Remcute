package com.golikehelper;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.PixelFormat;
import android.graphics.Point;
import android.hardware.display.DisplayManager;
import android.hardware.display.VirtualDisplay;
import android.media.Image;
import android.media.ImageReader;
import android.media.projection.MediaProjection;
import android.media.projection.MediaProjectionManager;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.util.Base64;
import android.view.WindowManager;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.*;
import java.net.*;
import java.nio.ByteBuffer;

public class HttpServerService extends Service {

    public static int    projectionResultCode;
    public static Intent projectionData;
    public static int    totalClicks = 0;

    private static final int    PORT       = 7788;
    private static final String CHANNEL_ID = "GoLikeHelperChannel";

    private ServerSocket    serverSocket;
    private Thread          serverThread;
    private MediaProjection mediaProjection;
    private ImageReader     imageReader;
    private VirtualDisplay  virtualDisplay;
    private int screenW, screenH, screenDpi;

    // ─────────────────────────────────────────
    //  Lifecycle
    // ─────────────────────────────────────────

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        startForeground(1, buildNotification());
        initScreenCapture();
        startHttpServer();
        return START_STICKY;
    }

    @Override
    public void onDestroy() {
        super.onDestroy();
        try { if (serverSocket != null) serverSocket.close(); } catch (Exception ignored) {}
        if (virtualDisplay  != null) virtualDisplay.release();
        if (mediaProjection != null) mediaProjection.stop();
        if (imageReader     != null) imageReader.close();
        MainActivity.addLog("Service da dung.");
    }

    @Override
    public IBinder onBind(Intent intent) { return null; }

    // ─────────────────────────────────────────
    //  Screen capture setup  (Android 15 safe)
    // ─────────────────────────────────────────

    @SuppressWarnings("deprecation")
    private void initScreenCapture() {
        MediaProjectionManager mgr =
            (MediaProjectionManager) getSystemService(Context.MEDIA_PROJECTION_SERVICE);
        mediaProjection = mgr.getMediaProjection(projectionResultCode, projectionData);

        // Android 15: must register callback before using MediaProjection
        mediaProjection.registerCallback(new MediaProjection.Callback() {
            @Override
            public void onStop() {
                MainActivity.addLog("MediaProjection da dung.");
                if (virtualDisplay != null) { virtualDisplay.release(); virtualDisplay = null; }
                if (imageReader   != null) { imageReader.close();       imageReader   = null; }
            }
        }, new Handler(Looper.getMainLooper()));

        // Get screen dimensions - compatible with all Android versions
        WindowManager wm = (WindowManager) getSystemService(Context.WINDOW_SERVICE);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            android.util.DisplayMetrics dm = getResources().getDisplayMetrics();
            android.view.WindowMetrics windowMetrics = wm.getCurrentWindowMetrics();
            android.graphics.Rect bounds = windowMetrics.getBounds();
            screenW   = bounds.width();
            screenH   = bounds.height();
            screenDpi = dm.densityDpi;
        } else {
            android.util.DisplayMetrics metrics = new android.util.DisplayMetrics();
            wm.getDefaultDisplay().getRealMetrics(metrics);
            screenW   = metrics.widthPixels;
            screenH   = metrics.heightPixels;
            screenDpi = metrics.densityDpi;
        }

        imageReader = ImageReader.newInstance(screenW, screenH, PixelFormat.RGBA_8888, 2);
        virtualDisplay = mediaProjection.createVirtualDisplay(
            "GoLikeHelper", screenW, screenH, screenDpi,
            DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR,
            imageReader.getSurface(), null, null);

        MainActivity.addLog("Screen capture san sang: " + screenW + "x" + screenH);
    }

    // ─────────────────────────────────────────
    //  HTTP Server
    // ─────────────────────────────────────────

    private void startHttpServer() {
        serverThread = new Thread(() -> {
            try {
                serverSocket = new ServerSocket(PORT);
                MainActivity.addLog("HTTP Server lang nghe tren port " + PORT);
                while (!serverSocket.isClosed()) {
                    Socket client = serverSocket.accept();
                    new Thread(() -> handleClient(client)).start();
                }
            } catch (IOException e) {
                if (serverSocket != null && !serverSocket.isClosed())
                    MainActivity.addLog("Server loi: " + e.getMessage());
            }
        });
        serverThread.setDaemon(true);
        serverThread.start();
    }

    private void handleClient(Socket client) {
        try {
            BufferedReader in  = new BufferedReader(new InputStreamReader(client.getInputStream()));
            OutputStream   out = client.getOutputStream();

            String requestLine = in.readLine();
            if (requestLine == null || requestLine.isEmpty()) { client.close(); return; }
            String[] parts  = requestLine.split(" ");
            String   method = parts[0];
            String   path   = parts.length > 1 ? parts[1] : "/";

            int contentLength = 0;
            String header;
            while ((header = in.readLine()) != null && !header.isEmpty()) {
                if (header.toLowerCase().startsWith("content-length:"))
                    contentLength = Integer.parseInt(header.split(":")[1].trim());
            }

            String body = "";
            if (contentLength > 0) {
                char[] buf = new char[contentLength];
                in.read(buf, 0, contentLength);
                body = new String(buf);
            }

            MainActivity.addLog(method + " " + path);

            String response;
            switch (path) {
                case "/ping":
                    response = ok("{\"status\":\"ok\",\"app\":\"GoLike Helper\",\"port\":"
                        + PORT + ",\"total_clicks\":" + totalClicks + "}");
                    break;
                case "/screenshot":
                    response = handleScreenshot();
                    break;
                case "/tap":
                    response = handleTap(body);
                    break;
                case "/longpress":
                    response = handleLongPress(body);
                    break;
                case "/click":
                    response = handleClick(body);
                    break;
                case "/swipe":
                    response = handleSwipe(body);
                    break;
                case "/credentials":
                    response = ok(MainActivity.getSavedCredentialsJson());
                    MainActivity.addLog("Bot doc thong tin credentials");
                    break;
                default:
                    response = "HTTP/1.1 404 Not Found\r\nContent-Length:2\r\n\r\n{}";
            }

            out.write(response.getBytes("UTF-8"));
            out.flush();
            client.close();
        } catch (Exception e) {
            MainActivity.addLog("Client error: " + e.getMessage());
        }
    }

    // ─────────────────────────────────────────
    //  Handlers
    // ─────────────────────────────────────────

    private String handleScreenshot() {
        try {
            if (imageReader == null)
                return ok("{\"error\":\"screen_capture_not_ready\"}");

            Image image = null;
            for (int i = 0; i < 5; i++) {
                image = imageReader.acquireLatestImage();
                if (image != null) break;
                Thread.sleep(100);
            }
            if (image == null)
                return ok("{\"error\":\"no_frame_available\"}");

            Image.Plane[] planes    = image.getPlanes();
            ByteBuffer    buffer    = planes[0].getBuffer();
            int pixelStride         = planes[0].getPixelStride();
            int rowStride           = planes[0].getRowStride();
            int rowPadding          = rowStride - pixelStride * screenW;

            Bitmap fullBitmap = Bitmap.createBitmap(
                screenW + rowPadding / pixelStride,
                screenH, Bitmap.Config.ARGB_8888);
            fullBitmap.copyPixelsFromBuffer(buffer);
            image.close();

            Bitmap cropped = Bitmap.createBitmap(fullBitmap, 0, 0, screenW, screenH);
            fullBitmap.recycle();

            int tw = screenW / 2, th = screenH / 2;
            Bitmap scaled = Bitmap.createScaledBitmap(cropped, tw, th, true);
            cropped.recycle();

            ByteArrayOutputStream baos = new ByteArrayOutputStream();
            scaled.compress(Bitmap.CompressFormat.JPEG, 75, baos);
            scaled.recycle();

            String b64 = Base64.encodeToString(baos.toByteArray(), Base64.NO_WRAP);
            MainActivity.addLog("Screenshot: " + tw + "x" + th + " " + (b64.length()/1024) + "KB");
            return ok("{\"image\":\"" + b64 + "\",\"width\":" + tw + ",\"height\":" + th + "}");

        } catch (Exception e) {
            return ok("{\"error\":\"" + e.getMessage().replace("\"","'") + "\"}");
        }
    }

    private String handleTap(String body) {
        try {
            JSONObject json = new JSONObject(body);
            float x = (float) json.getDouble("x");
            float y = (float) json.getDouble("y");
            if (AutoClickService.instance == null)
                return ok("{\"error\":\"accessibility_service_not_running\"}");
            boolean ok = AutoClickService.instance.performClick(x, y);
            return ok("{\"status\":\"" + (ok ? "ok" : "failed") + "\",\"x\":" + x + ",\"y\":" + y + "}");
        } catch (Exception e) {
            return ok("{\"error\":\"" + e.getMessage() + "\"}");
        }
    }

    private String handleLongPress(String body) {
        try {
            JSONObject json = new JSONObject(body);
            float x        = (float) json.getDouble("x");
            float y        = (float) json.getDouble("y");
            long  duration = json.optLong("duration", 800);
            if (AutoClickService.instance == null)
                return ok("{\"error\":\"accessibility_service_not_running\"}");
            boolean ok = AutoClickService.instance.performLongClick(x, y, duration);
            return ok("{\"status\":\"" + (ok ? "ok" : "failed") + "\",\"x\":" + x + ",\"y\":" + y + "}");
        } catch (Exception e) {
            return ok("{\"error\":\"" + e.getMessage() + "\"}");
        }
    }

    private String handleClick(String body) {
        try {
            JSONArray arr = new JSONArray(body);
            if (AutoClickService.instance == null)
                return ok("{\"error\":\"accessibility_service_not_running\"}");
            int count = 0;
            for (int i = 0; i < arr.length(); i++) {
                JSONObject pt = arr.getJSONObject(i);
                float x = (float) pt.getDouble("x");
                float y = (float) pt.getDouble("y");
                long  delay = pt.optLong("delay", 400);
                AutoClickService.instance.performClick(x, y);
                Thread.sleep(delay);
                count++;
            }
            return ok("{\"status\":\"ok\",\"clicked\":" + count + "}");
        } catch (Exception e) {
            return ok("{\"error\":\"" + e.getMessage() + "\"}");
        }
    }

    private String handleSwipe(String body) {
        try {
            JSONObject json = new JSONObject(body);
            float x1 = (float) json.getDouble("x1");
            float y1 = (float) json.getDouble("y1");
            float x2 = (float) json.getDouble("x2");
            float y2 = (float) json.getDouble("y2");
            long  ms = json.optLong("duration", 300);
            if (AutoClickService.instance == null)
                return ok("{\"error\":\"accessibility_service_not_running\"}");
            boolean result = AutoClickService.instance.performSwipe(x1, y1, x2, y2, ms);
            return ok("{\"status\":\"" + (result ? "ok" : "failed") + "\"}");
        } catch (Exception e) {
            return ok("{\"error\":\"" + e.getMessage() + "\"}");
        }
    }

    // ─────────────────────────────────────────
    //  Helpers
    // ─────────────────────────────────────────

    private String ok(String json) {
        byte[] bytes = new byte[0];
        try { bytes = json.getBytes("UTF-8"); } catch (Exception ignored) {}
        return "HTTP/1.1 200 OK\r\n"
             + "Content-Type: application/json; charset=utf-8\r\n"
             + "Content-Length: " + bytes.length + "\r\n"
             + "Access-Control-Allow-Origin: *\r\n"
             + "\r\n"
             + json;
    }

    private Notification buildNotification() {
        NotificationChannel ch = new NotificationChannel(
            CHANNEL_ID, "GoLike Helper", NotificationManager.IMPORTANCE_LOW);
        ((NotificationManager) getSystemService(NOTIFICATION_SERVICE))
            .createNotificationChannel(ch);
        return new Notification.Builder(this, CHANNEL_ID)
            .setContentTitle("GoLike Helper")
            .setContentText("HTTP Server dang chay tai port " + PORT)
            .setSmallIcon(android.R.drawable.ic_menu_camera)
            .build();
    }
}

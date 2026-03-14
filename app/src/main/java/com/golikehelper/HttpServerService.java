package com.golikehelper;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.PixelFormat;
import android.hardware.display.DisplayManager;
import android.hardware.display.VirtualDisplay;
import android.media.Image;
import android.media.ImageReader;
import android.media.projection.MediaProjection;
import android.media.projection.MediaProjectionManager;
import android.os.IBinder;
import android.util.Base64;
import android.util.DisplayMetrics;
import android.view.WindowManager;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.*;
import java.net.*;
import java.nio.ByteBuffer;

public class HttpServerService extends Service {

    public static int    projectionResultCode;
    public static Intent projectionData;
    public static boolean isScreenCaptureReady = false;

    public static volatile int totalRequests   = 0;
    public static volatile int totalScreenshots = 0;
    public static volatile int totalClicks     = 0;

    private static final int    PORT       = 7788;
    private static final String CHANNEL_ID = "GoLikeHelperChannel";

    private ServerSocket    serverSocket;
    private Thread          serverThread;
    private MediaProjection mediaProjection;
    private ImageReader     imageReader;
    private VirtualDisplay  virtualDisplay;
    private int screenW, screenH, screenDpi;

    // ──────────────────────────────────────────────────────
    //  Lifecycle
    // ──────────────────────────────────────────────────────

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
        isScreenCaptureReady = false;
        try { if (serverSocket != null) serverSocket.close(); } catch (Exception ignored) {}
        if (virtualDisplay  != null) virtualDisplay.release();
        if (mediaProjection != null) mediaProjection.stop();
        if (imageReader     != null) imageReader.close();
        MainActivity.addLog("■ HTTP Service đã dừng.");
    }

    @Override
    public IBinder onBind(Intent intent) { return null; }

    // ──────────────────────────────────────────────────────
    //  Screen Capture Init
    // ──────────────────────────────────────────────────────

    private void initScreenCapture() {
        try {
            MediaProjectionManager mgr =
                (MediaProjectionManager) getSystemService(Context.MEDIA_PROJECTION_SERVICE);
            mediaProjection = mgr.getMediaProjection(projectionResultCode, projectionData);

            mediaProjection.registerCallback(new MediaProjection.Callback() {
                @Override
                public void onStop() {
                    isScreenCaptureReady = false;
                    MainActivity.addLog("! MediaProjection đã dừng.");
                }
            }, null);

            WindowManager   wm      = (WindowManager) getSystemService(Context.WINDOW_SERVICE);
            DisplayMetrics  metrics = new DisplayMetrics();
            wm.getDefaultDisplay().getRealMetrics(metrics);
            screenW   = metrics.widthPixels;
            screenH   = metrics.heightPixels;
            screenDpi = metrics.densityDpi;

            imageReader    = ImageReader.newInstance(screenW, screenH, PixelFormat.RGBA_8888, 3);
            virtualDisplay = mediaProjection.createVirtualDisplay(
                "GoLikeHelper", screenW, screenH, screenDpi,
                DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR,
                imageReader.getSurface(), null, null);

            isScreenCaptureReady = true;
            MainActivity.addLog("✓ Screen capture: " + screenW + "×" + screenH);
        } catch (Exception e) {
            MainActivity.addLog("✗ Lỗi khởi tạo screen capture: " + e.getMessage());
        }
    }

    // ──────────────────────────────────────────────────────
    //  HTTP Server
    // ──────────────────────────────────────────────────────

    private void startHttpServer() {
        serverThread = new Thread(() -> {
            try {
                serverSocket = new ServerSocket();
                serverSocket.setReuseAddress(true);
                serverSocket.bind(new InetSocketAddress(PORT));
                MainActivity.addLog("✓ HTTP Server lắng nghe tại :" + PORT);
                while (!serverSocket.isClosed()) {
                    Socket client = serverSocket.accept();
                    new Thread(() -> handleClient(client)).start();
                }
            } catch (IOException e) {
                if (serverSocket != null && !serverSocket.isClosed())
                    MainActivity.addLog("✗ Server lỗi: " + e.getMessage());
            }
        });
        serverThread.setDaemon(true);
        serverThread.start();
    }

    private void handleClient(Socket client) {
        try {
            client.setSoTimeout(10000);
            BufferedReader in  = new BufferedReader(new InputStreamReader(client.getInputStream()));
            OutputStream   out = client.getOutputStream();

            String requestLine = in.readLine();
            if (requestLine == null || requestLine.isEmpty()) { client.close(); return; }

            String[] parts  = requestLine.split(" ");
            String   method = parts[0];
            String   path   = parts.length > 1 ? parts[1] : "/";

            // Strip query string from path
            int qi = path.indexOf('?');
            if (qi >= 0) path = path.substring(0, qi);

            int contentLength = 0;
            String header;
            while ((header = in.readLine()) != null && !header.isEmpty()) {
                String lh = header.toLowerCase();
                if (lh.startsWith("content-length:"))
                    contentLength = Integer.parseInt(header.split(":", 2)[1].trim());
            }

            String body = "";
            if (contentLength > 0) {
                char[] buf = new char[contentLength];
                int read = 0;
                while (read < contentLength) {
                    int r = in.read(buf, read, contentLength - read);
                    if (r < 0) break;
                    read += r;
                }
                body = new String(buf, 0, read);
            }

            totalRequests++;

            String response = route(method, path, body);
            out.write(response.getBytes("UTF-8"));
            out.flush();
            client.close();
        } catch (Exception e) {
            try { client.close(); } catch (Exception ignored) {}
        }
    }

    private String route(String method, String path, String body) {
        switch (path) {

            // ── GET /ping ──────────────────────────────────
            case "/ping":
                return json("{\"status\":\"ok\"," +
                    "\"app\":\"GoLike Helper\"," +
                    "\"version\":\"2.0\"," +
                    "\"port\":" + PORT + "," +
                    "\"screen_ready\":" + isScreenCaptureReady + "," +
                    "\"accessibility\":" + (AutoClickService.instance != null) + "," +
                    "\"requests\":" + totalRequests + "," +
                    "\"screenshots\":" + totalScreenshots + "," +
                    "\"clicks\":" + totalClicks + "}");

            // ── POST /screenshot ───────────────────────────
            case "/screenshot":
                return handleScreenshot(body);

            // ── POST /tap ──────────────────────────────────
            case "/tap":
                return handleTap(body);

            // ── POST /click ────────────────────────────────
            case "/click":
                return handleClick(body);

            // ── POST /longpress ────────────────────────────
            case "/longpress":
                return handleLongPress(body);

            // ── POST /swipe ────────────────────────────────
            case "/swipe":
                return handleSwipe(body);

            // ── POST /solve_captcha ────────────────────────
            case "/solve_captcha":
                return handleSolveCaptcha(body);

            // ── GET /status ────────────────────────────────
            case "/status":
                return json("{\"running\":true," +
                    "\"screen_ready\":" + isScreenCaptureReady + "," +
                    "\"accessibility\":" + (AutoClickService.instance != null) + "," +
                    "\"screen_w\":" + screenW + "," +
                    "\"screen_h\":" + screenH + "," +
                    "\"requests\":" + totalRequests + "," +
                    "\"screenshots\":" + totalScreenshots + "," +
                    "\"clicks\":" + totalClicks + "}");

            default:
                return "HTTP/1.1 404 Not Found\r\n" +
                    "Content-Type: application/json\r\n" +
                    "Content-Length: 27\r\n" +
                    "Access-Control-Allow-Origin: *\r\n\r\n" +
                    "{\"error\":\"endpoint not found\"}";
        }
    }

    // ──────────────────────────────────────────────────────
    //  Handlers
    // ──────────────────────────────────────────────────────

    private String handleScreenshot(String body) {
        if (!isScreenCaptureReady)
            return json("{\"error\":\"screen_capture_not_ready\"}");
        try {
            // Parse optional quality param
            int quality = 80;
            int scaleDiv = 2;
            if (!body.isEmpty()) {
                try {
                    JSONObject p = new JSONObject(body);
                    quality  = p.optInt("quality", 80);
                    scaleDiv = p.optInt("scale_div", 2);
                } catch (Exception ignored) {}
            }
            if (quality  < 10)  quality  = 10;
            if (quality  > 100) quality  = 100;
            if (scaleDiv < 1)   scaleDiv = 1;
            if (scaleDiv > 4)   scaleDiv = 4;

            Image image = null;
            for (int i = 0; i < 8; i++) {
                image = imageReader.acquireLatestImage();
                if (image != null) break;
                Thread.sleep(80);
            }
            if (image == null)
                return json("{\"error\":\"no_frame_available\"}");

            Image.Plane[] planes     = image.getPlanes();
            ByteBuffer    buffer     = planes[0].getBuffer();
            int           pixelStride = planes[0].getPixelStride();
            int           rowStride  = planes[0].getRowStride();
            int           rowPadding = rowStride - pixelStride * screenW;

            Bitmap full = Bitmap.createBitmap(
                screenW + rowPadding / pixelStride, screenH, Bitmap.Config.ARGB_8888);
            full.copyPixelsFromBuffer(buffer);
            image.close();

            Bitmap cropped = Bitmap.createBitmap(full, 0, 0, screenW, screenH);
            full.recycle();

            int tw = screenW / scaleDiv;
            int th = screenH / scaleDiv;
            Bitmap scaled = Bitmap.createScaledBitmap(cropped, tw, th, true);
            cropped.recycle();

            ByteArrayOutputStream baos = new ByteArrayOutputStream();
            scaled.compress(Bitmap.CompressFormat.JPEG, quality, baos);
            scaled.recycle();

            String b64 = Base64.encodeToString(baos.toByteArray(), Base64.NO_WRAP);
            totalScreenshots++;
            MainActivity.addLog("📷 Screenshot " + tw + "×" + th + " | " + (b64.length() / 1024) + "KB");
            return json("{\"image\":\"" + b64 + "\"," +
                "\"width\":" + tw + "," +
                "\"height\":" + th + "," +
                "\"quality\":" + quality + "}");

        } catch (Exception e) {
            return json("{\"error\":\"" + esc(e.getMessage()) + "\"}");
        }
    }

    private String handleTap(String body) {
        try {
            JSONObject json = new JSONObject(body);
            float x = (float) json.getDouble("x");
            float y = (float) json.getDouble("y");
            if (AutoClickService.instance == null)
                return json("{\"error\":\"accessibility_service_not_running\"}");
            boolean ok = AutoClickService.instance.performClick(x, y);
            return json("{\"status\":\"" + (ok ? "ok" : "failed") + "\"," +
                "\"x\":" + x + ",\"y\":" + y + "}");
        } catch (Exception e) {
            return json("{\"error\":\"" + esc(e.getMessage()) + "\"}");
        }
    }

    private String handleClick(String body) {
        try {
            JSONArray arr = new JSONArray(body);
            if (AutoClickService.instance == null)
                return json("{\"error\":\"accessibility_service_not_running\"}");
            int count = 0;
            for (int i = 0; i < arr.length(); i++) {
                JSONObject pt  = arr.getJSONObject(i);
                float      x   = (float) pt.getDouble("x");
                float      y   = (float) pt.getDouble("y");
                long       del = pt.optLong("delay", 400);
                AutoClickService.instance.performClick(x, y);
                Thread.sleep(del);
                count++;
            }
            return json("{\"status\":\"ok\",\"clicked\":" + count + "}");
        } catch (Exception e) {
            return json("{\"error\":\"" + esc(e.getMessage()) + "\"}");
        }
    }

    private String handleLongPress(String body) {
        try {
            JSONObject p = new JSONObject(body);
            float x   = (float) p.getDouble("x");
            float y   = (float) p.getDouble("y");
            long  dur = p.optLong("duration", 800);
            if (AutoClickService.instance == null)
                return json("{\"error\":\"accessibility_service_not_running\"}");
            boolean ok = AutoClickService.instance.performLongClick(x, y, dur);
            return json("{\"status\":\"" + (ok ? "ok" : "failed") + "\"}");
        } catch (Exception e) {
            return json("{\"error\":\"" + esc(e.getMessage()) + "\"}");
        }
    }

    private String handleSwipe(String body) {
        try {
            JSONObject p = new JSONObject(body);
            float x1  = (float) p.getDouble("x1");
            float y1  = (float) p.getDouble("y1");
            float x2  = (float) p.getDouble("x2");
            float y2  = (float) p.getDouble("y2");
            long  dur = p.optLong("duration", 300);
            if (AutoClickService.instance == null)
                return json("{\"error\":\"accessibility_service_not_running\"}");
            boolean ok = AutoClickService.instance.performSwipe(x1, y1, x2, y2, dur);
            return json("{\"status\":\"" + (ok ? "ok" : "failed") + "\"}");
        } catch (Exception e) {
            return json("{\"error\":\"" + esc(e.getMessage()) + "\"}");
        }
    }

    /**
     * /solve_captcha — chụp màn hình → gửi Gemini → click kết quả
     * Body JSON:
     * {
     *   "gemini_key": "AIza...",
     *   "prompt": "optional override prompt",
     *   "quality": 85,
     *   "click_results": true,
     *   "grid_top": 200, "grid_left": 30, "grid_w": 320, "grid_h": 320
     * }
     */
    private String handleSolveCaptcha(String body) {
        try {
            if (!isScreenCaptureReady)
                return json("{\"error\":\"screen_capture_not_ready\"}");
            if (AutoClickService.instance == null)
                return json("{\"error\":\"accessibility_service_not_running\"}");

            JSONObject p          = new JSONObject(body);
            String     geminiKey  = p.optString("gemini_key", "");
            boolean    doClick    = p.optBoolean("click_results", true);
            int        quality    = p.optInt("quality", 85);
            double     gridTop    = p.optDouble("grid_top",   -1);
            double     gridLeft   = p.optDouble("grid_left",  -1);
            double     gridW      = p.optDouble("grid_w",     -1);
            double     gridH      = p.optDouble("grid_h",     -1);

            if (geminiKey.isEmpty())
                return json("{\"error\":\"gemini_key required\"}");

            // 1. Take screenshot
            Image image = null;
            for (int i = 0; i < 8; i++) {
                image = imageReader.acquireLatestImage();
                if (image != null) break;
                Thread.sleep(80);
            }
            if (image == null) return json("{\"error\":\"no_frame\"}");

            Image.Plane[] planes     = image.getPlanes();
            ByteBuffer    buffer     = planes[0].getBuffer();
            int           pixelStride = planes[0].getPixelStride();
            int           rowStride  = planes[0].getRowStride();
            int           rowPadding = rowStride - pixelStride * screenW;

            Bitmap full = Bitmap.createBitmap(
                screenW + rowPadding / pixelStride, screenH, Bitmap.Config.ARGB_8888);
            full.copyPixelsFromBuffer(buffer);
            image.close();

            Bitmap shot = Bitmap.createBitmap(full, 0, 0, screenW, screenH);
            full.recycle();
            totalScreenshots++;

            // Crop to captcha grid if coordinates provided
            Bitmap toSend = shot;
            if (gridTop >= 0 && gridLeft >= 0 && gridW > 0 && gridH > 0) {
                int cx = Math.max(0, (int) gridLeft);
                int cy = Math.max(0, (int) gridTop);
                int cw = Math.min((int) gridW, screenW - cx);
                int ch = Math.min((int) gridH, screenH - cy);
                if (cw > 50 && ch > 50) {
                    toSend = Bitmap.createBitmap(shot, cx, cy, cw, ch);
                    shot.recycle();
                    shot = null;
                }
            }

            // Scale down
            int tw = toSend.getWidth() / 2;
            int th = toSend.getHeight() / 2;
            if (tw < 100) tw = toSend.getWidth();
            if (th < 100) th = toSend.getHeight();
            Bitmap scaled = Bitmap.createScaledBitmap(toSend, tw, th, true);
            toSend.recycle();
            if (shot != null) shot.recycle();

            ByteArrayOutputStream baos = new ByteArrayOutputStream();
            scaled.compress(Bitmap.CompressFormat.JPEG, quality, baos);
            scaled.recycle();
            String imgB64 = Base64.encodeToString(baos.toByteArray(), Base64.NO_WRAP);

            // 2. Call Gemini
            String geminiUrl = "https://generativelanguage.googleapis.com/v1beta/models/" +
                "gemini-1.5-flash:generateContent?key=" + geminiKey;

            String prompt = p.optString("prompt",
                "Google reCAPTCHA screenshot. Find the 3x3 grid.\n" +
                "1. Read the challenge title\n" +
                "2. Which cells (0-8, left-to-right, top-to-bottom) contain the requested object?\n" +
                "Reply ONLY in this format:\n" +
                "CHALLENGE: <name>\nINDICES: [x,y,z]");

            String geminiBody = "{\"contents\":[{\"parts\":[" +
                "{\"text\":" + JSONObject.quote(prompt) + "}," +
                "{\"inline_data\":{\"mime_type\":\"image/jpeg\",\"data\":\"" + imgB64 + "\"}}" +
                "]}],\"generationConfig\":{\"temperature\":0,\"maxOutputTokens\":80}}";

            java.net.URL url = new java.net.URL(geminiUrl);
            java.net.HttpURLConnection conn = (java.net.HttpURLConnection) url.openConnection();
            conn.setRequestMethod("POST");
            conn.setRequestProperty("Content-Type", "application/json");
            conn.setDoOutput(true);
            conn.setConnectTimeout(10000);
            conn.setReadTimeout(20000);
            try (OutputStream os = conn.getOutputStream()) {
                os.write(geminiBody.getBytes("UTF-8"));
            }

            StringBuilder sb = new StringBuilder();
            try (BufferedReader br = new BufferedReader(
                new InputStreamReader(conn.getInputStream(), "UTF-8"))) {
                String line;
                while ((line = br.readLine()) != null) sb.append(line);
            }

            JSONObject gResp     = new JSONObject(sb.toString());
            String     geminiTxt = "";
            try {
                geminiTxt = gResp.getJSONArray("candidates")
                    .getJSONObject(0).getJSONObject("content")
                    .getJSONArray("parts").getJSONObject(0).getString("text");
            } catch (Exception ex) {
                String errMsg = "";
                if (gResp.has("error"))
                    errMsg = gResp.getJSONObject("error").optString("message", "?");
                return json("{\"error\":\"gemini: " + esc(errMsg) + "\"}");
            }

            // Parse indices
            JSONArray indices = new JSONArray();
            java.util.regex.Matcher m = java.util.regex.Pattern
                .compile("INDICES\\s*:\\s*(\\[[\\d,\\s]*\\])", java.util.regex.Pattern.CASE_INSENSITIVE)
                .matcher(geminiTxt);
            if (m.find()) {
                try { indices = new JSONArray(m.group(1)); } catch (Exception ignored) {}
            }
            if (indices.length() == 0) {
                java.util.regex.Matcher m2 = java.util.regex.Pattern
                    .compile("\\[[\\d, ]+\\]").matcher(geminiTxt);
                if (m2.find()) {
                    try { indices = new JSONArray(m2.group(0)); } catch (Exception ignored) {}
                }
            }

            String challenge = "";
            java.util.regex.Matcher mc = java.util.regex.Pattern
                .compile("CHALLENGE\\s*:\\s*(.+)", java.util.regex.Pattern.CASE_INSENSITIVE)
                .matcher(geminiTxt);
            if (mc.find()) challenge = mc.group(1).trim();

            MainActivity.addLog("🤖 Gemini: \"" + challenge + "\" → " + indices);

            // 3. Click tiles if requested
            JSONArray clickedPts = new JSONArray();
            if (doClick && indices.length() > 0 && gridTop >= 0 && gridLeft >= 0
                && gridW > 0 && gridH > 0) {
                double gT = gridTop  + 75;
                double gL = gridLeft + 8;
                double cW = (gridW - 16) / 3.0;
                double cH = (gridH - 75 - 50) / 3.0;
                for (int i = 0; i < indices.length(); i++) {
                    int idx = indices.getInt(i);
                    if (idx < 0 || idx > 8) continue;
                    float cx = (float)(gL + (idx % 3) * cW + cW / 2);
                    float cy = (float)(gT + (idx / 3) * cH + cH / 2);
                    AutoClickService.instance.performClick(cx, cy);
                    JSONObject pt = new JSONObject();
                    pt.put("x", cx); pt.put("y", cy); pt.put("idx", idx);
                    clickedPts.put(pt);
                    Thread.sleep(350 + (long)(Math.random() * 120));
                }
                if (clickedPts.length() > 0) {
                    // Click Verify button (bottom-right of grid)
                    Thread.sleep(900);
                    float vx = (float)(gridLeft + gridW - 72);
                    float vy = (float)(gridTop  + gridH - 22);
                    AutoClickService.instance.performClick(vx, vy);
                    MainActivity.addLog("✓ Clicked " + clickedPts.length() + " tiles + Verify");
                }
            }

            return json("{\"status\":\"ok\"," +
                "\"challenge\":" + JSONObject.quote(challenge) + "," +
                "\"indices\":" + indices + "," +
                "\"clicked\":" + clickedPts + "," +
                "\"gemini_text\":" + JSONObject.quote(geminiTxt.trim()) + "}");

        } catch (Exception e) {
            MainActivity.addLog("✗ solve_captcha: " + e.getMessage());
            return json("{\"error\":\"" + esc(e.getMessage()) + "\"}");
        }
    }

    // ──────────────────────────────────────────────────────
    //  Helpers
    // ──────────────────────────────────────────────────────

    private String json(String body) {
        byte[] b = new byte[0];
        try { b = body.getBytes("UTF-8"); } catch (Exception ignored) {}
        return "HTTP/1.1 200 OK\r\n"
            + "Content-Type: application/json; charset=utf-8\r\n"
            + "Content-Length: " + b.length + "\r\n"
            + "Access-Control-Allow-Origin: *\r\n"
            + "\r\n"
            + body;
    }

    private String esc(String s) {
        if (s == null) return "null";
        return s.replace("\\", "\\\\").replace("\"", "'").replace("\n", " ");
    }

    private Notification buildNotification() {
        NotificationChannel ch = new NotificationChannel(
            CHANNEL_ID, "GoLike Helper", NotificationManager.IMPORTANCE_LOW);
        ch.setDescription("Dịch vụ chụp màn hình và auto-click");
        ((NotificationManager) getSystemService(NOTIFICATION_SERVICE))
            .createNotificationChannel(ch);

        Intent tapIntent = new Intent(this, MainActivity.class);
        PendingIntent pi = PendingIntent.getActivity(this, 0, tapIntent,
            PendingIntent.FLAG_IMMUTABLE);

        return new Notification.Builder(this, CHANNEL_ID)
            .setContentTitle("GoLike Helper đang chạy")
            .setContentText("HTTP :7788 | Chụp ảnh & Auto-click sẵn sàng")
            .setSmallIcon(android.R.drawable.ic_menu_camera)
            .setContentIntent(pi)
            .setOngoing(true)
            .build();
    }
}

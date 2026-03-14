package com.golike.bot;

import android.animation.AnimatorSet;
import android.animation.ObjectAnimator;
import android.annotation.SuppressLint;
import android.app.AlertDialog;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.view.WindowManager;
import android.webkit.JavascriptInterface;
import android.webkit.PermissionRequest;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.TextView;
import android.widget.Toast;
import androidx.appcompat.app.AppCompatActivity;

public class MainActivity extends AppCompatActivity {

    private WebView webView;
    private View splashView;
    private TextView loadingText;
    private static final int BOT_PORT = 8080;
    private final Handler handler = new Handler(Looper.getMainLooper());

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // Full screen immersive
        getWindow().setFlags(
            WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
            WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS
        );
        getWindow().getDecorView().setSystemUiVisibility(
            View.SYSTEM_UI_FLAG_LAYOUT_STABLE |
            View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
        );

        setContentView(R.layout.activity_bot);

        webView     = findViewById(R.id.webview);
        splashView  = findViewById(R.id.splash);
        loadingText = findViewById(R.id.loading_text);

        // Animate splash elements
        animateSplash();

        setupWebView();

        // Start bot service
        updateLoadingText("Khởi động bot service...");
        Intent svc = new Intent(this, BotService.class);
        svc.putExtra("port", BOT_PORT);
        try { startForegroundService(svc); } catch (Exception e) { startService(svc); }

        // Load URL after server starts
        updateLoadingText("Đang kết nối server...");
        handler.postDelayed(this::loadBot, 2500);
    }

    private void animateSplash() {
        View logo     = findViewById(R.id.logo_emoji);
        View title    = findViewById(R.id.app_title);
        View subtitle = findViewById(R.id.app_subtitle);

        if (logo == null) return;

        // Fade + scale in
        logo.setAlpha(0f); logo.setScaleX(0.5f); logo.setScaleY(0.5f);
        title.setAlpha(0f); title.setTranslationY(30f);
        subtitle.setAlpha(0f); subtitle.setTranslationY(20f);

        ObjectAnimator logoAlpha  = ObjectAnimator.ofFloat(logo,"alpha",0f,1f);
        ObjectAnimator logoScaleX = ObjectAnimator.ofFloat(logo,"scaleX",0.5f,1f);
        ObjectAnimator logoScaleY = ObjectAnimator.ofFloat(logo,"scaleY",0.5f,1f);
        AnimatorSet logoSet = new AnimatorSet();
        logoSet.playTogether(logoAlpha, logoScaleX, logoScaleY);
        logoSet.setDuration(600);
        logoSet.start();

        handler.postDelayed(() -> {
            ObjectAnimator ta = ObjectAnimator.ofFloat(title,"alpha",0f,1f);
            ObjectAnimator ty = ObjectAnimator.ofFloat(title,"translationY",30f,0f);
            AnimatorSet ts = new AnimatorSet(); ts.playTogether(ta,ty); ts.setDuration(400); ts.start();
        }, 400);

        handler.postDelayed(() -> {
            ObjectAnimator sa = ObjectAnimator.ofFloat(subtitle,"alpha",0f,1f);
            ObjectAnimator sy = ObjectAnimator.ofFloat(subtitle,"translationY",20f,0f);
            AnimatorSet ss = new AnimatorSet(); ss.playTogether(sa,sy); ss.setDuration(400); ss.start();
        }, 600);
    }

    private void loadBot() {
        updateLoadingText("Tải giao diện bot...");
        webView.loadUrl("http://localhost:" + BOT_PORT);

        // Hide splash when page loads
        handler.postDelayed(() -> {
            if (splashView != null) {
                ObjectAnimator fadeOut = ObjectAnimator.ofFloat(splashView, "alpha", 1f, 0f);
                fadeOut.setDuration(500);
                fadeOut.addListener(new android.animation.AnimatorListenerAdapter() {
                    @Override
                    public void onAnimationEnd(android.animation.Animator a) {
                        splashView.setVisibility(View.GONE);
                    }
                });
                fadeOut.start();
            }
        }, 4000);
    }

    private void updateLoadingText(String text) {
        handler.post(() -> { if (loadingText != null) loadingText.setText(text); });
    }

    @SuppressLint("SetJavaScriptEnabled")
    private void setupWebView() {
        WebSettings s = webView.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setAllowFileAccess(true);
        s.setAllowContentAccess(true);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setUseWideViewPort(true);
        s.setLoadWithOverviewMode(true);
        s.setCacheMode(WebSettings.LOAD_NO_CACHE);
        s.setUserAgentString(
            "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 " +
            "(KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36"
        );

        webView.addJavascriptInterface(new JsBridge(), "AndroidBridge");
        webView.setBackgroundColor(Color.parseColor("#07070d"));

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest req) {
                String url = req.getUrl().toString();
                if (url.contains("localhost") || url.contains("golike.net") ||
                    url.contains("shopee.vn") || url.contains("lazada.vn")) {
                    return false;
                }
                startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url)));
                return true;
            }

            @Override
            public void onPageFinished(WebView v, String url) {
                super.onPageFinished(v, url);
                if (url.contains("golike.net")) injectInterceptor();
            }
        });

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onPermissionRequest(PermissionRequest req) {
                req.grant(req.getResources());
            }

            @Override
            public boolean onJsAlert(WebView v, String url, String msg, android.webkit.JsResult r) {
                new AlertDialog.Builder(MainActivity.this)
                    .setMessage(msg).setPositiveButton("OK",(d,w)->r.confirm()).show();
                return true;
            }
        });
    }

    private void injectInterceptor() {
        String js =
            "(function(){" +
            "if(window.__glbot)return;" +
            "window.__glbot=true;" +
            "var P=" + BOT_PORT + ";" +
            "var f=window.fetch;" +
            "window.fetch=function(u,o){" +
                "var r=f.apply(this,arguments);" +
                "if(o&&o.body){try{" +
                    "var b=JSON.parse(o.body);" +
                    "if(b.captcha_token&&b.captcha_token.length>50){" +
                        "AndroidBridge.onToken(b.captcha_token);" +
                        "f('http://localhost:'+P+'/token?t='+encodeURIComponent(b.captcha_token));" +
                    "}" +
                "}catch(e){}}" +
                "return r;" +
            "};" +
            "})();";
        webView.evaluateJavascript(js, null);
    }

    class JsBridge {
        @JavascriptInterface
        public void onToken(String token) {
            runOnUiThread(() -> Toast.makeText(
                MainActivity.this, "✓ Token OK!", Toast.LENGTH_SHORT).show());
        }

        @JavascriptInterface
        public void log(String msg) { android.util.Log.d("GLBot", msg); }

        @JavascriptInterface
        public String getVersion() { return "GoLike Bot v9 Android"; }

        @JavascriptInterface
        public void openUrl(String url) {
            runOnUiThread(() -> startActivity(
                new Intent(Intent.ACTION_VIEW, Uri.parse(url))));
        }
    }

    @Override
    public void onBackPressed() {
        if (webView.canGoBack()) webView.goBack();
        else super.onBackPressed();
    }
}

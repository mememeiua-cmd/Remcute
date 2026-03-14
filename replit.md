# GoLike Helper

## Project Overview
Android app (APK) + Python bot system for automated GoLike captcha solving.
- **GoLike Helper App** (APK): Runs an HTTP server on the phone, uses MediaProjection to capture the real screen, and Accessibility Service to perform real clicks. No root required.
- **Python Bot v9** (`golike_bot_v9.py`): Multi-account GoLike bot (Shopee + Lazada) that calls the Android app to solve captchas automatically.

## Architecture

```
┌─────────────────────────────────────────┐
│  GoLike Helper App (APK)                │
│  ├─ HttpServerService (HTTP :7788)      │
│  │   ├─ GET  /ping         → status     │
│  │   ├─ GET  /status       → full info  │
│  │   ├─ POST /screenshot   → JPEG b64   │
│  │   ├─ POST /tap          → 1 click    │
│  │   ├─ POST /click        → multi-click│
│  │   ├─ POST /swipe        → swipe      │
│  │   ├─ POST /longpress    → long tap   │
│  │   └─ POST /solve_captcha → AI solve  │
│  ├─ MediaProjection → real screen shot  │
│  └─ AutoClickService → real tap/swipe   │
└─────────────────────────────────────────┘
         ↕ HTTP localhost:7788 (or ADB forward)
┌─────────────────────────────────────────┐
│  Python Bot v9 (golike_bot_v9.py)       │
│  → helper_ping()     : check app        │
│  → helper_screenshot(): capture screen  │
│  → helper_tap()      : real click       │
│  → helper_click_list(): multi-click     │
│  → helper_solve_captcha(): full AI flow │
│  → get_cap_token()   : browser fallback │
└─────────────────────────────────────────┘
```

## Android App Structure (`app/`)
```
app/src/main/
├─ AndroidManifest.xml                       # Permissions + services
├─ java/com/golikehelper/
│   ├─ MainActivity.java                     # UI + permission management + stats
│   ├─ HttpServerService.java                # HTTP server :7788 + all endpoints
│   └─ AutoClickService.java                 # Accessibility gestures (click/swipe/longpress)
└─ res/
    ├─ layout/activity_main.xml              # Dark-themed UI
    ├─ drawable/                             # card_bg, card_warn, log_bg, badge_*
    ├─ values/strings.xml
    └─ xml/accessibility_service.xml
```

## Python Bot (`golike_bot_v9.py`)
- Multi-account: runs multiple tokens in parallel
- Platforms: Shopee + Lazada
- History: saves to `golike_history.json`
- Helper integration: calls Android APK for real captcha solving
- Browser fallback: reCAPTCHA + Gemini audio solve if APK not available

## Building the APK
1. Open project in Android Studio
2. Build → Generate Signed Bundle/APK → APK
3. Min SDK: 26 (Android 8.0+), Target: 34

## Setup (One-time)
1. Install APK on phone
2. Open app → Grant: Accessibility + Overlay + Screen Capture
3. Tap **▶ KHỞI ĐỘNG SERVER**
4. On PC: `adb forward tcp:7788 tcp:7788`
5. Run: `python golike_bot_v9.py`

# GoLike Bot Android - v9

## Project Overview
Android application that automates GoLike tasks (Shopee, Lazada, TikTok) using a Python bot running in the background via Termux. The app wraps a WebView interface and communicates with a local HTTP server on port 8080 to deliver reCAPTCHA tokens for the bot.

## Architecture
- **Android App**: Java (MainActivity + BotService + BootReceiver)
- **Bot Backend**: Python script (bot.py) running via Termux Python
- **Web UI**: HTML/JS served by Python HTTP server on port 8080
- **AI Captcha**: Google Gemini 1.5 Flash for audio + visual captcha solving
- **CI/CD**: GitHub Actions → builds signed APK on each push

## Version History
- **v9** (current): Added TikTok platform, Pause/Resume control, auto-retry on network failure, BootReceiver for auto-start after reboot
- **v8**: Multi-account support, Lazada platform, history logging, Gemini AI captcha
- **v7**: Initial multi-account support
- **v6**: Gemini AI captcha integration

## Project Structure
```
├── app/
│   ├── build.gradle              # App config (versionCode 9)
│   └── src/main/
│       ├── AndroidManifest.xml   # Permissions + components
│       ├── assets/bot.py         # Python bot (1500+ lines)
│       ├── java/com/golike/bot/
│       │   ├── MainActivity.java # WebView + JS bridge
│       │   ├── BotService.java   # Foreground service runs Python
│       │   └── BootReceiver.java # Auto-start after reboot (NEW v9)
│       └── res/
│           ├── layout/           # activity_main.xml
│           ├── values/           # styles.xml
│           └── drawable/         # Logo/badge SVGs
├── .github/workflows/
│   └── build-apk.yml             # GitHub Actions CI (builds v9 APK)
├── build.gradle                  # Root Gradle config
└── settings.gradle
```

## Features (v9)
- **Multi-platform**: Shopee + Lazada + TikTok (new)
- **Pause/Resume**: Control bot from web UI (new)
- **Auto-retry**: Automatic retry on network failures (new)
- **Auto-start**: BootReceiver starts bot after device reboot (new)
- **Multi-account**: Run multiple GoLike accounts in parallel
- **AI Captcha**: Gemini 1.5 Flash solves audio + visual reCAPTCHA
- **History**: Local JSON log of all completed jobs
- **Wake Lock**: Keeps screen/CPU awake while running

## GitHub
- Repo: https://github.com/mememeiua-cmd/Remcute
- CI: Automatically builds APK on push to main
- Release: Tagged as v9.{run_number}

## Build Requirements
- Android Studio / Gradle 8.4
- JDK 17
- Android SDK 34/35
- Termux with Python 3 on device (for running bot.py)

## Development Notes
- Bot runs on port 8080 locally on the Android device
- WebView loads http://localhost:8080
- JS bridge injects captcha token interceptor into GoLike web pages
- The Python bot uses threading for parallel account execution
- bot_paused threading.Event controls pause/resume across all worker threads

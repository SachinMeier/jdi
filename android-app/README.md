# Android App

This is a separate Android implementation of the same narrow voice-control idea used by the Python Raspberry Pi service.

It does **not** run the Python app on Android. It is a native Kotlin Android app with:

- a foreground microphone service
- offline Vosk recognition
- an optional wake phrase
- a single hold-to-talk button in the UI
- direct LIFX LAN power control
- LIFX HTTP scene activation

## Why The Android App Is Separate

Android is a very different runtime environment from Raspberry Pi:

- no `systemd`
- no `gpiozero`
- different audio APIs
- different long-running service rules
- different battery policies

So the Android version reuses the same architecture, but not the same process model.

## Current Design

The app uses Vosk for both:

- wake phrase detection with a tiny grammar
- command recognition with a restricted command grammar

That means:

- no internet is used for speech recognition after the model is downloaded
- the app does not depend on `openWakeWord`
- scenes still use the LIFX HTTP API and therefore need internet

## Project Layout

- `app/src/main/java/.../ui`
  - activities and UI wiring
- `app/src/main/java/.../service`
  - foreground service, notification, voice engine state
- `app/src/main/java/.../recognition`
  - Vosk wrapper
- `app/src/main/java/.../lifx`
  - raw LAN packet client and HTTP client
- `app/src/main/java/.../config`
  - JSON config models, matcher, validation, storage
- `app/src/main/assets/default-config.json`
  - starting config copied into app-private storage on first launch

## What Works

- push-to-talk from the main screen
- optional wake phrase when the service is running
- LAN on/off and toggle commands for lights, groups, and `all`
- HTTP cloud scene activation by scene UUID
- config editing inside the app
- model download from the official Vosk model URL

## Policy Decisions

This app intentionally chooses the least fragile Android path for a dedicated phone:

- it uses a foreground service for microphone capture
- it asks the user to disable battery optimization for the app
- it does **not** silently auto-start microphone capture on boot

That last choice is deliberate. Android increasingly restricts background startup behavior, especially for apps that want microphone access. A dedicated device can tolerate opening the app after reboot far more easily than it can tolerate brittle boot hacks.

## Build And Sideload

These steps are for a Mac or other desktop with Android Studio installed.

1. Install Android Studio.
2. Open the folder:

```text
/Users/sachinmeier/Projects/Me/jdi/android-app
```

3. Let Android Studio install:
   - JDK
   - Android SDK
   - required build tools
   - Gradle dependencies
4. Connect your Android phone with USB debugging enabled.
5. Build and install the debug app from Android Studio.

You can also sideload the generated debug APK manually after a build from:

```text
android-app/app/build/outputs/apk/debug/
```

If you prefer the command line once the Android SDK is installed, the verified local build command is:

```bash
cd /Users/sachinmeier/Projects/Me/jdi/android-app
./gradlew --no-daemon --console=plain lintDebug testDebugUnitTest assembleDebug assembleRelease
```

## First-Run Setup On The Phone

1. Open the app.
2. Tap `Edit Config` and confirm the light labels and commands.
3. Add your LIFX HTTP token if you want cloud scene commands.
4. Tap `Download Offline Model`.
5. Tap `Disable Battery Optimizations`.
6. Tap `Start Voice Service`.
7. Use the large `Hold To Talk` button or leave wake phrase mode enabled.

## Config Format

The app stores its config as JSON in app-private storage.

Top-level sections:

- `audio`
- `recognition`
- `wakeWord`
- `lifx`
- `lights`
- `groups`
- `commands`

### Example Scene Command

Add a cloud scene command like this:

```json
{
  "phrases": ["movie time", "activate movie time"],
  "action": {
    "type": "scene",
    "sceneId": "replace-with-real-scene-uuid",
    "durationMs": 1000
  }
}
```

### Example HTTP Power Command

If you ever want to force a power command over HTTP instead of LAN:

```json
{
  "phrases": ["turn bedroom off over cloud"],
  "action": {
    "type": "power",
    "target": "bedroom",
    "value": "off",
    "transport": "http",
    "durationMs": 250
  }
}
```

## Dedicated Phone Recommendations

- keep the phone on a charger
- disable battery optimization for the app
- grant microphone permission
- grant notification permission
- leave the app in the foreground or keep the service notification active
- avoid aggressive vendor “battery saver” modes

## Verification Limits

This repo now contains the full Android project structure and implementation, but it was created in an environment without:

- a local JDK
- Gradle
- Android SDK / platform tools

So I could not produce a built APK here.

The code was written to be structurally coherent and organized for Android Studio import, but the first real verification step needs to happen on a machine with Android Studio or a configured Android CLI toolchain.

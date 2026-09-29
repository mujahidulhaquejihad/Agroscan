# AgroScan Android (Capacitor)

Package id: `com.mujahidulhaquejihad.agroscan`  
Hosted app: `https://agroscan.mujahidulhaquejihad.com`  
No on-device models. Scan, chat, and shop call the live site. A header pill shows connected / offline.

## Prerequisites

- Node.js 18+
- Android Studio (JDK 17+) with Android SDK
- Set `JAVA_HOME` to your JDK

## Build debug APK

```bash
cd mobile
npm install
npx cap add android
npm run build:apk
```

APK output:

`android/app/build/outputs/apk/debug/app-debug.apk`

Install on a phone:

```bash
adb install -r android/app/build/outputs/apk/debug/app-debug.apk
```

## After changing the web UI

```bash
npm run cap:sync
```

Then rebuild the APK.

# AgroScan Android (Capacitor)

Package id: `com.mujahidulhaquejihad.agroscan`  
API host: `https://agroscan.mujahidulhaquejihad.com`

## Prerequisites

- Node.js 18+
- Android Studio (JDK 17+) with Android SDK
- Set `JAVA_HOME` to your JDK

## Build debug APK

```bash
cd mobile
npm install
npm run sync:web
npx cap sync android
cd android
# Windows:
gradlew.bat assembleDebug
# Linux/macOS:
./gradlew assembleDebug
```

APK output:

`android/app/build/outputs/apk/debug/app-debug.apk`

Install on a phone:

```bash
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

Or open in Android Studio:

```bash
npx cap open android
```

## After changing the web UI

```bash
npm run cap:sync
```

Then rebuild the APK.

## Play Store later

1. Create a release keystore (keep it offline / secret).
2. Uncomment `signingConfigs` in `android/app/build.gradle`.
3. Build an AAB: `./gradlew bundleRelease`
4. Upload to Play Console with privacy policy URL and screenshots.

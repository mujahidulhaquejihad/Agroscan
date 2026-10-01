# Deploy AgroScan (server + PWA + Android)

Production hostname: **https://agroscan.mujahidulhaquejihad.com**

---

## 1. Server — Proxmox CT 101 (`root@192.168.0.51`, app in `/opt/agroscan`)

Routine update (code, web UI, disease/shop JSON). Keeps the server's `.env` and `data/*.db`:

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy\update-ct101.ps1
```

New models: copy the `.pt` files to `/opt/agroscan/models/` and run `systemctl restart agroscan`.

Fresh CT only (first install or rebuild — never for routine updates):

```powershell
ssh-copy-id root@192.168.0.51
powershell -ExecutionPolicy Bypass -File .\deploy\push-to-ct101.ps1
```

`push-to-ct101.ps1` copies the runtime and models, then runs `deploy/ct101-setup.sh` (venv, CPU torch, `requirements-ct.txt`, the `agroscan.service` systemd unit, cloudflared). Uvicorn binds **127.0.0.1:8000** only.

Check on the CT: `curl -sS http://127.0.0.1:8000/api/status` → `"ready": true`.

---

## 2. Cloudflare Tunnel (once per CT)

Cloudflare Zero Trust → Networks → Tunnels → Create `agroscan`. Public hostname `agroscan.mujahidulhaquejihad.com` → `http://127.0.0.1:8000`. Then on the CT:

```bash
cloudflared service install <TOKEN>
systemctl enable --now cloudflared
```

Verify in a browser:

- https://agroscan.mujahidulhaquejihad.com/
- https://agroscan.mujahidulhaquejihad.com/api/status
- https://agroscan.mujahidulhaquejihad.com/sw.js

### Google Sign-In (optional)

In Google Cloud Console → OAuth Web Client, add Authorized JavaScript origins:

- `http://localhost:8000`
- `https://agroscan.mujahidulhaquejihad.com`

---

## 3. PWA (install from the website)

After HTTPS is live:

1. Open **https://agroscan.mujahidulhaquejihad.com** in Chrome (Android) or Safari (iPhone).
2. Android: use the **Install AgroScan** banner, or Chrome menu → **Install app** / **Add to Home screen**.
3. iPhone: Share → **Add to Home Screen**.

The service worker caches the app shell; predictions still need network (models run on the server).

---

## 4. Android APK (Capacitor)

Project: [`mobile/`](../mobile/)  
App id: `com.mujahidulhaquejihad.agroscan`

On a machine with Android Studio / JDK 17+:

```bash
cd mobile
npm install
npm run sync:web
npx cap sync android
cd android
./gradlew assembleDebug          # Linux/macOS
# gradlew.bat assembleDebug      # Windows
```

APK path:

`mobile/android/app/build/outputs/apk/debug/app-debug.apk`

Sideload:

```bash
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

The APK loads the bundled UI and calls **https://agroscan.mujahidulhaquejihad.com** for `/api/predict` (see [`web/config.js`](../web/config.js)).

After web UI changes:

```bash
cd mobile
npm run cap:sync
# rebuild APK
```

More detail: [`mobile/README.md`](../mobile/README.md)

---

## 5. Play Store later (checklist)

Not required for this phase, but the project is prepared:

- [ ] Privacy policy page (HTTPS URL)
- [ ] Release keystore (store offline; never commit)
- [ ] Uncomment `signingConfigs` in `mobile/android/app/build.gradle`
- [ ] `./gradlew bundleRelease` → upload AAB
- [ ] Store listing: title, short/full description, screenshots, feature graphic
- [ ] Content rating questionnaire
- [ ] Target API level per Play requirements
- [ ] Data safety form (photos uploaded for disease detection)

---

## Architecture (short)

| Client | How it talks to the API |
|--------|-------------------------|
| Browser / PWA | Same origin via Cloudflare Tunnel |
| Android APK | `API_BASE = https://agroscan.mujahidulhaquejihad.com` when Capacitor native |

Inference always runs on the server (`POST /api/predict`). Updating `.pt` models on the server updates every client without a new APK.

#!/bin/sh
# Run on Proxmox CT 101 after the runtime tarball is unpacked to /opt/agroscan
set -eu
APP=/opt/agroscan
cd "$APP"

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends \
  python3 python3-venv python3-pip python3-dev \
  libgl1 libglib2.0-0 curl ca-certificates

python3 -m venv "$APP/.venv"
"$APP/.venv/bin/pip" install --upgrade pip
"$APP/.venv/bin/pip" install torch torchvision --index-url https://download.pytorch.org/whl/cpu
"$APP/.venv/bin/pip" install -r "$APP/deploy/requirements-ct.txt"

sed -i 's/\r$//' "$APP/deploy/agroscan.service" "$APP/deploy/ct101-setup.sh" 2>/dev/null || true
install -m 644 "$APP/deploy/agroscan.service" /etc/systemd/system/agroscan.service
systemctl daemon-reload
systemctl enable --now agroscan.service

if ! command -v cloudflared >/dev/null 2>&1; then
  curl -fsSL -o /tmp/cloudflared.deb \
    "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb"
  dpkg -i /tmp/cloudflared.deb || apt-get install -f -y
  rm -f /tmp/cloudflared.deb
fi

echo
echo "AgroScan is on 127.0.0.1:8000"
systemctl --no-pager --full status agroscan | head -n 20
echo
echo "Next: cloudflared service install TOKEN"
echo "Check: curl -sS http://127.0.0.1:8000/api/status"

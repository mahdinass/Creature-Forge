#!/bin/bash
# Runs ON the VM as user forge (idempotent). Adds the development toolchain used by infra/nebius/forge_dev.py:
# Node 22 (official nodejs.org tarball, SHA-256 checked against SHASUMS256.txt), Google Chrome stable (official .deb, the
# same browser the GitHub CI runner provides at /usr/bin/google-chrome) and the bare repository that receives dev snapshots.
# Never touches ~/creature-forge (the registered R1/R2/R3 research clone) or its venv.
set -euo pipefail
mkdir -p "$HOME/dev" "$HOME/dev/venvs" "$HOME/logs/dev"
[ -d "$HOME/dev/cf.git" ] || git init --bare --quiet "$HOME/dev/cf.git"

if ! command -v node >/dev/null || [ "$(node -p 'process.versions.node.split(".")[0]')" != "22" ]; then
  tmp=$(mktemp -d); cd "$tmp"
  base=https://nodejs.org/dist/latest-v22.x
  curl -fsSLO "$base/SHASUMS256.txt"
  tgz=$(grep -oE 'node-v22\.[0-9]+\.[0-9]+-linux-x64\.tar\.xz' SHASUMS256.txt | head -1)
  curl -fsSLO "$base/$tgz"
  grep " $tgz\$" SHASUMS256.txt | sha256sum -c -
  sudo rm -rf /opt/node && sudo mkdir -p /opt/node && sudo tar -xJf "$tgz" -C /opt/node --strip-components=1
  for b in node npm npx; do sudo ln -sf /opt/node/bin/$b /usr/local/bin/$b; done
  cd "$HOME"; rm -rf "$tmp"
fi

if [ ! -x /usr/bin/google-chrome ]; then
  tmp=$(mktemp -d)
  curl -fsSL -o "$tmp/chrome.deb" https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
  sudo DEBIAN_FRONTEND=noninteractive apt-get update -qq
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "$tmp/chrome.deb" fonts-liberation >/dev/null
  rm -rf "$tmp"
fi
echo "node $(node --version) npm $(npm --version) chrome $(/usr/bin/google-chrome --version)"

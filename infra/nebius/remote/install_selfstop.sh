#!/bin/bash
# Runs ON the VM via sudo. Args: <instance-id>. Expects in the current directory: nebius (CLI binary, same build as the
# Windows-side WSL CLI) and forge-selfstop. The service-account key arrives on stdin and is written straight to
# /root/.nebius/sa/key.json (mode 600); it is never stored in the repository, a log, or the forge user's home.
# Replaces the old in-guest poweroff deadman timer (a poweroff is restarted by the platform, see forge-selfstop).
set -euo pipefail
IID=$1
PROJECT=project-e01jjnn2pa00wm820bree9
install -m 755 nebius /usr/local/bin/nebius
install -m 755 forge-selfstop /usr/local/sbin/forge-selfstop
install -d -m 700 /root/.nebius /root/.nebius/sa
umask 077
cat > /root/.nebius/sa/key.json
chmod 600 /root/.nebius/sa/key.json
HOME=/root /usr/local/bin/nebius profile create cf-stopper --endpoint api.nebius.cloud \
  --service-account-file /root/.nebius/sa/key.json --parent-id "$PROJECT" >/dev/null
echo "$IID" > /var/lib/forge/instance_id
rm -f /var/lib/forge/selfstop_fails
cat > /etc/systemd/system/forge-selfstop.service <<'EOF'
[Service]
Type=oneshot
ExecStart=/usr/local/sbin/forge-selfstop
EOF
cat > /etc/systemd/system/forge-selfstop.timer <<'EOF'
[Timer]
OnBootSec=2min
OnUnitActiveSec=5min
[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload
systemctl disable --now forge-deadman.timer 2>/dev/null || true
systemctl enable --now forge-selfstop.timer
# self-test: the service account can read this instance (no stop)
HOME=/root /usr/local/bin/nebius --profile cf-stopper compute instance get --id "$IID" --format json \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print('selfstop installed; SA sees', d['metadata']['name'], d['status']['state'])"

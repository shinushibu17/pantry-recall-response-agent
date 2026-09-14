#!/bin/bash
set -euo pipefail
export AWS_DEFAULT_REGION='${AWS::Region}'
finish() {
  result=$?
  outcome=FAILURE
  if [ "$result" -eq 0 ]; then outcome=SUCCESS; fi
  if [ "$result" -ne 0 ]; then journalctl -u pantry-recall -n 50 --no-pager || true; fi
  aws cloudformation signal-resource --stack-name '${AWS::StackName}' --logical-resource-id Server --unique-id bootstrap --status "$outcome" || true
}
trap finish EXIT
command -v aws
dnf install -y python3.12 tar gzip util-linux
useradd --system --home-dir /var/lib/pantry --shell /sbin/nologin pantry
mkdir -p /opt/pantry /var/lib/pantry
volume='${DataVolume}'
serial=$(echo "$volume" | tr -d '-')
device=''
for attempt in $(seq 1 90); do
  device=$(lsblk -ndo NAME,SERIAL | awk -v serial="$serial" '$2 == serial {print "/dev/" $1}')
  if [ -n "$device" ]; then break; fi
  sleep 2
done
test -n "$device"
if [ -z "$(lsblk -ndo FSTYPE "$device")" ]; then mkfs.ext4 "$device"; fi
uuid=$(blkid -s UUID -o value "$device")
printf 'UUID=%s /var/lib/pantry ext4 defaults,nofail 0 2\n' "$uuid" >> /etc/fstab
mount /var/lib/pantry
chown pantry:pantry /var/lib/pantry
chmod 750 /var/lib/pantry
aws s3 cp 's3://__BUCKET__/__KEY__' /tmp/pantry-release.tar.gz
tar -xzf /tmp/pantry-release.tar.gz -C /opt/pantry
curl --proto '=https' --tlsv1.2 -LsSf https://astral.sh/uv/0.11.8/install.sh -o /tmp/install-uv.sh
UV_INSTALL_DIR=/usr/local/bin sh /tmp/install-uv.sh
cd /opt/pantry
/usr/local/bin/uv sync --frozen --no-dev --python /usr/bin/python3.12 --no-managed-python
printf 'PANTRY_PUBLIC_URL=https://deployment-pending.invalid\n' > /etc/pantry-public.env
cat > /etc/systemd/system/pantry-recall.service <<'SERVICE'
[Unit]
Description=Pantry Recall reviewer and Bedrock agent
After=network-online.target
Wants=network-online.target
RequiresMountsFor=/var/lib/pantry

[Service]
User=pantry
Group=pantry
WorkingDirectory=/opt/pantry
Environment=AWS_REGION=us-east-1
Environment=AWS_EC2_METADATA_DISABLED=false
Environment=PYTHONDONTWRITEBYTECODE=1
EnvironmentFile=/etc/pantry-public.env
ExecStart=/opt/pantry/.venv/bin/python -m pantry_recall.web --host 0.0.0.0 --port 8080 --db /var/lib/pantry/pantry.sqlite3
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/pantry

[Install]
WantedBy=multi-user.target
SERVICE
systemctl daemon-reload
systemctl enable --now pantry-recall
for attempt in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8080/health; then exit 0; fi
  sleep 2
done
exit 1

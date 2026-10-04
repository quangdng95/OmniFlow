#!/bin/bash
# Run ON THE VM (as the omniflow user, with sudo) after deploying the code:
#   bash ~/omniflow/remote_web/scripts/install-selfheal.sh
# Installs the 6-hourly self-heal timer. Optional push notifications: add
#   Environment=OMNIFLOW_NTFY_TOPIC=<a-long-random-topic>
# to the [Service] section of /etc/systemd/system/omniflow-selfheal.service.
set -euo pipefail
SRC="$HOME/omniflow/remote_web/deploy"
sudo cp "$SRC/omniflow-selfheal.service" "$SRC/omniflow-selfheal.timer" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now omniflow-selfheal.timer
systemctl list-timers omniflow-selfheal.timer --no-pager
echo "Run it once now with:  sudo systemctl start omniflow-selfheal.service   (log: journalctl -u omniflow-selfheal)"

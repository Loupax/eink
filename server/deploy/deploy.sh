#!/usr/bin/env bash
# Ships server/ + tools/ to the brick.local mini PC and (re)builds its venv.
# Restarting eink-weather.service needs sudo on the remote and a real TTY for
# the password prompt, so this script never does it - it just prints the
# command to run by hand afterward, same as the one-time setup steps.
set -euo pipefail

REMOTE=brick.local
REMOTE_DIR=/home/loupax/src/eink-weather
LOCAL_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

echo "==> syncing code to $REMOTE:$REMOTE_DIR"
ssh "$REMOTE" "mkdir -p $REMOTE_DIR"

# -i (itemize-changes) so we can tell afterward whether any .py file was
# touched - app.py/render_weather.py are imported once at process start, so
# they need a service restart to take effect. weather_template.html (and any
# other non-.py file) is read fresh from disk on every request - no restart
# needed for those.
tools_changes=$(rsync -avzi --delete \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  "$LOCAL_ROOT/tools/" "$REMOTE:$REMOTE_DIR/tools/")
echo "$tools_changes"

# todo.txt is per-machine data (like weather_config.py, but edited far more
# often) - never synced, so a local test list never clobbers the real one on
# brick and vice versa. It's read fresh from disk on every request just like
# weather_template.html, so editing it on brick directly takes effect
# immediately with no deploy or restart needed.
server_changes=$(rsync -avzi --delete \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude 'screen.bin' \
  --exclude 'screen.png' \
  --exclude '_weather_render.png' \
  --exclude 'weather_config.py.dist' \
  --exclude 'todo.txt' \
  "$LOCAL_ROOT/server/" "$REMOTE:$REMOTE_DIR/server/")
echo "$server_changes"

py_changed=0
if printf '%s\n%s\n' "$tools_changes" "$server_changes" | grep -qE '\.py$'; then
  py_changed=1
fi

echo "==> setting up venv + deps on $REMOTE"
ssh "$REMOTE" bash -s <<'EOF'
set -euo pipefail
cd /home/loupax/src/eink-weather
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install --upgrade pip >/dev/null
pip install Pillow playwright
playwright install chromium
EOF

if ssh "$REMOTE" "systemctl list-unit-files eink-weather.service" >/dev/null 2>&1; then
  if [ "$py_changed" = 1 ]; then
    cat <<MSG

.py file(s) changed - restart the service yourself (needs an interactive
sudo password prompt, run this in a real terminal, not scripted):

  ssh -t $REMOTE sudo systemctl restart eink-weather.service
MSG
  else
    cat <<MSG

No .py changes - no restart needed, the running service reads
weather_template.html fresh on every request. Reload
http://weather.local/screen.png to see it.
MSG
  fi
else
  cat <<MSG

Service not installed yet on $REMOTE. One-time setup (run these on $REMOTE,
or via 'ssh $REMOTE' then paste - all need sudo):

  sudo cp $REMOTE_DIR/server/deploy/eink-weather.service /etc/systemd/system/eink-weather.service
  sudo cp $REMOTE_DIR/server/deploy/nginx-weather.conf /etc/nginx/sites-available/weather.conf
  sudo ln -sf /etc/nginx/sites-available/weather.conf /etc/nginx/sites-enabled/weather.conf
  sudo systemctl daemon-reload
  sudo systemctl enable --now avahi-alias@weather.service
  sudo systemctl enable --now eink-weather.service
  sudo nginx -t && sudo systemctl reload nginx

After that, http://weather.local/screen.bin should respond. todo.txt isn't
synced (see above) - create $REMOTE_DIR/server/todo.txt by hand (copy
server/todo.txt.dist as a starting point) or the To-Do box just stays empty.

Also needs nss-mdns so brick can resolve eink.local at all (mDNS names
otherwise only work for the dedicated avahi-resolve tool, not curl/getent -
see server/deploy/eink-refresh.*):

  sudo pacman -S --needed nss-mdns
  sudo sed -i 's/^hosts: mymachines resolve/hosts: mymachines mdns4_minimal [NOTFOUND=return] resolve/' /etc/nsswitch.conf

To auto-refresh the eink display whenever todo.txt changes:

  sudo cp $REMOTE_DIR/server/deploy/eink-refresh.path /etc/systemd/system/eink-refresh.path
  sudo cp $REMOTE_DIR/server/deploy/eink-refresh.service /etc/systemd/system/eink-refresh.service
  sudo systemctl daemon-reload
  sudo systemctl enable --now eink-refresh.path
MSG
fi

echo "==> done"

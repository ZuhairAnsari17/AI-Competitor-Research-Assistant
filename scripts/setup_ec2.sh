#!/bin/bash
# Competitor Intelligence Agent — EC2 Setup
# Tested on Ubuntu 22.04 LTS
# Usage: bash scripts/setup_ec2.sh

set -e
echo "=== Competitor Intelligence Agent — EC2 Setup ==="
echo ""

# ── Docker ───────────────────────────────────────────────────────────────────
echo "[1/5] Installing Docker..."
apt-get update -q
apt-get install -y -q ca-certificates curl gnupg
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  > /etc/apt/sources.list.d/docker.list
apt-get update -q
apt-get install -y -q docker-ce docker-ce-cli containerd.io docker-compose-plugin git
systemctl enable docker
systemctl start docker
usermod -aG docker ubuntu
echo "Docker $(docker --version) installed."

# ── App directory ─────────────────────────────────────────────────────────────
echo "[2/5] Setting up app directory..."
APP_DIR="/opt/competitor-intel"
mkdir -p "$APP_DIR"
chown ubuntu:ubuntu "$APP_DIR"

# Copy current files if running from repo, else prompt for git clone
if [ -f "docker-compose.yml" ]; then
    cp -r . "$APP_DIR/"
else
    echo "Enter your GitHub repo URL (leave blank to skip):"
    read -r REPO_URL
    if [ -n "$REPO_URL" ]; then
        git clone "$REPO_URL" "$APP_DIR"
    fi
fi

cd "$APP_DIR"
mkdir -p data logs nginx/ssl

# ── Environment ───────────────────────────────────────────────────────────────
echo "[3/5] Setting up environment..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo ""
    echo ">>> Fill in your API keys before starting:"
    echo "    nano $APP_DIR/.env"
    echo ""
fi

# ── Firewall ──────────────────────────────────────────────────────────────────
echo "[4/5] Configuring firewall..."
apt-get install -y -q ufw
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
# Optionally allow direct access to Streamlit (useful during testing)
ufw allow 8501/tcp
ufw --force enable
echo "Firewall: SSH + HTTP + HTTPS + 8501 open."

# ── Systemd service ───────────────────────────────────────────────────────────
echo "[5/5] Creating systemd service for auto-start on reboot..."
cat > /etc/systemd/system/competitor-intel.service << SERVICE
[Unit]
Description=Competitor Intelligence Agent
Requires=docker.service
After=docker.service network-online.target

[Service]
WorkingDirectory=$APP_DIR
ExecStart=/usr/bin/docker compose up
ExecStop=/usr/bin/docker compose down
Restart=on-failure
RestartSec=15
User=ubuntu

[Install]
WantedBy=multi-user.target
SERVICE

systemctl daemon-reload
systemctl enable competitor-intel

# ── Done ──────────────────────────────────────────────────────────────────────
SERVER_IP=$(curl -s --max-time 5 ifconfig.me 2>/dev/null || echo "YOUR_EC2_IP")

echo ""
echo "╔═══════════════════════════════════════════════════════╗"
echo "║        Setup complete! Next steps:                    ║"
echo "╠═══════════════════════════════════════════════════════╣"
echo "║                                                       ║"
echo "║  1. Add your API keys:                                ║"
echo "║     nano $APP_DIR/.env"
echo "║                                                       ║"
echo "║  2. Start the app:                                    ║"
echo "║     cd $APP_DIR && docker compose up -d               ║"
echo "║                                                       ║"
echo "║  3. Watch startup logs:                               ║"
echo "║     docker compose logs -f api                        ║"
echo "║                                                       ║"
echo "║  Once running:                                        ║"
echo "║  Dashboard : http://$SERVER_IP                        ║"
echo "║  API docs  : http://$SERVER_IP/docs                   ║"
echo "║  Grafana   : http://$SERVER_IP/grafana/               ║"
echo "║                                                       ║"
echo "║  Optional — free SSL (after pointing a domain):       ║"
echo "║     apt install certbot                               ║"
echo "║     certbot certonly --standalone -d yourdomain.com   ║"
echo "║     cp /etc/letsencrypt/live/yourdomain.com/*.pem     ║"
echo "║        $APP_DIR/nginx/ssl/                            ║"
echo "║     (then uncomment HTTPS block in nginx/nginx.conf)  ║"
echo "║                                                       ║"
echo "╚═══════════════════════════════════════════════════════╝"

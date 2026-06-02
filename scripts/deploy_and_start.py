"""Upload code via SFTP and configure/restart all services on VPS."""
from __future__ import annotations

import base64
import os
import subprocess
import sys
from pathlib import Path

try:
    import paramiko
except ImportError:
    print("pip install paramiko", file=sys.stderr)
    sys.exit(1)

HOST = os.environ.get("CHAT_DEPLOY_HOST", "193.233.112.32")
USER = os.environ.get("CHAT_DEPLOY_USER", "root")
PASSWORD = os.environ.get("CHAT_DEPLOY_PASSWORD", "")
REMOTE = os.environ.get("CHAT_DEPLOY_REMOTE", "/opt/chat").rstrip("/")
DOMAIN = "proxy-mamont.click"
ROOT = Path(__file__).resolve().parents[1]


def run(client: paramiko.SSHClient, cmd: str, timeout: int = 180) -> tuple[int, str, str]:
    _, out, err = client.exec_command(cmd, timeout=timeout)
    rc = out.channel.recv_exit_status()
    return rc, out.read().decode("utf-8", "replace"), err.read().decode("utf-8", "replace")


def deploy_code() -> None:
    env = os.environ.copy()
    env["CHAT_DEPLOY_HOST"] = HOST
    env["CHAT_DEPLOY_USER"] = USER
    env["CHAT_DEPLOY_PASSWORD"] = PASSWORD
    env["CHAT_DEPLOY_REMOTE"] = REMOTE
    rc = subprocess.call([sys.executable, str(ROOT / "scripts/deploy_chat_sftp.py")], env=env)
    if rc != 0:
        raise SystemExit(f"deploy_chat_sftp failed: {rc}")


def configure_server(client: paramiko.SSHClient) -> None:
    nginx_conf = (ROOT / "infra/nginx/asyncgram-production.conf").read_text(encoding="utf-8")
    b64 = base64.b64encode(nginx_conf.encode()).decode()

    setup = f"""set -e
echo {b64} | base64 -d > /etc/nginx/sites-available/asyncgram.conf
ln -sf /etc/nginx/sites-available/asyncgram.conf /etc/nginx/sites-enabled/asyncgram.conf
rm -f /etc/nginx/sites-enabled/chat /etc/nginx/sites-enabled/default

grep -q '^DATABASE_URL=' {REMOTE}/.env || echo 'DATABASE_URL=sqlite:////opt/chat/database.db' >> {REMOTE}/.env
if grep -q '^DATABASE_URL=sqlite:///\\./' {REMOTE}/.env; then
  sed -i 's|^DATABASE_URL=sqlite:///\\./|DATABASE_URL=sqlite:////opt/chat/|' {REMOTE}/.env
fi
sed -i 's|^CORS_ORIGINS=.*|CORS_ORIGINS=https://{DOMAIN},https://www.{DOMAIN}|' {REMOTE}/.env
grep -q '^JWT_SECRET=' {REMOTE}/.env || echo "JWT_SECRET=$(openssl rand -hex 32)" >> {REMOTE}/.env
grep -q '^REDIS_URL=' {REMOTE}/.env || echo 'REDIS_URL=redis://127.0.0.1:6379/0' >> {REMOTE}/.env
grep -q '^AUTH_SERVICE_URL=' {REMOTE}/.env || echo 'AUTH_SERVICE_URL=http://127.0.0.1:8001' >> {REMOTE}/.env
grep -q '^CHAT_SERVICE_URL=' {REMOTE}/.env || echo 'CHAT_SERVICE_URL=http://127.0.0.1:8002' >> {REMOTE}/.env

mkdir -p {REMOTE}/uploads
touch {REMOTE}/database.db
chgrp www-data {REMOTE}
chmod 775 {REMOTE}
chown www-data:www-data {REMOTE}/database.db {REMOTE}/uploads
chmod 664 {REMOTE}/database.db

if [ ! -d {REMOTE}/venv ]; then
  python3 -m venv {REMOTE}/venv
fi
{REMOTE}/venv/bin/pip install -q -r {REMOTE}/requirements.txt

for u in auth chat ws media admin; do
  cp {REMOTE}/infra/systemd/asyncgram-$u.service /etc/systemd/system/
done
systemctl daemon-reload
systemctl enable redis-server
systemctl restart redis-server
systemctl restart asyncgram-auth asyncgram-chat asyncgram-ws asyncgram-media asyncgram-admin
sleep 3
nginx -t
systemctl reload nginx

echo '=== status ==='
systemctl is-active redis-server asyncgram-auth asyncgram-chat asyncgram-ws asyncgram-media asyncgram-admin nginx
curl -sf http://127.0.0.1:8001/health || true
curl -sf http://127.0.0.1:8002/health || true
curl -s -o /dev/null -w 'site:%{{http_code}}\\n' -H 'Host: {DOMAIN}' http://127.0.0.1/ || true
"""
    rc, out, err = run(client, setup, timeout=300)
    print(out)
    if err.strip():
        print("STDERR:", err)
    if rc != 0:
        raise SystemExit(f"server setup failed: {rc}")


def main() -> None:
    if not PASSWORD:
        print("CHAT_DEPLOY_PASSWORD required", file=sys.stderr)
        sys.exit(1)

    print("1/2 Upload code...")
    deploy_code()

    print("2/2 Configure and restart...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=90, banner_timeout=90)
    configure_server(client)
    client.close()
    print(f"Done: https://{DOMAIN}")


if __name__ == "__main__":
    main()

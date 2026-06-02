"""Fix auth, configure nginx for proxy-mamont.click only, restart services."""
from __future__ import annotations

from pathlib import Path

import paramiko

HOST = "193.233.112.32"
USER = "root"
PASSWORD = "CIad32fk6CaE"
DOMAIN = "proxy-mamont.click"
REMOTE = "/opt/chat"
ROOT = Path(__file__).resolve().parents[1]


def nginx_http_only() -> str:
    conf_path = ROOT / "infra/nginx/asyncgram-production.conf"
    return conf_path.read_text(encoding="utf-8")


def nginx_https() -> str:
    # Behind Cloudflare: do NOT redirect HTTP->HTTPS on origin (causes ERR_TOO_MANY_REDIRECTS).
    return nginx_http_only()


def main() -> None:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=45)

    sftp = client.open_sftp()
    sftp.put(
        str(ROOT / "services/auth_service/app/database.py"),
        f"{REMOTE}/services/auth_service/app/database.py",
    )
    dist = ROOT / "frontend/dist"

    def upload_dir(local: Path, remote_dir: str) -> None:
        for p in local.rglob("*"):
            if p.is_file():
                rel = p.relative_to(local).as_posix()
                sftp.put(str(p), f"{remote_dir}/{rel}")

    upload_dir(dist, f"{REMOTE}/frontend/dist")
    sftp.close()
    print("Uploaded fixes")

    _, o, _ = client.exec_command(
        f"test -f /etc/letsencrypt/live/{DOMAIN}/fullchain.pem && echo HAS_SSL || echo NO_SSL"
    )
    o.channel.recv_exit_status()
    has_ssl = "HAS_SSL" in o.read().decode()
    conf = nginx_https() if has_ssl else nginx_http_only()
    print("SSL cert:", has_ssl)

    # write nginx conf via base64 to avoid heredoc issues
    import base64

    b64 = base64.b64encode(conf.encode()).decode()
    setup = f"""set -e
echo {b64} | base64 -d > /etc/nginx/sites-available/asyncgram.conf
sed -i 's|^DATABASE_URL=sqlite:///\\./|DATABASE_URL=sqlite:////opt/chat/|' {REMOTE}/.env
grep -q 'https://{DOMAIN}' {REMOTE}/.env || echo 'CORS_ORIGINS=https://{DOMAIN},https://www.{DOMAIN}' >> {REMOTE}/.env
chown -R www-data:www-data {REMOTE}/uploads {REMOTE}/database.db 2>/dev/null || true
/opt/chat/venv/bin/pip install -q -r {REMOTE}/requirements.txt
for u in auth chat ws media admin; do cp {REMOTE}/infra/systemd/asyncgram-$u.service /etc/systemd/system/; done
systemctl daemon-reload
systemctl enable redis-server
systemctl restart redis-server asyncgram-auth asyncgram-chat asyncgram-ws asyncgram-media asyncgram-admin
rm -f /etc/nginx/sites-enabled/chat
ln -sf /etc/nginx/sites-available/asyncgram.conf /etc/nginx/sites-enabled/asyncgram.conf
nginx -t
systemctl reload nginx
systemctl is-active asyncgram-auth
systemctl is-active asyncgram-chat
systemctl is-active nginx
curl -sf http://127.0.0.1:8001/health
curl -sf -H Host:{DOMAIN} http://127.0.0.1/ -o /dev/null -w '%{{http_code}}'
"""
    _, o, e = client.exec_command(setup, timeout=180)
    rc = o.channel.recv_exit_status()
    print(o.read().decode())
    print(e.read().decode())
    print("exit", rc)
    client.close()


if __name__ == "__main__":
    main()
